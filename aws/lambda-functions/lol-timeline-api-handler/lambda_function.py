"""
Unified API Gateway Handler
Combines player processing, playstyle classification, timeline events, and RAG-based Q&A
"""

import json
import boto3
import os
import requests
import time
import math
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from boto3.dynamodb.conditions import Key, Attr
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError

# --- AWS Clients ---
dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')
s3_client = boto3.client('s3')
stepfunctions = boto3.client('stepfunctions')
sagemaker_runtime = boto3.client('sagemaker-runtime')
session = boto3.Session()
credentials = session.get_credentials()

# --- Environment Variables ---
EVENTS_TABLE_NAME = os.environ.get('EVENTS_TABLE_NAME', 'lol-timeline-events')
SUMMARIES_TABLE_NAME = os.environ.get('SUMMARIES_TABLE_NAME', 'lol-event-summaries')
QUESTIONS_TABLE_NAME = os.environ.get('QUESTIONS_TABLE_NAME', 'lol-player-questions')
PLAYER_PROFILES_TABLE_NAME = os.environ.get('PLAYER_PROFILES_TABLE_NAME', 'lol-player-profiles')
RIOT_API_KEY = os.environ['RIOT_API_KEY']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']
S3_BUCKET_RAW = os.environ['S3_BUCKET_RAW']
SAGEMAKER_ENDPOINT = os.environ['SAGEMAKER_ENDPOINT']
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
OPENSEARCH_REGION = 'us-west-2'
INDEX_NAME = 'lol-matches'

events_table = dynamodb.Table(EVENTS_TABLE_NAME)
summaries_table = dynamodb.Table(SUMMARIES_TABLE_NAME)
questions_table = dynamodb.Table(QUESTIONS_TABLE_NAME)
player_profiles_table = dynamodb.Table(PLAYER_PROFILES_TABLE_NAME)

BEDROCK_MODEL_ID = 'us.amazon.nova-pro-v1:0'
EMBEDDINGS_MODEL_ID = 'amazon.titan-embed-text-v2:0'
EMBEDDING_DIMENSION = 1024

# OpenSearch client
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
    timeout=30
)

# Global statistics from 150k+ games
GLOBAL_STATS = {
    "total_games": {"mean": 3.2249919039325006, "std": 5.254272357960088},
    "win_rate": {"mean": 0.4929653016264618, "std": 0.3994213414923714},
    "avg_kills": {"mean": 6.172342721284408, "std": 3.9854087224200025},
    "avg_deaths": {"mean": 6.294418398501851, "std": 2.7758456800010207},
    "avg_assists": {"mean": 8.379155992079713, "std": 4.989258092619942},
    "avg_kda": {"mean": 3.4153405666652397, "std": 3.029093819718261},
    "avg_cs_per_min": {"mean": 4.117095705028882, "std": 2.4286763589919595},
    "avg_gpm": {"mean": 387.7240377055939, "std": 72.58626910255333},
    "avg_dpm": {"mean": 703.0083293260915, "std": 284.2168459639315},
    "avg_vision_score": {"mean": 26.342648127922022, "std": 18.652806748839577},
    "avg_kill_participation": {"mean": 0.4599937851317357, "std": 0.1312101010930826},
    "avg_early_gold_adv": {"mean": 0.07729061639052412, "std": 0.2138571506360595},
    "avg_cs_at_10": {"mean": 39.24453235905662, "std": 25.412508737888604},
    "avg_team_damage_pct": {"mean": 0.1981815246129052, "std": 0.06695530113266078},
    "avg_objective_damage": {"mean": 12990.801800600986, "std": 12053.211943003807},
    "death_consistency": {"mean": 1.4641622654199804, "std": 1.752731122270569},
    "cs_consistency": {"mean": 0.7443884184113814, "std": 1.0915732263139033}
}

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def run_background_processing(event):
    """
    Worker: Downloads matches, calculates stats incrementally, updates DB.
    """
    game_name = event['game_name']
    tagline = event['tagline']
    puuid = event['puuid']
    match_ids = event['match_ids']
    player_id = f"{game_name}#{tagline}"

    print(f"Worker processing {len(match_ids)} matches for {player_id}")

    # Setup for incremental aggregation
    all_matches_df = pd.DataFrame()
    
    # Process in batches to update DB incrementally
    BATCH_SIZE = 5 
    
    for i in range(0, len(match_ids), BATCH_SIZE):
        batch = match_ids[i : i + BATCH_SIZE]
        
        # 1. Download Batch
        download_matches(game_name, tagline, batch)
        
        # 2. Load & Process Batch
        new_matches_df = load_player_matches_from_s3(game_name, tagline, puuid)
        
        if not new_matches_df.empty:
            # 3. Calculate Stats based on what we have SO FAR
            current_stats = create_player_aggregate(new_matches_df)
            most_played = get_most_played_champions(new_matches_df)
            
            # 4. Classify Playstyle
            playstyle = {}
            if i + BATCH_SIZE >= len(match_ids): # If final batch
                playstyle = classify_playstyle(current_stats)
                status = 'COMPLETED'
            else:
                status = 'PROCESSING'

            # 5. Update DynamoDB with INTERMEDIATE results
            player_profiles_table.update_item(
                Key={'player_id': player_id},
                UpdateExpression="""set 
                    stats = :s, 
                    most_played_champions = :mp, 
                    processing_status = :ps,
                    matches_processed_count = :cnt,
                    playstyle = :style
                """,
                ExpressionAttributeValues=convert_floats({
                    ':s': current_stats,
                    ':mp': most_played,
                    ':ps': status,
                    ':cnt': len(new_matches_df),
                    ':style': playstyle
                })
            )
            print(f"Updated profile: {len(new_matches_df)}/{len(match_ids)} matches processed.")

    # Trigger timeline processing at the very end
    trigger_timeline_processing(game_name, tagline, puuid, match_ids)
    return "Worker Completed"

# ============================================================================
# MAIN LAMBDA HANDLER
# ============================================================================

def lambda_handler(event, context):
    if not event.get('httpMethod') and not event.get('requestContext') and 'async_worker' in event:
        return run_background_processing(event)

    """Main API Gateway entry point"""
    try:
        http_method = event['requestContext']['http']['method']
        path = event['requestContext']['http']['path']
    except KeyError:
        try:
            http_method = event['httpMethod']
            path = event['path']
        except KeyError:
            return cors_response(400, {'error': 'Invalid event payload'})
    
    print(f"API request: {http_method} {path}")
    print(f"Raw event body: {event.get('body', 'NO BODY')}")  # Debug line
    
    if http_method == 'OPTIONS':
        return cors_response(200, {})
    
    try:
        # Player onboarding
        if path == '/player/process' and http_method == 'POST':
            return process_new_player(event, context)
        
        # Get player profile
        elif path == '/player/profile' and http_method == 'GET':
            return get_player_profile(event)

        # Get player percentile rankings
        elif path == '/player/percentiles' and http_method == 'GET':
            return get_player_percentiles(event)
        
        # Compare to another player
        elif path == '/player/compare' and http_method == 'POST':
            return compare_player(event)

        # Timeline events for a specific match
        elif path == '/timeline/events' and http_method == 'GET':
            return get_timeline_events(event)
        
        # Get event summary
        elif path == '/timeline/events/summary' and http_method == 'POST':
            return get_event_summary(event)
        
        # Ask event-specific question (WE'RE NOT DOING THIS)
        elif path == '/timeline/ask' and http_method == 'POST':
            return answer_event_question(event)
        
        # Ask open-ended performance question (RAG-based)
        elif path == '/player/ask' and http_method == 'POST':
            return answer_performance_question(event)
        
        else:
            return cors_response(404, {'error': 'Endpoint not found'})
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return cors_response(500, {'error': str(e)})

# ============================================================================
# PERCENTILE CALCULATION UTILITIES
# ============================================================================

def calculate_percentile(value: float, mean: float, std: float, lower_is_better: bool = False) -> float:
    """
    Calculate percentile using normal distribution (z-score)
    Returns percentile from 0-100
    
    For stats where lower is better (deaths, consistency), we invert the percentile
    """
    if std == 0:
        return 50.0
    
    # Calculate z-score
    z_score = (value - mean) / std
    
    # Use cumulative distribution function approximation
    def erf_approx(x):
        """Approximate error function"""
        a1 =  0.254829592
        a2 = -0.284496736
        a3 =  1.421413741
        a4 = -1.453152027
        a5 =  1.061405429
        p  =  0.3275911
        
        sign = 1 if x >= 0 else -1
        x = abs(x)
        
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
        
        return sign * y
    
    # Convert z-score to percentile
    percentile = (1 + erf_approx(z_score / math.sqrt(2))) / 2 * 100
    
    # Invert for "lower is better" stats
    if lower_is_better:
        percentile = 100 - percentile
    
    # Clamp between 0 and 100
    return max(0.0, min(100.0, percentile))


def get_percentile_interpretation(percentile: float) -> str:
    """Provide human-readable interpretation of percentile"""
    if percentile >= 95:
        return "Elite (Top 5%)"
    elif percentile >= 90:
        return "Excellent (Top 10%)"
    elif percentile >= 75:
        return "Above Average (Top 25%)"
    elif percentile >= 60:
        return "Above Average"
    elif percentile >= 40:
        return "Average"
    elif percentile >= 25:
        return "Below Average"
    elif percentile >= 10:
        return "Needs Improvement (Bottom 25%)"
    else:
        return "Needs Significant Improvement (Bottom 10%)"


# ============================================================================
# PLAYER PERCENTILE RANKINGS ENDPOINT
# ============================================================================

def get_player_percentiles(event):
    """
    GET /player/percentiles?game_name=XXX&tagline=YYY
    
    Returns percentile rankings for all player stats compared to global averages from 150k+ games
    """
    try:
        params = event.get('queryStringParameters', {})
        game_name = params.get('game_name')
        tagline = params.get('tagline')
        
        if not game_name or not tagline:
            return cors_response(400, {'error': 'game_name and tagline required'})
        
        player_id = f"{game_name}#{tagline}"
        
        # Get player profile
        response = player_profiles_table.get_item(Key={'player_id': player_id})
        
        if 'Item' not in response:
            return cors_response(404, {'error': 'Player not found. Process this player first via /player/process'})
        
        profile = response['Item']
        player_stats = profile.get('stats', {})
        status = profile.get('processing_status', 'UNKNOWN')
        processed_count = int(profile.get('matches_processed_count', 0))
        total_count = int(profile.get('total_matches_to_process', 0))

        if status == 'PROCESSING' and not player_stats:
            progress = int((processed_count / total_count) * 100) if total_count > 0 else 0
            return cors_response(200, {
                'status': 'PROCESSING',
                'progress_percentage': progress,
                'message': 'Analyzing match data...',
                'player_id': player_id,
                'percentiles': {},
                'most_played_champions': {},
                'strengths': [],
                'weaknesses': [],
                'ranked_stats': {'top_5': [], 'bottom_5': []},
                'overall_performance': {
                    'percentile': 0,
                    'interpretation': 'Calculating...',
                    'based_on_metrics': []
                },
                'comparison_base': {'total_games_analyzed': '0'}
            })
        
        # Calculate percentiles for each stat
        print(f"Printing player stats...")
        percentiles = {}
        
        # Map player stat keys to global stat keys with "lower is better" flag
        stat_mapping = {
            'win_rate': ('win_rate', False),
            'avg_kda': ('avg_kda', False),
            'avg_cs_per_min': ('avg_cs_per_min', False),
            'avg_gpm': ('avg_gpm', False),
            'avg_dpm': ('avg_dpm', False),
            'avg_vision_score': ('avg_vision_score', False),
            'avg_kill_participation': ('avg_kill_participation', False),
            'avg_early_gold_adv': ('avg_early_gold_adv', False),
            'avg_team_damage_pct': ('avg_team_damage_pct', False),
            'avg_objective_damage': ('avg_objective_damage', False),
            'avg_deaths': ('avg_deaths', True),  # Lower is better
            'death_consistency': ('death_consistency', True),  # Lower variance is better
            'cs_consistency': ('cs_consistency', True)  # Lower variance is better
        }
        
        for player_key, (global_key, lower_is_better) in stat_mapping.items():
            if player_key in player_stats and global_key in GLOBAL_STATS:
                player_value = float(player_stats[player_key])
                global_data = GLOBAL_STATS[global_key]
                
                percentile = calculate_percentile(
                    player_value,
                    global_data['mean'],
                    global_data['std'],
                    lower_is_better
                )
                
                percentiles[player_key] = {
                    'value': round(player_value, 2),
                    'percentile': round(percentile, 1),
                    'global_mean': round(global_data['mean'], 2),
                    'global_std': round(global_data['std'], 2),
                    'interpretation': get_percentile_interpretation(percentile),
                    'better_than_mean': player_value > global_data['mean'] if not lower_is_better else player_value < global_data['mean']
                }
        
        # Calculate overall performance score (average of key metrics)
        key_metrics = ['avg_kda', 'avg_cs_per_min', 'avg_vision_score', 
                       'avg_kill_participation', 'win_rate']
        key_percentiles = [percentiles[k]['percentile'] for k in key_metrics 
                           if k in percentiles]
        
        overall_percentile = sum(key_percentiles) / len(key_percentiles) if key_percentiles else 50.0
        
        # Identify strengths (top 3 stats >= 75th percentile)
        strengths = sorted(
            [(k, v['percentile']) for k, v in percentiles.items()],
            key=lambda x: x[1],
            reverse=True
        )
        top_strengths = [{'stat': k, 'percentile': p} for k, p in strengths if p >= 75.0][:3]
        
        # Identify weaknesses (top 3 stats <= 25th percentile)
        weaknesses = sorted(
            [(k, v['percentile']) for k, v in percentiles.items()],
            key=lambda x: x[1]
        )
        top_weaknesses = [{'stat': k, 'percentile': p} for k, p in weaknesses if p <= 25.0][:3]
        
        return cors_response(200, {
            'status': status,
            'progress_percentage': int((processed_count / total_count) * 100) if total_count > 0 else 0,
            'is_partial_results': status == 'PROCESSING',
            'player_id': player_id,
            'match_count': profile.get('match_count', 0),
            'overall_performance': {
                'percentile': round(overall_percentile, 1),
                'interpretation': get_percentile_interpretation(overall_percentile),
                'based_on_metrics': key_metrics
            },
            'percentiles': percentiles,
            'strengths': top_strengths,
            'weaknesses': top_weaknesses,
            'ranked_stats': {
                'top_5': [
                    {'stat': k, 'percentile': v['percentile'], 'value': v['value']}
                    for k, v in sorted(percentiles.items(), 
                                      key=lambda x: x[1]['percentile'], 
                                      reverse=True)[:5]
                ],
                'bottom_5': [
                    {'stat': k, 'percentile': v['percentile'], 'value': v['value']}
                    for k, v in sorted(percentiles.items(), 
                                      key=lambda x: x[1]['percentile'])[:5]
                ]
            },
            'comparison_base': {
                'total_games_analyzed': '150,000+',
                'data_source': 'global_avg.json'
            }
        })
        
    except Exception as e:
        print(f"Error in get_player_percentiles: {str(e)}")
        import traceback
        traceback.print_exc()
        return cors_response(500, {'error': str(e)})

# ============================================================================
# PLAYER PROCESSING (Onboarding)
# ============================================================================

def validate_and_decode_body(event: dict) -> tuple[str, str]:
    """
    Safely decode request body and validate UTF-8 encoding
    Returns (decoded_body_str, error_message or None)
    """
    raw_body = event.get('body', '{}')
    headers = event.get('headers', {})
    
    # Log headers for debugging
    content_type = headers.get('content-type', 'application/json')
    print(f"Content-Type: {content_type}")
    print(f"Raw body type: {type(raw_body)}")
    print(f"Body length: {len(raw_body) if isinstance(raw_body, (str, bytes)) else 'unknown'}")
    
    try:
        # Handle Base64 encoding
        if event.get('isBase64Encoded'):
            import base64
            try:
                decoded_bytes = base64.b64decode(raw_body)
                body_str = decoded_bytes.decode('utf-8', errors='strict')
                print("✓ Successfully decoded Base64 to UTF-8")
            except UnicodeDecodeError as e:
                print(f"✗ UTF-8 decode failed after Base64: {e}")
                return None, f"Invalid UTF-8 in Base64 payload: {str(e)}"
        elif isinstance(raw_body, bytes):
            try:
                body_str = raw_body.decode('utf-8', errors='strict')
                print("✓ Successfully decoded bytes to UTF-8")
            except UnicodeDecodeError as e:
                print(f"✗ UTF-8 decode failed: {e}")
                return None, f"Invalid UTF-8 in payload: {str(e)}"
        else:
            body_str = str(raw_body)
            print("✓ Body is already string")
        
        # Validate JSON structure
        try:
            json.loads(body_str)
            print("✓ Valid JSON structure")
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON: {e}")
            return None, f"Invalid JSON: {str(e)}"
        
        return body_str, None
        
    except Exception as e:
        print(f"✗ Unexpected error during decode: {e}")
        return None, str(e)


def process_new_player(event, context):
    """
    Dispatcher: Validates input, creates DB placeholder, invokes Worker asynchronously.
    Returns 202 ACCEPTED immediately.
    """
    # 1. Validation
    body_str, decode_error = validate_and_decode_body(event)
    if decode_error: return cors_response(400, {'error': decode_error})
    body = json.loads(body_str)
    
    game_name = body.get('game_name', '').strip()
    tagline = body.get('tagline', '').strip()
    num_games = min(int(body.get('num_games', 10)), 100)
    player_id = f"{game_name}#{tagline}"

    # 2. Fetch PUUID/MatchIDs immediately
    puuid, match_ids = fetch_riot_data(game_name, tagline, num_games)
    if not puuid or not match_ids:
        return cors_response(404, {'error': 'Player not found'})

    # 3. Save "PROCESSING" Placeholder to DynamoDB
    timestamp = int(datetime.utcnow().timestamp())
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    initial_profile = {
        'player_id': player_id,
        'puuid': puuid,
        'game_name': game_name,
        'tagline': tagline,
        'match_ids': match_ids,
        'processing_status': 'PROCESSING', # Flag for the frontend
        'matches_processed_count': 0,      # Progress bar metric
        'total_matches_to_process': len(match_ids),
        'stats': {}, # Empty stats initially
        'processed_at': timestamp,
        'ttl': ttl
    }
    player_profiles_table.put_item(Item=convert_floats(initial_profile))

    # 4. Invoke the Worker (Asynchronously)
    payload = json.dumps({
        'async_worker': True,
        'game_name': game_name,
        'tagline': tagline,
        'puuid': puuid,
        'match_ids': match_ids
    })

    lambda_client = boto3.client('lambda')
    lambda_client.invoke(
        FunctionName=context.function_name, # Invokes itself
        InvocationType='Event',             # 'Event' = Async (Fire and Forget)
        Payload=payload
    )

    print(f"Async worker started for {player_id}")

    # 5. Return Success Immediately
    return cors_response(202, {
        'success': True,
        'status': 'PROCESSING_STARTED',
        'message': 'Analysis started. Results will populate incrementally.',
        'player_id': player_id,
        'matches_found': len(match_ids)
    })

# ============================================================================
# SOCIAL COMPARSION
# ============================================================================

def compare_player(event):
    """
    POST /player/compare
    """
    try:
        body_str = event.get('body', '{}')
        
        # Handle Base64 encoding
        if event.get('isBase64Encoded', False):
            import base64
            body_str = base64.b64decode(body_str).decode('utf-8')
        elif isinstance(body_str, bytes):
            body_str = body_str.decode('utf-8')
        
        body = json.loads(body_str)
        game_name = body.get('game_name', '').strip()
        tagline = body.get('tagline', '').strip()
        num_games = min(int(body.get('num_games', 10)), 50)
        
        if not game_name or not tagline:
            return cors_response(400, {'error': 'game_name and tagline required'})
        
        print(f"Processing: {game_name}#{tagline} ({num_games} games)")
        
        # Step 1: Fetch Riot data
        puuid, match_ids = fetch_riot_data(game_name, tagline, num_games)
        if not puuid or not match_ids:
            return cors_response(404, {'error': 'Player not found or no ranked matches'})
        
        print(f"Found {len(match_ids)} ranked matches")
        
        # Step 2: Download matches to S3
        download_count = download_matches(game_name, tagline, match_ids)
        print(f"Downloaded {download_count} matches to S3")
        
        # Step 3: Extract features and classify playstyle
        matches_df = load_player_matches_from_s3(game_name, tagline, puuid)
        if matches_df.empty:
            return cors_response(500, {'error': 'Failed to load match data from S3'})
            
        player_stats = create_player_aggregate(matches_df)
        most_played = get_most_played_champions(matches_df, top_n=3)
        
        # Classify playstyle
        playstyle_result = classify_playstyle(player_stats)
        
        print(f"Playstyle: {playstyle_result.get('archetype', 'Unknown')}")
        
        # Step 4: Save INITIAL profile to DynamoDB 
        save_player_profile(
            game_name, tagline, puuid, match_ids, 
            playstyle_result, player_stats, most_played, []  # Pass empty list for timeline
        )

        # Step 5: Return 202 Accepted (or 200 OK) to signal the job was started
        return cors_response(200, {
            'success': True,
            'player_id': f"{game_name}#{tagline}",
            'puuid': puuid,
            'match_ids': match_ids,
            'matches_processed': len(match_ids),
            'playstyle': playstyle_result,
            'stats': player_stats,
            'most_played_champions': most_played,
        })
        
    except Exception as e:
        print(f"Error in process_new_player: {str(e)}")
        import traceback
        traceback.print_exc()
        return cors_response(500, {'error': str(e)})


def fetch_riot_data(game_name: str, tagline: str, num_games: int):
    """Fetch PUUID and match IDs from Riot API"""
    headers = {'X-Riot-Token': RIOT_API_KEY}
    
    # Get PUUID
    account_url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tagline}"
    try:
        resp = requests.get(account_url, headers=headers, timeout=10)
        resp.raise_for_status()
        puuid = resp.json()['puuid']
    except Exception as e:
        print(f"Error fetching PUUID: {e}")
        return None, None
    
    # Get match IDs (ranked only, past year)
    one_year_ago = int((datetime.utcnow() - timedelta(days=365)).timestamp())
    matches_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {'start': 0, 'count': num_games, 'type': 'ranked', 'startTime': one_year_ago}
    
    try:
        resp = requests.get(matches_url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        match_ids = resp.json()
        return puuid, match_ids
    except Exception as e:
        print(f"Error fetching matches: {e}")
        return puuid, []


def download_matches(game_name: str, tagline: str, match_ids: list) -> int:
    """Download match and timeline JSONs to S3"""
    headers = {'X-Riot-Token': RIOT_API_KEY}
    player_folder = f"{game_name}_{tagline}"
    download_count = 0
    
    for match_id in match_ids:
        try:
            # Check if already exists
            match_key = f"raw-matches/{player_folder}/{match_id}/match-data.json"
            try:
                s3_client.head_object(Bucket=S3_BUCKET_RAW, Key=match_key)
                print(f"Match {match_id} already exists, skipping")
                download_count += 1
                continue
            except:
                pass
            
            # Download match data
            match_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
            match_resp = requests.get(match_url, headers=headers, timeout=15)
            match_resp.raise_for_status()
            match_data = match_resp.json()
            
            # Download timeline
            timeline_url = f"{match_url}/timeline"
            timeline_resp = requests.get(timeline_url, headers=headers, timeout=15)
            timeline_resp.raise_for_status()
            timeline_data = timeline_resp.json()
            
            # Save to S3
            timeline_key = f"raw-matches/{player_folder}/{match_id}/timeline-data.json"
            s3_client.put_object(Bucket=S3_BUCKET_RAW, Key=match_key, Body=json.dumps(match_data))
            s3_client.put_object(Bucket=S3_BUCKET_RAW, Key=timeline_key, Body=json.dumps(timeline_data))
            
            download_count += 1
            time.sleep(1.2)  # Rate limiting
            
        except Exception as e:
            print(f"Error downloading {match_id}: {e}")
            continue
    
    return download_count


def load_player_matches_from_s3(game_name: str, tagline: str, puuid: str) -> pd.DataFrame:
    """Load player's matches from S3 and extract features"""
    prefix = f"raw-matches/{game_name}_{tagline}"
    matches_df = pd.DataFrame()
    
    paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=S3_BUCKET_RAW, Prefix=prefix)
    
    found_files = False
    for page in page_iterator:
        for obj in page.get('Contents', []):
            found_files = True
            key = obj['Key']
            if not key.endswith('match-data.json'):
                continue
            
            file_obj = s3_client.get_object(Bucket=S3_BUCKET_RAW, Key=key)
            match_data = json.loads(file_obj['Body'].read())
            
            match_df = extract_player_features(match_data, puuid)
            if match_df is not None:
                matches_df = pd.concat([matches_df, match_df], ignore_index=True)
    
    if not found_files:
        print(f"No files found in S3 at prefix: {prefix}")
        
    return matches_df


def extract_player_features(match_data: dict, puuid: str) -> pd.DataFrame:
    """Extract features for a single match"""
    try:
        df_match = pd.json_normalize(match_data)
        participants = df_match.loc[0, "info.participants"]
        
        player_data = next((p for p in participants if p.get("puuid") == puuid), None)
        if not player_data:
            return None
        
        df_participant = pd.json_normalize(player_data).add_prefix("participant.")
        df_participant["metadata.matchId"] = df_match.loc[0, "metadata.matchId"]
        df_participant["info.gameDuration"] = df_match.loc[0, "info.gameDuration"]
        
        # Define required columns with defaults for missing fields
        cols = {
            "metadata.matchId": "match_id",
            "info.gameDuration": "game_duration",
            "participant.puuid": "puuid",
            "participant.championName": "champion",
            "participant.teamPosition": "position",
            "participant.kills": "kills",
            "participant.deaths": "deaths",
            "participant.assists": "assists",
            "participant.totalMinionsKilled": "cs",
            "participant.neutralMinionsKilled": "jungle_cs",
            "participant.goldEarned": "gold_earned",
            "participant.totalDamageDealtToChampions": "damage_to_champions",
            "participant.visionScore": "vision_score",
            "participant.damageDealtToTurrets": "damage_to_turrets",
            "participant.dragonKills": "dragon_kills",
            "participant.baronKills": "baron_kills",
            "participant.challenges.killParticipation": "kill_participation",
            "participant.challenges.soloKills": "solo_kills",
            "participant.challenges.damagePerMinute": "dpm",
            "participant.challenges.goldPerMinute": "gpm",
            "participant.challenges.earlyLaningPhaseGoldExpAdvantage": "early_gold_advantage",
            "participant.challenges.teamDamagePercentage": "team_damage_pct",
            "participant.damageDealtToObjectives": "objective_damage",
            "participant.challenges.riftHeraldTakedowns": "herald_takedowns",
            "participant.challenges.dragonTakedowns": "dragon_takedowns",
            "participant.timeCCingOthers": "cc_time",
            "participant.totalTimeSpentDead": "time_dead",
            "participant.longestTimeSpentLiving": "longest_time_alive",
            "participant.totalHealsOnTeammates": "heals_on_teammates",
            "participant.totalDamageShieldedOnTeammates": "shields_on_teammates",
            "participant.challenges.outnumberedKills": "outnumbered_kills",
            "participant.challenges.killsNearEnemyTurret": "kills_near_enemy_tower",
            "participant.challenges.pickKillWithAlly": "pick_kills_with_ally",
            "participant.win": "win",
        }
        
        # Only select columns that exist, fill missing with 0
        available_cols = {k: v for k, v in cols.items() if k in df_participant.columns}
        df_flat = df_participant[list(available_cols.keys())].rename(columns=available_cols)
        
        # Add missing columns with default values
        for old_col, new_col in cols.items():
            if new_col not in df_flat.columns:
                df_flat[new_col] = 0
        
        # Calculate derived fields
        df_flat["kda"] = (df_flat["kills"] + df_flat["assists"]) / df_flat["deaths"].replace(0, 1)
        df_flat["game_duration_minutes"] = df_flat["game_duration"] / 60
        df_flat["cs_per_min"] = df_flat["cs"] / df_flat["game_duration_minutes"].replace(0, 1)
        
        return df_flat
        
    except Exception as e:
        print(f"Error extracting features: {e}")
        return None


def create_player_aggregate(df: pd.DataFrame) -> dict:
    """Create aggregated statistics from match data"""
    df = df.drop_duplicates(subset=["match_id", "puuid"])
    
    def safe_mean(col):
        return df[col].mean() if col in df.columns else 0.0
    
    features = {
        "avg_dpm": safe_mean("dpm"),
        "avg_gpm": safe_mean("gpm"),
        "avg_kill_participation": safe_mean("kill_participation"),
        "avg_kda": safe_mean("kda"),
        "avg_vision_score": safe_mean("vision_score"),
        "avg_cs_per_min": safe_mean("cs_per_min"),
        "avg_team_damage_pct": safe_mean("team_damage_pct"),
        "avg_outnumbered_kills": safe_mean("outnumbered_kills"),
        "avg_solo_kills": safe_mean("solo_kills"),
        "avg_kills_near_tower": safe_mean("kills_near_enemy_tower"),
        "avg_shields_on_teammates": safe_mean("shields_on_teammates"),
        "avg_objective_damage": safe_mean("objective_damage"),
        "avg_dragon_takedowns": safe_mean("dragon_takedowns"),
        "avg_herald_takedowns": safe_mean("herald_takedowns"),
        "avg_early_gold_adv": safe_mean("early_gold_advantage"),
        "avg_heals_on_teammates": safe_mean("heals_on_teammates"),
        "avg_longest_alive": safe_mean("longest_time_alive"),
        "avg_cc_time": safe_mean("cc_time"),
        "avg_time_dead": safe_mean("time_dead"),
        "avg_pick_kills": safe_mean("pick_kills_with_ally"),
        "avg_deaths": safe_mean("deaths"),
        "death_consistency": df["deaths"].std(ddof=0) if len(df) > 1 else 0.0,
        "cs_consistency": df["cs_per_min"].std(ddof=0) if len(df) > 1 else 0.0,
        "win_rate": (df["win"].sum() / len(df) * 100) if len(df) > 0 else 0.0,
    }
    
    # Regional composite scores for classifier
    features["bandle"] = (features["avg_outnumbered_kills"] * 0.4 + features["avg_kda"] * 0.3 + (features["avg_vision_score"] / 40.0) * 0.3)
    features["bilgewater"] = ((features["avg_gpm"] / 400) * 0.4 + features["avg_solo_kills"] * 0.3 + features["avg_kills_near_tower"] * 0.3)
    features["demacia"] = (features["avg_kill_participation"] * 0.4 + features["avg_team_damage_pct"] * 0.3 + (features["avg_shields_on_teammates"] / 500) * 0.3)
    features["ionia"] = ((features["avg_kda"] / 4) * 0.3 + ((features["avg_kill_participation"] * features["avg_cs_per_min"]) / 7) * 0.4 + (features["avg_vision_score"] / 40) * 0.3)
    features["ixtal"] = ((features["avg_objective_damage"] / 10000) * 0.4 + features["avg_dragon_takedowns"] * 0.3 + features["avg_herald_takedowns"] * 0.3)
    features["noxus"] = ((features["avg_dpm"] / 600) * 0.4 + (features["avg_early_gold_adv"] / 500) * 0.3)
    features["piltover"] = ((features["avg_gpm"] / 400) * 0.4 + (features["avg_cs_per_min"] / 7) * 0.3 + features["cs_consistency"] * 0.3)
    features["shadow_isles"] = ((features["avg_heals_on_teammates"] / 1000) * 0.4 + (features["avg_longest_alive"] / 600) * 0.3 + features["avg_kda"] * 0.3)
    features["shurima"] = ((features["avg_cs_per_min"] / 7) * 0.5 + features["avg_gpm"] * 0.5)
    features["targon"] = ((features["avg_vision_score"] / 40) * 0.4 + (features["avg_shields_on_teammates"] / 500) * 0.3 + (features["avg_heals_on_teammates"] / 1000) * 0.3)
    features["freljord"] = ((features["avg_cc_time"] / 20) * 0.4 + (features["avg_time_dead"] / 60) * -0.3 + (1 / (features["death_consistency"] + 0.1)) * 0.3)
    features["void"] = ((features["avg_dpm"] / 600) * 0.4 + features["avg_team_damage_pct"] * 0.4 + features["avg_solo_kills"] * 0.2)
    features["zaun"] = ((1 / (features["death_consistency"] + 0.1)) * -0.3 + features["avg_outnumbered_kills"] * 0.4 + features["avg_pick_kills"] * 0.3)
    
    return features


def get_most_played_champions(df: pd.DataFrame, top_n: int = 3) -> dict:
    """Get most played champions"""
    if "champion" not in df.columns:
        return {}
    return df["champion"].value_counts().head(top_n).to_dict()


def classify_playstyle(player_stats: dict) -> dict:
    """Call SageMaker endpoint for playstyle classification"""
    try:
        features_vector = [
            player_stats["bandle"], player_stats["bilgewater"], player_stats["demacia"],
            player_stats["ionia"], player_stats["ixtal"], player_stats["noxus"],
            player_stats["piltover"], player_stats["shadow_isles"], player_stats["shurima"],
            player_stats["targon"], player_stats["freljord"], player_stats["void"], player_stats["zaun"],
            player_stats["avg_dpm"], player_stats["avg_gpm"],
            player_stats["avg_kill_participation"], player_stats["avg_kda"],
            player_stats["avg_vision_score"], player_stats["avg_cs_per_min"],
            player_stats["avg_team_damage_pct"]
        ]
        
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType='application/json',
            Body=json.dumps({'features': features_vector})
        )
        
        return json.loads(response['Body'].read())
        
    except Exception as e:
        print(f"Playstyle classification error: {e}")
        return {'archetype': 'Unknown', 'error': str(e)}


def index_player_to_opensearch(matches_df: pd.DataFrame, puuid: str, 
                               game_name: str, tagline: str) -> int:
    """
    Index player's matches to OpenSearch for RAG
    """
    try:
        actions = []
        
        for _, row in matches_df.iterrows():
            # Create match summary text for embedding
            win_status = "won" if row['win'] else "lost"
            match_summary = f"{row['champion']} {row['position']}, {win_status} with {row['kills']}/{row['deaths']}/{row['assists']} KDA, {row['cs_per_min']:.1f} CS/min, {row['vision_score']} vision score"
            
            # Generate embedding for this match
            match_embedding = generate_embedding(match_summary)
            
            doc = {
                "match_id": row['match_id'],
                "player_puuid": puuid,
                "player_name": f"{game_name}#{tagline}",
                "champion": row['champion'],
                "position": row['position'],
                "win": bool(row['win']),
                "kills": int(row['kills']),
                "deaths": int(row['deaths']),
                "assists": int(row['assists']),
                "kda": float(row['kda']),
                "cs_per_min": float(row['cs_per_min']),
                "vision_score": int(row['vision_score']),
                "dpm": float(row.get('dpm', 0)),
                "gpm": float(row.get('gpm', 0)),
                "kill_participation": float(row.get('kill_participation', 0)),
                "game_duration": int(row['game_duration']),
                "match_summary": match_summary,
                "indexed_at": int(datetime.utcnow().timestamp())
            }
            
            # Add embedding if generation succeeded
            if match_embedding and len(match_embedding) == EMBEDDING_DIMENSION:
                doc["embedding"] = match_embedding
            
            action = {
                "_index": INDEX_NAME,
                "_id": f"{row['match_id']}_{puuid}",
                "_source": doc
            }
            actions.append(action)
        
        from opensearchpy import helpers
        success, failed = helpers.bulk(
            opensearch_client,
            actions,
            chunk_size=50,
            raise_on_error=False
        )
        
        print(f"Indexed {success} player matches to OpenSearch")
        return success
        
    except Exception as e:
        print(f"OpenSearch indexing error: {e}")
        return 0


def trigger_timeline_processing(game_name: str, tagline: str, puuid: str, match_ids: list) -> str:
    """
    Trigger Step Functions for timeline event extraction
    """
    timestamp = int(datetime.utcnow().timestamp())
    
    # Sanitize the execution name
    execution_name = f"timeline_{puuid[:16].replace('-', '')}_{timestamp}"
    
    # This is the S3 prefix where the files are stored
    s3_player_prefix = f"raw-matches/{game_name}_{tagline}"

    response = stepfunctions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=execution_name,
        input=json.dumps({
            'match_ids': match_ids,
            'puuid': puuid, 
            'game_name': game_name,    
            'tagline': tagline,    
            's3_player_prefix': s3_player_prefix, 
            'batch_mode': True
        })
    )
    
    print(f"Started Step Functions execution: {execution_name}")
    print(f"Processing player: {game_name}#{tagline} (PUUID: {puuid})")
    return response['executionArn']


def wait_for_completion(execution_arn: str, timeout: int = 300) -> bool:
    """Wait for Step Functions to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = stepfunctions.describe_execution(executionArn=execution_arn)
        status = response['status']
        
        if status == 'SUCCEEDED':
            return True
        elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
            print(f"Timeline processing failed: {status}")
            return False
        
        time.sleep(5)
    
    return False

def convert_floats(obj):
    """Recursively convert floats to Decimal for DynamoDB"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return Decimal('0')
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats(v) for v in obj]
    return obj

def save_player_profile(game_name: str, tagline: str, puuid: str, match_ids: list,
                        playstyle: dict, stats: dict, most_played: dict, timeline_data: list):
    """Save player profile to DynamoDB"""
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    try:
        # Convert all floats/NaNs to Decimal
        playstyle = convert_floats(playstyle)
        stats = convert_floats(stats)

        player_profiles_table.put_item(Item={
            'player_id': f"{game_name}#{tagline}",
            'puuid': puuid,
            'game_name': game_name,
            'tagline': tagline,
            'playstyle': playstyle,
            'stats': stats,
            'most_played_champions': most_played,
            'match_ids': match_ids,
            'processed_at': int(datetime.utcnow().timestamp()),
            'ttl': ttl,
            'match_count': len(match_ids),
            'timeline_summary': {
                'total_matches': len(timeline_data),
                'total_events': sum(len(m.get('events', [])) for m in timeline_data)
            }
        })
        print("Saved player profile to DynamoDB")
    except Exception as e:
        print(f"Error saving profile: {e}")
        import traceback
        traceback.print_exc()
        raise


# ============================================================================
# GET PLAYER PROFILE
# ============================================================================

def get_player_profile(event):
    """GET /player/profile?game_name=XXX&tagline=YYY"""
    params = event.get('queryStringParameters', {})
    game_name = params.get('game_name')
    tagline = params.get('tagline')
    
    if not game_name or not tagline:
        return cors_response(400, {'error': 'game_name and tagline required'})
    
    player_id = f"{game_name}#{tagline}"
    response = player_profiles_table.get_item(Key={'player_id': player_id})
    
    if 'Item' not in response:
        return cors_response(404, {'error': 'Player not found. Process this player first.'})
    
    profile = response['Item']
    puuid = profile.get('puuid')
    match_ids = profile.get('match_ids', [])
    
    # Get top timeline events for each match
    timeline_data = []
    for match_id in match_ids:
        events = get_top_events_for_match(puuid, match_id, limit=15)
        if events:
            timeline_data.append({
                'match_id': match_id,
                'events': events,
                'total_events': len(events)
            })
    
    # Check if timeline processing is still running
    is_processing = (len(timeline_data) == 0 and len(match_ids) > 0 and 
                     (int(datetime.utcnow().timestamp()) - int(profile.get('processed_at', 0))) < 600) # 10 min window

    return cors_response(200, {
        'player_id': player_id,
        'puuid': puuid,
        'game_name': game_name,
        'tagline': tagline,
        'playstyle': profile.get('playstyle', {}),
        'stats': profile.get('stats', {}),
        'most_played_champions': profile.get('most_played_champions', {}),
        'timeline_data': timeline_data,
        'match_count': profile.get('match_count', 0),
        'processed_at': int(profile.get('processed_at', 0)),
        'processing_status': 'PROCESSING' if is_processing else 'COMPLETED'
    })


# ============================================================================
# TIMELINE EVENT FUNCTIONS
# ============================================================================

def get_top_events_for_match(puuid: str, match_id: str, limit: int = 15) -> list:
    """Retrieve top impact events for a specific match"""
    try:
        response = events_table.query(
            IndexName='match-impact-index',
            KeyConditionExpression=Key('match_id').eq(match_id),
            FilterExpression=Attr('puuid').eq(puuid),
            ScanIndexForward=False # Sort by impact_score DESC
        )
        
        events = response.get('Items', [])
        
        if not events:
            return []
        
        sorted_events = sorted(events, key=lambda x: int(x.get('impact_score', 0)), reverse=True)
        
        seen_fingerprints = set()
        unique_events = []
        
        for event_item in sorted_events:
            event_details = json.loads(event_item.get('event_details', '{}'))
            
            fingerprint = (
                float(event_item.get('timestamp_minutes', 0)),
                event_item.get('event_type'),
                event_details.get('objective_type'),
                event_details.get('structure_type'),
                event_details.get('lane')
            )
            
            if fingerprint not in seen_fingerprints:
                seen_fingerprints.add(fingerprint)
                
                # Try to get summary
                event_obj = {
                    'event_id': event_item['event_id'],
                    'timestamp_minutes': float(event_item['timestamp_minutes']),
                    'event_type': event_item['event_type'],
                    'impact_score': int(event_item['impact_score']),
                    'game_state': event_item.get('game_state', 'mid'),
                    'event_details': event_details,
                    'context': json.loads(event_item.get('context', '{}')),
                    'has_summary': False,
                    'summary': None
                }
                
                # Check for summary
                for summary_type in ['enhanced_v2', 'enhanced', 'basic']:
                    try:
                        summary_resp = summaries_table.get_item(
                            Key={'event_id': event_item['event_id'], 'summary_type': summary_type}
                        )
                        if 'Item' in summary_resp:
                            event_obj['has_summary'] = True
                            event_obj['summary'] = summary_resp['Item'].get('summary_text')
                            event_obj['summary_version'] = summary_type
                            break
                    except:
                        continue
                
                unique_events.append(event_obj)
                
                if len(unique_events) >= limit:
                    break
        
        return unique_events
        
    except Exception as e:
        print(f"Error retrieving events for {match_id}: {e}")
        return []


def get_timeline_events(event):
    """GET /timeline/events?match_id=XXX&puuid=YYY"""
    params = event.get('queryStringParameters', {})
    match_id = params.get('match_id')
    puuid = params.get('puuid')
    
    if not match_id or not puuid:
        return cors_response(400, {'error': 'match_id and puuid required'})
    
    events = get_top_events_for_match(puuid, match_id, limit=50)
    
    return cors_response(200, {
        'match_id': match_id,
        'puuid': puuid,
        'events': events,
        'total_events': len(events)
    })


def get_event_summary(event):
    """POST /timeline/events/summary - Get cached summary for an event"""
    body = json.loads(event.get('body', '{}'))
    event_id = body.get('event_id')
    
    if not event_id:
        return cors_response(400, {'error': 'event_id required'})
    
    for summary_type in ['enhanced_v2', 'enhanced', 'basic']:
        cache_response = summaries_table.get_item(
            Key={'event_id': event_id, 'summary_type': summary_type}
        )
        
        if 'Item' in cache_response:
            return cors_response(200, {
                'event_id': event_id,
                'summary': cache_response['Item']['summary_text'],
                'cached': True,
                'summary_version': summary_type
            })
    
    return cors_response(404, {
        'event_id': event_id,
        'error': 'Summary not yet generated'
    })


def answer_event_question(event): # UNUSED
    """
    POST /timeline/ask
    Ask specific question about a timeline event
    Input: { event_id, match_id, puuid, question, match_context }
    """
    body = json.loads(event.get('body', '{}'))
    event_id = body.get('event_id')
    match_id = body.get('match_id')
    puuid = body.get('puuid')
    question = body.get('question')
    match_context = body.get('match_context', {})
    
    if not all([event_id, match_id, puuid, question]):
        return cors_response(400, {'error': 'event_id, match_id, puuid, and question required'})
    
    # Rate limiting: 5 questions per event
    question_count_response = questions_table.query(
        IndexName='event-questions-index',
        KeyConditionExpression=Key('event_id').eq(event_id),
        FilterExpression=Attr('puuid').eq(puuid)
    )
    
    question_count = len(question_count_response.get('Items', []))
    if question_count >= 5:
        return cors_response(429, {
            'error': 'Maximum 5 questions per event reached',
            'limit': 5,
            'used': question_count
        })
    
    # Get event data
    event_response = events_table.get_item(
        Key={'match_id': match_id, 'event_id': event_id}
    )
    
    if 'Item' not in event_response:
        return cors_response(404, {'error': 'Event not found'})
    
    event_data = event_response['Item']
    
    # Build prompt and call Bedrock
    prompt = build_event_qa_prompt(event_data, question, match_context)
    answer = invoke_bedrock_nova(prompt, max_tokens=200, temperature=0.4)
    
    # Save question
    question_id = f"{event_id}_{int(datetime.utcnow().timestamp())}"
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    questions_table.put_item(Item={
        'question_id': question_id,
        'event_id': event_id,
        'match_id': match_id,
        'puuid': puuid,
        'question': question,
        'answer': answer,
        'question_type': 'event_specific',
        'asked_at': int(datetime.utcnow().timestamp()),
        'ttl': ttl
    })
    
    return cors_response(200, {
        'event_id': event_id,
        'question': question,
        'answer': answer,
        'question_count': question_count + 1,
        'remaining_questions': 4 - question_count
    })


def build_event_qa_prompt(event_data: dict, question: str, match_context: dict) -> str:
    """Build prompt for event-specific question"""
    event_details = json.loads(event_data.get('event_details', '{}'))
    context = json.loads(event_data.get('context', '{}'))
    
    prompt = f"""MATCH SITUATION at {float(event_data.get('timestamp_minutes', 0)):.1f} minutes:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVENT: {event_data.get('event_type', 'Unknown')}
PLAYER POSITION: {context.get('player_location', {}).get('lane', 'Unknown')}
DISTANCE: {context.get('player_location', {}).get('distance_to_event', 0)} units
TELEPORT: {'Available' if context.get('summoner_spells', {}).get('tp_available', False) else 'On CD'}
GOLD STATE: {context.get('gold_state', 'unknown')}

QUESTION: "{question}"

Provide macro-focused coaching. Maximum 150 words."""
    
    return prompt


# ============================================================================
# RAG-BASED PERFORMANCE Q&A
# ============================================================================

def answer_performance_question(event):
    """
    POST /player/ask
    Macro-focused RAG performance answer
    """
    try:
        body_str = event.get('body', '{}')
        if isinstance(body_str, bytes):
            body_str = body_str.decode('utf-8')

        body = json.loads(body_str)
        game_name = body.get('game_name', '').strip()
        tagline = body.get('tagline', '').strip()
        question = body.get('question', '').strip()

        if not all([game_name, tagline, question]):
            return cors_response(400, {'error': 'game_name, tagline, and question required'})

        player_id = f"{game_name}#{tagline}"

        profile_response = player_profiles_table.get_item(Key={'player_id': player_id})
        if 'Item' not in profile_response:
            return cors_response(404, {
                'error': 'Player not found',
                'message': 'Process this player first via /player/process'
            })

        profile = profile_response['Item']
        puuid = profile['puuid']
        player_stats = profile.get('stats', {})
        most_played = profile.get('most_played_champions', {})

        one_hour_ago = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
        recent_questions = questions_table.query(
            KeyConditionExpression=Key('puuid').eq(puuid) & Key('asked_at').gt(one_hour_ago)
        )
        if len(recent_questions.get('Items', [])) >= 30:
            return cors_response(429, {'error': 'Rate limit exceeded (30 questions/hour)', 'reset_in_seconds': 3600})

        print(f"Answering macro performance question for {player_id}: {question}")

        player_opensearch_stats = get_player_stats_from_opensearch(puuid)

        query_embedding = generate_embedding(question)
        if query_embedding and len(query_embedding) == EMBEDDING_DIMENSION:
            similar_scenarios = search_similar_scenarios_knn(query_embedding, question, player_stats, limit=10)
            search_method = 'vector_knn'
        else:
            similar_scenarios = search_similar_scenarios_text(question, player_stats, limit=10)
            search_method = 'text'

        rag_prompt = build_rag_prompt(
            question,
            player_stats,
            player_opensearch_stats,
            most_played,
            similar_scenarios
        )

        answer = invoke_bedrock_nova(rag_prompt, max_tokens=520, temperature=0.6)

        question_id = f"perf_{int(datetime.utcnow().timestamp())}"
        ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())

        questions_table.put_item(Item={
            'puuid': puuid,
            'question_id': question_id,
            'asked_at': int(datetime.utcnow().timestamp()),
            'question': question,
            'answer': answer,
            'question_type': 'performance_rag_macro',
            'similar_scenarios_count': len(similar_scenarios),
            'search_method': search_method,
            'ttl': ttl
        })

        return cors_response(200, {
            'player_id': player_id,
            'question': question,
            'answer': answer,
            'context_used': {
                'player_matches': profile.get('match_count', 0),
                'database_matches': len(similar_scenarios),
                'search_method': search_method,
                'macro_indicators': compute_macro_indicators(player_stats, player_opensearch_stats)
            }
        })

    except Exception as e:
        print(f"Error in answer_performance_question: {str(e)}")
        import traceback
        traceback.print_exc()
        return cors_response(500, {'error': str(e)})


def get_player_stats_from_opensearch(puuid: str) -> dict:
    """Get aggregated statistics for player from OpenSearch"""
    query = {
        "query": {"term": {"player_puuid": puuid}},
        "size": 0,
        "aggs": {
            "avg_kda": {"avg": {"field": "kda"}},
            "avg_cs_per_min": {"avg": {"field": "cs_per_min"}},
            "avg_vision_score": {"avg": {"field": "vision_score"}},
            "avg_dpm": {"avg": {"field": "dpm"}},
            "avg_gpm": {"avg": {"field": "gpm"}},
            "avg_kill_participation": {"avg": {"field": "kill_participation"}},
            "avg_deaths": {"avg": {"field": "deaths"}},
            "win_rate": {"terms": {"field": "win", "size": 2}},
            "most_played_champions": {"terms": {"field": "champion", "size": 5}},
            "position_distribution": {"terms": {"field": "position", "size": 5}}
        }
    }
    
    try:
        response = opensearch_client.search(index=INDEX_NAME, body=query)
        aggs = response['aggregations']
        
        # Calculate win rate
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
            "avg_dpm": round(aggs.get('avg_dpm', {}).get('value', 0), 0),
            "avg_gpm": round(aggs.get('avg_gpm', {}).get('value', 0), 0),
            "avg_kill_participation": round(aggs.get('avg_kill_participation', {}).get('value', 0), 2),
            "avg_deaths": round(aggs.get('avg_deaths', {}).get('value', 0), 1),
            "most_played_champions": [
                {"champion": b['key'], "games": b['doc_count']}
                for b in aggs.get('most_played_champions', {}).get('buckets', [])
            ]
        }
    except Exception as e:
        print(f"Error getting player stats from OpenSearch: {e}")
        return {}


def generate_embedding(text: str) -> list:
    """Generate embedding for query text using Bedrock Titan"""
    try:
        if len(text) > 25000:
            text = text[:25000]
        
        request_body = {
            "inputText": text,
            "dimensions": EMBEDDING_DIMENSION,
            "normalize": True
        }
        
        response = bedrock_runtime.invoke_model(
            modelId=EMBEDDINGS_MODEL_ID,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )
        
        # Fix: Read body correctly
        response_body = json.loads(response['body'].read().decode('utf-8'))
        embedding = response_body.get('embedding', [])
        
        if not embedding:
            print(f"Empty embedding returned from Bedrock")
            return None
        
        return embedding
        
    except Exception as e:
        print(f"Embedding generation error: {e}")
        import traceback
        traceback.print_exc()
        return None


def compute_macro_indicators(player_stats: dict, opensearch_stats: dict) -> dict:
    """
    Derive macro indicators from raw stats (heuristic, lightweight).
    Accepts Decimal values from DynamoDB; coerces all numerics to float.
    """
    def f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    # Coerce needed fields
    deaths    = f(player_stats.get('avg_deaths', 0))
    kda       = f(player_stats.get('avg_kda', 0))
    cs        = f(player_stats.get('avg_cs_per_min', 0))
    kp        = f(player_stats.get('avg_kill_participation', 0))
    vision    = f(player_stats.get('avg_vision_score', 0))
    win_rate  = f(player_stats.get('win_rate', 0))
    obj_dmg   = f(player_stats.get('avg_objective_damage', 0))
    drag_tk   = f(player_stats.get('avg_dragon_takedowns', 0))
    herald_tk = f(player_stats.get('avg_herald_takedowns', 0))
    early_adv = f(player_stats.get('avg_early_gold_adv', 0))

    indicators = {}
    indicators['laning_efficiency'] = round(cs / 7 * 0.6 + (kda / 5) * 0.2 + (win_rate / 100) * 0.2, 3)
    indicators['objective_alignment'] = round(
        (obj_dmg / 15000) * 0.4 +
        (drag_tk / 2) * 0.3 +
        (herald_tk / 1.5) * 0.3, 3
    )
    indicators['map_influence'] = round(kp * 0.5 + (vision / 30) * 0.3 + (1 / (deaths + 1)) * 0.2, 3)
    indicators['risk_management'] = round((1 / (deaths + 1)) * 0.5 + (kda / 5) * 0.3 + (vision / 30) * 0.2, 3)
    indicators['tempo_conversion'] = round(
        (early_adv / 400) * 0.4 +
        (win_rate / 100) * 0.3 +
        (kda / 5) * 0.3, 3
    )

    indicators['early_game_flag'] = 'inefficient' if cs < 6.2 else 'stable' if cs < 7.2 else 'strong'
    indicators['death_pressure_flag'] = 'high' if deaths >= 5 else 'moderate' if deaths >= 3.5 else 'controlled'
    indicators['vision_flag'] = 'needs_upgrade' if vision < 15 else 'acceptable' if vision < 22 else 'impactful'

    return indicators


def build_rag_prompt(question: str, player_stats: dict, opensearch_stats: dict, 
                     most_played: dict, similar_scenarios: list) -> str:
    """
    Macro-focused coaching prompt (replaces previous verbose stat-centric prompt).
    """

    indicators = compute_macro_indicators(player_stats, opensearch_stats)

    # Compress stats (only essentials)
    concise_stats = (
        f"KDA {player_stats.get('avg_kda', 0):.2f}, CS/min {player_stats.get('avg_cs_per_min', 0):.2f}, "
        f"Deaths {player_stats.get('avg_deaths', 0):.1f}, KP {player_stats.get('avg_kill_participation', 0):.2f}, "
        f"Vision {player_stats.get('avg_vision_score', 0):.1f}, WinRate {player_stats.get('win_rate', 0):.1f}%"
    )

    # Scenario synthesis (no raw repetition)
    scenario_lines = []
    for s in similar_scenarios[:5]:
        scenario_lines.append(
            f"{s.get('champion')} {s.get('position')} | {'W' if s.get('win') else 'L'} | KDA {s.get('kda', 0):.2f} | "
            f"CSm {s.get('cs_per_min', 0):.2f} | KP {s.get('kill_participation', 0):.1%}"
        )
    scenarios_block = "\n".join(scenario_lines) if scenario_lines else "None"

    prompt = f"""
User Question: {question}

Player Snapshot (do NOT restate every number later): {concise_stats}
Derived Macro Indicators:
- Laning Efficiency: {indicators['laning_efficiency']}
- Objective Alignment: {indicators['objective_alignment']}
- Map Influence: {indicators['map_influence']}
- Risk Management: {indicators['risk_management']}
- Tempo Conversion: {indicators['tempo_conversion']}
Flags: EarlyGame={indicators['early_game_flag']}, DeathPressure={indicators['death_pressure_flag']}, Vision={indicators['vision_flag']}

Most Played (top 3): {', '.join([f'{c}({g})' for c, g in list(most_played.items())[:3]]) or 'N/A'}

Similar Scenario Summaries (aggregated, do NOT copy blindly):
{scenarios_block}

Output Requirements:
1. Do NOT repeat raw stat lists; reference concepts (e.g., "high death volatility") instead.
2. Identify one PRIMARY macro weakness (not mechanical) with reasoning.
3. Provide a MACRO IMPROVEMENT PLAN (phased: early → mid → late).
4. Extract DECISION PATTERNS from scenarios (pressure, over-extension, rotation timing).
5. Give 3 PRACTICAL DRILLS (each: objective, duration, measurable success metric).
6. Provide a ONE-WEEK FOCUS checklist (5 concise bullets).
7. Keep under 380 words. Avoid fluff. No generic motivational lines.
8. If the user question is unrelated (e.g., math), briefly answer then still deliver coaching.

Return ONLY this structured format:
Primary Weakness:
Macro Improvement Plan:
Decision Patterns:
Drills:
One-Week Focus:

Now generate the coaching response.
"""
    return prompt


def invoke_bedrock_nova(prompt: str, max_tokens: int = 520, temperature: float = 0.6) -> str:
    """
    Bedrock invoke for Amazon Nova (no 'system' role allowed).
    Embed coaching instructions into the single user message.
    Removes previous use of an invalid 'system' role.
    """
    coaching_preamble = (
        "ROLE: High-level League of Legends macro coach.\n"
        "STYLE: Concise, analytical; focus on rotations, lane management, vision timing, resource sequencing, "
        "objective trades, risk mitigation. Do NOT repeat raw numeric stat lists; refer to conceptual patterns.\n"
        "AVOID: Fluff, motivational filler, verbatim stat dumps."
    )

    request_body = {
        "messages": [
            {
                "role": "user",
                "content": [{
                    "text": f"{coaching_preamble}\n\nTASK INPUT:\n{prompt}"
                }]
            }
        ],
        "inferenceConfig": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9
        }
    }

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            raw = response['body'].read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                print(f"Bedrock response not JSON: {raw[:400]}")
                return "Model response parsing error."

            # Expected structure: body['output']['message']['content'][0]['text']
            out = (
                body.get('output', {})
                    .get('message', {})
                    .get('content', [])
            )
            if out and isinstance(out, list):
                text_candidate = out[0].get('text')
                if text_candidate:
                    return text_candidate.strip()

            # Fallback: search for any 'text' field
            def find_text(node):
                if isinstance(node, dict):
                    if 'text' in node and isinstance(node['text'], str):
                        return node['text']
                    for v in node.values():
                        found = find_text(v)
                        if found:
                            return found
                elif isinstance(node, list):
                    for v in node:
                        found = find_text(v)
                        if found:
                            return found
                return None

            fallback = find_text(body)
            if fallback:
                return fallback.strip()

            print(f"Unexpected Bedrock output structure: {json.dumps(body)[:500]}")
            return "No answer generated."
        except ClientError as e:
            code = e.response['Error'].get('Code', '')
            print(f"Bedrock ClientError {code}: {e}")
            if code in ('ThrottlingException', 'TooManyRequestsException') and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            return "Bedrock error."
        except Exception as e:
            print(f"Unexpected Bedrock exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            return "Unexpected error."
    return "System busy."


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def cors_response(status_code: int, body: dict) -> dict:
    """CORS-enabled API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def search_similar_scenarios_knn(query_embedding: list, question: str, player_stats: dict, limit: int = 10) -> list:
    """
    Search for similar match scenarios using KNN vector search in OpenSearch
    """
    try:
        # Build KNN query
        knn_query = {
            "size": limit,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": limit
                   
                    }
                }
            },
            "_source": [
                "match_id", "player_name", "champion", "position", "win",
                "kills", "deaths", "assists", "kda", "cs_per_min",
                "vision_score", "dpm", "gpm", "kill_participation",
                "match_summary"
            ]
        }
        
        response = opensearch_client.search(index=INDEX_NAME, body=knn_query)
        
        scenarios = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            scenarios.append({
                'match_id': source.get('match_id'),
                'player_name': source.get('player_name'),
                'champion': source.get('champion'),
                'position': source.get('position'),
                'win': source.get('win'),
                'kda': source.get('kda'),
                'cs_per_min': source.get('cs_per_min'),
                'vision_score': source.get('vision_score'),
                'dpm': source.get('dpm'),
                'gpm': source.get('gpm'),
                'kill_participation': source.get('kill_participation'),
                'summary': source.get('match_summary', ''),
                'relevance_score': hit['_score']
           
            })
        
        print(f"KNN search returned {len(scenarios)} scenarios")
        return scenarios
        
    except Exception as e:
        print(f"KNN search error: {e}")
        import traceback
        traceback.print_exc()
        return []


def search_similar_scenarios_text(question: str, player_stats: dict, limit: int = 10) -> list:
    """
    Fallback text-based search when embedding fails

    """
    try:
        # Extract keywords from question
        keywords = question.lower().split()
        search_terms = [k for k in keywords if len(k) > 3][:5]  # Top 5 meaningful words
        
        # Build multi-match query
        text_query = {
            "size": limit,
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": " ".join(search_terms),
                                "fields": ["match_summary^2", "champion", "position"],
                                "type": "best_fields"
                            }
                        },
                        {
                            "range": {
                                "kda": {
                                    "gte": max(0, player_stats.get('avg_kda', 2) - 1),
                                    "lte": player_stats.get('avg_kda', 2) + 1
                                }
                            }
                        }
                    ]
                }
            },
            "_source": [
                "match_id", "player_name", "champion", "position", "win",
                "kills", "deaths", "assists", "kda", "cs_per_min",
                "vision_score", "dpm", "gpm", "kill_participation",
                "match_summary"
            ]
        }
        
        response = opensearch_client.search(index=INDEX_NAME, body=text_query)
        
        scenarios = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            scenarios.append({
                'match_id': source.get('match_id'),
                'player_name': source.get('player_name'),
                'champion': source.get('champion'),
                'position': source.get('position'),
                'win': source.get('win'),
                'kda': source.get('kda'),
                'cs_per_min': source.get('cs_per_min'),
                'vision_score': source.get('vision_score'),
                'dpm': source.get('dpm'),
                'gpm': source.get('gpm'),
                'kill_participation': source.get('kill_participation'),
                'summary': source.get('match_summary', ''),
                'relevance_score': hit['_score']
            })
        
        print(f"Text search returned {len(scenarios)} scenarios")
        return scenarios
        
    except Exception as e:
        print(f"Text search error: {e}")
        import traceback
        traceback.print_exc()
        return []


def build_rag_prompt(question: str, player_stats: dict, opensearch_stats: dict, 
                     most_played: dict, similar_scenarios: list) -> str:
    """
    Macro-focused coaching prompt (replaces previous verbose stat-centric prompt).
    """

    indicators = compute_macro_indicators(player_stats, opensearch_stats)

    # Compress stats (only essentials)
    concise_stats = (
        f"KDA {player_stats.get('avg_kda', 0):.2f}, CS/min {player_stats.get('avg_cs_per_min', 0):.2f}, "
        f"Deaths {player_stats.get('avg_deaths', 0):.1f}, KP {player_stats.get('avg_kill_participation', 0):.2f}, "
        f"Vision {player_stats.get('avg_vision_score', 0):.1f}, WinRate {player_stats.get('win_rate', 0):.1f}%"
    )

    # Scenario synthesis (no raw repetition)
    scenario_lines = []
    for s in similar_scenarios[:5]:
        scenario_lines.append(
            f"{s.get('champion')} {s.get('position')} | {'W' if s.get('win') else 'L'} | KDA {s.get('kda', 0):.2f} | "
            f"CSm {s.get('cs_per_min', 0):.2f} | KP {s.get('kill_participation', 0):.1%}"
        )
    scenarios_block = "\n".join(scenario_lines) if scenario_lines else "None"

    prompt = f"""
User Question: {question}

Player Snapshot (do NOT restate every number later): {concise_stats}
Derived Macro Indicators:
- Laning Efficiency: {indicators['laning_efficiency']}
- Objective Alignment: {indicators['objective_alignment']}
- Map Influence: {indicators['map_influence']}
- Risk Management: {indicators['risk_management']}
- Tempo Conversion: {indicators['tempo_conversion']}
Flags: EarlyGame={indicators['early_game_flag']}, DeathPressure={indicators['death_pressure_flag']}, Vision={indicators['vision_flag']}

Most Played (top 3): {', '.join([f'{c}({g})' for c, g in list(most_played.items())[:3]]) or 'N/A'}

Similar Scenario Summaries (aggregated, do NOT copy blindly):
{scenarios_block}

Output Requirements:
1. Reference stats SPARINGLY and try to reference concepts (e.g., "high death volatility").
2. Keep under 380 words. Avoid fluff. No generic motivational lines.
3. If the user question is unrelated (e.g., math), briefly answer then still deliver coaching.
4. Focus highly on the user question.
5. Can refer to the player's top champions for advice.

Now generate the coaching response.
"""
    return prompt


def invoke_bedrock_nova(prompt: str, max_tokens: int = 520, temperature: float = 0.6) -> str:
    """
    Bedrock invoke for Amazon Nova (no 'system' role allowed).
    Embed coaching instructions into the single user message.
    Removes previous use of an invalid 'system' role.
    """
    coaching_preamble = (
        "ROLE: High-level League of Legends macro coach.\n"
        "STYLE: Concise, analytical; focus on rotations, lane management, vision timing, resource sequencing, "
        "objective trades, risk mitigation. Refer to conceptual patterns and macro gameplay.\n"
        "AVOID: Fluff, motivational filler, verbatim stat dumps."
    )

    request_body = {
        "messages": [
            {
                "role": "user",
                "content": [{
                    "text": f"{coaching_preamble}\n\nTASK INPUT:\n{prompt}"
                }]
            }
        ],
        "inferenceConfig": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9
        }
    }

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            raw = response['body'].read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                print(f"Bedrock response not JSON: {raw[:400]}")
                return "Model response parsing error."

            # Expected structure: body['output']['message']['content'][0]['text']
            out = (
                body.get('output', {})
                    .get('message', {})
                    .get('content', [])
            )
            if out and isinstance(out, list):
                text_candidate = out[0].get('text')
                if text_candidate:
                    return text_candidate.strip()

            # Fallback: search for any 'text' field
            def find_text(node):
                if isinstance(node, dict):
                    if 'text' in node and isinstance(node['text'], str):
                        return node['text']
                    for v in node.values():
                        found = find_text(v)
                        if found:
                            return found
                elif isinstance(node, list):
                    for v in node:
                        found = find_text(v)
                        if found:
                            return found
                return None

            fallback = find_text(body)
            if fallback:
                return fallback.strip()

            print(f"Unexpected Bedrock output structure: {json.dumps(body)[:500]}")
            return "No answer generated."
        except ClientError as e:
            code = e.response['Error'].get('Code', '')
            print(f"Bedrock ClientError {code}: {e}")
            if code in ('ThrottlingException', 'TooManyRequestsException') and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            return "Bedrock error."
        except Exception as e:
            print(f"Unexpected Bedrock exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            return "Unexpected error."
    return "System busy."
