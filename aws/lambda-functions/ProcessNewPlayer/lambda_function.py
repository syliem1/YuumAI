"""
Lambda function to process new players
Triggered by API Gateway POST request with game_name, tagline, num_games
"""

import boto3
import json
import requests
from datetime import datetime, timedelta
import time
import pandas as pd
from decimal import Decimal

s3_client = boto3.client('s3')
stepfunctions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
sagemaker_runtime = boto3.client('sagemaker-runtime')

# Configuration
RIOT_API_KEY = 'RGAPI-cdb417b3-2ebb-4ed3-8039-084087b1ef19'
STATE_MACHINE_ARN = 'arn:aws:states:us-west-2:768394660366:stateMachine:lol-timeline-batch-processor'
S3_BUCKET_RAW = 'lol-training-matches-150k'
SAGEMAKER_ENDPOINT = 'playstyle-profiler-20251108-073923'
PLAYER_PROFILES_TABLE = 'lol-player-profiles'


def lambda_handler(event, context):
    """
    Main Lambda handler
    Expected input: { game_name, tagline, num_games }
    """
    print("🚀 Process New Player Lambda invoked")
    
    try:
        # Parse input
        if 'body' in event and isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event
        
        game_name = body.get('game_name')
        tagline = body.get('tagline')
        num_games = body.get('num_games', 5)
        
        # Validation
        if not game_name or not tagline:
            return response(400, {
                'error': 'Missing required fields',
                'message': 'game_name and tagline are required'
            })
        
        # Validate num_games
        if not isinstance(num_games, int) or num_games < 1:
            num_games = 5
        if num_games > 100:
            num_games = 100  # Cap at 100 games
        
        print(f"Processing: {game_name}#{tagline} ({num_games} games)")
        
        # Step 1: Fetch Riot data
        puuid, match_ids = fetch_riot_data(game_name, tagline, num_games)
        
        if not puuid or not match_ids:
            return response(404, {
                'error': 'Player not found',
                'message': f'Could not find player {game_name}#{tagline} or no ranked matches available'
            })
        
        actual_games = len(match_ids)
        print(f"✓ Found {actual_games} ranked matches")
        
        # Step 2: Download match data to S3
        download_count = download_matches(game_name, tagline, match_ids)
        print(f"✓ Downloaded {download_count}/{actual_games} matches")
        
        # Step 3: Run playstyle profiler
        profiler_results = run_playstyle_profiler(game_name, tagline)
        print(f"✓ Playstyle: {profiler_results.get('archetype', 'Unknown')}")
        
        # Step 4: Trigger timeline processing (async)
        execution_arn = trigger_timeline_processing(game_name, tagline, puuid, match_ids)
        print(f"✓ Started timeline processing: {execution_arn}")
        
        # Step 5: Wait for timeline completion (with timeout)
        timeline_success = wait_for_completion(execution_arn, timeout=300)  # 5 min timeout
        
        # Step 6: Retrieve timeline results
        timeline_data = []
        if timeline_success:
            timeline_data = get_timeline_results(puuid, match_ids)
            print(f"✓ Retrieved timeline data: {len(timeline_data)} matches")
        
        # Step 7: Save to DynamoDB
        save_to_dynamodb(game_name, tagline, puuid, match_ids, profiler_results, timeline_data)
        
        # Return complete results
        return response(200, {
            'success': True,
            'player_id': f"{game_name}#{tagline}",
            'puuid': puuid,
            'playstyle': profiler_results,
            'matches_processed': actual_games,
            'matches_requested': num_games,
            'timeline_data': timeline_data,
            'timeline_processing_complete': timeline_success,
            'execution_arn': execution_arn
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return response(500, {
            'error': 'Processing failed',
            'message': str(e)
        })


def fetch_riot_data(game_name: str, tagline: str, num_games: int):
    """Fetch PUUID and match IDs from Riot API"""
    
    headers = {'X-Riot-Token': RIOT_API_KEY}
    
    # Get PUUID
    account_url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tagline}"
    
    try:
        resp = requests.get(account_url, headers=headers, timeout=10)
        resp.raise_for_status()
        account_data = resp.json()
        puuid = account_data['puuid']
    except Exception as e:
        print(f"Error fetching PUUID: {e}")
        return None, None
    
    # Get match history (past year only)
    one_year_ago = int((datetime.utcnow() - timedelta(days=365)).timestamp())
    
    matches_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {
        'start': 0,
        'count': num_games,
        'type': 'ranked',
        'startTime': one_year_ago
    }
    
    try:
        resp = requests.get(matches_url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        match_ids = resp.json()
        
        # If we got fewer matches than requested, that's all they have
        if len(match_ids) < num_games:
            print(f"Player has only {len(match_ids)} matches in past year (requested {num_games})")
        
        return puuid, match_ids
    except Exception as e:
        print(f"Error fetching matches: {e}")
        return puuid, []


def download_matches(game_name: str, tagline: str, match_ids: list):
    """Download match and timeline data to S3"""
    
    headers = {'X-Riot-Token': RIOT_API_KEY}
    player_folder = f"{game_name}_{tagline}"
    download_count = 0
    
    for idx, match_id in enumerate(match_ids, 1):
        print(f"[{idx}/{len(match_ids)}] Downloading {match_id}...")
        
        try:
            # Download match data
            match_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
            match_resp = requests.get(match_url, headers=headers, timeout=15)
            match_resp.raise_for_status()
            match_data = match_resp.json()
            
            # Download timeline data
            timeline_url = f"{match_url}/timeline"
            timeline_resp = requests.get(timeline_url, headers=headers, timeout=15)
            timeline_resp.raise_for_status()
            timeline_data = timeline_resp.json()
            
            # Save to S3
            match_key = f"raw-matches/{player_folder}/{match_id}/match-data.json"
            timeline_key = f"raw-matches/{player_folder}/{match_id}/timeline-data.json"
            
            s3_client.put_object(
                Bucket=S3_BUCKET_RAW,
                Key=match_key,
                Body=json.dumps(match_data),
                ContentType='application/json'
            )
            
            s3_client.put_object(
                Bucket=S3_BUCKET_RAW,
                Key=timeline_key,
                Body=json.dumps(timeline_data),
                ContentType='application/json'
            )
            
            download_count += 1
            
            # Rate limiting (1.2s between requests = ~50 requests/min)
            time.sleep(1.2)
            
        except Exception as e:
            print(f"Error downloading {match_id}: {e}")
            continue
    
    return download_count


def run_playstyle_profiler(game_name: str, tagline: str):
    """Run SageMaker playstyle profiler"""
    
    try:
        # Fetch matches from S3
        prefix = f"raw-matches/{game_name}_{tagline}"
        matches = []
        
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=S3_BUCKET_RAW, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if not key.endswith('match-data.json'):
                    continue
                
                file_obj = s3_client.get_object(Bucket=S3_BUCKET_RAW, Key=key)
                data = json.loads(file_obj['Body'].read())
                matches.append(data)
        
        if not matches:
            return {'error': 'No matches found for profiling'}
        
        # Extract features
        matches_df = pd.DataFrame()
        for match in matches:
            match_df = extract_player_features(match, game_name, tagline)
            if match_df is not None:
                matches_df = pd.concat([matches_df, match_df], ignore_index=True)
        
        if matches_df.empty:
            return {'error': 'Could not extract features'}
        
        # Create aggregate feature vector
        features_vector = create_aggregate_features(matches_df)
        
        # Call SageMaker endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType='application/json',
            Body=json.dumps({'features': features_vector})
        )
        
        result = json.loads(response['Body'].read())
        return result
        
    except Exception as e:
        print(f"Error in playstyle profiler: {e}")
        return {'error': str(e)}


def extract_player_features(match_data: dict, game_name: str, tagline: str):
    """Extract features for a single match"""
    try:
        df_match = pd.json_normalize(match_data)
        participants = df_match.loc[0, "info.participants"]
        
        player_data = next(
            (p for p in participants
             if p.get("riotIdGameName", "").lower() == game_name.lower()
             and p.get("riotIdTagline", "").lower() == tagline.lower()),
            None
        )
        
        if not player_data:
            return None
        
        df_participant = pd.json_normalize(player_data).add_prefix("participant.")
        df_participant["metadata.matchId"] = df_match.loc[0, "metadata.matchId"]
        df_participant["info.gameCreation"] = df_match.loc[0, "info.gameCreation"]
        df_participant["info.gameDuration"] = df_match.loc[0, "info.gameDuration"]
        df_participant["info.gameVersion"] = df_match.loc[0, "info.gameVersion"]
        
        cols = {
            "metadata.matchId": "match_id",
            "info.gameCreation": "game_creation",
            "info.gameDuration": "game_duration",
            "info.gameVersion": "game_version",
            "participant.puuid": "puuid",
            "participant.riotIdGameName": "game_name",
            "participant.riotIdTagline": "tagline",
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
            "participant.challenges.visionScorePerMinute": "vspm",
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
        }
        
        df_flat = df_participant[list(cols.keys())].rename(columns=cols)
        
        df_flat["kda"] = (df_flat["kills"] + df_flat["assists"]) / df_flat["deaths"].replace(0, pd.NA)
        df_flat["kda"].fillna(df_flat["kills"] + df_flat["assists"], inplace=True)
        df_flat["game_duration_minutes"] = df_flat["game_duration"] / 60
        df_flat["cs_per_min"] = df_flat["cs"] / df_flat["game_duration_minutes"]
        
        return df_flat
        
    except Exception as e:
        print(f"Error extracting features: {e}")
        return None


def create_aggregate_features(df: pd.DataFrame) -> list:
    """Create aggregated feature vector from match data"""
    
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
        "death_consistency": df["deaths"].std(ddof=0) if len(df) > 1 else 0.0,
        "cs_consistency": df["cs_per_min"].std(ddof=0) if len(df) > 1 else 0.0,
    }
    
    # Calculate region scores
    features["bandle"] = (features["avg_outnumbered_kills"] * 0.4 + features["avg_kda"] * 0.3 + 
                         (features["avg_vision_score"] / 40.0) * 0.3)
    features["bilgewater"] = ((features["avg_gpm"] / 400) * 0.4 + features["avg_solo_kills"] * 0.3 + 
                              features["avg_kills_near_tower"] * 0.3)
    features["demacia"] = (features["avg_kill_participation"] * 0.4 + features["avg_team_damage_pct"] * 0.3 + 
                          (features["avg_shields_on_teammates"] / 500) * 0.3)
    features["ionia"] = ((features["avg_kda"] / 4) * 0.3 + 
                        ((features["avg_kill_participation"] * features["avg_cs_per_min"]) / 7) * 0.4 + 
                        (features["avg_vision_score"] / 40) * 0.3)
    features["ixtal"] = ((features["avg_objective_damage"] / 10000) * 0.4 + features["avg_dragon_takedowns"] * 0.3 + 
                        features["avg_herald_takedowns"] * 0.3)
    features["noxus"] = ((features["avg_dpm"] / 600) * 0.4 + (features["avg_early_gold_adv"] / 500) * 0.3)
    features["piltover"] = ((features["avg_gpm"] / 400) * 0.4 + (features["avg_cs_per_min"] / 7) * 0.3 + 
                           features["cs_consistency"] * 0.3)
    features["shadow_isles"] = ((features["avg_heals_on_teammates"] / 1000) * 0.4 + 
                                (features["avg_longest_alive"] / 600) * 0.3 + features["avg_kda"] * 0.3)
    features["shurima"] = ((features["avg_cs_per_min"] / 7) * 0.5 + features["avg_gpm"] * 0.5)
    features["targon"] = ((features["avg_vision_score"] / 40) * 0.4 + 
                         (features["avg_shields_on_teammates"] / 500) * 0.3 + 
                         (features["avg_heals_on_teammates"] / 1000) * 0.3)
    features["freljord"] = ((features["avg_cc_time"] / 20) * 0.4 + (features["avg_time_dead"] / 60) * -0.3 + 
                           (1 / (features["death_consistency"] + 0.1)) * 0.3)
    features["void"] = ((features["avg_dpm"] / 600) * 0.4 + features["avg_team_damage_pct"] * 0.4 + 
                       features["avg_solo_kills"] * 0.2)
    features["zaun"] = ((1 / (features["death_consistency"] + 0.1)) * -0.3 + 
                       features["avg_outnumbered_kills"] * 0.4 + features["avg_pick_kills"] * 0.3)
    
    # Return ordered feature list
    return [
        features["bandle"], features["bilgewater"], features["demacia"], features["ionia"],
        features["ixtal"], features["noxus"], features["piltover"], features["shadow_isles"],
        features["shurima"], features["targon"], features["freljord"], features["void"], 
        features["zaun"], features["avg_dpm"], features["avg_gpm"], features["avg_kill_participation"],
        features["avg_kda"], features["avg_vision_score"], features["avg_cs_per_min"], 
        features["avg_team_damage_pct"]
    ]


def trigger_timeline_processing(game_name: str, tagline: str, puuid: str, match_ids: list):
    """Trigger Step Functions for timeline processing"""
    
    execution_name = f"player_{game_name}_{tagline}_{int(datetime.utcnow().timestamp())}"
    
    response = stepfunctions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=execution_name,
        input=json.dumps({
            'match_ids': match_ids,
            'puuid': puuid,
            'batch_mode': True
        })
    )
    
    return response['executionArn']


def wait_for_completion(execution_arn: str, timeout: int = 300):
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
    
    print("Timeline processing timeout")
    return False


def get_timeline_results(puuid: str, match_ids: list):
    """Retrieve timeline data from DynamoDB"""
    
    events_table = dynamodb.Table('lol-timeline-events')
    summaries_table = dynamodb.Table('lol-timeline-timeline-ai-summaries')
    
    timeline_data = []
    
    for match_id in match_ids:
        try:
            response = events_table.query(
                IndexName='match-impact-index',
                KeyConditionExpression='match_id = :mid',
                FilterExpression='puuid = :pid',
                ExpressionAttributeValues={':mid': match_id, ':pid': puuid},
                ScanIndexForward=False
            )
            
            events = response.get('Items', [])
            
            processed_events = []
            for event_item in events:
                event_obj = {
                    'event_id': event_item['event_id'],
                    'timestamp_minutes': float(event_item['timestamp_minutes']),
                    'event_type': event_item['event_type'],
                    'impact_score': int(event_item['impact_score']),
                    'game_state': event_item.get('game_state', 'mid'),
                    'has_summary': False,
                    'summary': None
                }
                
                # Try to get summary
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
                
                processed_events.append(event_obj)
            
            timeline_data.append({
                'match_id': match_id,
                'events': processed_events,
                'total_events': len(processed_events)
            })
            
        except Exception as e:
            print(f"Error retrieving timeline for {match_id}: {e}")
            continue
    
    return timeline_data


def save_to_dynamodb(game_name: str, tagline: str, puuid: str, match_ids: list, 
                     profiler_results: dict, timeline_data: list):
    """Save player profile to DynamoDB"""
    
    profiles_table = dynamodb.Table(PLAYER_PROFILES_TABLE)
    
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    try:
        profiles_table.put_item(Item={
            'player_id': f"{game_name}#{tagline}",
            'puuid': puuid,
            'game_name': game_name,
            'tagline': tagline,
            'playstyle': profiler_results,
            'match_ids': match_ids,
            'processed_at': int(datetime.utcnow().timestamp()),
            'ttl': ttl,
            'match_count': len(match_ids),
            'timeline_summary': {
                'total_matches': len(timeline_data),
                'total_events': sum(len(m.get('events', [])) for m in timeline_data)
            }
        })
        print("✓ Saved to DynamoDB")
    except Exception as e:
        print(f"Error saving to DynamoDB: {e}")


def response(status_code: int, body: dict):
    """Format API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }