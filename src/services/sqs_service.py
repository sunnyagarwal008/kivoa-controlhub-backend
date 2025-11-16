import boto3
import json
from botocore.exceptions import ClientError
from flask import current_app


class SQSService:
    """Service class for AWS SQS operations"""
    
    def __init__(self):
        self.sqs_client = None
    
    def _get_sqs_client(self):
        """Get or create SQS client"""
        if self.sqs_client is None:
            self.sqs_client = boto3.client(
                'sqs',
                aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
                region_name=current_app.config['AWS_REGION']
            )
        return self.sqs_client
    
    def send_message(self, product_id, prompt_id=None):
        """
        Send a product ID to SQS queue for processing

        Args:
            product_id: ID of the product to process
            prompt_id: Optional prompt ID for AI image generation

        Returns:
            dict: Response from SQS
        """
        sqs_client = self._get_sqs_client()
        queue_url = current_app.config['SQS_QUEUE_URL']

        try:
            message_body = {
                'product_id': product_id
            }

            # Include prompt_id if provided
            if prompt_id:
                message_body['prompt_id'] = prompt_id

            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body)
            )

            current_app.logger.info(f"Sent product_id {product_id} to SQS queue with prompt_id: {prompt_id}")
            return response

        except ClientError as e:
            current_app.logger.error(f"Error sending message to SQS: {str(e)}")
            raise Exception(f"Failed to send message to SQS: {str(e)}")
    
    def receive_messages(self, max_messages=1, wait_time=20):
        """
        Receive messages from SQS queue
        
        Args:
            max_messages: Maximum number of messages to receive (1-10)
            wait_time: Long polling wait time in seconds (0-20)
            
        Returns:
            list: List of messages
        """
        sqs_client = self._get_sqs_client()
        queue_url = current_app.config['SQS_QUEUE_URL']
        
        try:
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                MessageAttributeNames=['All']
            )
            
            return response.get('Messages', [])
            
        except ClientError as e:
            current_app.logger.error(f"Error receiving messages from SQS: {str(e)}")
            raise Exception(f"Failed to receive messages from SQS: {str(e)}")
    
    def delete_message(self, receipt_handle):
        """
        Delete a message from SQS queue after processing
        
        Args:
            receipt_handle: Receipt handle of the message to delete
        """
        sqs_client = self._get_sqs_client()
        queue_url = current_app.config['SQS_QUEUE_URL']
        
        try:
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            
            current_app.logger.info("Deleted message from SQS queue")
            
        except ClientError as e:
            current_app.logger.error(f"Error deleting message from SQS: {str(e)}")
            raise Exception(f"Failed to delete message from SQS: {str(e)}")


# Create a singleton instance
sqs_service = SQSService()

