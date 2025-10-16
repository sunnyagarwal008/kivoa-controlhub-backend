#!/usr/bin/env python
"""
Script to create AWS SQS queue for product image processing
Run this script to automatically create the SQS queue
"""
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()


def create_sqs_queue():
    """Create SQS queue for product image processing"""
    
    # Get AWS credentials from environment
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if not aws_access_key or not aws_secret_key:
        print("❌ Error: AWS credentials not found in .env file")
        print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return
    
    # Create SQS client
    sqs = boto3.client(
        'sqs',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    
    queue_name = 'product-image-processing'
    
    try:
        print(f"Creating SQS queue: {queue_name}")
        
        # Create queue with appropriate settings
        response = sqs.create_queue(
            QueueName=queue_name,
            Attributes={
                'VisibilityTimeout': '300',  # 5 minutes
                'MessageRetentionPeriod': '345600',  # 4 days
                'ReceiveMessageWaitTimeSeconds': '20',  # Long polling
                'DelaySeconds': '0'
            }
        )
        
        queue_url = response['QueueUrl']
        
        print(f"✓ Successfully created SQS queue!")
        print(f"\nQueue URL: {queue_url}")
        print(f"\nAdd this to your .env file:")
        print(f"SQS_QUEUE_URL={queue_url}")
        
        # Get queue attributes
        attrs = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        )
        
        print(f"\nQueue Configuration:")
        print(f"  - Visibility Timeout: {attrs['Attributes']['VisibilityTimeout']} seconds")
        print(f"  - Message Retention: {attrs['Attributes']['MessageRetentionPeriod']} seconds")
        print(f"  - Long Polling: {attrs['Attributes']['ReceiveMessageWaitTimeSeconds']} seconds")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        
        if error_code == 'QueueAlreadyExists':
            print(f"⚠️  Queue '{queue_name}' already exists")
            
            # Get existing queue URL
            try:
                response = sqs.get_queue_url(QueueName=queue_name)
                queue_url = response['QueueUrl']
                print(f"\nExisting Queue URL: {queue_url}")
                print(f"\nAdd this to your .env file:")
                print(f"SQS_QUEUE_URL={queue_url}")
            except ClientError:
                print("❌ Error: Could not retrieve existing queue URL")
        else:
            print(f"❌ Error creating queue: {str(e)}")
    
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")


if __name__ == '__main__':
    print("=" * 60)
    print("AWS SQS Queue Setup")
    print("=" * 60)
    print()
    create_sqs_queue()
    print()
    print("=" * 60)

