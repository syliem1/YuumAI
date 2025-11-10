"""
OpenSearch Indexer with Bedrock Embeddings
Processes match files and creates vector embeddings for semantic search
"""

import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import os
from typing import Dict, List
import math
import time

# AWS Clients
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
session = boto3.Session()
credentials = session.get_credentials()

# OpenSearch Configuration
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', 'search-lol-match-analysis-3mo5dmxf36hqqjxh6lhzullgza.us-west-2.es.amazonaws.com')
OPENSEARCH_REGION = 'us-west-2'
INDEX_NAME = 'lol-matches'

# Bedrock Embeddings Model
EMBEDDINGS_MODEL_ID = 'amazon.titan-embed-text-v2:0'
EMBEDDING_DIMENSION = 1024  # Titan v2 dimension

# AWS Auth for OpenSearch
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    OPENSEARCH_REGION,
    'es',
    session_token=credentials.token
)

# OpenSearch Client
opensearch_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=300
)


class EmbeddingGenerator:
    """Generates embeddings using Bedrock Titan"""
    
    def __init__(self):
        self.bedrock = bedrock_runtime
        self.model_id = EMBEDDINGS_MODEL_ID
        self.cache = {}  # Cache embeddings for identical texts
    
    def generate_embedding(self, text: str, normalize: bool = True) -> List[float]:
        """Generate embedding vector for text"""
        
        # Check cache
        cache_key = hash(text)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Truncate text if too long (Titan v2 max: ~8K tokens)
            if len(text) > 25000:
                text = text[:25000]
            
            request_body = {
                "inputText": text,
                "dimensions": EMBEDDING_DIMENSION,
                "normalize": normalize
            }
            
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            embedding = response_body.get('embedding', [])
            
            # Cache result
            self.cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            print(f"Embedding generation error: {str(e)}")
            # Return zero vector on error
            return [0.0] * EMBEDDING_DIMENSION
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        
        for text in texts:
            time.sleep(1.5)
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        
        return embeddings


class MatchIndexer:
    """Indexes match data with vector embeddings into OpenSearch"""
    
    def __init__(self):
        self.client = opensearch_client
        self.index_name = INDEX_NAME
        self.embedding_generator = EmbeddingGenerator()
    
    def create_index(self):
        """Create OpenSearch index with KNN vector field"""
        
        index_body = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.knn": True,  # Enable KNN
                "analysis": {
                    "analyzer": {
                        "lol_analyzer": {
                            "type": "standard",
                            "stopwords": "_english_"
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    # Match identifiers
                    "match_id": {"type": "keyword"},
                    "game_version": {"type": "keyword"},
                    "game_duration": {"type": "integer"},
                    "queue_id": {"type": "integer"},
                    
                    # Player info
                    "player_puuid": {"type": "keyword"},
                    "player_name": {"type": "text"},
                    "champion": {"type": "keyword"},
                    "position": {"type": "keyword"},
                    "team_id": {"type": "integer"},
                    "win": {"type": "boolean"},
                    
                    # Core stats
                    "kills": {"type": "integer"},
                    "deaths": {"type": "integer"},
                    "assists": {"type": "integer"},
                    "kda": {"type": "float"},
                    "level": {"type": "integer"},
                    
                    # Economy
                    "gold_earned": {"type": "integer"},
                    "total_cs": {"type": "integer"},
                    "cs_per_min": {"type": "float"},
                    "gold_per_min": {"type": "float"},
                    
                    # Combat
                    "damage_to_champions": {"type": "integer"},
                    "damage_taken": {"type": "integer"},
                    "damage_per_min": {"type": "float"},
                    "kill_participation": {"type": "float"},
                    
                    # Vision
                    "vision_score": {"type": "integer"},
                    "wards_placed": {"type": "integer"},
                    "wards_killed": {"type": "integer"},
                    "control_wards": {"type": "integer"},
                    
                    # Objectives
                    "turret_kills": {"type": "integer"},
                    "inhibitor_kills": {"type": "integer"},
                    "dragon_kills": {"type": "integer"},
                    "baron_kills": {"type": "integer"},
                    
                    # Items
                    "items": {"type": "keyword"},
                    "item_build_path": {"type": "text"},
                    
                    # Lane phase
                    "cs_at_10": {"type": "integer"},
                    "gold_at_10": {"type": "integer"},
                    "xp_at_10": {"type": "integer"},
                    "cs_diff_at_10": {"type": "integer"},
                    "gold_diff_at_10": {"type": "integer"},
                    
                    # Performance descriptions (for text search)
                    "early_game_performance": {"type": "text"},
                    "mid_game_performance": {"type": "text"},
                    "late_game_performance": {"type": "text"},
                    
                    # Text summary for hybrid search
                    "match_summary": {
                        "type": "text",
                        "analyzer": "lol_analyzer"
                    },
                    
                    # VECTOR EMBEDDING - KNN field
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": EMBEDDING_DIMENSION,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 16
                            }
                        }
                    }
                }
            }
        }
        
        try:
            if self.client.indices.exists(index=self.index_name):
                print(f"Index {self.index_name} already exists")
            else:
                self.client.indices.create(index=self.index_name, body=index_body)
                print(f"✓ Created index with KNN support: {self.index_name}")
        except Exception as e:
            print(f"Error creating index: {str(e)}")
    
    def extract_match_features(self, match_data: dict, timeline_data: dict) -> List[Dict]:
        """Extract features and generate embeddings for each participant"""
        
        try:
            participants = match_data['info']['participants']
            indexed_docs = []
            
            # Prepare all summaries for batch embedding
            summaries_to_embed = []
            participant_data = []
            
            for participant in participants:
                # Calculate derived metrics
                game_duration_min = match_data['info']['gameDuration'] / 60
                cs_total = participant.get('totalMinionsKilled', 0) + participant.get('neutralMinionsKilled', 0)
                cs_per_min = cs_total / game_duration_min if game_duration_min > 0 else 0
                gold_per_min = participant.get('goldEarned', 0) / game_duration_min if game_duration_min > 0 else 0
                damage_per_min = participant.get('totalDamageDealtToChampions', 0) / game_duration_min if game_duration_min > 0 else 0
                
                kda = ((participant.get('kills', 0) + participant.get('assists', 0)) / 
                       max(participant.get('deaths', 1), 1))
                
                # Get items
                items = [
                    participant.get(f'item{i}', 0) 
                    for i in range(7) 
                    if participant.get(f'item{i}', 0) != 0
                ]
                
                # Extract timeline stats
                timeline_stats = self._extract_timeline_stats(
                    timeline_data, 
                    participant['participantId']
                )
                
                # Build comprehensive match summary for embedding
                match_summary = self._build_match_summary(
                    participant, 
                    match_data['info'], 
                    timeline_stats,
                    cs_per_min,
                    gold_per_min,
                    damage_per_min
                )
                
                summaries_to_embed.append(match_summary)
                
                # Store participant data
                participant_data.append({
                    "match_id": match_data['metadata']['matchId'],
                    "game_version": match_data['info']['gameVersion'],
                    "game_duration": int(match_data['info']['gameDuration']),
                    "queue_id": match_data['info']['queueId'],
                    
                    "player_puuid": participant.get('puuid'),
                    "player_name": f"{participant.get('riotIdGameName', 'Unknown')}#{participant.get('riotIdTagline', '')}",
                    "champion": participant.get('championName'),
                    "position": participant.get('teamPosition', 'UNKNOWN'),
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
                    "item_build_path": self._get_item_names(items),
                    
                    "cs_at_10": timeline_stats.get('cs_at_10', 0),
                    "gold_at_10": timeline_stats.get('gold_at_10', 0),
                    "xp_at_10": timeline_stats.get('xp_at_10', 0),
                    "cs_diff_at_10": timeline_stats.get('cs_diff_at_10', 0),
                    "gold_diff_at_10": timeline_stats.get('gold_diff_at_10', 0),
                    
                    "early_game_performance": timeline_stats.get('early_game_summary', ''),
                    "mid_game_performance": timeline_stats.get('mid_game_summary', ''),
                    "late_game_performance": timeline_stats.get('late_game_summary', ''),
                    
                    "match_summary": match_summary
                })
            
            # Generate embeddings in batch
            print(f"Generating embeddings for {len(summaries_to_embed)} participants...")
            embeddings = self.embedding_generator.generate_batch_embeddings(summaries_to_embed)
            
            # Combine data with embeddings
            for i, data in enumerate(participant_data):
                data['embedding'] = embeddings[i]
                indexed_docs.append(data)
            
            return indexed_docs
            
        except Exception as e:
            print(f"Error extracting features: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _extract_timeline_stats(self, timeline_data: dict, participant_id: int) -> Dict:
        """Extract timeline-specific statistics"""
        
        stats = {
            'cs_at_10': 0,
            'gold_at_10': 0,
            'xp_at_10': 0,
            'cs_diff_at_10': 0,
            'gold_diff_at_10': 0,
            'early_game_summary': '',
            'mid_game_summary': '',
            'late_game_summary': ''
        }
        
        try:
            frames = timeline_data.get('info', {}).get('frames', [])
            
            # Find 10-minute mark
            if len(frames) >= 11:
                frame_10 = frames[10]
                participant_frame = frame_10.get('participantFrames', {}).get(str(participant_id), {})
                
                stats['cs_at_10'] = participant_frame.get('minionsKilled', 0) + participant_frame.get('jungleMinionsKilled', 0)
                stats['gold_at_10'] = participant_frame.get('totalGold', 0)
                stats['xp_at_10'] = participant_frame.get('xp', 0)
            
            # Analyze performance by game phase
            stats['early_game_summary'] = self._analyze_early_game(frames[:10], participant_id)
            stats['mid_game_summary'] = self._analyze_mid_game(frames[10:20], participant_id)
            stats['late_game_summary'] = self._analyze_late_game(frames[20:], participant_id)
            
        except Exception as e:
            print(f"Timeline extraction error: {str(e)}")
        
        return stats
    
    def _analyze_early_game(self, frames: List, participant_id: int) -> str:
        """Analyze early game performance"""
        if not frames:
            return "No early game data"
        
        try:
            first_frame = frames[0].get('participantFrames', {}).get(str(participant_id), {})
            last_frame = frames[-1].get('participantFrames', {}).get(str(participant_id), {})
            
            gold_growth = last_frame.get('totalGold', 0) - first_frame.get('totalGold', 0)
            cs_growth = (last_frame.get('minionsKilled', 0) - first_frame.get('minionsKilled', 0))
            
            if gold_growth > 2500 and cs_growth > 60:
                return "Strong early laning phase with excellent CS and gold income"
            elif gold_growth < 1500:
                return "Struggled in early laning phase, behind in gold"
            else:
                return "Average early game performance"
        except:
            return "Early game data incomplete"
    
    def _analyze_mid_game(self, frames: List, participant_id: int) -> str:
        """Analyze mid game"""
        if not frames:
            return "No mid game data"
        return "Mid game transition period with teamfights"
    
    def _analyze_late_game(self, frames: List, participant_id: int) -> str:
        """Analyze late game"""
        if not frames:
            return "Game ended before late game"
        return "Late game teamfighting and objective control phase"
    
    def _get_item_names(self, item_ids: List[int]) -> str:
        """Convert item IDs to readable format"""
        if not item_ids:
            return "No items"
        return f"Items: {', '.join(map(str, item_ids))}"
    
    def _build_match_summary(self, participant: dict, match_info: dict, 
                            timeline_stats: dict, cs_per_min: float,
                            gold_per_min: float, damage_per_min: float) -> str:
        """Build comprehensive text summary for embedding"""
        
        champion = participant.get('championName', 'Unknown')
        position = participant.get('teamPosition', 'UNKNOWN')
        win = "won" if participant.get('win') else "lost"
        kda = f"{participant.get('kills', 0)}/{participant.get('deaths', 0)}/{participant.get('assists', 0)}"
        
        game_duration_min = match_info.get('gameDuration', 0) / 60
        
        # Rich semantic summary for better embedding
        summary = f"""
        {champion} {position} game that was {win}.
        Performance: KDA {kda}, Level {participant.get('champLevel', 0)}.
        Game lasted {game_duration_min:.0f} minutes in ranked queue.
        
        Economy: {participant.get('goldEarned', 0)} total gold earned at {gold_per_min:.0f} gold per minute.
        CS: {participant.get('totalMinionsKilled', 0) + participant.get('neutralMinionsKilled', 0)} total minions at {cs_per_min:.1f} CS per minute.
        At 10 minutes had {timeline_stats.get('cs_at_10', 0)} CS and {timeline_stats.get('gold_at_10', 0)} gold.
        
        Combat: {participant.get('totalDamageDealtToChampions', 0)} damage to champions at {damage_per_min:.0f} damage per minute.
        Took {participant.get('totalDamageTaken', 0)} damage.
        Kill participation: {participant.get('challenges', {}).get('killParticipation', 0)*100:.0f}%.
        
        Vision: {participant.get('visionScore', 0)} vision score with {participant.get('wardsPlaced', 0)} wards placed and {participant.get('wardsKilled', 0)} wards destroyed.
        Control wards: {participant.get('visionWardsBoughtInGame', 0)}.
        
        Objectives: {participant.get('turretKills', 0)} turrets, {participant.get('dragonKills', 0)} dragons, {participant.get('baronKills', 0)} barons.
        
        Game phases:
        Early game (0-10 min): {timeline_stats.get('early_game_summary', 'Unknown')}.
        Mid game (10-20 min): {timeline_stats.get('mid_game_summary', 'Unknown')}.
        Late game (20+ min): {timeline_stats.get('late_game_summary', 'Unknown')}.
        
        This {'winning' if participant.get('win') else 'losing'} game demonstrates {'strong' if participant.get('win') else 'weak'} performance in {position} position.
        """
        
        return summary.strip()
    
    def index_match(self, match_data: dict, timeline_data: dict) -> bool:
        """Index a single match with embeddings"""
        
        try:
            docs = self.extract_match_features(match_data, timeline_data)
            
            if not docs:
                return False
            
            for doc in docs:
                doc_id = f"{doc['match_id']}_{doc['player_puuid']}"
                
                self.client.index(
                    index=self.index_name,
                    id=doc_id,
                    body=doc,
                    refresh=False
                )
            
            return True
            
        except Exception as e:
            print(f"Error indexing match: {str(e)}")
            return False
    
    def bulk_index_from_s3(self, bucket: str, max_matches: int = 1000):
        """Index multiple matches from S3"""
        
        print(f"Starting bulk indexing from s3://{bucket}")
        print(f"Using Bedrock embeddings: {EMBEDDINGS_MODEL_ID}")
        
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix='raw-matches/')
        
        indexed_count = 0
        failed_count = 0
        
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                if not key.endswith('match-data.json'):
                    continue
                
                if indexed_count >= max_matches:
                    break
                
                try:
                    # Get match data
                    match_obj = s3_client.get_object(Bucket=bucket, Key=key)
                    match_data = json.loads(match_obj['Body'].read())
                    
                    # Get timeline data
                    timeline_key = key.replace('match-data.json', 'timeline-data.json')
                    timeline_obj = s3_client.get_object(Bucket=bucket, Key=timeline_key)
                    timeline_data = json.loads(timeline_obj['Body'].read())
                    
                    # Index with embeddings
                    if self.index_match(match_data, timeline_data):
                        indexed_count += 1
                        
                        if indexed_count % 10 == 0:
                            print(f"Indexed {indexed_count} matches...")
                            self.client.indices.refresh(index=self.index_name)
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    print(f"Failed to process {key}: {str(e)}")
                    failed_count += 1
                    continue
        
        # Final refresh
        self.client.indices.refresh(index=self.index_name)
        
        print(f"✓ Indexing complete!")
        print(f"  Successful: {indexed_count}")
        print(f"  Failed: {failed_count}")
        
        return indexed_count


def lambda_handler(event, context):
    """Lambda handler for indexing with embeddings"""
    
    bucket = event.get('bucket', 'lol-training-matches-150k')
    max_matches = event.get('max_matches', 100)
    
    indexer = MatchIndexer()
    
    # Create index if doesn't exist
    indexer.create_index()
    
    # Bulk index
    count = indexer.bulk_index_from_s3(bucket, max_matches)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'matches_indexed': count,
            'index_name': INDEX_NAME,
            'embedding_model': EMBEDDINGS_MODEL_ID
        })
    }


if __name__ == "__main__":
    indexer = MatchIndexer()
    indexer.create_index()
    indexer.bulk_index_from_s3('lol-training-matches-150k', max_matches=50)
