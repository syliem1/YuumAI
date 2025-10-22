import json
import boto3
import os
import time

sqs_client = boto3.client('sqs')

def lambda_handler(event, context):
    try:
        SQS_QUEUE_URL = os.environ.get('SQS_FIFO_QUEUE_URL') 
        if not SQS_QUEUE_URL:
            raise ValueError('SQS_FIFO_QUEUE_URL environment variable not set')

        body = json.loads(event.get('body', '{}'))
        puuid = body.get('puuid')
        print(f"Received puuid: {puuid}")
        if not puuid:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing puuid'})}

        start_time = int(time.time()) - (365 * 24 * 60 * 60)

        message_body = {
            'puuid': puuid,
            'start_time': start_time
        }

        # Send the job to the SQS FIFO queue
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageGroupId='riot-api-processor'
        )
        print(f"Sent message to SQS: {message_body}")

        return {
            'statusCode': 202,
            'body': json.dumps({'message': f'Request for puuid {puuid} has been queued to {SQS_QUEUE_URL}.'})
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }