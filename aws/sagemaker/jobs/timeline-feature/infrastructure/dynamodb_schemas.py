"""
DynamoDB table definitions for timeline feature caching
"""
import boto3
import time

TIMELINE_EVENTS_TABLE = {
    'TableName': 'lol-timeline-events',
    'KeySchema': [
        {'AttributeName': 'match_id', 'KeyType': 'HASH'},  # Partition key
        {'AttributeName': 'event_id', 'KeyType': 'RANGE'}  # Sort key
    ],
    'AttributeDefinitions': [
        {'AttributeName': 'match_id', 'AttributeType': 'S'},
        {'AttributeName': 'event_id', 'AttributeType': 'S'},
        {'AttributeName': 'puuid', 'AttributeType': 'S'},
        {'AttributeName': 'timestamp_minutes', 'AttributeType': 'N'},
        {'AttributeName': 'impact_score', 'AttributeType': 'N'}
    ],
    'GlobalSecondaryIndexes': [
        {
            'IndexName': 'puuid-timestamp-index',
            'KeySchema': [
                {'AttributeName': 'puuid', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp_minutes', 'KeyType': 'RANGE'}
            ],
            'Projection': {'ProjectionType': 'ALL'},
            # ProvisionedThroughput removed
        },
        {
            'IndexName': 'match-impact-index',
            'KeySchema': [
                {'AttributeName': 'match_id', 'KeyType': 'HASH'},
                {'AttributeName': 'impact_score', 'KeyType': 'RANGE'}
            ],
            'Projection': {'ProjectionType': 'ALL'},
            # ProvisionedThroughput removed
        }
    ],
    'BillingMode': 'PAY_PER_REQUEST',
    'Tags': [
        {'Key': 'Project', 'Value': 'LOL-Coach'},
        {'Key': 'Component', 'Value': 'Timeline-Events'}
    ]
}

AI_SUMMARIES_CACHE_TABLE = {
    'TableName': 'lol-timeline-ai-summaries',
    'KeySchema': [
        {'AttributeName': 'event_id', 'KeyType': 'HASH'},  # Partition key
        {'AttributeName': 'summary_type', 'KeyType': 'RANGE'}  # Sort key (basic/detailed)
    ],
    'AttributeDefinitions': [
        {'AttributeName': 'event_id', 'AttributeType': 'S'},
        {'AttributeName': 'summary_type', 'AttributeType': 'S'},
        {'AttributeName': 'match_id', 'AttributeType': 'S'},
    ],
    'GlobalSecondaryIndexes': [
        {
            'IndexName': 'match-summaries-index',
            'KeySchema': [
                {'AttributeName': 'match_id', 'KeyType': 'HASH'}
            ],
            'Projection': {'ProjectionType': 'ALL'},
            # ProvisionedThroughput removed
        }
    ],
    # TimeToLiveSpecification removed from create_table definition
    'BillingMode': 'PAY_PER_REQUEST',
    'Tags': [
        {'Key': 'Project', 'Value': 'LOL-Coach'},
        {'Key': 'Component', 'Value': 'AI-Summaries-Cache'}
    ]
}

USER_QUESTIONS_TABLE = {
    'TableName': 'lol-timeline-user-questions',
    'KeySchema': [
        {'AttributeName': 'question_id', 'KeyType': 'HASH'},
    ],
    'AttributeDefinitions': [
        {'AttributeName': 'question_id', 'AttributeType': 'S'},
        {'AttributeName': 'event_id', 'AttributeType': 'S'},
        {'AttributeName': 'puuid', 'AttributeType': 'S'},
    ],
    'GlobalSecondaryIndexes': [
        {
            'IndexName': 'event-questions-index',
            'KeySchema': [
                {'AttributeName': 'event_id', 'KeyType': 'HASH'}
            ],
            'Projection': {'ProjectionType': 'ALL'},
            # ProvisionedThroughput removed
        },
        {
            'IndexName': 'user-questions-index',
            'KeySchema': [
                {'AttributeName': 'puuid', 'KeyType': 'HASH'}
            ],
            'Projection': {'ProjectionType': 'ALL'},
            # ProvisionedThroughput removed
        }
    ],
    # TimeToLiveSpecification removed from create_table definition
    'BillingMode': 'PAY_PER_REQUEST',
    'Tags': [
        {'Key': 'Project', 'Value': 'LOL-Coach'},
        {'Key': 'Component', 'Value': 'User-Questions'}
    ]
}

PLAYER_TIMELINE_METADATA_TABLE = {
    'TableName': 'lol-player-timeline-metadata',
    'KeySchema': [
        {'AttributeName': 'puuid', 'KeyType': 'HASH'},
        {'AttributeName': 'match_id', 'KeyType': 'RANGE'}
    ],
    'AttributeDefinitions': [
        {'AttributeName': 'puuid', 'AttributeType': 'S'},
        {'AttributeName': 'match_id', 'AttributeType': 'S'},
        {'AttributeName': 'processed_timestamp', 'AttributeType': 'N'}
    ],
    'GlobalSecondaryIndexes': [
        {
            'IndexName': 'processed-timestamp-index',
            'KeySchema': [
                {'AttributeName': 'puuid', 'KeyType': 'HASH'},
                {'AttributeName': 'processed_timestamp', 'KeyType': 'RANGE'}
            ],
            'Projection': {'ProjectionType': 'ALL'},
            # ProvisionedThroughput removed
        }
    ],
    'BillingMode': 'PAY_PER_REQUEST',
    'Tags': [
        {'Key': 'Project', 'Value': 'LOL-Coach'},
        {'Key': 'Component', 'Value': 'Timeline-Metadata'}
    ]
}

# --- Create Tables Script (Corrected) ---

def create_dynamodb_tables():
    """
    Creates all required DynamoDB tables and applies TTL settings.
    """
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    waiter = dynamodb.get_waiter('table_exists')

    tables = [
        TIMELINE_EVENTS_TABLE,
        AI_SUMMARIES_CACHE_TABLE,
        USER_QUESTIONS_TABLE,
        PLAYER_TIMELINE_METADATA_TABLE
    ]
    
    # Define TTL settings separately
    ttl_settings = {
        'lol-timeline-ai-summaries': 'ttl',
        'lol-timeline-user-questions': 'ttl'
    }

    for table_config in tables:
        table_name = table_config['TableName']
        try:
            print(f"Creating table: {table_name}")
            dynamodb.create_table(**table_config)
            print(f"Waiting for {table_name} to become active...")
            waiter.wait(TableName=table_name)
            print(f"✓ Table {table_name} created successfully")

            # After table is active, check if it needs TTL
            if table_name in ttl_settings:
                print(f"Applying TTL settings to {table_name}...")
                dynamodb.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': ttl_settings[table_name]
                    }
                )
                print(f"✓ TTL enabled for {table_name}")

        except dynamodb.exceptions.ResourceInUseException:
            print(f"⚠ Table {table_name} already exists")
            # Check if TTL needs to be applied to existing table
            try:
                if table_name in ttl_settings:
                    print(f"Verifying/Applying TTL settings to existing table {table_name}...")
                    dynamodb.update_time_to_live(
                        TableName=table_name,
                        TimeToLiveSpecification={
                            'Enabled': True,
                            'AttributeName': ttl_settings[table_name]
                        }
                    )
                    print(f"✓ TTL verified/enabled for {table_name}")
            except Exception as ttl_e:
                 print(f"✗ Error updating TTL for existing table {table_name}: {str(ttl_e)}")

        except Exception as e:
            print(f"✗ Error creating {table_name}: {str(e)}")

if __name__ == "__main__":
    create_dynamodb_tables()