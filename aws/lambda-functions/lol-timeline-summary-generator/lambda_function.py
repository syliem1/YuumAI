"""
Enhanced Bedrock Coaching Generator with Macro Focus
Generates personalized coaching summaries with reduced hallucinations
"""

import json
import boto3
import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# AWS clients
dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
s3_client = boto3.client('s3')

# DynamoDB tables
summaries_table = dynamodb.Table('lol-timeline-timeline-ai-summaries')

BEDROCK_MODEL_ID = 'amazon.nova-pro-v1:0'
MAX_TOKENS = 300
TEMPERATURE = 0.3  # Lowered for less hallucination


class RobustContextExtractor:
    """Extracts rich metrics with robust JSON parsing"""
    
    def __init__(self, timeline_data: dict, match_data: dict):
        self.timeline_data = timeline_data
        self.match_data = match_data
        self.frames = timeline_data.get('info', {}).get('frames', [])
        self.participants = self._build_participant_map(match_data)
    
    def _safe_json_parse(self, json_str: str, default: dict = None) -> dict:
        """Robustly parse JSON with multiple fallback strategies"""
        if default is None:
            default = {}
        
        if not json_str or not isinstance(json_str, str):
            return default
        
        # Try direct parse first
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Try removing problematic characters
        try:
            cleaned = json_str.replace('\x00', '').replace('\n', ' ')
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Try extracting valid JSON substrings
        try:
            match = re.search(r'\{.*\}', json_str)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        
        print(f"⚠️ Failed to parse JSON: {json_str[:100]}")
        return default
    
    def _build_participant_map(self, match_data: dict) -> Dict:
        """Build participant metadata from match data"""
        pmap = {}
        try:
            for p in match_data.get('info', {}).get('participants', []):
                p_id = p.get('participantId')
                pmap[p_id] = {
                    'name': p.get('riotIdGameName', 'Unknown'),
                    'champion': p.get('championName', 'Unknown'),
                    'team': p.get('teamId'),
                    'role': p.get('teamPosition', 'UNKNOWN'),
                    'puuid': p.get('puuid'),
                    # New: Add final stats for context
                    'final_kda': f"{p.get('kills', 0)}/{p.get('deaths', 0)}/{p.get('assists', 0)}",
                    'win': p.get('win', False)
                }
        except Exception as e:
            print(f"Error building participant map: {str(e)}")
        
        return pmap
    
    def get_frame_at_timestamp(self, timestamp_minutes: float) -> Tuple[dict, int]:
        """Find the closest frame to event timestamp"""
        if not self.frames:
            return {}, -1
        
        timestamp_ms = timestamp_minutes * 60 * 1000
        
        closest_frame = None
        closest_diff = float('inf')
        closest_idx = -1
        
        for idx, frame in enumerate(self.frames):
            frame_time = frame.get('timestamp', 0)
            diff = abs(frame_time - timestamp_ms)
            
            if diff < closest_diff:
                closest_diff = diff
                closest_frame = frame
                closest_idx = idx
        
        return closest_frame or {}, closest_idx
    
    def get_player_frame_stats(self, participant_id: int, frame: dict) -> Dict:
        """Extract detailed stats for player at frame"""
        participant_frames = frame.get('participantFrames', {})
        player_frame = participant_frames.get(str(participant_id), {})
        
        champion_stats = player_frame.get('championStats', {})
        damage_stats = player_frame.get('damageStats', {})
        
        return {
            'level': player_frame.get('level', 1),
            'minions_killed': player_frame.get('minionsKilled', 0),
            'jungle_minions': player_frame.get('jungleMinionsKilled', 0),
            'total_gold': player_frame.get('totalGold', 0),
            'current_gold': player_frame.get('currentGold', 0),
            'xp': player_frame.get('xp', 0),
            'position': player_frame.get('position', {'x': 0, 'y': 0}),
            'stats': {
                'health': {
                    'current': champion_stats.get('health', 0),
                    'max': champion_stats.get('healthMax', 0)
                },
                'armor': champion_stats.get('armor', 0),
                'mr': champion_stats.get('magicResist', 0),
                'ad': champion_stats.get('attackDamage', 0),
                'ap': champion_stats.get('abilityPower', 0),
            },
            'damage': {
                'total_damage_dealt': damage_stats.get('totalDamageDone', 0),
                'total_damage_taken': damage_stats.get('totalDamageTaken', 0)
            }
        }
    
    def get_team_stats(self, frame: dict, team_id: int) -> Dict:
        """Get aggregated team statistics at this frame"""
        participant_frames = frame.get('participantFrames', {})
        
        team_members = [
            p_id for p_id, p_info in self.participants.items()
            if p_info.get('team') == team_id
        ]
        
        total_gold = 0
        total_kills = 0
        avg_level = 0
        
        for p_id in team_members:
            p_frame = participant_frames.get(str(p_id), {})
            total_gold += p_frame.get('totalGold', 0)
            avg_level += p_frame.get('level', 0)
        
        return {
            'total_gold': total_gold,
            'avg_level': avg_level / max(len(team_members), 1),
            'member_count': len(team_members)
        }
    
    def calculate_distance(self, pos1: dict, pos2: dict) -> float:
        """Euclidean distance between two positions"""
        x1 = pos1.get('x', 0)
        y1 = pos1.get('y', 0)
        x2 = pos2.get('x', 0)
        y2 = pos2.get('y', 0)
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def get_location_context(self, player_pos: dict, event_pos: dict) -> Dict:
        """Get spatial relationship context"""
        distance = self.calculate_distance(player_pos, event_pos)
        
        # Classify distance (in game units)
        if distance < 1500:
            proximity = "IMMEDIATE"
        elif distance < 3000:
            proximity = "CLOSE"
        elif distance < 5000:
            proximity = "MEDIUM"
        elif distance < 8000:
            proximity = "FAR"
        else:
            proximity = "VERY_FAR"
        
        # Classify location
        map_center_x, map_center_y = 7500, 7500
        event_x = event_pos.get('x', 0)
        event_y = event_pos.get('y', 0)
        
        # Determine quadrant and lane
        if event_x < 4000:
            if event_y < 4000:
                location = "BOTTOM_JUNGLE"
            elif event_y > 10000:
                location = "BOTTOM_LANE"
            else:
                location = "BOTTOM_RIVER"
        elif event_x > 10000:
            if event_y < 4000:
                location = "TOP_LANE"
            elif event_y > 10000:
                location = "TOP_JUNGLE"
            else:
                location = "TOP_RIVER"
        else:
            if event_y < 6000:
                location = "MID_LANE"
            elif event_y > 9000:
                location = "MID_LANE"
            else:
                location = "CENTER"
        
        return {
            'distance_units': int(distance),
            'proximity': proximity,
            'location': location,
            'event_x': int(event_x),
            'event_y': int(event_y),
            'player_x': int(player_pos.get('x', 0)),
            'player_y': int(player_pos.get('y', 0))
        }


class EnhancedBedrockCoachingGenerator:
    """Generates personalized coaching with macro focus and hallucination prevention"""
    
    # Forbidden terms that indicate ability hallucination
    ABILITY_RED_FLAGS = [
        'ultimate', 'ult ', ' q ', ' w ', ' e ', ' r ',
        'passive', 'combo', 'cast', 'channel',
        'skill shot', 'skillshot', 'execute',
        'dash', 'leap', 'blink', 'jump'
    ]
    
    # Allowed terms even if they contain red flags
    ALLOWED_TERMS = [
        'teleport', 'flash', 'tp ', 'recall',
        'ult point', 'ultimate objective'  # Context matters
    ]
    
    def __init__(self):
        self.bedrock = bedrock_runtime
        self.model_id = BEDROCK_MODEL_ID
        self.rejected_count = 0
        self.total_count = 0
    
    def generate_event_summary(self, event: Dict, context_extractor: RobustContextExtractor) -> str:
        """Generate coaching summary with spatial context and validation"""
        
        self.total_count += 1
        
        # Parse event data robustly
        player_context = self._extract_player_context(event, context_extractor)
        event_details = self._extract_event_details(event)
        location_context = self._extract_location_context(event, context_extractor)
        
        if not player_context.get('champion'):
            print(f"  ⚠️ Could not determine champion for event {event.get('event_id')}")
            return ""
        
        # Get enhanced metrics
        enhanced_metrics = self._get_enhanced_metrics(event, context_extractor, player_context)
        
        # Build coaching prompt
        coaching_prompt = self._build_coaching_prompt(
            event,
            player_context,
            event_details,
            location_context,
            enhanced_metrics,
            context_extractor
        )
        
        print(f"🎯 Coaching Prompt Preview:\n{coaching_prompt[:300]}...\n")
        
        summary = self._invoke_bedrock(coaching_prompt, player_context.get('champion'))
        
        # Log rejection rate
        if self.total_count % 5 == 0:
            rejection_rate = (self.rejected_count / self.total_count) * 100
            print(f"📊 Rejection Rate: {rejection_rate:.1f}% ({self.rejected_count}/{self.total_count})")
        
        return summary
    
    def _get_enhanced_metrics(self, event: Dict, extractor: RobustContextExtractor, 
                             player_context: Dict) -> Dict:
        """Extract enhanced metrics for better coaching context"""
        
        timestamp = float(event.get('timestamp_minutes', 0))
        frame, frame_idx = extractor.get_frame_at_timestamp(timestamp)
        
        metrics = {
            'player_stats': {},
            'team_comparison': {},
            'wave_state': 'unknown',
            'objective_timers': {}
        }
        
        if not frame:
            return metrics
        
        try:
            # Find participant ID
            puuid = event.get('puuid')
            participant_id = None
            team_id = None
            
            for p_id, p_info in extractor.participants.items():
                if p_info.get('puuid') == puuid:
                    participant_id = p_id
                    team_id = p_info.get('team')
                    break
            
            if not participant_id:
                return metrics
            
            # Get player stats
            player_stats = extractor.get_player_frame_stats(participant_id, frame)
            metrics['player_stats'] = {
                'level': player_stats['level'],
                'gold': player_stats['total_gold'],
                'cs': player_stats['minions_killed'] + player_stats['jungle_minions'],
                'health_percent': int((player_stats['stats']['health']['current'] / 
                                      max(player_stats['stats']['health']['max'], 1)) * 100)
            }
            
            # Get team comparison
            if team_id:
                player_team_stats = extractor.get_team_stats(frame, team_id)
                enemy_team_id = 200 if team_id == 100 else 100
                enemy_team_stats = extractor.get_team_stats(frame, enemy_team_id)
                
                gold_diff = player_team_stats['total_gold'] - enemy_team_stats['total_gold']
                level_diff = player_team_stats['avg_level'] - enemy_team_stats['avg_level']
                
                metrics['team_comparison'] = {
                    'gold_difference': int(gold_diff),
                    'level_difference': round(level_diff, 1),
                    'gold_state': 'ahead' if gold_diff > 2000 else 'behind' if gold_diff < -2000 else 'even'
                }
            
            # Estimate wave state based on CS
            expected_cs = timestamp * 4  # Rough estimate: ~4 CS per minute
            cs_diff = metrics['player_stats']['cs'] - expected_cs
            
            if cs_diff > 10:
                metrics['wave_state'] = 'ahead_in_lane'
            elif cs_diff < -10:
                metrics['wave_state'] = 'behind_in_lane'
            else:
                metrics['wave_state'] = 'even_in_lane'
            
            # Objective timers (approximations based on game time)
            if timestamp >= 5:
                metrics['objective_timers']['dragon_available'] = timestamp >= 5
            if timestamp >= 8:
                metrics['objective_timers']['herald_available'] = timestamp >= 8 and timestamp < 20
            if timestamp >= 20:
                metrics['objective_timers']['baron_available'] = timestamp >= 20
                
        except Exception as e:
            print(f"Error extracting enhanced metrics: {str(e)}")
        
        return metrics
    
    def _extract_player_context(self, event: Dict, extractor: RobustContextExtractor) -> Dict:
        """Robustly extract player context"""
        player_context_str = event.get('player_context', '{}')
        if isinstance(player_context_str, dict) and 'S' in player_context_str:
            player_context_str = player_context_str['S']
        
        player_context = extractor._safe_json_parse(player_context_str, {})
        
        # Fallback: try to get from participants if extraction failed
        if not player_context.get('champion'):
            puuid = event.get('puuid', '')
            for p_id, p_info in extractor.participants.items():
                if p_info.get('puuid') == puuid:
                    player_context = {
                        'champion': p_info.get('champion', 'Unknown'),
                        'position': p_info.get('role', 'UNKNOWN'),
                        'team_id': p_info.get('team'),
                        'summoner_name': p_info.get('name', 'Player'),
                    }
                    break
        
        return player_context
    
    def _extract_event_details(self, event: Dict) -> Dict:
        """Extract event details"""
        event_details_str = event.get('event_details', '{}')
        if isinstance(event_details_str, dict) and 'S' in event_details_str:
            event_details_str = event_details_str['S']
        
        extractor = RobustContextExtractor({}, {})
        return extractor._safe_json_parse(event_details_str, {})
    
    def _extract_location_context(self, event: Dict, extractor: RobustContextExtractor) -> Dict:
        """Extract location and positioning data"""
        context_str = event.get('context', '{}')
        if isinstance(context_str, dict) and 'S' in context_str:
            context_str = context_str['S']
        
        context = extractor._safe_json_parse(context_str, {})
        
        player_pos = context.get('player_location', {}).get('position', {'x': 0, 'y': 0})
        event_details = self._extract_event_details(event)
        event_pos = {
            'x': event_details.get('event_position_x', 0),
            'y': event_details.get('event_position_y', 0)
        }
        
        location = extractor.get_location_context(player_pos, event_pos)
        location['player_lane'] = context.get('player_location', {}).get('lane', 'UNKNOWN')
        location['summoner_spells'] = context.get('summoner_spells', {})
        
        return location
    
    def _build_coaching_prompt(self, event: Dict, player_context: Dict, 
                               event_details: Dict, location_context: Dict,
                               enhanced_metrics: Dict,
                               extractor: RobustContextExtractor) -> str:
        """Build detailed coaching prompt focused on macro gameplay"""
        
        timestamp = float(event.get('timestamp_minutes', 0))
        champion = player_context.get('champion', 'Unknown')
        position = player_context.get('position', 'UNKNOWN')
        event_type = event.get('event_type', 'UNKNOWN')
        
        # Check if player was actively involved in the event
        player_role = event_details.get('player_role', 'spectator')
        was_participant = player_role in ['killer', 'victim', 'assistant']
        
        # If player participated, distance is effectively 0
        if was_participant:
            distance = 0
            proximity = "PARTICIPANT"
            event_location = location_context.get('location', 'UNKNOWN')
            player_lane = location_context.get('player_lane', 'UNKNOWN')
        else:
            distance = location_context.get('distance_units', 0)
            proximity = location_context.get('proximity', 'UNKNOWN')
            event_location = location_context.get('location', 'UNKNOWN')
            player_lane = location_context.get('player_lane', 'UNKNOWN')
        
        # Summoner spell context
        summoner_spells = location_context.get('summoner_spells', {})
        flash_cd = summoner_spells.get('flash_cooldown', 0)
        other_spell = summoner_spells.get('other_spell', 'Unknown')
        other_cd = summoner_spells.get('other_cooldown', 0)
        tp_available = summoner_spells.get('tp_available', False)
        
        spell_status = []
        if tp_available:
            spell_status.append("✓ Teleport AVAILABLE")
        elif other_spell == 'Teleport':
            spell_status.append(f"✗ Teleport on CD ({other_cd}s)")
        
        if flash_cd == 0:
            spell_status.append("✓ Flash available")
        else:
            spell_status.append(f"✗ Flash on CD ({flash_cd}s)")
        
        spell_info = " | ".join(spell_status) if spell_status else "Summoner status unknown"
        
        # Enhanced metrics
        player_stats = enhanced_metrics.get('player_stats', {})
        team_comp = enhanced_metrics.get('team_comparison', {})
        wave_state = enhanced_metrics.get('wave_state', 'unknown')
        
        stats_line = ""
        if player_stats:
            stats_line = f"Level {player_stats.get('level', '?')}, {player_stats.get('cs', '?')} CS, {player_stats.get('gold', 0)}g"
        
        team_state = ""
        if team_comp:
            gold_diff = team_comp.get('gold_difference', 0)
            if abs(gold_diff) >= 1000:
                team_state = f"Team is {abs(gold_diff)}g {'AHEAD' if gold_diff > 0 else 'BEHIND'}"
            else:
                team_state = "Team gold is EVEN"
        
        # Build event-specific context
        event_context = self._build_event_specific_context(event_type, event_details, player_context)
        
        # Determine coaching focus based on participation
        if was_participant:
            # Player was involved - focus on cost-benefit analysis
            coaching_focus = f"""COACHING FOCUS:
The player ({champion}) was an ACTIVE PARTICIPANT in this event as {player_role}.
Analyze whether participating in this event was the correct macro decision.

Consider:
- What did the player sacrifice to be here? (Wave state, CS, tower plates)
- What did the team gain? (Gold, objectives, map pressure)
- Was this the highest priority action at {timestamp:.1f} minutes?
- What should the player do AFTER this event? (Push, recall, rotate, take objective)"""
        else:
            # Player was not involved - focus on rotation decision
            coaching_focus = f"""COACHING FOCUS:
The player ({champion}) was NOT involved in this event (distance: {distance} units).
Analyze whether the player made the correct rotation decision.

Consider:
- Should they have rotated to help? (Distance: {distance} units, {proximity})
- Was staying in {player_lane} the better choice?
- What were they doing instead? (Pushing, farming, taking objectives)
- Did their decision maximize team advantage?"""
        
        prompt = f"""MATCH SITUATION at {timestamp:.1f} minutes:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PLAYER: {champion} ({position} role)
CURRENT POSITION: {player_lane} lane
{stats_line}
{team_state}

EVENT: {event_type}
EVENT LOCATION: {event_location}
{'PLAYER PARTICIPATION: Active participant ('+player_role+')' if was_participant else 'DISTANCE FROM PLAYER: '+str(distance)+' units ('+proximity+')'}

SUMMONER SPELLS: {spell_info}

WAVE STATE: {wave_state}

{event_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{coaching_focus}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provide macro-focused coaching for {champion}.

STRICT REQUIREMENTS:
- Focus ONLY on: map rotations, wave management, objective priority, vision control
- NO champion abilities, combos, or specific mechanics
- Maximum 100 words

FORMAT:
1. Describe what happened and the player's involvement (1-2 sentences)
2. Analyze the macro decision: Was participating/not participating the right choice?
3. ONE specific actionable tip for similar situations"""
        
        return prompt
    
    def _build_event_specific_context(self, event_type: str, event_details: Dict, 
                                     player_context: Dict) -> str:
        """Build context specific to the event type"""
        
        if event_type == "OBJECTIVE":
            obj_type = event_details.get('objective_type', 'Unknown')
            securing_team = event_details.get('securing_team', 'Unknown')
            
            obj_values = {
                'DRAGON': '1000g + permanent buff',
                'BARON_NASHOR': '3000g + Baron buff (significant)',
                'RIFTHERALD': '1500g + tower pressure',
                'HORDE': '500g + team stats'
            }
            obj_value = obj_values.get(obj_type, 'Unknown value')
            
            return f"OBJECTIVE DETAILS:\n- Type: {obj_type} ({obj_value})\n- Secured by: {securing_team}"
        
        elif event_type == "KILL":
            victim = event_details.get('victim', 'Unknown')
            killer = event_details.get('killer', 'Unknown')
            player_role = event_details.get('player_role', 'unknown')
            assistants = event_details.get('assistants', [])
            shutdown_gold = event_details.get('shutdown_gold', 0)
            
            # Calculate gold value
            base_kill_gold = 300
            total_kill_gold = base_kill_gold + shutdown_gold
            assist_gold = int(total_kill_gold * 0.5) if assistants else 0
            
            involvement_text = ""
            if player_role == 'killer':
                involvement_text = f"You got the kill: +{total_kill_gold}g"
            elif player_role == 'assistant':
                involvement_text = f"You assisted: +{assist_gold}g"
            elif player_role == 'victim':
                involvement_text = "You died: Gave enemy gold and map pressure"
            else:
                involvement_text = "Your team was involved"
            
            return f"KILL DETAILS:\n- Victim: {victim}\n- Killer: {killer}\n- Assistants: {len(assistants)}\n- {involvement_text}\n- Shutdown value: {shutdown_gold}g"
        
        elif event_type == "STRUCTURE":
            structure = event_details.get('structure_type', 'Unknown')
            destroying_team = event_details.get('destroying_team', 'Unknown')
            lane = event_details.get('lane', 'Unknown')
            
            structure_values = {
                'TOWER_BUILDING': '250-300g split + map pressure',
                'INHIBITOR': '50g each + super minions (huge)'
            }
            structure_value = structure_values.get(structure, 'Unknown value')
            
            return f"STRUCTURE DETAILS:\n- Type: {structure} ({structure_value})\n- Lane: {lane}\n- Destroyed by: {destroying_team}"
        
        elif event_type == "TEAMFIGHT":
            outcome = event_details.get('outcome', 'Unknown')
            player_kills = event_details.get('player_team_kills', 0)
            enemy_kills = event_details.get('enemy_team_kills', 0)
            duration = event_details.get('duration_seconds', 0)
            
            return f"TEAMFIGHT DETAILS:\n- Outcome: {outcome}\n- Score: {player_kills} kills vs {enemy_kills} deaths\n- Duration: {duration} seconds\n- Approximate gold swing: {abs(player_kills - enemy_kills) * 300}g"
        
        return ""
    
    def _invoke_bedrock(self, user_prompt: str, champion: str) -> str:
        """Call Bedrock API with macro-focused system prompt and validation"""
        
        system_prompt = [{
            "text": """You are an elite League of Legends macro strategy coach. You analyze rotations, wave management, and objective priority.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES - VIOLATIONS RESULT IN REJECTED RESPONSE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NEVER mention champion abilities (Q, W, E, R, ultimate, passive, combos)
2. NEVER describe champion mechanics or kits
3. ONLY discuss: Teleport, Flash, map rotations, wave states, objective timing
4. If you don't know something, focus on general positioning instead of guessing

COACHING APPROACH:
- If player WAS INVOLVED: Analyze cost-benefit of their participation
- If player WAS NOT INVOLVED: Analyze their rotation decision

FOCUS ON MACRO DECISIONS:
✓ Cost-benefit analysis (what did they gain vs sacrifice?)
✓ Wave management (push, freeze, recall)
✓ Objective trading (give up X to take Y)
✓ Post-event sequencing (what to do after the play)
✓ Timing windows (when to move based on distance and summoner spells)

RESPONSE STRUCTURE (100 words max):
1. What happened + player's involvement (1-2 sentences)
2. Cost-benefit analysis OR rotation analysis (1-2 sentences)
3. ONE actionable tip for similar situations (1 sentence)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOOD EXAMPLES - WHEN PLAYER PARTICIPATED:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Darius assisted Diana in securing a kill on Gnar in mid lane at 11 minutes. While the kill netted your team 268 gold and removed Gnar from the map temporarily, Darius left a large top wave crashing into his tower, sacrificing approximately 120 gold and experience. Given the team was already 3600 gold ahead, the better decision would have been to finish pushing the top wave, then recall to buy items. Against a losing opponent, prioritize your own gold and experience leads over low-value kills."

"Your team secured the Ocean Dragon at 16 minutes while you were 9500 units away in top lane. Since you couldn't reach the objective even with Teleport on cooldown, staying top to push the wave was the optimal play. This forced the enemy top laner to choose between helping at Dragon or losing tower plates. After your team secures an objective while you're split pushing, immediately look to back and regroup for the next objective timer."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOOD EXAMPLES - WHEN PLAYER DID NOT PARTICIPATE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"The Rift Herald was secured at top river, 10,500 units from where you were pushing bottom lane. With Teleport on cooldown and your team already securing the objective, you made the correct decision to continue pushing. This created map pressure and forced the enemy bot laner to stay in lane. When objectives are being taken without you and you can't rotate in time, always look to apply pressure elsewhere to prevent enemy rotations."

"A teamfight broke out mid lane, 7600 units from your bot lane position. With Flash and Teleport both available, you should have immediately started rotating toward the fight. Even though the fight may end before you arrive, positioning yourself closer creates pressure and allows you to help secure follow-up objectives like towers or Dragon. Track teamfight patterns and begin moving 10-15 seconds before fights typically start."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BAD EXAMPLES - NEVER DO THIS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Use your ultimate to dash to the fight" ← WRONG: Mentions abilities
"Chain your Q into E combo" ← WRONG: Discusses mechanics
"Your passive would have helped" ← WRONG: References kit
"Execute with ultimate" ← WRONG: Ability-focused
"Flash in and use your combo" ← WRONG: Tactical execution"""
        }]
        
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_prompt}]
                }
            ],
            "system": system_prompt,
            "inferenceConfig": {
                "max_new_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
                "top_p": 0.85,
                "top_k": 50
            }
        }
        
        try:
            response = bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            
            if 'output' in response_body and 'message' in response_body['output']:
                content = response_body['output']['message'].get('content', [])
                if content:
                    summary = content[0].get('text', '').strip()
                    clean_summary = self._clean_response(summary)
                    
                    # Validate response
                    validated = self._validate_response(clean_summary, champion)
                    
                    if not validated:
                        self.rejected_count += 1
                        print(f"❌ REJECTED response for {champion} (contained ability references)")
                        return ""
                    
                    return validated
            
            return ""
            
        except Exception as e:
            print(f"❌ Bedrock error: {str(e)}")
            return ""
    
    def _validate_response(self, text: str, champion: str) -> str:
        """Validate response doesn't contain ability hallucinations"""
        
        if not text or len(text) < 20:
            return ""
        
        text_lower = ' ' + text.lower() + ' '
        
        # Check for red flags
        for red_flag in self.ABILITY_RED_FLAGS:
            if red_flag in text_lower:
                # Check if it's in an allowed context
                is_allowed = False
                for allowed in self.ALLOWED_TERMS:
                    if allowed in text_lower:
                        # Additional check: make sure the red flag isn't near the allowed term
                        allowed_pos = text_lower.find(allowed)
                        red_pos = text_lower.find(red_flag)
                        if abs(allowed_pos - red_pos) < 20:  # Within 20 characters
                            is_allowed = True
                            break
                
                if not is_allowed:
                    print(f"⚠️ Validation failed: Found '{red_flag.strip()}' in response")
                    return ""
        
        return text
    
    def _clean_response(self, text: str) -> str:
        """Clean response of formatting artifacts"""
        # Remove XML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        # Normalize whitespace
        text = ' '.join(text.split()).strip()
        
        return text if len(text) > 15 else ""


def lambda_handler(event, context):
    """Enhanced Lambda handler with better metrics"""
    
    print("🚀 Enhanced Bedrock Coaching Generator v2.0")
    print(f"Event keys: {event.keys() if isinstance(event, dict) else 'Not a dict'}")
    
    try:
        # Parse input
        if 'body' in event and isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event
        
        match_id = body.get('match_id')
        puuid = body.get('puuid')
        player_folder = body.get('player_folder')
        
        # Reconstruct player_folder if missing
        if not player_folder and 'events' in body and body['events']:
            events_list = body['events']
            if isinstance(events_list, dict) and 'Items' in events_list:
                events_list = events_list['Items']
            
            if events_list:
                first_event = events_list[0]
                pc_str = first_event.get('player_context', {})
                if isinstance(pc_str, dict) and 'S' in pc_str:
                    pc_str = pc_str['S']
                
                extractor_temp = RobustContextExtractor({}, {})
                player_context = extractor_temp._safe_json_parse(pc_str, {})
                
                summoner_name = player_context.get('summoner_name', '')
                summoner_tag = player_context.get('summoner_tag', '')
                
                if summoner_name and summoner_tag:
                    player_folder = f"{summoner_name}_{summoner_tag}"
        
        if not all([match_id, puuid, player_folder]):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Missing fields - match_id={match_id}, puuid={puuid}, player_folder={player_folder}'})
            }
        
        # Load timeline and match data
        s3_bucket = 'lol-training-matches-150k'
        base_path = f'raw-matches/{player_folder}/{match_id}'
        
        try:
            timeline_obj = s3_client.get_object(Bucket=s3_bucket, Key=f'{base_path}/timeline-data.json')
            timeline_data = json.loads(timeline_obj['Body'].read())
            
            match_obj = s3_client.get_object(Bucket=s3_bucket, Key=f'{base_path}/match-data.json')
            match_data = json.loads(match_obj['Body'].read())
        except Exception as e:
            return {'statusCode': 404, 'body': json.dumps({'error': f'S3 load failed: {str(e)}'})}
        
        # Initialize components
        context_extractor = RobustContextExtractor(timeline_data, match_data)
        generator = EnhancedBedrockCoachingGenerator()
        
        # Process events
        raw_events = body.get('events', [])
        if isinstance(raw_events, dict) and 'Items' in raw_events:
            raw_events = raw_events['Items']
        
        summaries_generated = 0
        errors = []
        
        print(f"📝 Processing {len(raw_events[:15])} events...")
        
        for idx, event_item in enumerate(raw_events[:15], 1):
            try:
                print(f"\n{'='*60}")
                print(f"Event {idx}/15: {event_item.get('event_type', {}).get('S', 'UNKNOWN')}")
                print(f"{'='*60}")
                
                # Parse event
                event = {
                    'event_id': event_item.get('event_id', {}).get('S') if isinstance(event_item.get('event_id'), dict) else event_item.get('event_id'),
                    'timestamp_minutes': float(event_item.get('timestamp_minutes', {}).get('N', 0) if isinstance(event_item.get('timestamp_minutes'), dict) else event_item.get('timestamp_minutes', 0)),
                    'event_type': event_item.get('event_type', {}).get('S') if isinstance(event_item.get('event_type'), dict) else event_item.get('event_type'),
                    'event_details': event_item.get('event_details', {}).get('S') if isinstance(event_item.get('event_details'), dict) else event_item.get('event_details'),
                    'player_context': event_item.get('player_context', {}).get('S') if isinstance(event_item.get('player_context'), dict) else event_item.get('player_context'),
                    'context': event_item.get('context', {}).get('S') if isinstance(event_item.get('context'), dict) else event_item.get('context'),
                    'puuid': puuid
                }
                
                # Generate summary
                summary = generator.generate_event_summary(event, context_extractor)
                
                if summary and len(summary) > 15:
                    summaries_table.put_item(Item={
                        'event_id': event['event_id'],
                        'summary_type': 'enhanced_v2',
                        'match_id': match_id,
                        'puuid': puuid,
                        'summary_text': summary,
                        'generated_at': int(datetime.utcnow().timestamp()),
                        'ttl': int((datetime.utcnow() + timedelta(days=7)).timestamp()),
                        'model_version': 'nova-pro-v1-macro-focused'
                    })
                    summaries_generated += 1
                    print(f"✅ Generated: {summary[:80]}...")
                else:
                    print(f"⚠️ No valid summary generated (likely rejected for ability mentions)")
                    
            except Exception as e:
                error_msg = f"{event_item.get('event_id')}: {str(e)}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
        
        # Final statistics
        rejection_rate = (generator.rejected_count / max(generator.total_count, 1)) * 100
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'summaries_generated': summaries_generated,
                'events_processed': len(raw_events[:15]),
                'rejection_rate': f"{rejection_rate:.1f}%",
                'rejections': generator.rejected_count,
                'errors': errors if errors else None
            })
        }
        
    except Exception as e:
        print(f"💥 Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}