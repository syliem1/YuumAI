"""
API Gateway handler for timeline feature
Provides endpoints for frontend to retrieve and interact with timeline events

WELCOME TO THE API ROUTE NEXUS!!!!
"""

import json
import boto3
import os  
from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')

try:
    EVENTS_TABLE_NAME = os.environ['EVENTS_TABLE_NAME']
    SUMMARIES_TABLE_NAME = os.environ['SUMMARIES_TABLE_NAME']
    QUESTIONS_TABLE_NAME = os.environ['QUESTIONS_TABLE_NAME']
    METADATA_TABLE_NAME = os.environ['METADATA_TABLE_NAME']

    events_table = dynamodb.Table(EVENTS_TABLE_NAME)
    summaries_table = dynamodb.Table(SUMMARIES_TABLE_NAME)
    questions_table = dynamodb.Table(QUESTIONS_TABLE_NAME)
    metadata_table = dynamodb.Table(METADATA_TABLE_NAME)

except KeyError as e:
    print(f"[ERROR] Missing required environment variable: {str(e)}")
    print("Please redeploy the Lambda with the correct environment variables set.")
    events_table = dynamodb.Table('placeholder-events')
    summaries_table = dynamodb.Table('placeholder-summaries')
    questions_table = dynamodb.Table('placeholder-questions')
    metadata_table = dynamodb.Table('placeholder-metadata')
# --------------------------------------------------------

# Bedrock configuration
BEDROCK_MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0'


class DecimalEncoder(json.JSONEncoder):
    """Helper to convert DynamoDB Decimals to JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    """
    Routes API requests to appropriate handlers
    """
    print(f"API Gateway hit.")
    try:
        # Try v2.0 (HTTP API) payload first
        http_method = event['requestContext']['http']['method']
        path = event['requestContext']['http']['path']
    except KeyError:
        try:
            # Fallback to v1.0 (REST API) payload
            http_method = event['httpMethod']
            path = event['path']
        except KeyError:
            print("[ERROR] Invalid event payload. Does not match API Gateway v2.0 or v1.0 format.")
            print(json.dumps(event)) # Log the unexpected event structure
            return cors_response(400, {'error': 'Invalid event payload'})
    # ----------------------------------------------------------
    
    print(f"API request: {http_method} {path}")
    
    # CORS preflight
    if http_method == 'OPTIONS':
        return cors_response(200, {})
    
    try:
        if path == '/timeline/events' and http_method == 'GET':
            return get_timeline_events(event)
        
        elif path == '/timeline/events/summary' and http_method == 'POST':
            return get_event_summary(event)
        
        elif path == '/timeline/ask' and http_method == 'POST':
            return answer_question(event)
        
        elif path == '/timeline/player/matches' and http_method == 'GET':
            return get_player_matches(event)
        
        elif path == '/timeline/batch-process' and http_method == 'POST':
            return trigger_batch_processing(event)
        
        else:
            return cors_response(404, {'error': 'Endpoint not found'})
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return cors_response(500, {'error': str(e)})


def get_timeline_events(event):
    """
    GET /timeline/events?match_id=XXX&puuid=YYY
    Returns critical events for a specific match
    """
    
    params = event.get('queryStringParameters', {})
    if not params:
        return cors_response(400, {'error': 'Missing query parameters'})
    
    match_id = params.get('match_id')
    puuid = params.get('puuid')
    
    if not match_id or not puuid:
        return cors_response(400, {'error': 'match_id and puuid required'})
    
    print(f"Fetching events for match {match_id}, player {puuid}")
    
    # Query events
    response = events_table.query(
        IndexName='match-impact-index',
        KeyConditionExpression=Key('match_id').eq(match_id),
        FilterExpression=Attr('puuid').eq(puuid),
        ScanIndexForward=False  # Sort by impact score descending
    )
    
    events = response.get('Items', [])
    
    # Get cached summaries
    event_data = []
    for event_item in events:
        event_obj = {
            'event_id': event_item['event_id'],
            'timestamp_minutes': float(event_item['timestamp_minutes']),
            'event_type': event_item['event_type'],
            'impact_score': int(event_item['impact_score']),
            'game_state': event_item.get('game_state', 'mid'),
            'event_details': json.loads(event_item.get('event_details', '{}')),
            'context': json.loads(event_item.get('context', '{}')),
            'has_summary': False,
            'summary': None
        }
        
        # Check for cached summary
        summary_response = summaries_table.get_item(
            Key={
                'event_id': event_item['event_id'],
                'summary_type': 'basic'
            }
        )
        
        if 'Item' in summary_response:
            event_obj['has_summary'] = True
            event_obj['summary'] = summary_response['Item'].get('summary_text')
        
        event_data.append(event_obj)
    
    return cors_response(200, {
        'match_id': match_id,
        'puuid': puuid,
        'events': event_data,
        'total_events': len(event_data)
    })


def get_event_summary(event):
    """
    POST /timeline/events/summary
    Body: { event_id, match_id, puuid, player_context }
    Generates or retrieves AI summary for a specific event
    """
    
    # v2.0 payload body is just a string, must be parsed
    body_str = event.get('body', '{}')
    body = json.loads(body_str) if body_str else {}
    
    event_id = body.get('event_id')
    match_id = body.get('match_id')
    puuid = body.get('puuid')
    player_context = body.get('player_context', {})
    
    if not event_id or not match_id:
        return cors_response(400, {'error': 'event_id and match_id required'})
    
    print(f"Getting summary for event {event_id}")
    
    # Check cache first
    cache_response = summaries_table.get_item(
        Key={
            'event_id': event_id,
            'summary_type': 'basic'
        }
    )
    
    if 'Item' in cache_response:
        print("Cache hit")
        return cors_response(200, {
            'event_id': event_id,
            'summary': cache_response['Item']['summary_text'],
            'cached': True,
            'generated_at': int(cache_response['Item']['generated_at'])
        })
    
    # Cache miss - generate new summary
    print("Cache miss - generating new summary")
    
    # Get event details
    event_response = events_table.get_item(
        Key={'match_id': match_id, 'event_id': event_id}
    )
    
    if 'Item' not in event_response:
        return cors_response(404, {'error': 'Event not found'})
    
    event_data = event_response['Item']
    
    try:
        from lambda_bedrock_summary_generator.lambda_function import BedrockSummaryGenerator
    except ImportError:
        print("[ERROR] Could not import BedrockSummaryGenerator. Make sure it's in a shared layer.")
        return cors_response(500, {'error': 'Summary generator logic not found'})

    generator = BedrockSummaryGenerator()
    summary = generator.generate_event_summary(event_data, player_context)
    
    # Cache the result
    from datetime import timedelta
    ttl = int((datetime.utcnow() + timedelta(days=7)).timestamp())
    
    summaries_table.put_item(Item={
        'event_id': event_id,
        'summary_type': 'basic',
        'match_id': match_id,
        'puuid': puuid,
        'summary_text': summary,
        'generated_at': int(datetime.utcnow().timestamp()),
        'ttl': ttl,
        'model_used': BEDROCK_MODEL_ID
    })
    
    return cors_response(200, {
        'event_id': event_id,
        'summary': summary,
        'cached': False,
        'generated_at': int(datetime.utcnow().timestamp())
    })


def answer_question(event):
    """
    POST /timeline/ask
    Body: { event_id, match_id, puuid, question, match_context }
    Answers user questions about specific events using Bedrock
    """
    
    # v2.0 payload body is just a string, must be parsed
    body_str = event.get('body', '{}')
    body = json.loads(body_str) if body_str else {}
    
    event_id = body.get('event_id')
    match_id = body.get('match_id')
    puuid = body.get('puuid')
    question = body.get('question')
    match_context = body.get('match_context', {})
    
    if not all([event_id, match_id, puuid, question]):
        return cors_response(400, {
            'error': 'event_id, match_id, puuid, and question required'
        })
    
    # Rate limiting: check question count
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
    
    print(f"Answering question for event {event_id}: {question}")
    
    # Get event details
    event_response = events_table.get_item(
        Key={'match_id': match_id, 'event_id': event_id}
    )
    
    if 'Item' not in event_response:
        return cors_response(404, {'error': 'Event not found'})
    
    event_data = event_response['Item']
    
    # Build prompt for question answering
    prompt = build_qa_prompt(event_data, question, match_context)
    
    # Call Bedrock
    request_body = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 250,
        "temperature": 0.7
    }
    
    try:
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract from OpenAI response format
        if 'choices' in response_body and len(response_body['choices']) > 0:
            answer = response_body['choices'][0]['message']['content']
        else:
            answer = "I apologize, but I couldn't generate an answer at this time."
            
    except Exception as e:
        print(f"Bedrock error: {str(e)}")
        answer = "I apologize, but I couldn't generate an answer at this time. Please try again."
    
    # Save question and answer
    question_id = f"{event_id}_{int(datetime.utcnow().timestamp())}"
    from datetime import timedelta
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    questions_table.put_item(Item={
        'question_id': question_id,
        'event_id': event_id,
        'match_id': match_id,
        'puuid': puuid,
        'question': question,
        'answer': answer,
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


def get_player_matches(event):
    """
    GET /timeline/player/matches?puuid=XXX
    Returns all processed matches for a player
    """
    
    params = event.get('queryStringParameters', {})
    puuid = params.get('puuid')
    
    if not puuid:
        return cors_response(400, {'error': 'puuid required'})
    
    # Query metadata table
    response = metadata_table.query(
        KeyConditionExpression=Key('puuid').eq(puuid),
        ScanIndexForward=False,  # Most recent first
        Limit=100
    )
    
    matches = response.get('Items', [])
    
    match_data = []
    for match in matches:
        match_data.append({
            'match_id': match['match_id'],
            'processed_timestamp': int(match['processed_timestamp']),
            'events_count': int(match.get('events_count', 0)),
            'processing_status': match.get('processing_status', 'unknown')
        })
    
    return cors_response(200, {
        'puuid': puuid,
        'matches': match_data,
        'total_matches': len(match_data)
    })


def trigger_batch_processing(event):
    """
    POST /timeline/batch-process
    Body: { match_ids, puuid }
    Triggers Step Functions workflow for batch processing
    """
    
    # v2.0 payload body is just a string, must be parsed
    body_str = event.get('body', '{}')
    body = json.loads(body_str) if body_str else {}
    
    match_ids = body.get('match_ids', [])
    puuid = body.get('puuid')
    
    if not match_ids or not puuid:
        return cors_response(400, {'error': 'match_ids and puuid required'})
    
    # Trigger Step Functions
    stepfunctions = boto3.client('stepfunctions')
    state_machine_arn = os.environ.get('STEP_FUNCTIONS_ARN')
    
    if not state_machine_arn:
        return cors_response(500, {'error': 'Step Functions not configured'})
    
    execution_name = f"batch_{puuid}_{int(datetime.utcnow().timestamp())}"
    
    try:
        response = stepfunctions.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps({
                'match_ids': match_ids,
                'puuid': puuid,
                'batch_mode': True
            })
        )
        
        return cors_response(200, {
            'execution_arn': response['executionArn'],
            'execution_name': execution_name,
            'match_count': len(match_ids)
        })
        
    except Exception as e:
        print(f"Step Functions error: {str(e)}")
        return cors_response(500, {'error': f'Failed to start batch processing: {str(e)}'})


def build_qa_prompt(event: Dict, question: str, match_context: Dict) -> str:
    """
    Builds prompt for question answering
    """
    
    event_details = json.loads(event.get('event_details', '{}'))
    context = json.loads(event.get('context', '{}'))
    
    prompt = f"""You are an expert League of Legends coach answering a player's question about a specific moment in their ranked match.

**Event Context:**
- Type: {event['event_type']}
- Time: {float(event['timestamp_minutes']):.1f} minutes
- Game State: {event.get('game_state', 'mid')}
- Impact Score: {int(event['impact_score'])}/100
- Gold Difference: {context.get('gold_difference', 0)}g

**Event Details:**
{json.dumps(event_details, indent=2)}

**Match Context:**
{json.dumps(match_context, indent=2)}

**Player Question:** {question}

Provide a helpful, specific answer in 2-3 sentences. Focus on:
1. Directly answering their question
2. Providing ONE actionable tip they can apply

Be conversational but professional. Under 100 words."""

    return prompt


def cors_response(status_code: int, body: dict) -> dict:
    """
    Adds CORS headers to response
    """
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