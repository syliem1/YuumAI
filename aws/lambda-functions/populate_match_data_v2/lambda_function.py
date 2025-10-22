import json
import boto3
import os
import requests
import time
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
session = requests.Session()

# test comment

# .env variables
RIOT_API_KEY = os.environ['RIOT_API_KEY']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
dynamo_table = dynamodb.Table(DYNAMODB_TABLE_NAME)

TIME_PER_REQUEST = 1.3
RETRY_TIMER = 15


def delete_sqs_message(receipt_handle, riot_id_key):
    """Delete message from SQS queue"""
    try:
        sqs_client.delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle
        )
        print(f"Deleted message for {riot_id_key} from queue.")
    except Exception as e:
        print(f"Error deleting message for {riot_id_key}: {e}")


def unmark_player_as_processed(riot_id_key):
    """Remove player from DynamoDB to allow reprocessing"""
    try:
        dynamo_table.delete_item(Key={'riotId': riot_id_key})
        print(f"Unmarked {riot_id_key} as processed due to API error.")
    except Exception as e:
        print(f"Error unmarking player {riot_id_key}: {e}")


def get_puuid_by_riot_id(game_name, tag_line):
    ''' fetches puuid using a player's game name and tag line '''

    try:
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        params = {'api_key': RIOT_API_KEY}
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('puuid')

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Rate limit hit getting puuid. Waiting {retry_after} seconds.")
            time.sleep(retry_after)
            return get_puuid_by_riot_id(game_name, tag_line)
        elif e.response.status_code == 401:
            print(f"401 Unauthorized error getting puuid for {game_name}#{tag_line}: {e}")
            raise 
        print(f"HTTP Error getting puuid for {game_name}#{tag_line}: {e}")
        return None

    except Exception as e:
        print(f"Unexpected error getting puuid for {game_name}#{tag_line}: {e}")
        return None


def get_account_details_by_puuid(puuid):
    ''' fetches game name and tag line using a player's puuid '''
    
    try:
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
        params = {'api_key': RIOT_API_KEY}
        response = session.get(url, params=params)
        response.raise_for_status()
        account_data = response.json()
        return account_data.get('gameName'), account_data.get('tagLine')

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Rate limit hit getting account details. Waiting {retry_after} seconds.")
            time.sleep(retry_after)
            return get_account_details_by_puuid(puuid)
        elif e.response.status_code == 401:
            print(f"401 Unauthorized error getting account for {puuid}: {e}")
            raise 
        print(f"HTTP Error getting account for {puuid}: {e}")
        return None, None

    except Exception as e:
        print(f"Unexpected error getting account for {puuid}: {e}")
        return None, None


def fetch_and_process_match(match_id, s3_folder_key):
    ''' gets a single match from a player and saves it to s3 '''

    try:
        detail_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
        timeline_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        params = {'api_key': RIOT_API_KEY}
        
        response = session.get(detail_url, params=params)
        response.raise_for_status()
        match_data = response.json()

        # filter matches
        if match_data.get('info', {}).get('queueId') not in [420, 440]:
            return None
        if match_data.get('info', {}).get('gameDuration', 0) < 900:
            return None

        # save to s3
        s3_key = f"raw-matches/{s3_folder_key}/{match_id}/match-data.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(match_data)
        )
        time.sleep(TIME_PER_REQUEST)

        # get timeline
        response = session.get(timeline_url, params=params)
        response.raise_for_status()
        timeline_data = response.json()

        s3_key = f"raw-matches/{s3_folder_key}/{match_id}/timeline-data.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(timeline_data)
        )
        return match_data.get('metadata', {}).get('participants', [])

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Rate limit hit fetching match details. Waiting for {retry_after} seconds.")
            time.sleep(retry_after)
            return fetch_and_process_match(match_id, s3_folder_key)
        elif e.response.status_code == 401:
            print(f"401 Unauthorized error fetching match {match_id}: {e}")
            raise  
        else:
            print(f"HTTP Error fetching match {match_id}: {e}")
            return None

    except Exception as e:
        print(f"An unexpected error occurred processing match {match_id}: {e}")
        return None


def lambda_handler(event, context):
    ''' processes one player from SQS, fetches history, finds new players, and requeues jobs '''

    record = event['Records'][0]
    receipt_handle = record['receiptHandle']
    
    payload = json.loads(record['body'])
    game_name = payload['gameName']
    tag_line = payload['tagLine']
    start_index = payload.get('start_index', 0)
    
    riot_id_key = f"{game_name}#{tag_line}"

    # on the first fetch for a player, immediately mark them as processed
    if start_index == 0:
        try:
            # prevents race conditions across multiple lambdas
            dynamo_table.put_item(
                Item={'riotId': riot_id_key, 'processedAt': int(time.time())},
                ConditionExpression='attribute_not_exists(riotId)'
            )
            print(f"Successfully marked {riot_id_key} as processing.")

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print(f"Skipping already processed or in-progress player: {riot_id_key}")
                # Delete message since we're skipping this player
                delete_sqs_message(receipt_handle, riot_id_key)
                return {'statusCode': 200}
            else:
                print(f"DynamoDB Error marking {riot_id_key}: {e}")
                raise e 
    
    try:
        # get player puuid
        puuid = get_puuid_by_riot_id(game_name, tag_line)
        if not puuid:
            print(f"Could not retrieve PUUID for {riot_id_key}. Aborting.")
            # Delete message for unrecoverable errors
            delete_sqs_message(receipt_handle, riot_id_key)
            return {'statusCode': 404}
        time.sleep(TIME_PER_REQUEST)

        # fetch match history
        ids_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        start_time = int(time.time()) - (365 * 24 * 60 * 60)
        params = {'startTime': start_time, 'start': start_index, 'count': 50, 'api_key': RIOT_API_KEY}
        
        response = session.get(ids_url, params=params)
        response.raise_for_status()
        match_ids = response.json()
        
        print(f"Fetched {len(match_ids)} match IDs for {riot_id_key} at index {start_index}")

        new_puuids_to_process = set()
        for match_id in match_ids:
            participants = fetch_and_process_match(match_id, riot_id_key)
            if participants:
                new_puuids_to_process.update(participants)
            time.sleep(TIME_PER_REQUEST)

        # requeue if more than 50 matches
        if len(match_ids) == 50:
            next_index = start_index + 50
            print(f"Re-queueing job for {riot_id_key} at next index {next_index}")
            sqs_client.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps({'gameName': game_name, 'tagLine': tag_line, 'start_index': next_index}),
                MessageGroupId='riot-api-processor' # GroupID for FIFO
            )

        # process all newly found participants
        for new_puuid in new_puuids_to_process:
            if new_puuid == puuid: continue 

            # get the new player's riot ID
            new_game_name, new_tag_line = get_account_details_by_puuid(new_puuid)
            time.sleep(TIME_PER_REQUEST)
            
            if not new_game_name or not new_tag_line:
                continue
            
            new_riot_id_key = f"{new_game_name}#{new_tag_line}"
            
            # check dynamodb for existing player using the new player's riot ID
            response = dynamo_table.get_item(Key={'riotId': new_riot_id_key})
            if 'Item' in response:
                print(f"Player {new_riot_id_key} already processed, skipping.")
                continue

            # queue the new player
            print(f"Queueing new player: {new_riot_id_key}")
            sqs_client.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps({'gameName': new_game_name, 'tagLine': new_tag_line}),
                MessageGroupId='riot-api-processor'
            )

        print(f"Successfully completed processing batch for {riot_id_key}.")
        delete_sqs_message(receipt_handle, riot_id_key)
        return {'statusCode': 200}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"401 Unauthorized error - unmarking player {riot_id_key}")
            unmark_player_as_processed(riot_id_key)
            delete_sqs_message(receipt_handle, riot_id_key)
            return {'statusCode': 401, 'body': 'API authentication failed'}
        else:
            print(f"HTTP error processing {riot_id_key}: {e}")
            raise

    except Exception as e:
        print(f"Error processing match list for {riot_id_key}: {e}")
        unmark_player_as_processed(riot_id_key)
        raise