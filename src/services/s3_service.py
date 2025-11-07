import boto3
from botocore.exceptions import ClientError
from flask import current_app
import uuid
import os
import requests
import tempfile


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

    def upload_file(self, file_path, bucket_name, key):
        s3_client = self._get_s3_client()
        s3_client.upload_file(file_path, bucket_name, key)

        # Construct file URL (assuming public bucket or CDN)
        region = current_app.config.get('AWS_REGION', 'ap-south-1')
        cdn_domain = current_app.config.get('CDN_DOMAIN')  # optional custom domain

        if cdn_domain:
            file_url = f"https://{cdn_domain}/{key}"
        else:
            file_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"

        return file_url

    
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
        cdn_domain = current_app.config.get('CDN_DOMAIN')

        try:
            # Extract key from URL - handle both CDN and S3 URLs
            if cdn_domain and cdn_domain in file_url:
                # CDN URL format: https://{cdn_domain}/{key}
                key = file_url.split(f"{cdn_domain}/")[1]
            else:
                # S3 URL format: https://{bucket}.s3.{region}.amazonaws.com/{key}
                key = file_url.split(f"{bucket_name}.s3.{current_app.config['AWS_REGION']}.amazonaws.com/")[1]

            s3_client.delete_object(Bucket=bucket_name, Key=key)
            current_app.logger.info(f"Deleted file from S3: {key}")

        except (ClientError, IndexError) as e:
            current_app.logger.error(f"Error deleting file from S3: {str(e)}")
            raise Exception(f"Failed to delete file: {str(e)}")

    def copy_image_from_url_to_s3(self, image_url, key):
        """
        Download an image from a URL and upload it to S3

        Args:
            image_url: URL of the image to download
            key: S3 key where the image should be stored

        Returns:
            str: Public S3 URL of the uploaded image
        """
        bucket_name = current_app.config['S3_BUCKET_NAME']

        try:
            # Download the image from URL
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            # Get file extension from URL or content-type
            file_extension = os.path.splitext(image_url.split('?')[0])[1]
            if not file_extension:
                content_type = response.headers.get('content-type', '')
                if 'jpeg' in content_type or 'jpg' in content_type:
                    file_extension = '.jpg'
                elif 'png' in content_type:
                    file_extension = '.png'
                elif 'gif' in content_type:
                    file_extension = '.gif'
                elif 'webp' in content_type:
                    file_extension = '.webp'
                else:
                    file_extension = '.jpg'  # default

            # Create temporary file to save the downloaded image
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name

            try:
                # Upload to S3
                file_url = self.upload_file(temp_path, bucket_name, key)
                current_app.logger.info(f"Copied image from {image_url} to S3: {key}")
                return file_url
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except requests.RequestException as e:
            current_app.logger.error(f"Error downloading image from URL: {str(e)}")
            raise Exception(f"Failed to download image from URL: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error copying image to S3: {str(e)}")
            raise Exception(f"Failed to copy image to S3: {str(e)}")


# Create a singleton instance
s3_service = S3Service()

