import boto3
from botocore.exceptions import ClientError
from flask import current_app
import uuid
import os


class S3Service:
    """Service class for AWS S3 operations"""
    
    def __init__(self):
        self.s3_client = None
    
    def _get_s3_client(self):
        """Get or create S3 client"""
        if self.s3_client is None:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
                region_name=current_app.config['AWS_REGION']
            )
        return self.s3_client
    
    def generate_presigned_url(self, filename, content_type):
        """
        Generate a presigned URL for uploading a file to S3
        
        Args:
            filename: Original filename
            content_type: MIME type of the file
            
        Returns:
            dict: Contains presigned_url, file_url, and expires_in
        """
        s3_client = self._get_s3_client()
        bucket_name = current_app.config['S3_BUCKET_NAME']
        expiration = current_app.config['PRESIGNED_URL_EXPIRATION']
        
        # Generate unique filename to avoid collisions
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"products/{uuid.uuid4()}{file_extension}"
        
        try:
            # Generate presigned URL for PUT operation
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': unique_filename,
                    'ContentType': content_type
                },
                ExpiresIn=expiration
            )
            
            # Generate the final file URL (without query parameters)
            file_url = f"https://{bucket_name}.s3.{current_app.config['AWS_REGION']}.amazonaws.com/{unique_filename}"
            
            return {
                'presigned_url': presigned_url,
                'file_url': file_url,
                'expires_in': expiration
            }
        
        except ClientError as e:
            current_app.logger.error(f"Error generating presigned URL: {str(e)}")
            raise Exception(f"Failed to generate presigned URL: {str(e)}")
    
    def delete_file(self, file_url):
        """
        Delete a file from S3
        
        Args:
            file_url: Full URL of the file to delete
        """
        s3_client = self._get_s3_client()
        bucket_name = current_app.config['S3_BUCKET_NAME']
        
        try:
            # Extract key from URL
            key = file_url.split(f"{bucket_name}.s3.{current_app.config['AWS_REGION']}.amazonaws.com/")[1]
            
            s3_client.delete_object(Bucket=bucket_name, Key=key)
            current_app.logger.info(f"Deleted file from S3: {key}")
            
        except (ClientError, IndexError) as e:
            current_app.logger.error(f"Error deleting file from S3: {str(e)}")
            raise Exception(f"Failed to delete file: {str(e)}")


# Create a singleton instance
s3_service = S3Service()

