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

    def _get_queue_url(self, queue_type='image_processing'):
        """
        Get the appropriate queue URL based on queue type

        Args:
            queue_type: Type of queue ('image_processing' or 'catalog_sync')

        Returns:
            str: Queue URL
        """
        if queue_type == 'catalog_sync':
            return current_app.config.get('CATALOG_SYNC_QUEUE_URL')
        else:
            return current_app.config.get('SQS_QUEUE_URL')
    
    def send_message(self, product_id, prompt_id=None, is_raw_image=False):
        """
        Send a product ID to SQS queue for image processing

        Args:
            product_id: ID of the product to process
            prompt_id: Optional prompt ID for AI image generation
            is_raw_image: Whether the product has a raw image that needs AI processing (default: False)

        Returns:
            dict: Response from SQS
        """
        sqs_client = self._get_sqs_client()
        queue_url = self._get_queue_url('image_processing')

        try:
            message_body = {
                'product_id': product_id,
                'is_raw_image': is_raw_image
            }

            # Include prompt_id if provided
            if prompt_id:
                message_body['prompt_id'] = prompt_id

            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body)
            )

            current_app.logger.info(f"Sent product_id {product_id} to image processing queue with prompt_id: {prompt_id}, is_raw_image: {is_raw_image}")
            return response

        except ClientError as e:
            current_app.logger.error(f"Error sending message to SQS: {str(e)}")
            raise Exception(f"Failed to send message to SQS: {str(e)}")

    def send_catalog_sync_message(self, product_id, action='create'):
        """
        Send a product ID to catalog sync SQS queue for Shopify sync

        Args:
            product_id: ID of the product to sync
            action: Action to perform ('create' or 'update')

        Returns:
            dict: Response from SQS
        """
        sqs_client = self._get_sqs_client()
        queue_url = self._get_queue_url('catalog_sync')

        if not queue_url:
            current_app.logger.warning("CATALOG_SYNC_QUEUE_URL not configured, skipping catalog sync")
            return None

        try:
            message_body = {
                'product_id': product_id,
                'action': action
            }

            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body)
            )

            current_app.logger.info(f"Sent product_id {product_id} to catalog sync queue with action: {action}")
            return response

        except ClientError as e:
            current_app.logger.error(f"Error sending catalog sync message to SQS: {str(e)}")
            raise Exception(f"Failed to send catalog sync message to SQS: {str(e)}")
    
    def receive_messages(self, max_messages=1, wait_time=20, queue_type='image_processing'):
        """
        Receive messages from SQS queue

        Args:
            max_messages: Maximum number of messages to receive (1-10)
            wait_time: Long polling wait time in seconds (0-20)
            queue_type: Type of queue to receive from ('image_processing' or 'catalog_sync')

        Returns:
            list: List of messages
        """
        sqs_client = self._get_sqs_client()
        queue_url = self._get_queue_url(queue_type)

        if not queue_url:
            return []

        try:
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                MessageAttributeNames=['All']
            )

            return response.get('Messages', [])

        except ClientError as e:
            current_app.logger.error(f"Error receiving messages from SQS ({queue_type}): {str(e)}")
            raise Exception(f"Failed to receive messages from SQS: {str(e)}")
    
    def delete_message(self, receipt_handle, queue_type='image_processing'):
        """
        Delete a message from SQS queue after processing

        Args:
            receipt_handle: Receipt handle of the message to delete
            queue_type: Type of queue to delete from ('image_processing' or 'catalog_sync')
        """
        sqs_client = self._get_sqs_client()
        queue_url = self._get_queue_url(queue_type)

        if not queue_url:
            return

        try:
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )

            current_app.logger.info(f"Deleted message from SQS queue ({queue_type})")

        except ClientError as e:
            current_app.logger.error(f"Error deleting message from SQS ({queue_type}): {str(e)}")
            raise Exception(f"Failed to delete message from SQS: {str(e)}")


# Create a singleton instance
sqs_service = SQSService()

