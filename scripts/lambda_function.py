import json
import boto3
import os
import queue
import time

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb_client = boto3.client('dynamodb')

def wait_for_matches(puuid, bucket_name):
    for attempt in range(10):
        matches = s3_client.list_objects_v2(
            Bucket=bucket_name, 
            Prefix=f"lol-match-data/raw-matches/{puuid}/"
        )
        if 'Contents' in matches and len(matches['Contents']) > 0:
            return matches
        print(f"No matches yet for {puuid}, retrying ({attempt})...")
        time.sleep(2)
    return None

def get_recursion_puuids(table_name, start_key=None):
    scan_params = {
        'TableName': table_name,
        'FilterExpression' : '#used = :val',
        'ExpressionAttributeNames' : {
            '#used' : 'used-for-recursion'
        },
        'ExpressionAttributeValues' : {
            ':val' :{'BOOL': False}
        },
        'Limit': 10
    }
    if start_key:
        scan_params['ExclusiveStartKey'] = start_key
    response = dynamodb_client.scan(**scan_params)
    return {
        'items' : response.get('Items', []),
        'NextStartKey' : response.get('LastEvaluatedKey')
    }

def lambda_handler(event, context):
    S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
    DYNAMO_TABLE_NAME = os.environ['DYNAMO_TABLE_NAME']
    if not S3_BUCKET_NAME or not DYNAMO_TABLE_NAME:
        raise ValueError("Environmental variables not set.")
    try:
        # gets first back of puuids to use on recursion
        recursion_puuids = get_recursion_puuids(DYNAMO_TABLE_NAME, None)
        pagination_key = recursion_puuids['NextStartKey']
        recursion_puuids_list = recursion_puuids['items']
        if not recursion_puuids_list:
            return {
                'statusCode': 400,
                'body': 'no unused puuids available'
            }
        match_count = 0 

        # sets up queues for puuids used for recursion and puuids used to call lambda
        recursion_queue = queue.Queue()
        puuid_queue = queue.Queue()
        for item in recursion_puuids_list:
            recursion_queue.put(item['puuid']['S'])
        recursion_puuid = recursion_queue.get()
        matches = wait_for_matches(recursion_puuid, S3_BUCKET_NAME)
        if matches:
            first_match_key = matches['Contents'][0]['Key']
            first_match_obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=first_match_key)
            first_match = json.loads(first_match_obj['Body'].read())
            next_puuids = first_match['metadata']['participants']
            for next_puuid in next_puuids:
                used_check = dynamodb_client.get_item(
                    TableName=DYNAMO_TABLE_NAME,
                    Key={'puuid': {'S': next_puuid}}
                )
                if not 'Item' in used_check:
                    puuid_queue.put(next_puuid)
            try:
                dynamodb_client.update_item(
                    TableName=DYNAMO_TABLE_NAME,
                    Key={
                        'puuid': {'S': recursion_puuid}
                    },
                    UpdateExpression='SET #used = :true',
                    ConditionExpression='#used = :false',
                    ExpressionAttributeNames={
                        '#used' : 'used-for-recursion'
                    },
                    ExpressionAttributeValues={
                        ':true' : {'BOOL': True},
                        ':false' : {'BOOL': False}
                    }
                )
            except dynamodb_client.exceptions.ConditionalCheckFailedException:
                print(f"puuid {recursion_puuid} already marked as used")
            recursion_puuid = None
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'no matches for target puuid'})
            }
        print("starting match population")
        while match_count < 100000:
            
            if puuid_queue.empty(): # fills queue when empty
                if not recursion_puuid:
                    if recursion_queue.empty(): # fills recursion queue with new puuids if needed
                        recursion_puuids = get_recursion_puuids(DYNAMO_TABLE_NAME, pagination_key)
                        pagination_key = recursion_puuids['NextStartKey']
                        recursion_puuids_list = recursion_puuids['items']
                        if not recursion_puuids_list:
                            return {
                                'statusCode': 400,
                                'body': 'no unused puuids available'
                            }
                        for item in recursion_puuids_list:
                            recursion_queue.put(item['puuid']['S'])
                        print("added new keys to queue for recursion")
                    recursion_puuid = recursion_queue.get()
                matches = wait_for_matches(recursion_puuid, S3_BUCKET_NAME)
                if matches:
                    first_match_key = matches['Contents'][0]['Key']
                    first_match_obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=first_match_key)
                    first_match = json.loads(first_match_obj['Body'].read())
                    next_puuids = first_match['metadata']['participants']
                    for next_puuid in next_puuids:
                        used_check = dynamodb_client.get_item(
                            TableName=DYNAMO_TABLE_NAME,
                            Key={'puuid': {'S': next_puuid}}
                        )
                        if not 'Item' in used_check:
                            puuid_queue.put(next_puuid)
                    try:
                        dynamodb_client.update_item(
                            TableName=DYNAMO_TABLE_NAME,
                            Key={
                                'puuid': {'S': recursion_puuid}
                            },
                            UpdateExpression='SET #used = :true',
                            ConditionExpression='#used = :false',
                            ExpressionAttributeNames={
                                '#used' : 'used-for-recursion'
                            },
                            ExpressionAttributeValues={
                                ':true' : {'BOOL': True},
                                ':false' : {'BOOL': False}
                            }
                        )
                    except dynamodb_client.exceptions.ConditionalCheckFailedException:
                        print(f"puuid {recursion_puuid} already marked as used")
                    recursion_puuid = None
            else:
                # call lambda on current puuid
                current_puuid = puuid_queue.get()
                payload = {"body" : json.dumps({"puuid": current_puuid})}
                print(f"payload: {payload}")
                response = lambda_client.invoke(
                    FunctionName='StartHistorySearch',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )
                lambda_res = response.get('StatusCode')
                print(f"response from lambda: {lambda_res}")
                dynamodb_client.put_item(
                    TableName=DYNAMO_TABLE_NAME,
                    Item={
                        'puuid' : {'S': current_puuid},
                        'used-for-recursion' : {'BOOL': False}
                    }
                )
                print(f"made api request for {current_puuid}")

            # check match count from s3 bucket
            match_count_json = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key="used-puuids/match-count.json")
            match_count_data = json.loads(match_count_json['Body'].read().decode('utf-8'))
            match_count = match_count_data['match-count']
            print(match_count)
            if match_count >= 100000:
                break

        return {
            'statusCode': 202,
            'body': json.dumps({'message': 'match data has been populated'})
        }
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ValueError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'some other error': str(e)})
        }

    