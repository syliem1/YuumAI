"""
Processes timeline-data.json files and extracts critical events
Triggered by S3 upload events
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
import uuid

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Get table names from environment variables
EVENTS_TABLE_NAME = os.environ.get('EVENTS_TABLE_NAME', 'lol-timeline-events')
METADATA_TABLE_NAME = os.environ.get('METADATA_TABLE_NAME', 'lol-player-timeline-metadata')

events_table = dynamodb.Table(EVENTS_TABLE_NAME)
metadata_table = dynamodb.Table(METADATA_TABLE_NAME)


class TimelineEventExtractor:
    """
    Extracts critical moments from League of Legends timeline data
    """
    
    CRITICAL_EVENT_TYPES = [
        'CHAMPION_KILL',
        'ELITE_MONSTER_KILL',
        'BUILDING_KILL',
        'CHAMPION_SPECIAL_KILL',
    ]
    
    OBJECTIVE_VALUES = {
        'DRAGON': 1000,
        'BARON_NASHOR': 3000,
        'RIFTHERALD': 1500,
        'TOWER_PLATE': 300,
        'OUTER_TURRET': 800,
        'INNER_TURRET': 1000,
        'BASE_TURRET': 1200,
        'NEXUS_TURRET': 1500,
        'INHIBITOR': 1500
    }
    
    def __init__(self):
        self.events = []
        
    def extract_critical_moments(self, timeline_data: dict, 
                                 match_data: dict, 
                                 target_puuid: str) -> List[Dict]:
        """
        Identifies critical moments that significantly impacted game outcome
        """
        critical_moments = []
        
        frames = timeline_data.get('info', {}).get('frames', [])
        participant_map = self._build_participant_map(match_data)
        target_participant_id = self._get_participant_id(match_data, target_puuid)
        
        if not target_participant_id:
            print(f"Warning: Could not find participant ID for {target_puuid}")
            return []
        
        # Extract player's team
        target_team = participant_map.get(target_participant_id, {}).get('team')
        
        for frame_idx, frame in enumerate(frames):
            timestamp = frame.get('timestamp', 0) / 1000 / 60  # Convert to minutes
            
            # Extract events from this frame
            for event in frame.get('events', []):
                event_type = event.get('type')
                
                if event_type in self.CRITICAL_EVENT_TYPES:
                    critical_event = self._analyze_event(
                        event, frame, timestamp, participant_map, 
                        target_participant_id, target_team
                    )
                    
                    if critical_event:
                        critical_moments.append(critical_event)
        
        # Detect teamfights
        teamfights = self._detect_teamfights(
            frames, participant_map, target_participant_id, target_team
        )
        critical_moments.extend(teamfights)
        
        # Sort by impact score
        critical_moments.sort(key=lambda x: x['impact_score'], reverse=True)
        
        # Return top 15 moments
        return critical_moments[:15]
    
    def _analyze_event(self, event: dict, frame: dict, 
                       timestamp: float, participant_map: dict,
                       target_participant_id: int, target_team: int) -> Dict:
        """
        Analyzes individual event for criticality
        """
        event_type = event.get('type')
        impact_score = 0
        event_details = {}
        
        if event_type == 'CHAMPION_KILL':
            killer_id = event.get('killerId')
            victim_id = event.get('victimId')
            assisting_ids = event.get('assistingParticipantIds', [])
            
            # Check if target player was involved
            is_player_involved = (
                killer_id == target_participant_id or 
                victim_id == target_participant_id or
                target_participant_id in assisting_ids
            )
            
            if not is_player_involved:
                # Still track high-impact kills on player's team
                killer_team = participant_map.get(killer_id, {}).get('team')
                if killer_team != target_team:
                    return None  # Enemy kill, not involving player
            
            shutdown_bounty = event.get('bounty', 0)
            
            # Calculate impact
            impact_score = 50  # Base kill impact
            if len(assisting_ids) >= 3:
                impact_score += 30  # Team fight kill
            if shutdown_bounty > 500:
                impact_score += 400  # High-value shutdown
            if killer_id == target_participant_id:
                impact_score += 20  # Player got the kill
            elif victim_id == target_participant_id:
                impact_score += 25  # Player died (learning opportunity)
            
            event_details = {
                'killer': participant_map.get(killer_id, {}).get('champion'),
                'killer_name': participant_map.get(killer_id, {}).get('name'),
                'victim': participant_map.get(victim_id, {}).get('champion'),
                'victim_name': participant_map.get(victim_id, {}).get('name'),
                'assistants': [
                    participant_map.get(aid, {}).get('champion') 
                    for aid in assisting_ids
                ],
                'shutdown_gold': int(shutdown_bounty),
                'position': event.get('position', {}),
                'player_role': (
                    'killer' if killer_id == target_participant_id
                    else 'victim' if victim_id == target_participant_id
                    else 'assistant' if target_participant_id in assisting_ids
                    else 'team_involved'
                )
            }
            
            return {
                'event_id': f"KILL_{timestamp:.1f}_{uuid.uuid4().hex[:8]}",
                'timestamp_minutes': float(timestamp),
                'event_type': 'KILL',
                'impact_score': int(impact_score),
                'event_details': event_details,
                'game_state': self._get_game_state(timestamp),
                'context': self._build_event_context(frame, participant_map, target_team)
            }
            
        elif event_type == 'ELITE_MONSTER_KILL':
            monster_type = event.get('monsterType')
            killer_team_id = event.get('killerTeamId')
            
            # Only track objectives relevant to player's team
            is_player_team = (killer_team_id == target_team)
            
            impact_score = self.OBJECTIVE_VALUES.get(monster_type, 500)
            if is_player_team:
                impact_score += 50  # Bonus for securing
            else:
                impact_score += 30  # Still important to know enemy secured
            
            event_details = {
                'objective_type': monster_type,
                'securing_team': 'PLAYER_TEAM' if is_player_team else 'ENEMY_TEAM',
                'position': event.get('position', {}),
                'killer_id': event.get('killerId')
            }
            
            return {
                'event_id': f"OBJECTIVE_{timestamp:.1f}_{uuid.uuid4().hex[:8]}",
                'timestamp_minutes': float(timestamp),
                'event_type': 'OBJECTIVE',
                'impact_score': int(impact_score),
                'event_details': event_details,
                'game_state': self._get_game_state(timestamp),
                'context': self._build_event_context(frame, participant_map, target_team)
            }
            
        elif event_type == 'BUILDING_KILL':
            building_type = event.get('buildingType')
            killer_team_id = event.get('killerTeamId')
            lane = event.get('laneType', 'UNKNOWN')
            
            is_player_team = (killer_team_id == target_team)
            
            if 'INHIBITOR' in building_type:
                impact_score = self.OBJECTIVE_VALUES['INHIBITOR']
            else:
                impact_score = self.OBJECTIVE_VALUES.get('OUTER_TURRET', 800)
            
            if is_player_team:
                impact_score += 40
            else:
                impact_score += 25
            
            event_details = {
                'structure_type': building_type,
                'lane': lane,
                'destroying_team': 'PLAYER_TEAM' if is_player_team else 'ENEMY_TEAM'
            }
            
            return {
                'event_id': f"STRUCTURE_{timestamp:.1f}_{uuid.uuid4().hex[:8]}",
                'timestamp_minutes': float(timestamp),
                'event_type': 'STRUCTURE',
                'impact_score': int(impact_score),
                'event_details': event_details,
                'game_state': self._get_game_state(timestamp),
                'context': self._build_event_context(frame, participant_map, target_team)
            }
        
        return None
    
    def _detect_teamfights(self, frames: List[dict], 
                          participant_map: dict,
                          target_participant_id: int,
                          target_team: int) -> List[Dict]:
        """
        Detects teamfights by clustering kills/deaths in time and space
        """
        teamfights = []
        
        # Collect all kills
        kill_events = []
        for frame in frames:
            timestamp = frame.get('timestamp', 0) / 1000 / 60
            
            for event in frame.get('events', []):
                if event.get('type') == 'CHAMPION_KILL':
                    kill_events.append({
                        'timestamp': timestamp,
                        'position': event.get('position', {}),
                        'killer_id': event.get('killerId'),
                        'victim_id': event.get('victimId'),
                        'assisting_ids': event.get('assistingParticipantIds', [])
                    })
        
        # Cluster events (within 30 seconds)
        i = 0
        while i < len(kill_events):
            cluster = [kill_events[i]]
            j = i + 1
            
            while j < len(kill_events):
                time_diff = abs(kill_events[j]['timestamp'] - kill_events[i]['timestamp'])
                
                if time_diff <= 0.5:  # 30 seconds
                    cluster.append(kill_events[j])
                    j += 1
                else:
                    break
            
            # Check if it's a teamfight (3+ kills, 6+ participants)
            if len(cluster) >= 3:
                all_participants = set()
                player_involved = False
                
                for kill in cluster:
                    all_participants.add(kill['killer_id'])
                    all_participants.add(kill['victim_id'])
                    all_participants.update(kill['assisting_ids'])
                    
                    if target_participant_id in [kill['killer_id'], kill['victim_id']] or \
                       target_participant_id in kill['assisting_ids']:
                        player_involved = True
                
                if len(all_participants) >= 6 and player_involved:
                    # Determine outcome
                    player_team_kills = sum(
                        1 for kill in cluster 
                        if participant_map.get(kill['killer_id'], {}).get('team') == target_team
                    )
                    enemy_kills = len(cluster) - player_team_kills
                    
                    outcome = 'WON' if player_team_kills > enemy_kills else \
                              'LOST' if enemy_kills > player_team_kills else 'EVEN'
                    
                    teamfights.append({
                        'event_id': f"TEAMFIGHT_{cluster[0]['timestamp']:.1f}_{uuid.uuid4().hex[:8]}",
                        'timestamp_minutes': float(cluster[0]['timestamp']),
                        'event_type': 'TEAMFIGHT',
                        'impact_score': int(100 + (len(cluster) * 20)),
                        'event_details': {
                            'kills_count': len(cluster),
                            'participants_count': len(all_participants),
                            'player_team_kills': player_team_kills,
                            'enemy_team_kills': enemy_kills,
                            'outcome': outcome,
                            'duration_seconds': int((cluster[-1]['timestamp'] - cluster[0]['timestamp']) * 60)
                        },
                        'game_state': self._get_game_state(cluster[0]['timestamp']),
                        'context': {}
                    })
            
            i = j if j > i + 1 else i + 1
        
        return teamfights
    
    def _build_participant_map(self, match_data: dict) -> Dict:
        """
        Creates mapping of participantId to player info
        """
        participant_map = {}
        
        participants = match_data.get('info', {}).get('participants', [])
        for participant in participants:
            participant_map[participant['participantId']] = {
                'name': f"{participant.get('riotIdGameName', 'Unknown')}",
                'champion': participant.get('championName'),
                'team': participant.get('teamId'),
                'position': participant.get('teamPosition'),
                'puuid': participant.get('puuid')
            }
        
        return participant_map
    
    def _get_participant_id(self, match_data: dict, puuid: str) -> int:
        """
        Gets participant ID for given PUUID
        """
        participants = match_data.get('info', {}).get('participants', [])
        for participant in participants:
            if participant.get('puuid') == puuid:
                return participant['participantId']
        return None
    
    def _build_event_context(self, frame: dict, participant_map: dict, 
                             target_team: int) -> Dict:
        """
        Builds contextual information for the event
        """
        participant_frames = frame.get('participantFrames', {})
        
        team_100_gold = sum(
            p.get('totalGold', 0) 
            for p_id, p in participant_frames.items() 
            if participant_map.get(int(p_id), {}).get('team') == 100
        )
        team_200_gold = sum(
            p.get('totalGold', 0) 
            for p_id, p in participant_frames.items() 
            if participant_map.get(int(p_id), {}).get('team') == 200
        )
        
        if target_team == 100:
            gold_diff = team_100_gold - team_200_gold
        else:
            gold_diff = team_200_gold - team_100_gold
        
        return {
            'gold_difference': int(gold_diff),
            'gold_state': 'ahead' if gold_diff > 1000 else 'behind' if gold_diff < -1000 else 'even'
        }
    
    def _get_game_state(self, timestamp: float) -> str:
        """
        Determines game state based on timestamp
        """
        if timestamp < 15:
            return 'early'
        elif timestamp < 25:
            return 'mid'
        else:
            return 'late'

def lambda_handler(event, context):
    """
    Processes timeline data and extracts critical events
    Triggered when new timeline-data.json uploaded to S3
    """
    
    print("Timeline Processor Lambda invoked (S3 Trigger)")
    processing_results = []

    try:
        # --- CASE 1: S3 Event Trigger ---
        if 'Records' in event:
            print(f"Processing {len(event['Records'])} S3 event record(s)")
            for record in event['Records']:
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                
                print(f"Processing file: s3://{bucket}/{key}")
                
                parts = key.split('/')
                if len(parts) < 4:
                    print(f"Invalid key format: {key}")
                    continue
                
                player_folder = parts[1]  # GAMENAME_TAGLINE
                match_id = parts[2]

                # Download match data
                match_key = key.replace('timeline-data.json', 'match-data.json')
                match_obj = s3_client.get_object(Bucket=bucket, Key=match_key)
                match_data = json.loads(match_obj['Body'].read())

                # Get target player PUUID
                target_puuid = None
                player_folder_parts = player_folder.split('_')
                if len(player_folder_parts) >= 2:
                    target_game_name = player_folder_parts[0]
                    target_tagline = '_'.join(player_folder_parts[1:])
                    
                    print(f"DEBUG: Looking for GameName='{target_game_name}' and Tagline='{target_tagline}'")

                    for p in match_data.get('info', {}).get('participants', []):
                        
                        p_name = p.get('riotIdGameName')
                        p_tag = p.get('riotIdTagline')
                        print(f"DEBUG: Checking participant {p_name}#{p_tag}")

                        if p.get('riotIdGameName') == target_game_name and p.get('riotIdTagline') == target_tagline:
                            target_puuid = p.get('puuid')
                            print(f"DEBUG: Match found! PUUID is {target_puuid}")
                            break
                
                if not target_puuid:
                    print(f"Warning: Could not find PUUID for {player_folder}. Aborting.")
                    continue
                    
                # Download timeline data
                timeline_obj = s3_client.get_object(Bucket=bucket, Key=key)
                timeline_data = json.loads(timeline_obj['Body'].read())
                
                print(f"Extracting events for match {match_id}, player {target_puuid}")
                
                # Extract critical events
                extractor = TimelineEventExtractor()
                critical_moments = extractor.extract_critical_moments(
                    timeline_data, match_data, target_puuid
                )
                
                print(f"Extracted {len(critical_moments)} critical moments")
                
                # Save to DynamoDB
                save_count = 0
                if critical_moments: # Only write if there's something to write
                    with events_table.batch_writer() as batch:
                        for moment in critical_moments:
                            item = {
                                'match_id': match_id,
                                'event_id': moment['event_id'],
                                'puuid': target_puuid,
                                'timestamp_minutes': Decimal(str(moment['timestamp_minutes'])),
                                'event_type': moment['event_type'],
                                'impact_score': moment['impact_score'],
                                'game_state': moment['game_state'],
                                'event_details': json.dumps(moment['event_details']),
                                'context': json.dumps(moment.get('context', {})),
                                'created_at': int(datetime.utcnow().timestamp())
                            }
                            batch.put_item(Item=item)
                            save_count += 1
                
                print(f"Saved {save_count} events to DynamoDB")
                
                # Update metadata table
                metadata_table.put_item(Item={
                    'puuid': target_puuid,
                    'match_id': match_id,
                    'processed_timestamp': int(datetime.utcnow().timestamp()),
                    'events_count': len(critical_moments),
                    'processing_status': 'completed_s3', # Mark as S3 complete
                    'player_folder': player_folder,
                    's3_key': key 
                })
                
                print(f"✓ Successfully processed {key}")
                processing_results.append({'match_id': match_id, 'events_found': save_count})
        
        # --- CASE 2: Step Function Event Trigger ---
        elif 'match_id' in event:
            # This logic is flawed because it relies on S3 data that might
            # not be findable. We will ignore it for now.
            # The S3 trigger MUST succeed.
            print(f"Warning: Step Function trigger received, but this Lambda is configured for S3 only.")
            print(f"Step Function-based processing is not yet implemented correctly.")
            # We'll just return success so the SFN can proceed
            return {
                'statusCode': 200,
                'body': {'events_extracted': 0, 'message': 'SFN trigger not implemented'}
            }
            
        else:
            raise ValueError("Invalid event payload. Expected S3 or SFN trigger.")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(processing_results)} match files',
                'results': processing_results
            })
        }
        
    except Exception as e:
        print(f"Error processing timeline: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }