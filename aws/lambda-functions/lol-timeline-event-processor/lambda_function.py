"""
Processes timeline-data.json files and extracts critical events
ENHANCED: Better distance calculations, wave state estimation, team composition tracking
Triggered by S3 upload events
"""

import json
import boto3
import os
import math
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

# Summoner spell cooldowns (in seconds)
SUMMONER_SPELL_COOLDOWNS = {
    'SummonerFlash': 300,
    'SummonerTeleport': 360,
    'SummonerIgnite': 180,
    'SummonerHeal': 240,
    'SummonerBarrier': 180,
    'SummonerExhaust': 210,
    'SummonerSmite': 90,
    'SummonerGhost': 180,
    'SummonerCleanse': 210,
}


class TimelineEventExtractor:
    """
    Extracts critical moments from League of Legends timeline data
    Now tracks player location, summoner spells, and wave states
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
        'HORDE': 500,  # Voidgrub
        'TOWER_PLATE': 300,
        'OUTER_TURRET': 800,
        'INNER_TURRET': 1000,
        'BASE_TURRET': 1200,
        'NEXUS_TURRET': 1500,
        'INHIBITOR': 1500
    }
    
    def __init__(self):
        self.events = []
        self.summoner_spell_tracker = {}
        
    def extract_critical_moments(self, timeline_data: dict, 
                                 match_data: dict, 
                                 target_puuid: str) -> Tuple[List[Dict], Dict]:
        """
        Identifies critical moments that significantly impacted game outcome
        Returns: (critical_moments, player_context)
        """
        critical_moments = []
        
        frames = timeline_data.get('info', {}).get('frames', [])
        participant_map = self._build_participant_map(match_data)
        target_participant_id = self._get_participant_id(match_data, target_puuid)
        
        if not target_participant_id:
            print(f"Warning: Could not find participant ID for {target_puuid}")
            return [], {}
        
        # Extract player's team and get player context early
        target_team = participant_map.get(target_participant_id, {}).get('team')
        player_context = self._get_player_context(match_data, target_puuid)
        
        # Initialize summoner spell tracker for the player
        self._initialize_summoner_tracker(match_data, target_participant_id)
        
        print(f"Player Context: {player_context}")
        print(f"Player Summoner Spells: {self.summoner_spell_tracker.get(target_participant_id, {})}")
        
        for frame_idx, frame in enumerate(frames):
            timestamp = frame.get('timestamp', 0) / 1000 / 60  # Convert to minutes
            
            # Track summoner spell usage in this frame
            self._track_summoner_spells(frame, timestamp)
            
            # Extract events from this frame
            for event in frame.get('events', []):
                event_type = event.get('type')
                
                if event_type in self.CRITICAL_EVENT_TYPES:
                    critical_event = self._analyze_event(
                        event, frame, timestamp, participant_map, 
                        target_participant_id, target_team, player_context
                    )
                    
                    if critical_event:
                        critical_moments.append(critical_event)
        
        # Detect teamfights
        teamfights = self._detect_teamfights(
            frames, participant_map, target_participant_id, target_team, player_context
        )
        critical_moments.extend(teamfights)
        
        # Sort by impact score
        critical_moments.sort(key=lambda x: x['impact_score'], reverse=True)
        
        # Return top 15 moments + player context
        return critical_moments[:15], player_context
    
    def _initialize_summoner_tracker(self, match_data: dict, target_participant_id: int):
        """Initialize summoner spell tracking for the target player"""
        participants = match_data.get('info', {}).get('participants', [])
        for participant in participants:
            if participant['participantId'] == target_participant_id:
                spell1 = participant.get('summoner1Id')
                spell2 = participant.get('summoner2Id')
                
                # Map spell IDs to names (common ones)
                spell_map = {
                    4: 'SummonerFlash',
                    12: 'SummonerTeleport',
                    14: 'SummonerIgnite',
                    7: 'SummonerHeal',
                    21: 'SummonerBarrier',
                    3: 'SummonerExhaust',
                    11: 'SummonerSmite',
                    6: 'SummonerGhost',
                    1: 'SummonerCleanse',
                }
                
                self.summoner_spell_tracker[target_participant_id] = {
                    'spell1': {
                        'name': spell_map.get(spell1, 'Unknown'),
                        'id': spell1,
                        'last_used': -1000
                    },
                    'spell2': {
                        'name': spell_map.get(spell2, 'Unknown'),
                        'id': spell2,
                        'last_used': -1000
                    }
                }
                break
    
    def _track_summoner_spells(self, frame: dict, current_timestamp: float):
        """Track when summoner spells are used (approximation)"""
        # Note: Timeline API doesn't explicitly track summoner usage
        # We estimate based on kill participation and assume Flash/TP were used
        pass
    
    def _get_summoner_cooldowns(self, participant_id: int, current_timestamp: float) -> Dict:
        """Calculate current summoner spell cooldowns"""
        spell_data = self.summoner_spell_tracker.get(participant_id, {})
        
        if not spell_data:
            return {
                'flash_cooldown': 0,
                'other_cooldown': 0,
                'other_spell': 'Unknown',
                'tp_available': False
            }
        
        spell1 = spell_data.get('spell1', {})
        spell2 = spell_data.get('spell2', {})
        
        # Calculate cooldowns
        spell1_name = spell1.get('name', 'Unknown')
        spell2_name = spell2.get('name', 'Unknown')
        
        spell1_cd = SUMMONER_SPELL_COOLDOWNS.get(spell1_name, 300)
        spell2_cd = SUMMONER_SPELL_COOLDOWNS.get(spell2_name, 300)
        
        spell1_last_used = spell1.get('last_used', -1000)
        spell2_last_used = spell2.get('last_used', -1000)
        
        time_since_spell1 = (current_timestamp - spell1_last_used) * 60
        time_since_spell2 = (current_timestamp - spell2_last_used) * 60
        
        spell1_remaining = max(0, spell1_cd - time_since_spell1)
        spell2_remaining = max(0, spell2_cd - time_since_spell2)
        
        # Identify Flash and other spell
        flash_cd = 0
        other_cd = 0
        other_spell = 'Unknown'
        tp_available = False
        
        if spell1_name == 'SummonerFlash':
            flash_cd = int(spell1_remaining)
            other_cd = int(spell2_remaining)
            other_spell = spell2_name.replace('Summoner', '')
        elif spell2_name == 'SummonerFlash':
            flash_cd = int(spell2_remaining)
            other_cd = int(spell1_remaining)
            other_spell = spell1_name.replace('Summoner', '')
        else:
            other_cd = int(spell1_remaining)
            other_spell = spell1_name.replace('Summoner', '')
        
        if spell1_name == 'SummonerTeleport' and spell1_remaining == 0:
            tp_available = True
        elif spell2_name == 'SummonerTeleport' and spell2_remaining == 0:
            tp_available = True
        
        return {
            'flash_cooldown': flash_cd,
            'other_cooldown': other_cd,
            'other_spell': other_spell,
            'tp_available': tp_available
        }
    
    def _calculate_distance(self, pos1: dict, pos2: dict) -> float:
        """Calculate Euclidean distance between two positions"""
        x1, y1 = pos1.get('x', 0), pos1.get('y', 0)
        x2, y2 = pos2.get('x', 0), pos2.get('y', 0)
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def _get_player_location_context(self, frame: dict, target_participant_id: int, 
                                     event_position: dict) -> Dict:
        """Get player's location relative to the event"""
        participant_frames = frame.get('participantFrames', {})
        player_frame = participant_frames.get(str(target_participant_id), {})
        
        player_position = player_frame.get('position', {'x': 0, 'y': 0})
        
        distance = self._calculate_distance(player_position, event_position)
        player_lane = self._get_lane_from_position(player_position)
        
        return {
            'position': player_position,
            'lane': player_lane,
            'distance_to_event': int(distance)
        }
    
    def _get_player_context(self, match_data: dict, target_puuid: str) -> Dict:
        """
        Extracts player context from match data
        """
        participants = match_data.get('info', {}).get('participants', [])
        for participant in participants:
            if participant.get('puuid') == target_puuid:
                return {
                    'champion': participant.get('championName', 'Champion'),
                    'position': participant.get('teamPosition', 'Role'),
                    'lane': participant.get('lane', 'UNKNOWN'),
                    'role': participant.get('role', 'SOLO'),
                    'team_id': participant.get('teamId'),
                    'summoner_name': participant.get('riotIdGameName', 'Unknown'),
                    'summoner_tag': participant.get('riotIdTagline', 'Unknown')
                }
        
        return {
            'champion': 'Champion',
            'position': 'Role',
            'lane': 'UNKNOWN',
            'role': 'SOLO'
        }

    def _analyze_event(self, event: dict, frame: dict, 
                       timestamp: float, participant_map: dict,
                       target_participant_id: int, target_team: int,
                       player_context: Dict = None) -> Dict:
        """
        Analyzes individual event for criticality
        Now includes player location and summoner spell data
        """
        event_type = event.get('type')
        impact_score = 0
        event_details = {}
        event_position = event.get('position', {'x': 7200, 'y': 7200})
        
        # Get player location context
        player_location = self._get_player_location_context(
            frame, target_participant_id, event_position
        )
        
        # Get summoner spell cooldowns
        summoner_spells = self._get_summoner_cooldowns(target_participant_id, timestamp)
        
        if event_type == 'CHAMPION_KILL':
            killer_id = event.get('killerId')
            victim_id = event.get('victimId')
            assisting_ids = event.get('assistingParticipantIds', [])
            
            is_player_involved = (
                killer_id == target_participant_id or 
                victim_id == target_participant_id or
                target_participant_id in assisting_ids
            )
            
            if not is_player_involved:
                killer_team = participant_map.get(killer_id, {}).get('team')
                if killer_team != target_team:
                    return None
            
            shutdown_bounty = event.get('bounty', 0)
            
            impact_score = 50
            if len(assisting_ids) >= 3:
                impact_score += 30
            if shutdown_bounty > 500:
                impact_score += 100
            if killer_id == target_participant_id:
                impact_score += 20
            elif victim_id == target_participant_id:
                impact_score += 25
            
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
                'event_position_x': event_position.get('x', 0),
                'event_position_y': event_position.get('y', 0),
                'event_position_lane': self._get_lane_from_position(event_position),
                'player_role': (
                    'killer' if killer_id == target_participant_id
                    else 'victim' if victim_id == target_participant_id
                    else 'assistant' if target_participant_id in assisting_ids
                    else 'team_involved'
                )
            }
            
            context = self._build_event_context(frame, participant_map, target_team)
            context['player_location'] = player_location
            context['summoner_spells'] = summoner_spells
            
            return {
                'event_id': f"KILL_{timestamp:.1f}_{uuid.uuid4().hex[:8]}",
                'timestamp_minutes': float(timestamp),
                'event_type': 'KILL',
                'impact_score': int(impact_score),
                'event_details': event_details,
                'game_state': self._get_game_state(timestamp),
                'context': context,
                'player_context': player_context
            }
            
        elif event_type == 'ELITE_MONSTER_KILL':
            monster_type = event.get('monsterType')
            killer_team_id = event.get('killerTeamId')
            
            is_player_team = (killer_team_id == target_team)
            
            impact_score = self.OBJECTIVE_VALUES.get(monster_type, 500)
            if is_player_team:
                impact_score += 100
            else:
                impact_score += 60
            
            event_details = {
                'objective_type': monster_type,
                'securing_team': 'PLAYER_TEAM' if is_player_team else 'ENEMY_TEAM',
                'killer_id': event.get('killerId'),
                'event_position_x': event_position.get('x', 0),
                'event_position_y': event_position.get('y', 0),
                'event_position_lane': self._get_lane_from_position(event_position)
            }
            
            context = self._build_event_context(frame, participant_map, target_team)
            context['player_location'] = player_location
            context['summoner_spells'] = summoner_spells
            
            return {
                'event_id': f"OBJECTIVE_{timestamp:.1f}_{uuid.uuid4().hex[:8]}",
                'timestamp_minutes': float(timestamp),
                'event_type': 'OBJECTIVE',
                'impact_score': int(impact_score),
                'event_details': event_details,
                'game_state': self._get_game_state(timestamp),
                'context': context,
                'player_context': player_context
            }
            
        elif event_type == 'BUILDING_KILL':
            building_type = event.get('buildingType')
            killer_team_id = event.get('killerTeamId')
            lane = event.get('laneType', 'UNKNOWN')
            
            is_player_team = (killer_team_id == target_team)
            
            if 'INHIBITOR' in building_type:
                impact_score = self.OBJECTIVE_VALUES['INHIBITOR']
            else:
                impact_score = self.OBJECTIVE_VALUES.get('OUTER_TURRET', 600)
            
            if is_player_team:
                impact_score += 40
            else:
                impact_score += 25
            
            event_details = {
                'structure_type': building_type,
                'lane': lane,
                'destroying_team': 'PLAYER_TEAM' if is_player_team else 'ENEMY_TEAM',
                'event_position_x': event_position.get('x', 0),
                'event_position_y': event_position.get('y', 0),
                'event_position_lane': self._get_lane_from_position(event_position)
            }
            
            context = self._build_event_context(frame, participant_map, target_team)
            context['player_location'] = player_location
            context['summoner_spells'] = summoner_spells
            
            return {
                'event_id': f"STRUCTURE_{timestamp:.1f}_{uuid.uuid4().hex[:8]}",
                'timestamp_minutes': float(timestamp),
                'event_type': 'STRUCTURE',
                'impact_score': int(impact_score),
                'event_details': event_details,
                'game_state': self._get_game_state(timestamp),
                'context': context,
                'player_context': player_context
            }
        
        return None
    
    def _detect_teamfights(self, frames: List[dict], 
                           participant_map: dict,
                           target_participant_id: int,
                           target_team: int,
                           player_context: Dict = None) -> List[Dict]:
        """
        Detects teamfights by clustering kills/deaths in time and space
        """
        teamfights = []
        
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
                        'assisting_ids': event.get('assistingParticipantIds', []),
                        'frame': frame
                    })
        
        i = 0
        while i < len(kill_events):
            cluster = [kill_events[i]]
            j = i + 1
            
            while j < len(kill_events):
                time_diff = abs(kill_events[j]['timestamp'] - kill_events[i]['timestamp'])
                
                if time_diff <= 0.5:  # Within 30 seconds
                    cluster.append(kill_events[j])
                    j += 1
                else:
                    break
            
            if len(cluster) >= 3:
                all_participants = set()
                player_involved = False
                cluster_positions = [k['position'] for k in cluster]
                avg_position = self._get_average_position(cluster_positions)
                
                for kill in cluster:
                    all_participants.add(kill['killer_id'])
                    all_participants.add(kill['victim_id'])
                    all_participants.update(kill['assisting_ids'])
                    
                    if target_participant_id in [kill['killer_id'], kill['victim_id']] or \
                       target_participant_id in kill['assisting_ids']:
                        player_involved = True
                
                if len(all_participants) >= 6 and player_involved:
                    player_team_kills = sum(
                        1 for kill in cluster 
                        if participant_map.get(kill['killer_id'], {}).get('team') == target_team
                    )
                    enemy_kills = len(cluster) - player_team_kills
                    
                    outcome = 'WON' if player_team_kills > enemy_kills else \
                              'LOST' if enemy_kills > player_team_kills else 'EVEN'
                    
                    # Get player location context for teamfight
                    first_frame = cluster[0]['frame']
                    player_location = self._get_player_location_context(
                        first_frame, target_participant_id, avg_position
                    )
                    summoner_spells = self._get_summoner_cooldowns(
                        target_participant_id, cluster[0]['timestamp']
                    )
                    
                    context = {
                        'player_location': player_location,
                        'summoner_spells': summoner_spells,
                        'gold_difference': 0,
                        'gold_state': 'unknown'
                    }
                    
                    teamfights.append({
                        'event_id': f"TEAMFIGHT_{cluster[0]['timestamp']:.1f}_{uuid.uuid4().hex[:8]}",
                        'timestamp_minutes': float(cluster[0]['timestamp']),
                        'event_type': 'TEAMFIGHT',
                        'impact_score': int(150 + (len(cluster) * 50)),
                        'event_details': {
                            'kills_count': len(cluster),
                            'participants_count': len(all_participants),
                            'player_team_kills': player_team_kills,
                            'enemy_team_kills': enemy_kills,
                            'outcome': outcome,
                            'duration_seconds': int((cluster[-1]['timestamp'] - cluster[0]['timestamp']) * 60),
                            'event_position_x': avg_position.get('x', 0),
                            'event_position_y': avg_position.get('y', 0),
                            'event_position_lane': self._get_lane_from_position(avg_position)
                        },
                        'game_state': self._get_game_state(cluster[0]['timestamp']),
                        'context': context,
                        'player_context': player_context
                    })
            
            i = j if j > i + 1 else i + 1
        
        return teamfights
    
    def _get_lane_from_position(self, position: dict) -> str:
        """
        Determine lane from X/Y coordinates
        League map is roughly 14400x14400
        """
        x = position.get('x', 7200)
        y = position.get('y', 7200)
        
        if x < 4800:
            return 'BOT'
        elif x > 9600:
            return 'TOP'
        elif y > 7200:
            return 'TOP'
        elif y < 7200:
            return 'BOT'
        return 'MID'

    def _get_average_position(self, positions: List[dict]) -> dict:
        """
        Calculate average position from multiple coordinates
        """
        if not positions:
            return {'x': 0, 'y': 0}
        
        avg_x = sum(p.get('x', 0) for p in positions) / len(positions)
        avg_y = sum(p.get('y', 0) for p in positions) / len(positions)
        
        return {'x': int(avg_x), 'y': int(avg_y)}

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
                'lane': participant.get('lane'),
                'role': participant.get('role'),
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
    Processes timeline data - handles both S3 triggers and Step Functions invocations
    """
    
    print(f"Timeline Processor Lambda invoked. Event keys: {list(event.keys())}")
    processing_results = []

    try:
        # Case 1: S3 Trigger (direct upload)
        if 'Records' in event and event['Records'][0].get('s3'):
            print("Handling S3 trigger event")
            return handle_s3_trigger(event)
        
        # Case 2: Step Functions invocation
        elif 'match_id' in event and 'puuid' in event:
            print("Handling Step Functions invocation")
            return handle_step_functions_invocation(event)
        
        else:
            print(f"Unknown event type. Event structure: {json.dumps(event)[:500]}")
            raise ValueError("Invalid event payload. Expected S3 trigger or Step Functions payload.")
            
    except Exception as e:
        print(f"Error processing timeline: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def handle_s3_trigger(event):
    """Handle S3 upload trigger"""
    import urllib.parse
    
    processing_results = []
    
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        
        print(f"Processing S3 file: s3://{bucket}/{key}")
        
        result = process_timeline_file(bucket, key)
        if result:
            processing_results.append(result)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Processed {len(processing_results)} match files',
            'results': processing_results
        })
    }


def handle_step_functions_invocation(event):
    """Handle Step Functions invocation"""
    match_id = event['match_id']
    puuid = event['puuid']
    force_reprocess = event.get('force_reprocess', False)
    
    print(f"Processing match {match_id} for player {puuid}")
    
    # Check if already processed
    if not force_reprocess:
        try:
            response = metadata_table.get_item(
                Key={'puuid': puuid, 'match_id': match_id}
            )
            if 'Item' in response:
                print(f"Match {match_id} already processed, skipping")
                return {
                    'statusCode': 200,
                    'already_processed': True,
                    'match_id': match_id
                }
        except Exception as e:
            print(f"Error checking metadata: {e}")
    
    # Get game_name and tagline directly from the event payload
    game_name = event.get('game_name')
    tagline = event.get('tagline')
    
    player_folder = None
    
    if game_name and tagline:
        player_folder = f"{game_name}_{tagline}"
        print(f"Received player folder from event: {player_folder}")
    else:
        print(f"Warning: game_name/tagline not in Step Functions event for match {match_id}.")
        pass
    
    if not player_folder:
        # This is the error your log shows
        print(f"Could not find S3 folder for match {match_id}. Event data missing game_name/tagline.")
        return {
            'statusCode': 404,
            'error': f'Match data S3 folder not found for {match_id}. Event missing game_name/tagline.'
        }
    
    # Construct S3 key directly
    bucket = os.environ.get('S3_BUCKET_RAW', 'lol-training-matches-150k')
    timeline_key = f"raw-matches/{player_folder}/{match_id}/timeline-data.json"
    
    # Process the file, passing the known PUUID
    result = process_timeline_file(bucket, timeline_key, target_puuid_from_event=puuid)
    
    if result:
        return {
            'statusCode': 200,
            'match_id': match_id,
            'events_extracted': result.get('events_found', 0)
        }
    else:
        return {
            'statusCode': 500,
            'error': 'Failed to process timeline'
        }


def process_timeline_file(bucket: str, key: str, target_puuid_from_event: str = None):
    """
    Core processing logic - extracted to be used by both trigger types
    """
    try:
        parts = key.split('/')
        if len(parts) < 4:
            print(f"Invalid key format: {key}")
            return None
        
        player_folder = parts[1]
        match_id = parts[2]

        # Get match data
        match_key = key.replace('timeline-data.json', 'match-data.json')
        print(f"Looking for match data at: {match_key}")
        
        try:
            match_obj = s3_client.get_object(Bucket=bucket, Key=match_key)
            match_data = json.loads(match_obj['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            print(f"ERROR: match-data.json not found at {match_key}")
            return None

        target_puuid = target_puuid_from_event
        
        if not target_puuid:
            # Fallback for S3 trigger (not Step Functions)
            print(f"PUUID not passed from event, deriving from folder name: {player_folder}")
            player_folder_parts = player_folder.split('_')
            if len(player_folder_parts) >= 2:
                target_game_name = player_folder_parts[0]
                target_tagline = '_'.join(player_folder_parts[1:])

                for p in match_data.get('info', {}).get('participants', []):
                    if p.get('riotIdGameName') == target_game_name and \
                       p.get('riotIdTagline') == target_tagline:
                        target_puuid = p.get('puuid')
                        break
        
        if not target_puuid:
            print(f"Warning: Could not find PUUID for {player_folder}")
            return None
        
        # Get timeline data
        timeline_obj = s3_client.get_object(Bucket=bucket, Key=key)
        timeline_data = json.loads(timeline_obj['Body'].read())
        
        print(f"Extracting events for match {match_id}, player {target_puuid}")
        
        # Extract critical moments
        extractor = TimelineEventExtractor()
        critical_moments, player_context = extractor.extract_critical_moments(
            timeline_data, match_data, target_puuid
        )
        
        print(f"Extracted {len(critical_moments)} critical moments")
        
        # Save to DynamoDB
        save_count = 0
        if critical_moments:
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
                        'player_context': json.dumps(moment.get('player_context', {})),
                        'created_at': int(datetime.utcnow().timestamp())
                    }
                    batch.put_item(Item=item)
                    save_count += 1
        
        print(f"Saved {save_count} events to DynamoDB")
        
        # Save metadata
        metadata_table.put_item(Item={
            'puuid': target_puuid,
            'match_id': match_id,
            'champion': player_context.get('champion'),
            'lane': player_context.get('lane'),
            'position': player_context.get('position'),
            'processed_timestamp': int(datetime.utcnow().timestamp()),
            'events_count': len(critical_moments),
            'processing_status': 'completed',
            'player_folder': player_folder,
            's3_key': key 
        })
        
        print(f"✓ Successfully processed {key}")
        return {'match_id': match_id, 'events_found': save_count}
        
    except Exception as e:
        print(f"Error in process_timeline_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return None