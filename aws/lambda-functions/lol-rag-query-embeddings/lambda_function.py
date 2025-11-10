"""
RAG Query Handler with Bedrock Embeddings
Uses vector similarity search for superior semantic matching
"""

import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import os
from typing import Dict, List
from datetime import datetime, timedelta

# AWS Clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
session = boto3.Session()
credentials = session.get_credentials()

# Configuration
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', 'your-domain.us-west-2.es.amazonaws.com')
OPENSEARCH_REGION = 'us-west-2'
INDEX_NAME = 'lol-matches'
BEDROCK_MODEL_ID = 'amazon.nova-pro-v1:0'
EMBEDDINGS_MODEL_ID = 'amazon.titan-embed-text-v2:0'
EMBEDDING_DIMENSION = 1024
QUESTIONS_TABLE_NAME = os.environ.get('QUESTIONS_TABLE_NAME', 'lol-player-questions')

# OpenSearch Auth
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
    connection_class=RequestsHttpConnection
)

questions_table = dynamodb.Table(QUESTIONS_TABLE_NAME)


class EmbeddingGenerator:
    """Generates embeddings for queries"""
    
    def __init__(self):
        self.bedrock = bedrock_runtime
        self.model_id = EMBEDDINGS_MODEL_ID
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for query text"""
        
        try:
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
            return response_body.get('embedding', [])
            
        except Exception as e:
            print(f"Embedding generation error: {str(e)}")
            return [0.0] * EMBEDDING_DIMENSION


class RAGQueryEngine:
    """Vector-based RAG engine using OpenSearch KNN + Bedrock"""
    
    def __init__(self):
        self.opensearch = opensearch_client
        self.bedrock = bedrock_runtime
        self.index_name = INDEX_NAME
        self.embedding_generator = EmbeddingGenerator()
    
    def get_player_matches(self, puuid: str, limit: int = 20) -> List[Dict]:
        """Retrieve player's recent matches"""
        
        query = {
            "query": {
                "term": {"player_puuid": puuid}
            },
            "sort": [
                {"game_duration": {"order": "desc"}}
            ],
            "size": limit,
            "_source": {
                "excludes": ["embedding"]  # Don't return large vectors
            }
        }
        
        try:
            response = self.opensearch.search(
                index=self.index_name,
                body=query
            )
            
            return [hit['_source'] for hit in response['hits']['hits']]
        except Exception as e:
            print(f"Error fetching player matches: {str(e)}")
            return []
    
    def search_similar_scenarios_vector(self, question: str, player_context: Dict, 
                                       limit: int = 15) -> List[Dict]:
        """
        Vector similarity search using KNN
        Finds semantically similar game scenarios
        """
        
        print(f"Generating embedding for question: {question[:100]}...")
        
        # Generate embedding for the question
        question_embedding = self.embedding_generator.generate_embedding(question)
        
        if not question_embedding or len(question_embedding) != EMBEDDING_DIMENSION:
            print("Failed to generate valid embedding, falling back to text search")
            return self.search_similar_scenarios_text(question, player_context, limit)
        
        # Build filters based on question context
        filters = self._build_filters_from_question(question, player_context)
        
        # KNN query with filters
        query = {
            "size": limit,
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": question_embedding,
                                    "k": limit * 2  # Over-fetch for filtering
                                }
                            }
                        }
                    ],
                    "filter": filters
                }
            },
            "_source": {
                "excludes": ["embedding"]  # Don't return large vectors
            }
        }
        
        try:
            response = self.opensearch.search(
                index=self.index_name,
                body=query
            )
            
            results = []
            for hit in response['hits']['hits']:
                result = hit['_source']
                result['relevance_score'] = hit['_score']
                results.append(result)
            
            print(f"Found {len(results)} similar scenarios via vector search")
            return results
            
        except Exception as e:
            print(f"Vector search error: {str(e)}")
            # Fallback to text search
            return self.search_similar_scenarios_text(question, player_context, limit)
    
    def search_similar_scenarios_text(self, question: str, player_context: Dict, 
                                     limit: int = 15) -> List[Dict]:
        """Fallback text-based search"""
        
        filters = self._build_filters_from_question(question, player_context)
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": question,
                                "fields": [
                                    "match_summary^3",
                                    "early_game_performance^2",
                                    "mid_game_performance^2",
                                    "late_game_performance^2",
                                    "champion^2"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        }
                    ],
                    "filter": filters
                }
            },
            "size": limit,
            "_source": {
                "excludes": ["embedding"]
            }
        }
        
        try:
            response = self.opensearch.search(
                index=self.index_name,
                body=query
            )
            
            results = []
            for hit in response['hits']['hits']:
                result = hit['_source']
                result['relevance_score'] = hit['_score']
                results.append(result)
            
            return results
        except Exception as e:
            print(f"Text search error: {str(e)}")
            return []
    
    def _build_filters_from_question(self, question: str, player_context: Dict) -> List[Dict]:
        """Build smart filters based on question intent"""
        
        filters = []
        question_lower = question.lower()
        
        # Champion-specific questions
        if 'champion' in player_context and any(term in question_lower for term in ['champion', 'build', 'items']):
            filters.append({"term": {"champion": player_context['champion']}})
        
        # Position-specific
        if 'position' in player_context and any(term in question_lower for term in ['lane', 'position', 'role']):
            filters.append({"term": {"position": player_context['position']}})
        
        # Winning patterns for improvement questions
        if any(term in question_lower for term in ['improve', 'better', 'win', 'success']):
            filters.append({"term": {"win": True}})
        
        # Jungle-specific
        if any(term in question_lower for term in ['jungle', 'jungling', 'gank']):
            filters.append({"term": {"position": "JUNGLE"}})
        
        # Aggression/deaths
        if any(term in question_lower for term in ['aggressive', 'death', 'dying', 'survive']):
            # Look at varied death patterns
            pass  # Don't filter, we want range of examples
        
        # CS/farming questions
        if any(term in question_lower for term in ['cs', 'farm', 'minion', 'creep']):
            # Prioritize high CS games
            filters.append({"range": {"cs_per_min": {"gte": 6.0}}})
        
        # Vision questions
        if any(term in question_lower for term in ['vision', 'ward', 'pink']):
            filters.append({"range": {"vision_score": {"gte": 30}}})
        
        return filters
    
    def get_player_statistics(self, puuid: str) -> Dict:
        """Get aggregated statistics for the player"""
        
        query = {
            "query": {
                "term": {"player_puuid": puuid}
            },
            "size": 0,
            "aggs": {
                "avg_kda": {"avg": {"field": "kda"}},
                "avg_cs_per_min": {"avg": {"field": "cs_per_min"}},
                "avg_vision_score": {"avg": {"field": "vision_score"}},
                "avg_damage_per_min": {"avg": {"field": "damage_per_min"}},
                "avg_gold_per_min": {"avg": {"field": "gold_per_min"}},
                "avg_kill_participation": {"avg": {"field": "kill_participation"}},
                "win_rate": {
                    "terms": {"field": "win", "size": 2}
                },
                "most_played_champions": {
                    "terms": {"field": "champion", "size": 5}
                },
                "position_distribution": {
                    "terms": {"field": "position", "size": 5}
                },
                "avg_deaths": {"avg": {"field": "deaths"}},
                "avg_cs_at_10": {"avg": {"field": "cs_at_10"}},
                "death_percentiles": {
                    "percentiles": {"field": "deaths", "percents": [25, 50, 75, 90]}
                },
                "cs_percentiles": {
                    "percentiles": {"field": "cs_per_min", "percents": [25, 50, 75, 90]}
                }
            }
        }
        
        try:
            response = self.opensearch.search(
                index=self.index_name,
                body=query
            )
            
            aggs = response['aggregations']
            
            # Win rate
            win_buckets = aggs.get('win_rate', {}).get('buckets', [])
            total_games = sum(bucket['doc_count'] for bucket in win_buckets)
            wins = next((bucket['doc_count'] for bucket in win_buckets if bucket['key'] == 1), 0)
            win_rate = (wins / total_games * 100) if total_games > 0 else 0
            
            return {
                "total_games": total_games,
                "win_rate": round(win_rate, 1),
                "avg_kda": round(aggs.get('avg_kda', {}).get('value', 0), 2),
                "avg_cs_per_min": round(aggs.get('avg_cs_per_min', {}).get('value', 0), 2),
                "avg_vision_score": round(aggs.get('avg_vision_score', {}).get('value', 0), 1),
                "avg_damage_per_min": round(aggs.get('avg_damage_per_min', {}).get('value', 0), 0),
                "avg_gold_per_min": round(aggs.get('avg_gold_per_min', {}).get('value', 0), 0),
                "avg_kill_participation": round(aggs.get('avg_kill_participation', {}).get('value', 0), 2),
                "avg_deaths": round(aggs.get('avg_deaths', {}).get('value', 0), 1),
                "avg_cs_at_10": round(aggs.get('avg_cs_at_10', {}).get('value', 0), 1),
                "death_percentiles": aggs.get('death_percentiles', {}).get('values', {}),
                "cs_percentiles": aggs.get('cs_percentiles', {}).get('values', {}),
                "most_played_champions": [
                    {"champion": bucket['key'], "games": bucket['doc_count']}
                    for bucket in aggs.get('most_played_champions', {}).get('buckets', [])
                ],
                "position_distribution": [
                    {"position": bucket['key'], "games": bucket['doc_count']}
                    for bucket in aggs.get('position_distribution', {}).get('buckets', [])
                ]
            }
        except Exception as e:
            print(f"Error getting player statistics: {str(e)}")
            return {}
    
    def answer_question(self, question: str, puuid: str, player_context: Dict = None) -> Dict:
        """Main RAG pipeline with vector search"""
        
        print(f"Answering question for {puuid}: {question}")
        
        if not player_context:
            player_context = {}
        
        # Step 1: Get player's statistics
        player_stats = self.get_player_statistics(puuid)
        
        # Step 2: Get player's recent matches
        player_matches = self.get_player_matches(puuid, limit=10)
        
        # Step 3: Vector search for similar scenarios from database
        similar_scenarios = self.search_similar_scenarios_vector(
            question, 
            player_context, 
            limit=15
        )
        
        # Step 4: Build RAG prompt
        prompt = self._build_rag_prompt(
            question,
            player_stats,
            player_matches,
            similar_scenarios,
            player_context
        )
        
        print(f"RAG prompt length: {len(prompt)} chars")
        
        # Step 5: Call Bedrock for answer
        answer = self._invoke_bedrock(prompt)
        
        return {
            "question": question,
            "answer": answer,
            "player_stats": player_stats,
            "similar_scenarios_count": len(similar_scenarios),
            "search_method": "vector_knn",
            "context_used": {
                "player_matches": len(player_matches),
                "database_matches": len(similar_scenarios)
            }
        }
    
    def _build_rag_prompt(self, question: str, player_stats: Dict, 
                          player_matches: List[Dict], similar_scenarios: List[Dict],
                          player_context: Dict) -> str:
        """Build comprehensive RAG prompt"""
        
        # Player overview
        player_overview = f"""
PLAYER PROFILE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Games Analyzed: {player_stats.get('total_games', 0)}
Win Rate: {player_stats.get('win_rate', 0)}%
Average KDA: {player_stats.get('avg_kda', 0)}
Average CS/min: {player_stats.get('avg_cs_per_min', 0)}
Average Deaths: {player_stats.get('avg_deaths', 0)} per game
Average Vision Score: {player_stats.get('avg_vision_score', 0)}
Average Damage/min: {player_stats.get('avg_damage_per_min', 0)}
Average CS at 10min: {player_stats.get('avg_cs_at_10', 0)}
Kill Participation: {player_stats.get('avg_kill_participation', 0)*100:.1f}%

Death Consistency:
  - 25th percentile: {player_stats.get('death_percentiles', {}).get('25.0', 0):.1f} deaths
  - Median: {player_stats.get('death_percentiles', {}).get('50.0', 0):.1f} deaths
  - 75th percentile: {player_stats.get('death_percentiles', {}).get('75.0', 0):.1f} deaths

Most Played Champions:
{self._format_champion_list(player_stats.get('most_played_champions', []))}

Main Positions:
{self._format_position_list(player_stats.get('position_distribution', []))}
"""
        
        # Recent matches summary
        recent_matches_summary = "\nRECENT MATCHES:\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for idx, match in enumerate(player_matches[:5], 1):
            recent_matches_summary += f"{idx}. {match['champion']} ({match['position']}): "
            recent_matches_summary += f"{'WIN' if match['win'] else 'LOSS'} - "
            recent_matches_summary += f"KDA {match['kills']}/{match['deaths']}/{match['assists']} - "
            recent_matches_summary += f"{match['cs_per_min']} CS/min - "
            recent_matches_summary += f"{match['vision_score']} vision\n"
        
        # Database insights from vector search
        database_insights = "\nSIMILAR SCENARIOS FROM DATABASE (Vector-matched):\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if similar_scenarios:
            # Winners vs player
            winners = [s for s in similar_scenarios if s.get('win')]
            
            if winners:
                avg_kda_winners = sum(s['kda'] for s in winners) / len(winners)
                avg_cs_winners = sum(s['cs_per_min'] for s in winners) / len(winners)
                avg_vision_winners = sum(s['vision_score'] for s in winners) / len(winners)
                avg_deaths_winners = sum(s['deaths'] for s in winners) / len(winners)
                
                database_insights += f"Successful players in similar situations average:\n"
                database_insights += f"  - KDA: {avg_kda_winners:.2f} (yours: {player_stats.get('avg_kda', 0):.2f})\n"
                database_insights += f"  - CS/min: {avg_cs_winners:.2f} (yours: {player_stats.get('avg_cs_per_min', 0):.2f})\n"
                database_insights += f"  - Vision: {avg_vision_winners:.1f} (yours: {player_stats.get('avg_vision_score', 0):.1f})\n"
                database_insights += f"  - Deaths: {avg_deaths_winners:.1f} (yours: {player_stats.get('avg_deaths', 0):.1f})\n\n"
            
            # Item builds if relevant
            if any(term in question.lower() for term in ['item', 'build', 'buy', 'purchase']):
                database_insights += "Popular winning builds in similar games:\n"
                for idx, scenario in enumerate(winners[:5], 1):
                    database_insights += f"  {idx}. {scenario.get('champion', 'Unknown')}: {scenario.get('item_build_path', 'N/A')}\n"
                database_insights += "\n"
            
            # Top scenarios
            database_insights += f"Top semantically similar game scenarios:\n"
            for idx, scenario in enumerate(similar_scenarios[:3], 1):
                summary = scenario.get('match_summary', 'N/A')
                # Truncate for brevity
                summary_short = summary[:300] + "..." if len(summary) > 300 else summary
                database_insights += f"\n{idx}. {summary_short}\n"
        
        # Build final prompt
        prompt = f"""You are an elite League of Legends coach analyzing a player's performance using data from 150,000+ games.

{player_overview}

{recent_matches_summary}

{database_insights}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PLAYER'S QUESTION:
"{question}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provide a comprehensive, data-driven answer that:

1. DIRECTLY ANSWERS their question using their specific statistics
2. COMPARES their performance to successful players from our database
3. Identifies SPECIFIC improvement areas with quantifiable goals
4. Provides 3-5 CONCRETE, actionable recommendations
5. Uses the similar scenarios to support your advice

COACHING APPROACH:
- Reference their actual numbers vs. database benchmarks
- Explain WHY improvements matter (not just WHAT to do)
- Be encouraging but honest about weaknesses
- Focus on macro gameplay and decision-making
- Maximum 300 words

RULES:
- NO champion abilities or mechanics
- Only strategic/macro advice
- Data-driven insights only
- Friendly, motivating tone

Begin your answer:"""
        
        return prompt
    
    def _format_champion_list(self, champions: List[Dict]) -> str:
        """Format champion list"""
        if not champions:
            return "  No data available"
        return "\n".join(f"  {i+1}. {c['champion']} ({c['games']} games)" 
                        for i, c in enumerate(champions))
    
    def _format_position_list(self, positions: List[Dict]) -> str:
        """Format position list"""
        if not positions:
            return "  No data available"
        return "\n".join(f"  {i+1}. {p['position']} ({p['games']} games)" 
                        for i, p in enumerate(positions))
    
    def _invoke_bedrock(self, prompt: str) -> str:
        """Call Bedrock Nova Pro for answer generation"""
        
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": {
                "max_new_tokens": 600,
                "temperature": 0.5,
                "top_p": 0.9
            }
        }
        
        try:
            response = self.bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            
            if 'output' in response_body and 'message' in response_body['output']:
                content = response_body['output']['message'].get('content', [])
                if content:
                    return content[0].get('text', '').strip()
            
            return "I apologize, but I couldn't generate an answer at this time."
            
        except Exception as e:
            print(f"Bedrock error: {str(e)}")
            return "I apologize, but I encountered an error generating your answer."


def lambda_handler(event, context):
    """Lambda handler for RAG-based question answering"""
    
    try:
        # Parse request
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event
        
        question = body.get('question')
        puuid = body.get('puuid')
        player_context = body.get('player_context', {})
        
        if not question or not puuid:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'question and puuid required'})
            }
        
        # Rate limiting
        question_count = check_rate_limit(puuid)
        if question_count >= 10:
            return {
                'statusCode': 429,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Rate limit exceeded (10 questions/hour)',
                    'limit': 10,
                    'reset_in_seconds': 3600
                })
            }
        
        # Answer question using RAG
        rag_engine = RAGQueryEngine()
        result = rag_engine.answer_question(question, puuid, player_context)
        
        # Save question/answer
        save_question(puuid, question, result['answer'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def check_rate_limit(puuid: str) -> int:
    """Check rate limit"""
    one_hour_ago = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
    
    try:
        response = questions_table.query(
            KeyConditionExpression='puuid = :puuid AND asked_at > :time',
            ExpressionAttributeValues={
                ':puuid': puuid,
                ':time': one_hour_ago
            }
        )
        return len(response.get('Items', []))
    except:
        return 0


def save_question(puuid: str, question: str, answer: str):
    """Save question/answer"""
    question_id = f"rag_{int(datetime.utcnow().timestamp())}"
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    try:
        questions_table.put_item(Item={
            'puuid': puuid,
            'question_id': question_id,
            'asked_at': int(datetime.utcnow().timestamp()),
            'question': question,
            'answer': answer,
            'question_type': 'performance_rag_vector',
            'ttl': ttl
        })
    except Exception as e:
        print(f"Failed to save question: {str(e)}")
