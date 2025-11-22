#!/usr/bin/env python
"""
Migration script to fix Content-Type headers for all product images in S3

This script:
1. Fetches all product images from the product_images table
2. For each S3 image URL, updates the Content-Type metadata in S3
3. Uses S3 copy_object to update metadata without re-uploading files
4. Determines correct content type based on file extension

The script updates the Content-Type header in place on S3 without modifying
the database or downloading/re-uploading files.

Usage:
    python scripts/fix_s3_content_types.py

Requirements:
    - AWS credentials must be configured in environment variables
    - S3_BUCKET_NAME must be set in config
    - Database must be accessible

The script will:
    - Show progress for each image being processed
    - Display current and new Content-Type for each update
    - Skip images that already have correct Content-Type
    - Provide a summary at the end with statistics
"""

import sys
from pathlib import Path
import os
from urllib.parse import urlparse

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models.product import ProductImage
import boto3
from botocore.exceptions import ClientError


def get_content_type_from_extension(file_path):
    """
    Determine content type from file extension
    
    Args:
        file_path: Path or URL of the file
        
    Returns:
        str: MIME type of the file
    """
    # Get file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    # Map common image extensions to MIME types
    content_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.svg': 'image/svg+xml',
    }
    
    return content_type_map.get(ext, 'image/jpeg')  # Default to image/jpeg


def extract_s3_key_from_url(url, bucket_name, region, cdn_domain=None):
    """
    Extract S3 key from URL
    
    Args:
        url: Full S3 or CDN URL
        bucket_name: S3 bucket name
        region: AWS region
        cdn_domain: Optional CDN domain
        
    Returns:
        str: S3 key (path within bucket)
    """
    try:
        # Handle CDN URLs
        if cdn_domain and cdn_domain in url:
            # CDN URL format: https://{cdn_domain}/{key}
            key = url.split(f"{cdn_domain}/")[1]
            return key
        
        # Handle S3 URLs
        # Format: https://{bucket}.s3.{region}.amazonaws.com/{key}
        if f"{bucket_name}.s3.{region}.amazonaws.com/" in url:
            key = url.split(f"{bucket_name}.s3.{region}.amazonaws.com/")[1]
            return key
        
        # Alternative S3 URL format: https://s3.{region}.amazonaws.com/{bucket}/{key}
        if f"s3.{region}.amazonaws.com/{bucket_name}/" in url:
            key = url.split(f"s3.{region}.amazonaws.com/{bucket_name}/")[1]
            return key
        
        # If we can't parse it, try to extract everything after the domain
        parsed = urlparse(url)
        key = parsed.path.lstrip('/')
        return key
        
    except Exception as e:
        print(f"    ⚠ Warning: Could not parse URL: {url}")
        print(f"      Error: {str(e)}")
        return None


def update_s3_content_type(s3_client, bucket_name, key, content_type):
    """
    Update Content-Type metadata for an S3 object
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: S3 bucket name
        key: S3 object key
        content_type: New content type to set
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First, get the current object metadata
        head_response = s3_client.head_object(Bucket=bucket_name, Key=key)
        current_content_type = head_response.get('ContentType', 'unknown')
        
        # Skip if already correct
        if current_content_type == content_type:
            return True, current_content_type, True  # success, current_type, was_already_correct
        
        # Copy object to itself with new metadata
        # This updates the metadata without re-uploading the file
        s3_client.copy_object(
            Bucket=bucket_name,
            Key=key,
            CopySource={'Bucket': bucket_name, 'Key': key},
            ContentType=content_type,
            MetadataDirective='REPLACE'
        )
        
        return True, current_content_type, False  # success, old_type, was_already_correct
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404' or error_code == 'NoSuchKey':
            print(f"      ⚠ Object not found in S3: {key}")
        else:
            print(f"      ❌ S3 Error ({error_code}): {str(e)}")
        return False, None, False
    except Exception as e:
        print(f"      ❌ Error: {str(e)}")
        return False, None, False


def fix_content_types():
    """
    Main migration function
    """
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("FIX S3 CONTENT-TYPE HEADERS FOR PRODUCT IMAGES")
        print("=" * 70)
        print()
        
        # Get AWS configuration
        bucket_name = app.config.get('S3_BUCKET_NAME')
        region = app.config.get('AWS_REGION', 'ap-south-1')
        cdn_domain = app.config.get('CDN_DOMAIN')
        
        if not bucket_name:
            print("❌ Error: S3_BUCKET_NAME not configured in environment")
            return
        
        print(f"S3 Bucket: {bucket_name}")
        print(f"AWS Region: {region}")
        if cdn_domain:
            print(f"CDN Domain: {cdn_domain}")
        print()
        
        # Initialize S3 client
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
                region_name=region
            )
        except Exception as e:
            print(f"❌ Error initializing S3 client: {str(e)}")
            return
        
        # Fetch all product images
        print("Fetching product images from database...")
        product_images = ProductImage.query.all()
        
        if not product_images:
            print("✓ No product images found in database")
            return
        
        print(f"Found {len(product_images)} product images")
        print()
        
        # Statistics
        total_images = len(product_images)
        updated_count = 0
        already_correct_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Process each image
        for idx, product_image in enumerate(product_images, start=1):
            image_url = product_image.image_url
            
            print(f"[{idx}/{total_images}] Processing image ID {product_image.id}")
            print(f"  URL: {image_url}")
            
            # Extract S3 key from URL
            s3_key = extract_s3_key_from_url(image_url, bucket_name, region, cdn_domain)
            
            if not s3_key:
                print(f"  ⏭  Skipped: Could not extract S3 key from URL")
                skipped_count += 1
                continue
            
            print(f"  S3 Key: {s3_key}")
            
            # Determine correct content type
            content_type = get_content_type_from_extension(s3_key)
            print(f"  Target Content-Type: {content_type}")
            
            # Update S3 metadata
            success, old_content_type, was_already_correct = update_s3_content_type(
                s3_client, bucket_name, s3_key, content_type
            )
            
            if success:
                if was_already_correct:
                    print(f"  ✓ Already correct: {old_content_type}")
                    already_correct_count += 1
                else:
                    print(f"  ✓ Updated: {old_content_type} → {content_type}")
                    updated_count += 1
            else:
                print(f"  ❌ Failed to update")
                failed_count += 1
            
            print()
        
        # Print summary
        print("=" * 70)
        print("MIGRATION SUMMARY")
        print("=" * 70)
        print(f"Total images:        {total_images}")
        print(f"✓ Updated:           {updated_count}")
        print(f"✓ Already correct:   {already_correct_count}")
        print(f"⏭  Skipped:           {skipped_count}")
        print(f"❌ Failed:            {failed_count}")
        print("=" * 70)
        
        if failed_count > 0:
            print()
            print("⚠ Some images failed to update. Please review the errors above.")
        elif updated_count > 0:
            print()
            print(f"✓ Successfully updated {updated_count} image(s)!")
        else:
            print()
            print("✓ All images already have correct Content-Type headers!")


if __name__ == '__main__':
    try:
        fix_content_types()
    except KeyboardInterrupt:
        print("\n\n⚠ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

