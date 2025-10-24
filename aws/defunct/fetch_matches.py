import json
import boto3
import os
import requests
import time

s3_client = boto3.client('s3')
session = requests.Session()

def fetch_match_details(match_id, puuid, api_key, s3_bucket):
    try:
        detail_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
        params = {'api_key': api_key}
        response = session.get(detail_url, params=params)
        response.raise_for_status()
        match_data = response.json()

        # Filter for ranked games (queueId 420=Solo/Duo, 440=Flex)
        queue_id = match_data.get('info', {}).get('queueId', 0)
        if queue_id not in [420, 440]:
            print(f"Skipping non-ranked game {match_id} (queue {queue_id})")
            return

        # Filter for games longer than 15 minutes
        game_duration = match_data.get('info', {}).get('gameDuration', 0)
        if game_duration < 900:
            print(f"Skipping short game {match_id} ({game_duration} seconds)")
            return

        # Save to S3
        s3_key = f"raw-matches/{puuid}/{match_id}.json"
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=json.dumps(match_data)
        )
        print(f"Successfully processed and saved match {match_id}")

    # Specific handling for rate limit errors
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get('Retry-After', 10))
            print(f"Rate limit hit. Waiting for {retry_after} seconds.")
            time.sleep(retry_after)
            fetch_match_details(match_id, puuid, api_key, s3_bucket)
        else:
            print(f"HTTP Error fetching match {match_id}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred for match {match_id}: {e}")


def lambda_handler(event, context):
    RIOT_API_KEY = os.environ['RIOT_API_KEY']
    S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']

    for record in event['Records']:
        payload = json.loads(record['body'])
        puuid = payload['puuid']
        start_time = payload['start_time']

        start_index = 0
        count = 100
        has_more_matches = True

        while has_more_matches:
            try:
                # 1. Get a batch of match IDs
                ids_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
                params = {
                    'startTime': start_time,
                    'start': start_index,
                    'count': count,
                    'api_key': RIOT_API_KEY
                }
                print(f"Fetching match IDs for {puuid} with headers {params}...")
                response = session.get(ids_url, params=params)
                response.raise_for_status()
                match_ids = response.json()

                print(f"Fetched {len(match_ids)} match IDs for puuid {puuid} starting at index {start_index}.")

                # 2. Process each match ID in the batch
                for match_id in match_ids:
                    fetch_match_details(match_id, puuid, RIOT_API_KEY, S3_BUCKET_NAME)
                    time.sleep(1.5)

                # 3. Check if we need to paginate for more matches
                if len(match_ids) < count:
                    has_more_matches = False
                else:
                    start_index += count

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get('Retry-After', 10))
                    print(f"Rate limit hit on match ID batch. Waiting {retry_after} seconds.")
                    time.sleep(retry_after)
                else:
                    print(f"HTTP Error fetching match IDs: {e}")
                    has_more_matches = False
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                has_more_matches = False
        match_count_json = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key="used-puuids/match-count.json")
        match_count_data = json.loads(match_count_json['Body'].read().decode('utf-8'))
        match_count = match_count_data['match-count']
        match_count += count
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key="used-puuids/match-count.json",
            Body=json.dumps({"match-count": match_count})
        )
        
    return {'statusCode': 200, 'body': json.dumps('Processing complete.')}