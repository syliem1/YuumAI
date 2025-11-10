"""
Packages and deploys all Lambda functions for timeline feature
"""

import boto3
import json
import zipfile
import os
import shutil
import subprocess
from pathlib import Path

# --- Path Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
# ---

lambda_client = boto3.client('lambda')
apigateway = boto3.client('apigatewayv2')

# Load infrastructure config
config_path = 'infrastructure_config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

LAMBDA_ROLE_ARN = config['lambda_role_arn']
PROJECT_PREFIX = config['project_prefix']
AWS_REGION = config['region']
AWS_ACCOUNT_ID = config['account_id'] 


def package_lambda(function_dir: Path, output_zip: Path, requirements: list = None):
    """
    Packages Lambda function code with dependencies
    
    MODIFIED: Type hints changed to Path for clarity
    """
    
    print(f"Packaging {function_dir.name}...")
    temp_dir = f'/tmp/{function_dir.name}_package'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    # Copy function code
    for file in os.listdir(function_dir):
        if file.endswith('.py'):
            # MODIFIED: Use Path objects for copying
            shutil.copy(function_dir / file, temp_dir)
    
    # Install dependencies if specified
    if requirements:
        print(f"  Installing dependencies: {', '.join(requirements)}")
        subprocess.run([
            'pip', 'install',
            '-t', temp_dir,
            '--upgrade'
        ] + requirements, check=True)
    
    # Create zip file
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    
    # Cleanup
    shutil.rmtree(temp_dir)
    
    print(f"  ✓ Created {output_zip}")
    return output_zip


def deploy_lambda_function(function_name: str, zip_file: Path,
                           handler: str, memory: int = 512, 
                           timeout: int = 60, env_vars: dict = None):
    """
    Deploys or updates Lambda function
    """
    
    print(f"Deploying Lambda function: {function_name}")
    
    with open(zip_file, 'rb') as f:
        zip_content = f.read()
    
    environment = {'Variables': env_vars} if env_vars else {'Variables': {}}
    
    try:
        # Try to update existing function
        lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_content
        )
        print(f"  ✓ Updated function code")

        # Wait for the code update to complete before updating the config
        print(f"  Waiting for code update to finalize...")
        code_waiter = lambda_client.get_waiter('function_updated')
        code_waiter.wait(
            FunctionName=function_name,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 60} # Poll every 5s, max 5 mins
        )
        print(f"  ✓ Code update complete")

        # Now, update the configuration
        config_response = lambda_client.update_function_configuration(
            FunctionName=function_name,
            Role=LAMBDA_ROLE_ARN,
            Handler=handler,
            Runtime='python3.11',
            Timeout=timeout,
            MemorySize=memory,
            Environment=environment
        )
        print(f"  ✓ Updated function configuration")

        # Wait for the configuration update to complete
        print(f"  Waiting for config update to finalize...")
        config_waiter = lambda_client.get_waiter('function_updated')
        config_waiter.wait(
            FunctionName=function_name,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 60} # Poll every 5s, max 5 mins
        )
        print(f"  ✓ Config update complete")
        
        return config_response['FunctionArn']

    except lambda_client.exceptions.ResourceNotFoundException:
        # Create new function
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime='python3.11',
            Role=LAMBDA_ROLE_ARN,
            Handler=handler,
            Code={'ZipFile': zip_content},
            Timeout=timeout,
            MemorySize=memory,
            Environment=environment,
            Tags={
                'Project': 'LOL-Coach',
                'Component': 'Timeline-Feature'
            }
        )
        print(f"  ✓ Created new function")

        # Wait for the new function to become active
        print(f"  Waiting for function to become active...")
        active_waiter = lambda_client.get_waiter('function_active')
        active_waiter.wait(
            FunctionName=function_name,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 60} # Poll every 5s, max 5 mins
        )
        print(f"  ✓ Function is active")
        
        return response['FunctionArn']

    except Exception as e:
        print(f"  ✗ Error deploying {function_name}: {str(e)}")
        raise e


def deploy_all_lambdas():
    """
    Deploys all Lambda functions
    """
    
    print("\n=== Deploying Lambda Functions ===\n")
    
    deployed_functions = {}
    
    # 1. Timeline Event Processor
    zip_file = package_lambda(
        PROJECT_ROOT / 'lambda_timeline_processor',
        PROJECT_ROOT / 'lambda_timeline_processor.zip',
        requirements=['boto3']
    )
    
    function_arn = deploy_lambda_function(
        function_name=f'{PROJECT_PREFIX}-event-processor',
        zip_file=zip_file,
        handler='lambda_function.lambda_handler',
        memory=1024,
        timeout=300,
        env_vars={
            'EVENTS_TABLE_NAME': f'{PROJECT_PREFIX}-timeline-events',
            'METADATA_TABLE_NAME': f'{PROJECT_PREFIX}-player-timeline-metadata'
        }
    )
    deployed_functions['event_processor'] = function_arn
    
    # 2. Bedrock Summary Generator
    zip_file = package_lambda(
        PROJECT_ROOT / 'lambda_bedrock_summary_generator',
        PROJECT_ROOT / 'lambda_bedrock_summary_generator.zip',
        requirements=['boto3']
    )
    
    function_arn = deploy_lambda_function(
        function_name=f'{PROJECT_PREFIX}-summary-generator',
        zip_file=zip_file,
        handler='lambda_function.lambda_handler',
        memory=512,
        timeout=120
    )
    deployed_functions['summary_generator'] = function_arn
    
    # 3. API Handler
    zip_file = package_lambda(
        PROJECT_ROOT / 'lambda_api_timeline_handler',
        PROJECT_ROOT / 'lambda_api_handler.zip',
        requirements=['boto3']
    )
    
    function_arn = deploy_lambda_function(
        function_name=f'{PROJECT_PREFIX}-api-handler',
        zip_file=zip_file,
        handler='lambda_function.lambda_handler',
        memory=512,
        timeout=30,
        env_vars={
            'STEP_FUNCTIONS_ARN': 'TO_BE_UPDATED',
            'EVENTS_TABLE_NAME': f'{PROJECT_PREFIX}-timeline-events',
            'METADATA_TABLE_NAME': f'{PROJECT_PREFIX}-player-timeline-metadata',
            'SUMMARIES_TABLE_NAME': f'{PROJECT_PREFIX}-timeline-ai-summaries',
            'QUESTIONS_TABLE_NAME': f'{PROJECT_PREFIX}-timeline-user-questions'
        }
    )
    deployed_functions['api_handler'] = function_arn
    
    return deployed_functions


def create_api_gateway(api_handler_arn: str):
    """
    Creates HTTP API Gateway for timeline endpoints
    """
    
    print("\n=== Creating API Gateway ===\n")
    
    api_name = f'{PROJECT_PREFIX}-api'
    
    # Create API
    try:
        api = apigateway.create_api(
            Name=api_name,
            ProtocolType='HTTP',
            Description='Timeline feature API endpoints',
            CorsConfiguration={
                'AllowOrigins': ['*'],
                'AllowMethods': ['GET', 'POST', 'OPTIONS'],
                'AllowHeaders': ['Content-Type', 'Authorization'],
                'MaxAge': 300
            }
        )
        api_id = api['ApiId']
        print(f"✓ Created API: {api_name}")
        print(f"  API ID: {api_id}")
        
    except apigateway.exceptions.ConflictException:
        # API already exists, get its ID
        apis = apigateway.get_apis()
        api_id = next((a['ApiId'] for a in apis['Items'] if a['Name'] == api_name), None)
        print(f"⚠ API already exists: {api_name}")
    
    # Create Lambda integration
    integration = apigateway.create_integration(
        ApiId=api_id,
        IntegrationType='AWS_PROXY',
        IntegrationUri=api_handler_arn,
        PayloadFormatVersion='2.0'
    )
    integration_id = integration['IntegrationId']
    print(f"✓ Created Lambda integration")
    
    # Create routes
    routes = [
        ('GET', '/timeline/events'),
        ('POST', '/timeline/events/summary'),
        ('POST', '/timeline/ask'),
        ('GET', '/timeline/player/matches'),
        ('POST', '/timeline/batch-process')
    ]
    
    for method, path in routes:
        try:
            route = apigateway.create_route(
                ApiId=api_id,
                RouteKey=f'{method} {path}',
                Target=f'integrations/{integration_id}'
            )
            print(f"  ✓ Created route: {method} {path}")
        except Exception as e:
            print(f"  ⚠ Route may already exist: {method} {path}")
    
    # Create default stage
    try:
        stage = apigateway.create_stage(
            ApiId=api_id,
            StageName='$default',
            AutoDeploy=True
        )
        print(f"✓ Created stage: $default")
    except Exception as e:
        print(f"⚠ Stage may already exist")
    
    # Get API endpoint
    api_endpoint = f"https://{api_id}.execute-api.{AWS_REGION}.amazonaws.com"
    print(f"\n✓ API Gateway endpoint: {api_endpoint}")
    
    # Grant API Gateway permission to invoke Lambda
    try:
        lambda_client.remove_permission(
            FunctionName=f'{PROJECT_PREFIX}-api-handler',
            StatementId='AllowAPIGatewayInvoke'
        )
        print(f"✓ Removed old/stale API Gateway permission")
    except lambda_client.exceptions.ResourceNotFoundException:
        # This is fine, it just means no permission existed
        print(f"  No old permission found, skipping removal.")
    except Exception as e:
        print(f"⚠ Warning: Could not remove old permission: {str(e)}")
    
    # Now, add the new, correct permission
    try:
        lambda_client.add_permission(
            FunctionName=f'{PROJECT_PREFIX}-api-handler',
            StatementId='AllowAPIGatewayInvoke',
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=f"arn:aws:execute-api:{AWS_REGION}:{AWS_ACCOUNT_ID}:{api_id}/*/*"
        )
        print(f"✓ Granted new API Gateway invocation permission")
    except lambda_client.exceptions.ResourceConflictException:
        print(f"⚠ Permission already exists (conflict)")
    
    return api_endpoint


def configure_s3_trigger(function_arn: str):
    """
    Configures S3 to trigger Lambda on timeline file uploads
    """
    
    print("\n=== Configuring S3 Trigger ===\n")
    
    bucket_name = 'lol-training-matches-150k'
    
    # Grant S3 permission to invoke Lambda
    try:
        lambda_client.add_permission(
            FunctionName=f'{PROJECT_PREFIX}-event-processor',
            StatementId='AllowS3Invoke',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn=f'arn:aws:s3:::{bucket_name}'
        )
        print(f"✓ Granted S3 invocation permission")
    except lambda_client.exceptions.ResourceConflictException:
        print(f"⚠ Permission already exists")
    
    # Configure S3 notification
    s3 = boto3.client('s3')
    
    notification_config = {
        'LambdaFunctionConfigurations': [
            {
                'Id': f'{PROJECT_PREFIX}-timeline-upload',
                'LambdaFunctionArn': function_arn,
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [
                            {'Name': 'suffix', 'Value': 'timeline-data.json'}
                        ]
                    }
                }
            }
        ]
    }
    
    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_config
        )
        print(f"✓ Configured S3 bucket notification")
        print(f"  Bucket: {bucket_name}")
        print(f"  Trigger: timeline-data.json uploads")
    except Exception as e:
        print(f"⚠ Error configuring S3 notification: {str(e)}")
        print(f"  You may need to configure this manually in the AWS Console")


def main():
    """
    Orchestrates Lambda deployment
    """
    
    print("="*60)
    print("LOL Coach Timeline Feature - Lambda Deployment")
    print("="*60)
    
    # Deploy all Lambda functions
    deployed_functions = deploy_all_lambdas()
    
    # Create API Gateway
    api_endpoint = create_api_gateway(deployed_functions['api_handler'])
    
    # Configure S3 trigger
    configure_s3_trigger(deployed_functions['event_processor'])
    
    # Save deployment info
    deployment_info = {
        'functions': deployed_functions,
        'api_endpoint': api_endpoint,
        'deployed_at': str(boto3.client('sts').get_caller_identity())
    }
    
    # MODIFIED: Write the output file to the project root
    output_info_path = PROJECT_ROOT / 'lambda_deployment_info.json'
    with open(output_info_path, 'w') as f:
        json.dump(deployment_info, f, indent=2)
    
    print("\n" + "="*60)
    print("Lambda Deployment Complete!")
    print("="*60)
    print(f"\nAPI Endpoint: {api_endpoint}")
    print(f"\nDeployed Functions:")
    for name, arn in deployed_functions.items():
        print(f"  {name}: {arn}")
    # MODIFIED: Use absolute path in log
    print(f"\nDeployment info saved to: {output_info_path}")
    print("\nNext step: Deploy Step Functions workflow")
    print(f"  python {SCRIPT_DIR / 'deploy_step_functions.py'}") # MODIFIED: Show correct next command


if __name__ == "__main__":
    main()