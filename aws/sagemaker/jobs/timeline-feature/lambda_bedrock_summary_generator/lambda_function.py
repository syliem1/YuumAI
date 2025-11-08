# lambda_bedrock_summary_generator/lambda_function.py
"""
Generates AI summaries for critical timeline events using AWS Bedrock
Can be triggered by Step Functions or direct API calls
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List

dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

# DynamoDB tables
events_table = dynamodb.Table('lol-timeline-events')
summaries_table = dynamodb.Table('lol-timeline-ai-summaries')
metadata_table = dynamodb.Table('lol-player-timeline-metadata')

# Bedrock configuration
BEDROCK_MODEL_ID = 'openai.gpt-oss-20b-1:0' 
MAX_TOKENS = 300
TEMPERATURE = 0.7


class BedrockSummaryGenerator:
    """
    Generates AI-powered summaries and insights for timeline events
    """
    
    def __init__(self):
        self.bedrock = bedrock_runtime
        self.model_id = BEDROCK_MODEL_ID
    
    def generate_event_summary(self, event: Dict, player_context: Dict) -> str:
    """
    Generates concise AI summary for a critical moment
    """

    system_prompt = """You are an expert League of Legends coach analyzing a key moment.
Write 2-3 sentences analyzing the event.
Be direct, constructive, and actionable.
Keep the entire response under 70 words."""
    
    prompt = self._build_event_prompt(event, player_context)
    request_body = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE
    }
    
    try:
        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract the content from OpenAI response format
        if 'choices' in response_body and len(response_body['choices']) > 0:
            summary = response_body['choices'][0]['message']['content'].strip()
        else:
            # Fallback if response structure is different
            print(f"Unexpected response structure: {response_body}")
            return self._generate_fallback_summary(event)
        
        return summary
        
    except Exception as e:
        print(f"Bedrock error: {str(e)}")
        import traceback
        traceback.print_exc()
        return self._generate_fallback_summary(event)
    
    def _build_event_prompt(self, event: Dict, player_context: Dict) -> str:
        """
        Builds optimized prompt for event analysis
        """
        event_type = event['event_type']
        timestamp = event['timestamp_minutes']
        impact = event['impact_score']
        game_state = event.get('game_state', 'mid')
        
        event_details = json.loads(event.get('event_details', '{}'))
        context = json.loads(event.get('context', '{}'))
        
        # Build context-aware prompt based on event type
        if event_type == 'KILL':
            return self._build_kill_prompt(
                event_details, timestamp, game_state, context, player_context
            )
        elif event_type == 'OBJECTIVE':
            return self._build_objective_prompt(
                event_details, timestamp, game_state, context, player_context
            )
        elif event_type == 'TEAMFIGHT':
            return self._build_teamfight_prompt(
                event_details, timestamp, game_state, context, player_context
            )
        elif event_type == 'STRUCTURE':
            return self._build_structure_prompt(
                event_details, timestamp, game_state, context, player_context
            )
        else:
            return self._build_generic_prompt(
                event, timestamp, game_state, context, player_context
            )
    
    def _build_kill_prompt(self, details: Dict, timestamp: float, 
                          game_state: str, context: Dict, player_ctx: Dict) -> str:
        """
        Specialized prompt for kill events
        """
        player_role = details.get('player_role', 'team_involved')
        killer = details.get('killer', 'Unknown')
        victim = details.get('victim', 'Unknown')
        shutdown = details.get('shutdown_gold', 0)
        gold_diff = context.get('gold_difference', 0)
        gold_state = context.get('gold_state', 'even')
        
        champion = player_ctx.get('champion', 'your champion')
        position = player_ctx.get('position', 'your role')
        
        if player_role == 'killer':
            base_prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**Critical Kill at {timestamp:.1f} minutes ({game_state} game)**

Player Action: You ({champion} - {position}) killed {victim}
Shutdown Gold: {shutdown}g
Team Gold State: {gold_state} ({gold_diff:+d}g)
Assistants: {', '.join(details.get('assistants', [])) if details.get('assistants') else 'Solo kill'}

Provide a 2-3 sentence analysis:
1. Why this kill was significant for the game outcome
2. ONE specific tip to replicate this success or improve the execution

Be direct and actionable. Under 80 words."""

        elif player_role == 'victim':
            base_prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**Critical Death at {timestamp:.1f} minutes ({game_state} game)**

Player Action: You ({champion} - {position}) were killed by {killer}
Gold Lost: {shutdown}g bounty
Team Gold State: {gold_state} ({gold_diff:+d}g)
Enemy Assistants: {len(details.get('assistants', []))} players involved

Provide a 2-3 sentence analysis:
1. What likely went wrong in this situation
2. ONE specific way to avoid this in future games

Be constructive and actionable. Under 80 words."""

        else:
            base_prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**Team Fight Kill at {timestamp:.1f} minutes ({game_state} game)**

Action: {killer} killed {victim}
Team Gold State: {gold_state} ({gold_diff:+d}g)
Your Champion: {champion} ({position})

Provide a 2-3 sentence analysis:
1. How this kill impacted the game state
2. ONE tip for how you could have influenced this situation

Be direct and actionable. Under 80 words."""

        return base_prompt
    
    def _build_objective_prompt(self, details: Dict, timestamp: float,
                                game_state: str, context: Dict, player_ctx: Dict) -> str:
        """
        Specialized prompt for objective events
        """
        objective = details.get('objective_type', 'OBJECTIVE')
        securing_team = details.get('securing_team', 'UNKNOWN')
        gold_diff = context.get('gold_difference', 0)
        gold_state = context.get('gold_state', 'even')
        
        champion = player_ctx.get('champion', 'your champion')
        position = player_ctx.get('position', 'your role')
        
        if securing_team == 'PLAYER_TEAM':
            prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**{objective} Secured at {timestamp:.1f} minutes ({game_state} game)**

Your Team: Successfully secured {objective}
Team Gold State Before: {gold_state} ({gold_diff:+d}g)
Your Champion: {champion} ({position})

Provide a 2-3 sentence analysis:
1. Why securing this objective was crucial at this timing
2. ONE tip to maintain the advantage gained from this objective

Be direct and actionable. Under 80 words."""

        else:
            prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**{objective} Lost at {timestamp:.1f} minutes ({game_state} game)**

Enemy Team: Secured {objective}
Team Gold State Before: {gold_state} ({gold_diff:+d}g)
Your Champion: {champion} ({position})

Provide a 2-3 sentence analysis:
1. Why losing this objective was impactful
2. ONE specific action your team could have taken to contest or trade

Be constructive and actionable. Under 80 words."""

        return prompt
    
    def _build_teamfight_prompt(self, details: Dict, timestamp: float,
                               game_state: str, context: Dict, player_ctx: Dict) -> str:
        """
        Specialized prompt for teamfight events
        """
        outcome = details.get('outcome', 'UNKNOWN')
        player_kills = details.get('player_team_kills', 0)
        enemy_kills = details.get('enemy_team_kills', 0)
        duration = details.get('duration_seconds', 0)
        gold_diff = context.get('gold_difference', 0)
        gold_state = context.get('gold_state', 'even')
        
        champion = player_ctx.get('champion', 'your champion')
        position = player_ctx.get('position', 'your role')
        
        prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**Major Teamfight at {timestamp:.1f} minutes ({game_state} game)**

Outcome: Your team {outcome} ({player_kills} kills vs {enemy_kills} deaths)
Duration: {duration} seconds
Team Gold State Before: {gold_state} ({gold_diff:+d}g)
Your Champion: {champion} ({position})

Provide a 2-3 sentence analysis:
1. What made this teamfight decisive for the game
2. ONE specific tip for your role in teamfights at this stage

Be direct and actionable. Under 80 words."""

        return prompt
    
    def _build_structure_prompt(self, details: Dict, timestamp: float,
                               game_state: str, context: Dict, player_ctx: Dict) -> str:
        """
        Specialized prompt for structure events
        """
        structure = details.get('structure_type', 'STRUCTURE')
        lane = details.get('lane', 'UNKNOWN')
        destroying_team = details.get('destroying_team', 'UNKNOWN')
        gold_diff = context.get('gold_difference', 0)
        gold_state = context.get('gold_state', 'even')
        
        champion = player_ctx.get('champion', 'your champion')
        position = player_ctx.get('position', 'your role')
        
        if destroying_team == 'PLAYER_TEAM':
            prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**{structure} Destroyed at {timestamp:.1f} minutes ({game_state} game)**

Your Team: Destroyed {lane} lane {structure}
Team Gold State: {gold_state} ({gold_diff:+d}g)
Your Champion: {champion} ({position})

Provide a 2-3 sentence analysis:
1. How destroying this structure opens up the map
2. ONE specific way to capitalize on this advantage

Be direct and actionable. Under 80 words."""

        else:
            prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**{structure} Lost at {timestamp:.1f} minutes ({game_state} game)**

Enemy Team: Destroyed your {lane} lane {structure}
Team Gold State: {gold_state} ({gold_diff:+d}g)
Your Champion: {champion} ({position})

Provide a 2-3 sentence analysis:
1. How losing this structure impacts map control
2. ONE defensive strategy to prevent further losses

Be constructive and actionable. Under 80 words."""

        return prompt
    
    def _build_generic_prompt(self, event: Dict, timestamp: float,
                             game_state: str, context: Dict, player_ctx: Dict) -> str:
        """
        Generic fallback prompt
        """
        event_type = event.get('event_type', 'EVENT')
        impact = event.get('impact_score', 0)
        
        prompt = f"""You are an expert League of Legends coach analyzing a ranked match.

**Critical {event_type} at {timestamp:.1f} minutes ({game_state} game)**

Impact Score: {impact}/100
Game State: {game_state}

Provide a 2-3 sentence analysis:
1. Why this moment was significant
2. ONE actionable tip for improvement

Be direct and under 80 words."""

        return prompt
    
    def _generate_fallback_summary(self, event: Dict) -> str:
        """
        Rule-based fallback if Bedrock fails
        """
        event_type = event.get('event_type', 'EVENT')
        timestamp = event.get('timestamp_minutes', 0)
        impact = event.get('impact_score', 0)
        
        return f"Critical {event_type} at {timestamp:.1f} minutes with impact score {impact}. This was a key moment in the match that significantly affected the outcome."


def lambda_handler(event, context):
    """
    Generates AI summaries for timeline events
    Can be invoked by:
    1. Step Functions (batch processing)
    2. API Gateway (on-demand)
    """
    
    print("Bedrock Summary Generator Lambda invoked")
    
    try:
        # Parse input
        if 'body' in event:
            # API Gateway invocation
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            # Step Functions invocation
            body = event
        
        match_id = body.get('match_id')
        puuid = body.get('puuid')
        event_ids = body.get('event_ids', [])  # Optional: specific events to process
        batch_mode = body.get('batch_mode', False)
        
        print(f"Processing match {match_id} for player {puuid}")
        
        # Get events to process
        if event_ids:
            events_to_process = []
            for event_id in event_ids:
                response = events_table.get_item(
                    Key={'match_id': match_id, 'event_id': event_id}
                )
                if 'Item' in response:
                    events_to_process.append(response['Item'])
        else:
            # Get all events for this match
            response = events_table.query(
                IndexName='match-impact-index',
                KeyConditionExpression='match_id = :match_id',
                ExpressionAttributeValues={':match_id': match_id},
                ScanIndexForward=False  # Descending order by impact score
            )
            events_to_process = response.get('Items', [])
        
        # In batch mode, only process top 5 events
        if batch_mode:
            events_to_process = sorted(
                events_to_process, 
                key=lambda x: x.get('impact_score', 0), 
                reverse=True
            )[:5]
        
        print(f"Processing {len(events_to_process)} events")
        
        # Get player context (champion, position, etc.)
        # This should come from match data or be passed in
        player_context = body.get('player_context', {
            'champion': 'Champion',
            'position': 'Role'
        })
        
        # Generate summaries
        generator = BedrockSummaryGenerator()
        summaries_generated = 0
        
        for event in events_to_process:
            event_id = event['event_id']
            
            # Check if summary already exists (cache hit)
            cache_check = summaries_table.get_item(
                Key={
                    'event_id': event_id,
                    'summary_type': 'basic'
                }
            )
            
            if 'Item' in cache_check:
                print(f"Cache hit for event {event_id}")
                summaries_generated += 1
                continue
            
            # Generate new summary
            print(f"Generating summary for event {event_id}")
            summary = generator.generate_event_summary(event, player_context)
            
            # Save to cache
            ttl = int((datetime.utcnow() + timedelta(days=7)).timestamp())
            
            summaries_table.put_item(Item={
                'event_id': event_id,
                'summary_type': 'basic',
                'match_id': match_id,
                'puuid': puuid,
                'summary_text': summary,
                'generated_at': int(datetime.utcnow().timestamp()),
                'ttl': ttl,
                'model_used': BEDROCK_MODEL_ID,
                'tokens_used': MAX_TOKENS  # Approximate
            })
            
            summaries_generated += 1
            print(f"✓ Summary generated and cached for {event_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Summaries generated successfully',
                'match_id': match_id,
                'summaries_generated': summaries_generated,
                'events_processed': len(events_to_process)
            })
        }
        
    except Exception as e:
        print(f"Error generating summaries: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }