#!/usr/bin/env python
"""
Migration script to migrate product images from Google Drive to S3
This script:
1. Fetches all product images from the product_images table
2. Downloads images from Google Drive URLs (from image_url field)
3. Uploads them to S3 with naming convention: {sku}-{number}.{extension}
4. Updates the product_images table with new S3 URLs in the s3_url field
   (Original Google Drive URLs remain in image_url field)
"""

import sys
from pathlib import Path
import requests
import tempfile
import os
from collections import defaultdict

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models.product import Product, ProductImage
from src.services.s3_service import S3Service


def extract_google_drive_id(url):
    """
    Extract file ID from Google Drive URL
    Supports various Google Drive URL formats
    """
    if 'drive.google.com' not in url:
        return None
    
    # Format: https://drive.google.com/file/d/{FILE_ID}/view
    if '/file/d/' in url:
        file_id = url.split('/file/d/')[1].split('/')[0]
        return file_id
    
    # Format: https://drive.google.com/open?id={FILE_ID}
    if 'id=' in url:
        file_id = url.split('id=')[1].split('&')[0]
        return file_id
    
    return None


def download_from_google_drive(url, destination):
    """
    Download file from Google Drive URL
    
    Args:
        url: Google Drive URL
        destination: Local file path to save the downloaded file
    
    Returns:
        bool: True if successful, False otherwise
    """
    file_id = extract_google_drive_id(url)
    
    if not file_id:
        print(f"  ❌ Could not extract file ID from URL: {url}")
        return False
    
    # Google Drive direct download URL
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    try:
        session = requests.Session()
        response = session.get(download_url, stream=True)
        
        # Handle large files with confirmation token
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={value}"
                response = session.get(download_url, stream=True)
                break
        
        if response.status_code == 200:
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            print(f"  ❌ Failed to download. Status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error downloading file: {str(e)}")
        return False


def get_file_extension(url):
    """
    Get file extension from URL or default to .jpg
    """
    # Try to get extension from URL
    path = url.split('?')[0]  # Remove query parameters
    ext = os.path.splitext(path)[1]
    
    if ext and ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        return ext.lower()
    
    # Default to .jpg
    return '.jpg'


def migrate_images():
    """
    Main migration function
    """
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("PRODUCT IMAGES MIGRATION: Google Drive → S3")
        print("=" * 70)
        print()
        
        # Initialize S3 service
        s3_service = S3Service()
        bucket_name = app.config['S3_BUCKET_NAME']
        
        if not bucket_name:
            print("❌ Error: S3_BUCKET_NAME not configured in environment")
            return
        
        print(f"S3 Bucket: {bucket_name}")
        print(f"AWS Region: {app.config['AWS_REGION']}")
        print()
        
        # Fetch all product images with their associated products
        print("Fetching product images from database...")
        product_images = db.session.query(ProductImage).join(Product).all()
        
        if not product_images:
            print("✓ No product images found in database")
            return
        
        print(f"Found {len(product_images)} product images to migrate")
        print()
        
        # Group images by product_id to assign sequential numbers
        images_by_product = defaultdict(list)
        for img in product_images:
            images_by_product[img.product_id].append(img)
        
        # Statistics
        total_images = len(product_images)
        migrated_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Process each product's images
        for product_id, images in images_by_product.items():
            # Get product to access SKU
            product = db.session.query(Product).get(product_id)
            
            if not product:
                print(f"⚠ Warning: Product {product_id} not found, skipping {len(images)} images")
                skipped_count += len(images)
                continue
            
            print(f"\nProcessing Product: {product.sku} (ID: {product_id})")
            print(f"  Images to migrate: {len(images)}")
            
            # Process each image for this product
            for idx, product_image in enumerate(images, start=1):
                image_url = product_image.image_url

                # Skip if already migrated to S3 (check s3_url field)
                if product_image.s3_url:
                    print(f"  [{idx}] ⏭  Already migrated, skipping: {product_image.s3_url}")
                    skipped_count += 1
                    continue

                print(f"  [{idx}] Migrating: {image_url}")
                
                # Get file extension
                file_extension = get_file_extension(image_url)
                
                # Create S3 key with naming convention: {sku}-{number}.{extension}
                s3_key = f"product-images/{product.sku}-{idx}{file_extension}"
                
                # Create temporary file for download
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                    temp_path = temp_file.name
                
                try:
                    # Download from Google Drive
                    print(f"      Downloading from Google Drive...")
                    if not download_from_google_drive(image_url, temp_path):
                        print(f"      ❌ Failed to download image")
                        failed_count += 1
                        continue
                    
                    # Upload to S3
                    print(f"      Uploading to S3: {s3_key}")
                    new_url = s3_service.upload_file(temp_path, bucket_name, s3_key)

                    # Update database - save to s3_url field (keep original in image_url)
                    product_image.s3_url = new_url
                    db.session.commit()

                    print(f"      ✓ Migrated successfully")
                    print(f"      S3 URL: {new_url}")
                    migrated_count += 1
                    
                except Exception as e:
                    db.session.rollback()
                    print(f"      ❌ Error: {str(e)}")
                    failed_count += 1
                
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
        
        # Print summary
        print()
        print("=" * 70)
        print("MIGRATION SUMMARY")
        print("=" * 70)
        print(f"Total images:     {total_images}")
        print(f"✓ Migrated:       {migrated_count}")
        print(f"⏭  Skipped:        {skipped_count}")
        print(f"❌ Failed:         {failed_count}")
        print("=" * 70)
        
        if failed_count > 0:
            print()
            print("⚠ Some images failed to migrate. Please review the errors above.")
        elif migrated_count > 0:
            print()
            print("✓ Migration completed successfully!")


if __name__ == '__main__':
    try:
        migrate_images()
    except KeyboardInterrupt:
        print("\n\n⚠ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

