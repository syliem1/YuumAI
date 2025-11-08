# deploy_infrastructure.py
"""
Sets up all AWS infrastructure for timeline feature
Run this first before deploying Lambda functions
"""

import boto3
import json
import time
from botocore.exceptions import ClientError

# AWS clients
iam = boto3.client('iam')
dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
sns = boto3.client('sns')
stepfunctions = boto3.client('stepfunctions')

# Configuration
AWS_REGION = 'us-west-2'
AWS_ACCOUNT_ID = '768394660366'
PROJECT_PREFIX = 'lol-timeline'


def create_iam_roles():
    """
    Creates IAM roles for Lambda functions and Step Functions
    """
    
    print("\n=== Creating IAM Roles ===")
    
    # Lambda execution role
    lambda_role_name = f'{PROJECT_PREFIX}-lambda-role'
    lambda_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    lambda_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/{PROJECT_PREFIX}-*",
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/{PROJECT_PREFIX}-*/index/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject"
                ],
                "Resource": [
                    "arn:aws:s3:::lol-training-matches-150k/*",
                    "arn:aws:s3:::lol-coach-processed-data/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel"
                ],
                "Resource": f"arn:aws:bedrock:{AWS_REGION}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "states:StartExecution"
                ],
                "Resource": f"arn:aws:states:{AWS_REGION}:{AWS_ACCOUNT_ID}:stateMachine:{PROJECT_PREFIX}-*"
            }
        ]
    }
    
    try:
        lambda_role = iam.create_role(
            RoleName=lambda_role_name,
            AssumeRolePolicyDocument=json.dumps(lambda_trust_policy),
            Description='Execution role for timeline Lambda functions'
        )
        print(f"✓ Created Lambda role: {lambda_role_name}")
        
        # Attach inline policy
        iam.put_role_policy(
            RoleName=lambda_role_name,
            PolicyName=f'{PROJECT_PREFIX}-lambda-policy',
            PolicyDocument=json.dumps(lambda_policy)
        )
        print(f"✓ Attached Lambda policy")
        
        lambda_role_arn = lambda_role['Role']['Arn']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"⚠ Lambda role already exists: {lambda_role_name}")
            lambda_role_arn = f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/{lambda_role_name}"
        else:
            raise
    
    # Step Functions execution role
    sfn_role_name = f'{PROJECT_PREFIX}-stepfunctions-role'
    sfn_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "states.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    sfn_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": [
                    f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:{PROJECT_PREFIX}-*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:Query"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/{PROJECT_PREFIX}-*",
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/{PROJECT_PREFIX}-*/index/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sns:Publish"
                ],
                "Resource": f"arn:aws:sns:{AWS_REGION}:{AWS_ACCOUNT_ID}:{PROJECT_PREFIX}-*"
            }
        ]
    }
    
    try:
        sfn_role = iam.create_role(
            RoleName=sfn_role_name,
            AssumeRolePolicyDocument=json.dumps(sfn_trust_policy),
            Description='Execution role for Step Functions workflow'
        )
        print(f"✓ Created Step Functions role: {sfn_role_name}")
        
        iam.put_role_policy(
            RoleName=sfn_role_name,
            PolicyName=f'{PROJECT_PREFIX}-stepfunctions-policy',
            PolicyDocument=json.dumps(sfn_policy)
        )
        print(f"✓ Attached Step Functions policy")
        
        sfn_role_arn = sfn_role['Role']['Arn']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"⚠ Step Functions role already exists: {sfn_role_name}")
            sfn_role_arn = f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/{sfn_role_name}"
        else:
            raise
    
    # Wait for roles to propagate
    print("Waiting for IAM roles to propagate...")
    time.sleep(10)
    
    return lambda_role_arn, sfn_role_arn


def create_dynamodb_tables():
    """
    Creates all DynamoDB tables
    """
    
    print("\n=== Creating DynamoDB Tables ===")
    
    from dynamodb_schemas import (
        TIMELINE_EVENTS_TABLE,
        AI_SUMMARIES_CACHE_TABLE,
        USER_QUESTIONS_TABLE,
        PLAYER_TIMELINE_METADATA_TABLE
    )
    
    tables = [
        TIMELINE_EVENTS_TABLE,
        AI_SUMMARIES_CACHE_TABLE,
        USER_QUESTIONS_TABLE,
        PLAYER_TIMELINE_METADATA_TABLE
    ]
    
    for table_config in tables:
        try:
            table_config['TableName'] = f"{PROJECT_PREFIX}-{table_config['TableName'].replace('lol-', '')}"
            
            print(f"Creating table: {table_config['TableName']}")
            dynamodb.create_table(**table_config)
            print(f"✓ Table {table_config['TableName']} created")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print(f"⚠ Table {table_config['TableName']} already exists")
            else:
                raise
    
    print("Waiting for tables to become active...")
    time.sleep(30)


def create_sns_topics():
    """
    Creates SNS topics for notifications
    """
    
    print("\n=== Creating SNS Topics ===")
    
    topic_name = f'{PROJECT_PREFIX}-processing-complete'
    
    try:
        response = sns.create_topic(Name=topic_name)
        topic_arn = response['TopicArn']
        print(f"✓ Created SNS topic: {topic_name}")
        print(f"  ARN: {topic_arn}")
        
        return topic_arn
        
    except ClientError as e:
        print(f"Error creating SNS topic: {str(e)}")
        return None


def create_s3_event_notifications():
    """
    Configures S3 bucket to trigger Lambda on timeline file uploads
    """
    
    print("\n=== Configuring S3 Event Notifications ===")
    
    bucket_name = 'lol-training-matches-150k'
    
    # Note: This requires the Lambda function to exist first
    # This will be configured after Lambda deployment
    
    print(f"⚠ S3 event notifications must be configured after Lambda deployment")
    print(f"  Bucket: {bucket_name}")
    print(f"  Event: s3:ObjectCreated:*")
    print(f"  Filter: raw-matches/*/*/timeline-data.json")


def main():
    """
    Orchestrates infrastructure setup
    """
    
    print("="*60)
    print("LOL Coach Timeline Feature - Infrastructure Setup")
    print("="*60)
    
    # Create IAM roles
    lambda_role_arn, sfn_role_arn = create_iam_roles()
    
    # Create DynamoDB tables
    create_dynamodb_tables()
    
    # Create SNS topics
    topic_arn = create_sns_topics()
    
    # Note about S3 configuration
    create_s3_event_notifications()
    
    # Save configuration
    config = {
        'lambda_role_arn': lambda_role_arn,
        'stepfunctions_role_arn': sfn_role_arn,
        'sns_topic_arn': topic_arn,
        'region': AWS_REGION,
        'account_id': AWS_ACCOUNT_ID,
        'project_prefix': PROJECT_PREFIX
    }
    
    with open('infrastructure_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n" + "="*60)
    print("Infrastructure Setup Complete!")
    print("="*60)
    print(f"\nConfiguration saved to: infrastructure_config.json")
    print(f"\nLambda Role ARN: {lambda_role_arn}")
    print(f"Step Functions Role ARN: {sfn_role_arn}")
    print(f"SNS Topic ARN: {topic_arn}")
    print("\nNext steps:")
    print("1. Deploy Lambda functions: python deploy_lambda_functions.py")
    print("2. Create Step Functions state machine: python deploy_step_functions.py")
    print("3. Configure S3 event notifications manually or via AWS CLI")


if __name__ == "__main__":
    main()