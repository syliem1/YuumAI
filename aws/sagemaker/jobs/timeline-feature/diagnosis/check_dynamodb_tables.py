# check_dynamodb_tables.py
"""
Checks if DynamoDB tables exist with correct names
"""

import boto3

dynamodb = boto3.client('dynamodb', region_name='us-west-2')

EXPECTED_TABLES = [
    'lol-timeline-timeline-events',
    'lol-timeline-ai-summaries',
    'lol-timeline-user-questions',
    'lol-timeline-player-timeline-metadata'
]

def check_tables():
    """Check if DynamoDB tables exist"""
    print("Checking DynamoDB tables...")
    
    try:
        response = dynamodb.list_tables()
        existing_tables = response['TableNames']
        
        print(f"\n✓ Found {len(existing_tables)} table(s) in region us-west-2\n")
        
        all_exist = True
        for table_name in EXPECTED_TABLES:
            if table_name in existing_tables:
                print(f"  ✓ {table_name}")
                
                # Get table details
                table_info = dynamodb.describe_table(TableName=table_name)
                status = table_info['Table']['TableStatus']
                item_count = table_info['Table']['ItemCount']
                
                print(f"      Status: {status}, Items: {item_count}")
            else:
                print(f"  ✗ {table_name} - NOT FOUND")
                all_exist = False
        
        if not all_exist:
            print("\n⚠ Some tables are missing. Looking for similar names...")
            for table in existing_tables:
                if 'timeline' in table.lower():
                    print(f"    Found: {table}")
        
        return all_exist
        
    except Exception as e:
        print(f"✗ Error checking tables: {e}")
        return False


def check_table_items(match_id='TEST_MATCH_123'):
    """Check if test data exists in tables"""
    print(f"\nChecking for test match data (match_id: {match_id})...")
    
    dynamodb_resource = boto3.resource('dynamodb', region_name='us-west-2')
    
    for table_name in EXPECTED_TABLES:
        if 'events' not in table_name:
            continue
            
        try:
            table = dynamodb_resource.Table(table_name)
            
            # Try to query by match_id
            response = table.query(
                KeyConditionExpression='match_id = :match_id',
                ExpressionAttributeValues={':match_id': match_id},
                Limit=1
            )
            
            if response['Items']:
                print(f"  ✓ {table_name}: Found test data")
            else:
                print(f"  - {table_name}: No test data")
                
        except Exception as e:
            print(f"  ✗ {table_name}: Error - {e}")


def main():
    print("="*60)
    print("DynamoDB Tables Checker")
    print("="*60)
    
    if check_tables():
        print("\n✓ All expected tables exist")
        check_table_items()
    else:
        print("\n✗ Missing tables detected")


if __name__ == "__main__":
    main()