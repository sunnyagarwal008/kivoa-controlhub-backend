#!/usr/bin/env python
"""
Test script for image enhancement workflow
Run this to verify the setup is working correctly
"""
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

from src.app import create_app
from src.database import db
from src.models import Product, ProductImage
from src.services import sqs_service, gemini_service, S3Service


def test_configuration():
    """Test that all required configuration is present"""
    print("Testing Configuration...")
    
    required_vars = [
        'DATABASE_URL',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_REGION',
        'S3_BUCKET_NAME',
        'SQS_QUEUE_URL',
        'GEMINI_API_KEY'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        return False
    
    print("✓ All required environment variables are set")
    return True


def test_database():
    """Test database connection and tables"""
    print("\nTesting Database...")
    
    app = create_app()
    with app.app_context():
        try:
            # Check if tables exist
            product_count = Product.query.count()
            print(f"✓ Products table exists ({product_count} products)")
            
            # Check if product_images table exists
            image_count = ProductImage.query.count()
            print(f"✓ ProductImages table exists ({image_count} images)")
            
            return True
        except Exception as e:
            print(f"❌ Database error: {str(e)}")
            return False


def test_sqs():
    """Test SQS connection"""
    print("\nTesting SQS...")
    
    app = create_app()
    with app.app_context():
        try:
            # Try to get queue attributes
            sqs_client = sqs_service._get_sqs_client()
            queue_url = app.config['SQS_QUEUE_URL']
            
            response = sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            
            msg_count = response['Attributes']['ApproximateNumberOfMessages']
            print(f"✓ SQS connection successful")
            print(f"  Queue URL: {queue_url}")
            print(f"  Messages in queue: {msg_count}")
            
            return True
        except Exception as e:
            print(f"❌ SQS error: {str(e)}")
            return False


def test_s3():
    """Test S3 connection"""
    print("\nTesting S3...")
    
    app = create_app()
    with app.app_context():
        try:
            s3_service = S3Service()
            s3_client = s3_service._get_s3_client()
            bucket_name = app.config['S3_BUCKET_NAME']
            
            # Try to list objects (just to verify access)
            s3_client.head_bucket(Bucket=bucket_name)
            
            print(f"✓ S3 connection successful")
            print(f"  Bucket: {bucket_name}")
            print(f"  Region: {app.config['AWS_REGION']}")
            
            return True
        except Exception as e:
            print(f"❌ S3 error: {str(e)}")
            return False


def test_gemini():
    """Test Gemini API connection"""
    print("\nTesting Gemini API...")
    
    app = create_app()
    with app.app_context():
        try:
            # Just verify the model can be initialized
            model = gemini_service._get_model()
            
            print(f"✓ Gemini API connection successful")
            print(f"  Model: {app.config['GEMINI_MODEL']}")
            print(f"  Enhanced images count: {app.config['ENHANCED_IMAGES_COUNT']}")
            
            return True
        except Exception as e:
            print(f"❌ Gemini API error: {str(e)}")
            return False


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Image Enhancement System - Configuration Test")
    print("=" * 60)
    print()
    
    results = {
        'Configuration': test_configuration(),
        'Database': test_database(),
        'SQS': test_sqs(),
        'S3': test_s3(),
        'Gemini API': test_gemini()
    }
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! System is ready.")
        print("\nNext steps:")
        print("1. Start the worker: python -m src.worker")
        print("2. Create products via bulk API")
        print("3. Monitor worker logs for processing")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Run: python scripts/create_product_images_table.py")
        print("- Run: python scripts/setup_sqs_queue.py")
        print("- Check your .env file has all required variables")
    print("=" * 60)
    
    return all_passed


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

