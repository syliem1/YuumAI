"""
Optimized Batch Indexer with Bedrock Embeddings
Parallel processing with batched embedding generation
"""

import boto3
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth
import os
from typing import List, Dict

s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
session = boto3.Session()
credentials = session.get_credentials()

# Configuration
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', 'your-domain.us-west-2.es.amazonaws.com')
OPENSEARCH_REGION = 'us-west-2'
INDEX_NAME = 'lol-matches'
S3_BUCKET = 'lol-training-matches-150k'
EMBEDDINGS_MODEL_ID = 'amazon.titan-embed-text-v2:0'
EMBEDDING_DIMENSION = 1024

# AWS Auth
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    OPENSEARCH_REGION,
    'es',
    session_token=credentials.token
)

opensearch_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
    max_retries=3,
    retry_on_timeout=True
)


class BatchEmbeddingGenerator:
    """Generate embeddings in batches to optimize Bedrock calls"""
    
    def __init__(self, batch_size=5):
        self.bedrock = bedrock_runtime
        self.model_id = EMBEDDINGS_MODEL_ID
        self.batch_size = batch_size
    
    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        
        embeddings = []
        
        for text in texts:
            try:
                # Truncate if needed
                if len(text) > 25000:
                    text = text[:25000]
                
                request_body = {
                    "inputText": text,
                    "dimensions": EMBEDDING_DIMENSION,
                    "normalize": True
                }
                
                response = self.bedrock.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    contentType='application/json',
                    accept='application/json'
                )
                
                response_body = json.loads(response['body'].read())
                embedding = response_body.get('embedding', [0.0] * EMBEDDING_DIMENSION)
                embeddings.append(embedding)
                
                # Small delay to respect rate limits
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Embedding error: {str(e)}")
                embeddings.append([0.0] * EMBEDDING_DIMENSION)
        
        return embeddings


class BatchIndexer:
    """Optimized batch indexer with embeddings"""
    
    def __init__(self, batch_size=50, max_workers=3):
        self.client = opensearch_client
        self.index_name = INDEX_NAME
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.embedding_generator = BatchEmbeddingGenerator()
        self.stats = {
            'processed': 0,
            'indexed': 0,
            'failed': 0,
            'embeddings_generated': 0
        }
    
    def get_all_match_keys(self, prefix='raw-matches/', limit=None):
        """Get all match-data.json keys from S3"""
        
        print(f"Scanning S3 bucket: {S3_BUCKET}")
        
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix)
        
        match_keys = []
        
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                if key.endswith('match-data.json'):
                    match_keys.append(key)
                    
                    if limit and len(match_keys) >= limit:
                        return match_keys
        
        print(f"Found {len(match_keys)} match files")
        return match_keys
    
    def process_match_file(self, match_key: str) -> List[Dict]:
        """Process a single match file"""
        
        try:
            # Get match data
            match_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=match_key)
            match_data = json.loads(match_obj['Body'].read())
            
            # Get timeline data
            timeline_key = match_key.replace('match-data.json', 'timeline-data.json')
            timeline_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=timeline_key)
            timeline_data = json.loads(timeline_obj['Body'].read())
            
            # Extract features
            docs = self.extract_match_features(match_data, timeline_data)
            
            return docs
            
        except Exception as e:
            print(f"Error processing {match_key}: {str(e)}")
            return []
    
    def extract_match_features(self, match_data: dict, timeline_data: dict) -> List[Dict]:
        """Extract features and prepare for embedding"""
        
        try:
            participants = match_data['info']['participants']
            game_duration_min = match_data['info']['gameDuration'] / 60
            
            docs = []
            summaries = []
            
            for participant in participants:
                cs_total = participant.get('totalMinionsKilled', 0) + participant.get('neutralMinionsKilled', 0)
                cs_per_min = cs_total / game_duration_min if game_duration_min > 0 else 0
                gold_per_min = participant.get('goldEarned', 0) / game_duration_min if game_duration_min > 0 else 0
                damage_per_min = participant.get('totalDamageDealtToChampions', 0) / game_duration_min if game_duration_min > 0 else 0
                
                kda = ((participant.get('kills', 0) + participant.get('assists', 0)) / 
                       max(participant.get('deaths', 1), 1))
                
                items = [
                    participant.get(f'item{i}', 0) 
                    for i in range(7) 
                    if participant.get(f'item{i}', 0) != 0
                ]
                
                # Get timeline stats
                timeline_stats = self._extract_timeline_stats(timeline_data, participant['participantId'])
                
                # Build rich match summary
                champion = participant.get('championName', 'Unknown')
                position = participant.get('teamPosition', 'UNKNOWN')
                win = "won" if participant.get('win') else "lost"
                
                match_summary = f"""
                {champion} {position} game that was {win}.
                KDA: {participant.get('kills', 0)}/{participant.get('deaths', 0)}/{participant.get('assists', 0)}.
                CS: {cs_total} at {cs_per_min:.1f} per minute. At 10 min had {timeline_stats.get('cs_at_10', 0)} CS.
                Gold: {participant.get('goldEarned', 0)} at {gold_per_min:.0f} per minute.
                Damage: {participant.get('totalDamageDealtToChampions', 0)} at {damage_per_min:.0f} per minute.
                Vision: {participant.get('visionScore', 0)} score with {participant.get('wardsPlaced', 0)} wards placed.
                Objectives: {participant.get('turretKills', 0)} turrets, {participant.get('dragonKills', 0)} dragons.
                Kill participation: {participant.get('challenges', {}).get('killParticipation', 0)*100:.0f}%.
                Early game: {timeline_stats.get('early_game_summary', 'Unknown')}.
                This {'winning' if participant.get('win') else 'losing'} game in {position} position.
                """
                
                summaries.append(match_summary.strip())
                
                doc_data = {
                    "match_id": match_data['metadata']['matchId'],
                    "game_version": match_data['info']['gameVersion'],
                    "game_duration": int(match_data['info']['gameDuration']),
                    "queue_id": match_data['info']['queueId'],
                    
                    "player_puuid": participant.get('puuid'),
                    "player_name": f"{participant.get('riotIdGameName', 'Unknown')}#{participant.get('riotIdTagline', '')}",
                    "champion": champion,
                    "position": position,
                    "team_id": participant.get('teamId'),
                    "win": participant.get('win', False),
                    
                    "kills": participant.get('kills', 0),
                    "deaths": participant.get('deaths', 0),
                    "assists": participant.get('assists', 0),
                    "kda": round(kda, 2),
                    "level": participant.get('champLevel', 0),
                    
                    "gold_earned": participant.get('goldEarned', 0),
                    "total_cs": cs_total,
                    "cs_per_min": round(cs_per_min, 2),
                    "gold_per_min": round(gold_per_min, 2),
                    
                    "damage_to_champions": participant.get('totalDamageDealtToChampions', 0),
                    "damage_taken": participant.get('totalDamageTaken', 0),
                    "damage_per_min": round(damage_per_min, 2),
                    "kill_participation": round(participant.get('challenges', {}).get('killParticipation', 0), 2),
                    
                    "vision_score": participant.get('visionScore', 0),
                    "wards_placed": participant.get('wardsPlaced', 0),
                    "wards_killed": participant.get('wardsKilled', 0),
                    "control_wards": participant.get('visionWardsBoughtInGame', 0),
                    
                    "turret_kills": participant.get('turretKills', 0),
                    "inhibitor_kills": participant.get('inhibitorKills', 0),
                    "dragon_kills": participant.get('dragonKills', 0),
                    "baron_kills": participant.get('baronKills', 0),
                    
                    "items": items,
                    "item_build_path": f"Items: {', '.join(map(str, items))}",
                    
                    "cs_at_10": timeline_stats.get('cs_at_10', 0),
                    "gold_at_10": timeline_stats.get('gold_at_10', 0),
                    "xp_at_10": timeline_stats.get('xp_at_10', 0),
                    
                    "early_game_performance": timeline_stats.get('early_game_summary', ''),
                    "mid_game_performance": "Mid game teamfights",
                    "late_game_performance": "Late game objective control",
                    
                    "match_summary": match_summary.strip()
                }
                
                docs.append(doc_data)
            
            # Generate embeddings for all summaries in this match
            embeddings = self.embedding_generator.generate_batch(summaries)
            self.stats['embeddings_generated'] += len(embeddings)
            
            # Add embeddings to docs
            for i, doc in enumerate(docs):
                doc['embedding'] = embeddings[i]
            
            return docs
            
        except Exception as e:
            print(f"Feature extraction error: {str(e)}")
            return []
    
    def _extract_timeline_stats(self, timeline_data: dict, participant_id: int) -> Dict:
        """Extract timeline stats"""
        stats = {
            'cs_at_10': 0,
            'gold_at_10': 0,
            'xp_at_10': 0,
            'early_game_summary': 'Unknown'
        }
        
        try:
            frames = timeline_data.get('info', {}).get('frames', [])
            
            if len(frames) >= 11:
                frame_10 = frames[10]
                participant_frame = frame_10.get('participantFrames', {}).get(str(participant_id), {})
                
                stats['cs_at_10'] = participant_frame.get('minionsKilled', 0) + participant_frame.get('jungleMinionsKilled', 0)
                stats['gold_at_10'] = participant_frame.get('totalGold', 0)
                stats['xp_at_10'] = participant_frame.get('xp', 0)
                
                # Simple early game analysis
                if stats['gold_at_10'] > 3500:
                    stats['early_game_summary'] = "Strong early laning phase"
                elif stats['gold_at_10'] < 2500:
                    stats['early_game_summary'] = "Struggled in early laning"
                else:
                    stats['early_game_summary'] = "Average early game"
        except:
            pass
        
        return stats
    
    def bulk_index_documents(self, documents):
        """Bulk index with OpenSearch helpers"""
        
        if not documents:
            return 0
        
        # Prepare for bulk indexing
        actions = []
        for doc in documents:
            action = {
                "_index": self.index_name,
                "_id": f"{doc['match_id']}_{doc['player_puuid']}",
                "_source": doc
            }
            actions.append(action)
        
        try:
            success, failed = helpers.bulk(
                self.client,
                actions,
                chunk_size=50,
                raise_on_error=False,
                request_timeout=30
            )
            
            return success
            
        except Exception as e:
            print(f"Bulk indexing error: {str(e)}")
            return 0
    
    def process_batch(self, match_keys_batch):
        """Process a batch of matches"""
        
        all_docs = []
        
        for match_key in match_keys_batch:
            docs = self.process_match_file(match_key)
            all_docs.extend(docs)
            self.stats['processed'] += 1
        
        if all_docs:
            indexed = self.bulk_index_documents(all_docs)
            self.stats['indexed'] += indexed
            self.stats['failed'] += (len(all_docs) - indexed)
        
        return len(all_docs)
    
    def index_all_parallel(self, match_keys):
        """Index all matches with parallel processing"""
        
        print(f"\n{'='*60}")
        print(f"Batch Indexer with Bedrock Embeddings")
        print(f"{'='*60}")
        print(f"Total matches: {len(match_keys)}")
        print(f"Batch size: {self.batch_size}")
        print(f"Workers: {self.max_workers}")
        print(f"Embedding model: {EMBEDDINGS_MODEL_ID}")
        print(f"{'='*60}\n")
        
        # Split into batches
        batches = [match_keys[i:i + self.batch_size] 
                   for i in range(0, len(match_keys), self.batch_size)]
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.process_batch, batch): i 
                      for i, batch in enumerate(batches)}
            
            for future in as_completed(futures):
                batch_idx = futures[future]
                
                try:
                    docs_count = future.result()
                    
                    if (batch_idx + 1) % 5 == 0:
                        elapsed = time.time() - start_time
                        rate = self.stats['processed'] / elapsed if elapsed > 0 else 0
                        
                        print(f"Progress: {self.stats['processed']}/{len(match_keys)} matches "
                              f"({rate:.1f} matches/sec)")
                        print(f"  Indexed: {self.stats['indexed']} docs")
                        print(f"  Embeddings: {self.stats['embeddings_generated']}")
                        print(f"  Failed: {self.stats['failed']}")
                        
                except Exception as e:
                    print(f"Batch {batch_idx} failed: {str(e)}")
                    self.stats['failed'] += self.batch_size
        
        elapsed = time.time() - start_time
        
        print(f"\n{'='*60}")
        print(f"Indexing Complete!")
        print(f"{'='*60}")
        print(f"Matches processed: {self.stats['processed']}")
        print(f"Documents indexed: {self.stats['indexed']}")
        print(f"Embeddings generated: {self.stats['embeddings_generated']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Time elapsed: {elapsed/60:.1f} minutes")
        print(f"Average rate: {self.stats['processed'] / elapsed:.2f} matches/sec")
        print(f"{'='*60}\n")


def main():
    """Main execution"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch index with Bedrock embeddings')
    parser.add_argument('--limit', type=int, default=None, help='Max matches')
    parser.add_argument('--batch-size', type=int, default=20, help='Batch size (lower for embeddings)')
    parser.add_argument('--workers', type=int, default=2, help='Parallel workers (lower for rate limits)')
    
    args = parser.parse_args()
    
    # Create indexer
    indexer = BatchIndexer(batch_size=args.batch_size, max_workers=args.workers)
    
    # Get match keys
    match_keys = indexer.get_all_match_keys(limit=args.limit)
    
    if not match_keys:
        print("No match files found!")
        return
    
    # Index all
    indexer.index_all_parallel(match_keys)
    
    # Verify
    print("Verifying index...")
    count_query = opensearch_client.count(index=INDEX_NAME)
    print(f"Total documents in index: {count_query['count']}")


if __name__ == "__main__":
    main()