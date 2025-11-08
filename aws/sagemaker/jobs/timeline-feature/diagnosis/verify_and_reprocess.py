# verify_and_reprocess.py
"""
Verifies Lambda deployment and reprocesses matches to get KILL/TEAMFIGHT events
"""

import boto3
import json
import time

lambda_client = boto3.client('lambda', region_name='us-west-2')
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
s3_client = boto3.client('s3', region_name='us-west-2')

FUNCTION_NAME = 'lol-timeline-event-processor'
BUCKET_NAME = 'lol-training-matches-150k'

def check_lambda_code():
    """Check if Lambda has the latest code"""
    
    print("="*60)
    print("Checking Lambda Function Code")
    print("="*60)
    
    try:
        response = lambda_client.get_function(FunctionName=FUNCTION_NAME)
        
        last_modified = response['Configuration']['LastModified']
        code_size = response['Configuration']['CodeSize']
        
        print(f"\n✓ Lambda Function: {FUNCTION_NAME}")
        print(f"  Last Modified: {last_modified}")
        print(f"  Code Size: {code_size} bytes")
        
        # The fixed version should have specific logging
        # Let's test invoke and check logs
        
        print(f"\nTesting Lambda invocation to check for event breakdown logging...")
        
        # Find a test file
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix='raw-matches/ShadowLeaf_8005/',
            MaxKeys=1
        )
        
        timeline_key = None
        for obj in response.get('Contents', []):
            if obj['Key'].endswith('timeline-data.json'):
                timeline_key = obj['Key']
                break
        
        if timeline_key:
            event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': BUCKET_NAME},
                        'object': {'key': timeline_key}
                    }
                }]
            }
            
            lambda_response = lambda_client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType='RequestResponse',
                Payload=json.dumps(event),
                LogType='Tail'
            )
            
            # Check logs for "Event breakdown"
            if 'LogResult' in lambda_response:
                import base64
                logs = base64.b64decode(lambda_response['LogResult']).decode('utf-8')
                
                if 'Event breakdown' in logs:
                    print(f"\n✓ Lambda has the UPDATED code (includes event breakdown logging)")
                    print(f"\nLog snippet:")
                    for line in logs.split('\n'):
                        if 'Event breakdown' in line or 'Extracted' in line:
                            print(f"  {line}")
                    return True
                else:
                    print(f"\n✗ Lambda has OLD code (missing event breakdown logging)")
                    print(f"\nLogs:")
                    print(logs)
                    return False
        
        return None
        
    except Exception as e:
        print(f"\n✗ Error checking Lambda: {e}")
        return None


def clear_old_events(match_ids):
    """Delete old events so we can reprocess"""
    
    print(f"\n{'='*60}")
    print("Clearing Old Events from DynamoDB")
    print(f"{'='*60}")
    
    events_table = dynamodb.Table('lol-timeline-timeline-events')
    
    deleted_count = 0
    for match_id in match_ids:
        try:
            # Query events for this match
            response = events_table.query(
                IndexName='match-impact-index',
                KeyConditionExpression='match_id = :match_id',
                ExpressionAttributeValues={':match_id': match_id}
            )
            
            items = response.get('Items', [])
            
            if items:
                print(f"  Deleting {len(items)} events from {match_id}")
                
                with events_table.batch_writer() as batch:
                    for item in items:
                        batch.delete_item(Key={
                            'match_id': item['match_id'],
                            'event_id': item['event_id']
                        })
                        deleted_count += 1
            
        except Exception as e:
            print(f"  ✗ Error deleting events for {match_id}: {e}")
    
    print(f"\n✓ Deleted {deleted_count} old events")


def reprocess_matches(game_name, tagline, match_ids):
    """Reprocess matches with updated Lambda"""
    
    print(f"\n{'='*60}")
    print(f"Reprocessing Matches for {game_name}#{tagline}")
    print(f"{'='*60}")
    
    player_folder = f"{game_name}_{tagline}"
    
    success_count = 0
    event_breakdown = {'KILL': 0, 'TEAMFIGHT': 0, 'OBJECTIVE': 0, 'STRUCTURE': 0}
    
    for idx, match_id in enumerate(match_ids, 1):
        timeline_key = f"raw-matches/{player_folder}/{match_id}/timeline-data.json"
        
        print(f"\n[{idx}/{len(match_ids)}] {match_id}")
        
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': BUCKET_NAME},
                    'object': {'key': timeline_key}
                }
            }]
        }
        
        try:
            response = lambda_client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType='RequestResponse',
                Payload=json.dumps(event),
                LogType='Tail'
            )
            
            payload = json.loads(response['Payload'].read())
            
            if payload.get('statusCode') == 200:
                body = json.loads(payload.get('body', '{}'))
                results = body.get('results', [])
                
                if results:
                    events_found = results[0].get('events_found', 0)
                    print(f"  ✓ Extracted {events_found} events")
                    success_count += 1
                    
                    # Check logs for breakdown
                    if 'LogResult' in response:
                        import base64
                        logs = base64.b64decode(response['LogResult']).decode('utf-8')
                        
                        for line in logs.split('\n'):
                            if 'Event breakdown' in line:
                                print(f"  {line.strip()}")
                                # Parse breakdown
                                try:
                                    breakdown_str = line.split('Event breakdown:')[1].strip()
                                    breakdown = eval(breakdown_str)
                                    for event_type, count in breakdown.items():
                                        event_breakdown[event_type] = event_breakdown.get(event_type, 0) + count
                                except:
                                    pass
            else:
                print(f"  ✗ Error: {payload}")
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ✗ Exception: {e}")
    
    print(f"\n{'='*60}")
    print("Reprocessing Complete!")
    print(f"{'='*60}")
    print(f"Successfully processed: {success_count}/{len(match_ids)}")
    print(f"\nEvent Breakdown Across All Matches:")
    for event_type, count in sorted(event_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"  {event_type}: {count}")


def verify_new_events(match_ids):
    """Verify the new events include KILL and TEAMFIGHT"""
    
    print(f"\n{'='*60}")
    print("Verifying New Events in DynamoDB")
    print(f"{'='*60}")
    
    events_table = dynamodb.Table('lol-timeline-timeline-events')
    
    event_types = {'KILL': 0, 'TEAMFIGHT': 0, 'OBJECTIVE': 0, 'STRUCTURE': 0}
    
    for match_id in match_ids:
        try:
            response = events_table.query(
                IndexName='match-impact-index',
                KeyConditionExpression='match_id = :match_id',
                ExpressionAttributeValues={':match_id': match_id}
            )
            
            items = response.get('Items', [])
            
            for item in items:
                event_type = item.get('event_type')
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
        except Exception as e:
            print(f"  ✗ Error querying {match_id}: {e}")
    
    print(f"\nEvent Types in DynamoDB:")
    for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  ✓ {event_type}: {count}")
        else:
            print(f"  ✗ {event_type}: {count} (MISSING!)")
    
    if event_types['KILL'] > 0 and event_types['TEAMFIGHT'] > 0:
        print(f"\n✓ SUCCESS! KILL and TEAMFIGHT events are now present!")
        return True
    else:
        print(f"\n✗ Still missing KILL or TEAMFIGHT events")
        return False


def main():
    print("="*60)
    print("Timeline Event Type Verification & Reprocessing")
    print("="*60)
    
    # Step 1: Check if Lambda has updated code
    has_updated_code = check_lambda_code()
    
    if has_updated_code is False:
        print("\n⚠ Lambda needs to be updated with the latest code")
        print("Run: python fix_event_filtering.py")
        return
    
    # Step 2: Define matches to reprocess
    match_ids = [
        'NA1_5376250054',
        'NA1_5376358183',
        'NA1_5380404735',
        'NA1_5381737611',
        'NA1_5381745546'
    ]
    
    print(f"\n{'='*60}")
    print(f"Found {len(match_ids)} matches to reprocess")
    print(f"{'='*60}")
    
    response = input("\nClear old events and reprocess? (y/n): ")
    
    if response.lower() != 'y':
        print("Aborted")
        return
    
    # Step 3: Clear old events
    clear_old_events(match_ids)
    
    # Step 4: Wait a moment
    print("\nWaiting 3 seconds...")
    time.sleep(3)
    
    # Step 5: Reprocess matches
    reprocess_matches('ShadowLeaf', '8005', match_ids)
    
    # Step 6: Wait for DynamoDB writes
    print("\nWaiting 5 seconds for DynamoDB writes...")
    time.sleep(5)
    
    # Step 7: Verify
    success = verify_new_events(match_ids)
    
    if success:
        print("\n🎉 All event types are now present!")
        print("\nYou can now:")
        print("  1. Export events from DynamoDB")
        print("  2. Test AI summary generation")
        print("  3. Process all remaining matches")
    else:
        print("\n⚠ There may be an issue with the Lambda code")
        print("Check CloudWatch logs for errors")


if __name__ == "__main__":
    main()