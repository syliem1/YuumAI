import json
import boto3
import os
import requests
import time

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
session = requests.Session()

# .env variables
RIOT_API_KEY = os.environ['RIOT_API_KEY']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
dynamo_table = dynamodb.Table(DYNAMODB_TABLE_NAME)
TIME_PER_REQUEST = 1.5

def fetch_and_process_match(match_id, puuid):
    ''' Gets a single match from a player and saves it to s3 '''

    try:
        # constants
        DETAIL_URL = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
        PARAMS = {'api_key': RIOT_API_KEY}
        RETRY_TIMER = 15

        response = session.get(DETAIL_URL, params=PARAMS)
        response.raise_for_status()
        match_data = response.json()

        # filter non-ranked matches
        queue_id = match_data.get('info', {}).get('queueId', 0)
        if queue_id not in [420, 440]:
            return None

        # filter short matches
        game_duration = match_data.get('info', {}).get('gameDuration', 0)
        if game_duration < 900:
            return None

        # save to s3
        s3_key = f"raw-matches/{puuid}/{match_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(match_data)
        )
        #print(f"Successfully saved match {match_id}")
        
        # return all match participants for recursive iteration
        return match_data.get('metadata', {}).get('participants', [])

    except requests.exceptions.HTTPError as e:

        # hit rate limit -> should retry
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Rate limit hit fetching match details. Waiting for {retry_after} seconds.")
            time.sleep(retry_after)
            return fetch_and_process_match(match_id, puuid)
        else:
            print(f"HTTP Error fetching match {match_id}: {e}")
            return None
    except Exception as e:
        print(f"An unexpected error occurred processing match {match_id}: {e}")
        return None

def lambda_handler(event, context):
    ''' Processes 1 puuid from the SQS queue, fetches history, recursively adds new found puuids '''

    # load data from SQS queue
    record = event['Records'][0]
    payload = json.loads(record['body'])
    puuid = payload['puuid']
    start_index = payload.get('start_index',0)

    if start_index == 0:    # check only on first iteration
        try:
            response = dynamo_table.get_item(Key={'puuid': puuid})
            if 'Item' in response:
                print(f"Skipping already processed puuid: {puuid}")
                return

            # immediately update as marked
            dynamo_table.put_item(Item={'puuid': puuid, 'processedAt': int(time.time())})  
        except Exception as e:
            print(f"Error checking DynamoDB for puuid {puuid}: {e}")
            raise e

    # fetch match history for this single puuid
    year_in_seconds = (365 * 24 * 60 * 60)
    start_time = int(time.time()) - year_in_seconds
    new_puuids_to_queue = set()

    # continue while this specific individual player match id queue is full
    try:
        ids_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        params = {'startTime': start_time, 'start': start_index, 'count': 100, 'api_key': RIOT_API_KEY}
        
        response = session.get(ids_url, params=params)
        response.raise_for_status()
        match_ids = response.json()
        
        print(f"Fetched {len(match_ids)} match IDs for {puuid} at index {start_index}")

        for match_id in match_ids:
            participants = fetch_and_process_match(match_id, puuid)
            if participants:
                new_puuids_to_queue.update(participants)
            time.sleep(TIME_PER_REQUEST)

        # 
        if len(match_ids) == 100:
            next_index = start_index + 100
            print(f"Re-queueing job for {puuid} at next index {next_index}")
            sqs_client.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps({'puuid': puuid, 'start_index': next_index}),
                MessageGroupId='riot-api-processor'
            )

    except Exception as e:
        print(f"Error processing match list for {puuid}: {e}")

    # add new puuids to SQS queue
    for new_puuid in new_puuids_to_queue:

        # anti-reflexive check
        if new_puuid == puuid: 
            continue
        
        # don't queue dupes
        response = dynamo_table.get_item(Key={'puuid': new_puuid})
        if 'Item' not in response:
            sqs_client.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps({'puuid': new_puuid}),
                MessageGroupId='riot-api-processor'
            )
    
    print(f"Successfully completed processing for {puuid}.")
    return {'statusCode': 200}