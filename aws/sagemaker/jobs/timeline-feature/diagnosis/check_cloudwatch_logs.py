# check_cloudwatch_logs.py
"""
Checks CloudWatch logs for Lambda function errors
"""

import boto3
from datetime import datetime, timedelta
import time

logs_client = boto3.client('logs', region_name='us-west-2')

FUNCTION_NAME = 'lol-timeline-event-processor'
LOG_GROUP = f'/aws/lambda/{FUNCTION_NAME}'

def get_recent_logs(minutes=10):
    """Get recent Lambda logs"""
    print(f"Checking CloudWatch logs for last {minutes} minutes...")
    
    try:
        # Get log streams
        streams_response = logs_client.describe_log_streams(
            logGroupName=LOG_GROUP,
            orderBy='LastEventTime',
            descending=True,
            limit=5
        )
        
        if not streams_response.get('logStreams'):
            print(f"✗ No log streams found for {LOG_GROUP}")
            return
        
        print(f"\n✓ Found {len(streams_response['logStreams'])} recent log stream(s)\n")
        
        start_time = int((datetime.utcnow() - timedelta(minutes=minutes)).timestamp() * 1000)
        end_time = int(datetime.utcnow().timestamp() * 1000)
        
        # Get logs from each stream
        for stream in streams_response['logStreams'][:3]:  # Check top 3 streams
            stream_name = stream['logStreamName']
            print(f"{'='*60}")
            print(f"Stream: {stream_name}")
            print(f"{'='*60}")
            
            try:
                events_response = logs_client.get_log_events(
                    logGroupName=LOG_GROUP,
                    logStreamName=stream_name,
                    startTime=start_time,
                    endTime=end_time,
                    limit=100
                )
                
                events = events_response.get('events', [])
                
                if not events:
                    print("(No recent events)\n")
                    continue
                
                # Print all log messages
                for event in events:
                    timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                    message = event['message'].strip()
                    print(f"[{timestamp.strftime('%H:%M:%S')}] {message}")
                
                print()
                
            except Exception as e:
                print(f"Error reading stream: {e}\n")
        
    except logs_client.exceptions.ResourceNotFoundException:
        print(f"✗ Log group not found: {LOG_GROUP}")
        print("The Lambda function may never have been invoked.")
    except Exception as e:
        print(f"✗ Error accessing logs: {e}")


def search_for_errors():
    """Search for error messages in logs"""
    print("\nSearching for errors in logs...")
    
    try:
        start_time = int((datetime.utcnow() - timedelta(minutes=30)).timestamp() * 1000)
        
        response = logs_client.filter_log_events(
            logGroupName=LOG_GROUP,
            startTime=start_time,
            filterPattern='ERROR',
            limit=50
        )
        
        errors = response.get('events', [])
        
        if errors:
            print(f"\n✗ Found {len(errors)} error(s):\n")
            for event in errors[:10]:  # Show first 10
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}]")
                print(f"  {event['message']}\n")
        else:
            print("✓ No errors found in recent logs")
            
    except Exception as e:
        print(f"✗ Error searching logs: {e}")


def main():
    print("="*60)
    print("CloudWatch Logs Checker")
    print("="*60)
    
    get_recent_logs(minutes=15)
    search_for_errors()


if __name__ == "__main__":
    main()