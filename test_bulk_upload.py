#!/usr/bin/env python
"""
Test script for bulk product upload API
Demonstrates how to use the bulk upload endpoint
"""

import requests
import json

# API Configuration
BASE_URL = "http://localhost:5000"
BULK_UPLOAD_ENDPOINT = f"{BASE_URL}/api/products/bulk"

# Sample products data
sample_products = {
    "products": [
        {
            "category": "Electronics",
            "raw_image": "https://example.com/images/laptop.jpg",
            "mrp": 1200.00,
            "price": 999.00,
            "discount": 201.00,
            "gst": 18.00
        },
        {
            "category": "Clothing",
            "raw_image": "https://example.com/images/tshirt.jpg",
            "mrp": 500.00,
            "price": 399.00,
            "discount": 101.00,
            "gst": 12.00
        },
        {
            "category": "Books",
            "raw_image": "https://example.com/images/book.jpg",
            "mrp": 300.00,
            "price": 250.00,
            "discount": 50.00,
            "gst": 5.00
        },
        {
            "category": "Home & Kitchen",
            "raw_image": "https://example.com/images/blender.jpg",
            "mrp": 2500.00,
            "price": 1999.00,
            "discount": 501.00,
            "gst": 18.00
        },
        {
            "category": "Sports",
            "raw_image": "https://example.com/images/football.jpg",
            "mrp": 800.00,
            "price": 650.00,
            "discount": 150.00,
            "gst": 18.00
        }
    ]
}

def test_bulk_upload():
    """Test the bulk upload endpoint"""
    
    print("=" * 60)
    print("Testing Bulk Product Upload API")
    print("=" * 60)
    print()
    
    print(f"Endpoint: {BULK_UPLOAD_ENDPOINT}")
    print(f"Number of products: {len(sample_products['products'])}")
    print()
    
    try:
        # Make the request
        print("Sending bulk upload request...")
        response = requests.post(
            BULK_UPLOAD_ENDPOINT,
            json=sample_products,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print()
        
        # Parse response
        result = response.json()
        
        print("Response:")
        print("-" * 60)
        print(json.dumps(result, indent=2))
        print("-" * 60)
        print()
        
        # Summary
        if result.get('success'):
            data = result.get('data', {})
            print("✅ Bulk Upload Summary:")
            print(f"   Total Products: {data.get('total', 0)}")
            print(f"   Successfully Created: {data.get('created', 0)}")
            print(f"   Failed: {data.get('failed', 0)}")
            
            if data.get('errors'):
                print()
                print("❌ Errors:")
                for error in data['errors']:
                    print(f"   - Product at index {error['index']}: {error['errors']}")
        else:
            print(f"❌ Request failed: {result.get('error', 'Unknown error')}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the API")
        print("   Make sure the Flask server is running:")
        print("   python run.py")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    print()
    print("=" * 60)


if __name__ == '__main__':
    test_bulk_upload()

