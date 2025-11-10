# deploy_step_functions.py
"""
Creates and deploys Step Functions state machine for batch processing
"""

import boto3
import json

stepfunctions = boto3.client('stepfunctions')
lambda_client = boto3.client('lambda')

# Load configurations
with open('infrastructure_config.json', 'r') as f:
    infra_config = json.load(f)

with open('lambda_deployment_info.json', 'r') as f:
    lambda_info = json.load(f)

PROJECT_PREFIX = infra_config['project_prefix']
SFN_ROLE_ARN = infra_config['stepfunctions_role_arn']
AWS_REGION = infra_config['region']
AWS_ACCOUNT_ID = infra_config['account_id']


def create_state_machine():
    """
    Creates Step Functions state machine
    """
    
    print("\n=== Creating Step Functions State Machine ===\n")
    
    state_machine_name = f'{PROJECT_PREFIX}-batch-processor'
    
    # Load state machine definition
    with open('step_functions_definition.json', 'r') as f:
        definition = json.load(f)
    
    # Replace placeholders with actual ARNs
    definition_str = json.dumps(definition)
    definition_str = definition_str.replace(
        '"FunctionName": "timeline-event-processor"',
        f'"FunctionName": "{PROJECT_PREFIX}-event-processor"'
    )
    definition_str = definition_str.replace(
        '"FunctionName": "bedrock-summary-generator"',
        f'"FunctionName": "{PROJECT_PREFIX}-summary-generator"'
    )
    definition_str = definition_str.replace(
        '"TableName": "lol-timeline-events"',
        f'"TableName": "{PROJECT_PREFIX}-timeline-events"'
    )
    definition_str = definition_str.replace(
        '"TableName": "lol-player-timeline-metadata"',
        f'"TableName": "{PROJECT_PREFIX}-player-timeline-metadata"'
    )
    definition_str = definition_str.replace(
        '"TopicArn": "arn:aws:sns:us-west-2:768394660366:timeline-processing-complete"',
        f'"TopicArn": "{infra_config["sns_topic_arn"]}"'
    )
    
    definition = json.loads(definition_str)
    
    try:
        # Try to create new state machine
        response = stepfunctions.create_state_machine(
            name=state_machine_name,
            definition=json.dumps(definition),
            roleArn=SFN_ROLE_ARN,
            type='STANDARD',
            tags=[
                {'key': 'Project', 'value': 'LOL-Coach'},
                {'key': 'Component', 'value': 'Timeline-Batch-Processing'}
            ]
        )
        
        state_machine_arn = response['stateMachineArn']
        print(f"✓ Created state machine: {state_machine_name}")
        print(f"  ARN: {state_machine_arn}")
        
    except stepfunctions.exceptions.StateMachineAlreadyExists:
        # Update existing state machine
        state_machine_arn = f"arn:aws:states:{AWS_REGION}:{AWS_ACCOUNT_ID}:stateMachine:{state_machine_name}"
        
        response = stepfunctions.update_state_machine(
            stateMachineArn=state_machine_arn,
            definition=json.dumps(definition),
            roleArn=SFN_ROLE_ARN
        )
        
        print(f"✓ Updated existing state machine: {state_machine_name}")
        print(f"  ARN: {state_machine_arn}")
    
    return state_machine_arn


def update_api_lambda_with_sfn_arn(state_machine_arn: str):
    """
    Updates API Lambda function with Step Functions ARN
    """
    
    print("\n=== Updating API Lambda Configuration ===\n")
    
    function_name = f'{PROJECT_PREFIX}-api-handler'
    
    lambda_client.update_function_configuration(
        FunctionName=function_name,
        Environment={
            'Variables': {
                'STEP_FUNCTIONS_ARN': state_machine_arn
            }
        }
    )
    
    print(f"✓ Updated {function_name} with Step Functions ARN")


def main():
    """
    Orchestrates Step Functions deployment
    """
    
    print("="*60)
    print("LOL Coach Timeline Feature - Step Functions Deployment")
    print("="*60)
    
    # Create state machine
    state_machine_arn = create_state_machine()
    
    # Update API Lambda with Step Functions ARN
    update_api_lambda_with_sfn_arn(state_machine_arn)
    
    # Save deployment info
    deployment_info = {
        'state_machine_arn': state_machine_arn,
        'state_machine_name': f'{PROJECT_PREFIX}-batch-processor',
        'deployed_at': boto3.client('sts').get_caller_identity()
    }
    
    with open('stepfunctions_deployment_info.json', 'w') as f:
        json.dump(deployment_info, f, indent=2)
    
    print("\n" + "="*60)
    print("Step Functions Deployment Complete!")
    print("="*60)
    print(f"\nState Machine ARN: {state_machine_arn}")
    print(f"\nDeployment info saved to: stepfunctions_deployment_info.json")
    print("\n✓ All infrastructure deployed successfully!")
    print("\nYou can now:")
    print("1. Test the API endpoints")
    print("2. Upload timeline-data.json files to S3 to trigger processing")
    print("3. Use the batch processing API to process multiple matches")


if __name__ == "__main__":
    main()