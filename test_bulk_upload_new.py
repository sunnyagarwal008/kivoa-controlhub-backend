#!/usr/bin/env python
"""
Test script for the updated bulk product upload API with category_id, SKU, and purchase_month
"""

import requests
from datetime import datetime

# API endpoint
BASE_URL = "http://localhost:5000/api"
CATEGORIES_ENDPOINT = f"{BASE_URL}/categories"
BULK_UPLOAD_ENDPOINT = f"{BASE_URL}/products/bulk"
PRODUCTS_ENDPOINT = f"{BASE_URL}/products"

def test_get_categories():
    """Test getting all categories"""
    print("\n" + "=" * 60)
    print("Step 1: Getting Available Categories")
    print("=" * 60)
    
    try:
        response = requests.get(CATEGORIES_ENDPOINT)
        
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                categories = data['data']
                print(f"✓ Found {len(categories)} categories:")
                for cat in categories:
                    print(f"  • ID: {cat['id']}, Name: {cat['name']}, Prefix: {cat['prefix']}, Sequence: {cat['sku_sequence_number']}")
                return categories
            else:
                print(f"✗ Error: {data.get('error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            print(response.text)
        
        return []
        
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return []


def test_bulk_upload(categories):
    """Test the bulk upload endpoint with new structure"""
    print("\n" + "=" * 60)
    print("Step 2: Testing Bulk Product Upload")
    print("=" * 60)

    if not categories:
        print("⚠ No categories available. Please create categories first.")
        return

    # Use the first two categories (or first one if only one exists)
    category_1 = categories[0]
    category_2 = categories[1] if len(categories) > 1 else categories[0]

    # Get current month in MMYY format
    purchase_month = datetime.now().strftime('%m%y')
    print(f"Purchase month: {purchase_month}")

    # Sample products with new structure (using category names)
    sample_products = {
        "products": [
            {
                "category": category_1['name'],
                "purchase_month": purchase_month,
                "raw_image": "https://example.com/images/laptop.jpg",
                "mrp": 1200.00,
                "price": 1000.00,
                "discount": 200.00,
                "gst": 18.00
            },
            {
                "category": category_2['name'],
                "purchase_month": purchase_month,
                "raw_image": "https://example.com/images/smartphone.jpg",
                "mrp": 800.00,
                "price": 650.00,
                "discount": 150.00,
                "gst": 18.00
            },
            {
                "category": category_1['name'],
                "purchase_month": purchase_month,
                "raw_image": "https://example.com/images/headphones.jpg",
                "mrp": 300.00,
                "price": 250.00,
                "discount": 50.00,
                "gst": 12.00
            }
        ]
    }

    print(f"\nUploading {len(sample_products['products'])} products...")
    print(f"Categories used: {category_1['name']}, {category_2['name']}")
    
    try:
        response = requests.post(
            BULK_UPLOAD_ENDPOINT,
            json=sample_products,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\nResponse Status Code: {response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            print("\n✓ SUCCESS!")
            print(f"Message: {data['message']}")
            print(f"Created: {data['data']['created']} products")
            
            print("\nCreated Products:")
            for product in data['data']['products']:
                print(f"  • ID: {product['id']}")
                print(f"    SKU: {product['sku']}")
                print(f"    Category: {product['category']} (ID: {product['category_id']})")
                print(f"    Purchase Month: {product['purchase_month']}")
                print(f"    Price: ${product['price']}")
                print(f"    Status: {product['status']}")
                print()
        else:
            data = response.json()
            print("\n✗ FAILED!")
            print(f"Error: {data.get('error', 'Unknown error')}")
            if 'details' in data:
                print(f"Details: {data['details']}")
        
    except Exception as e:
        print(f"\n✗ Exception occurred: {str(e)}")


def test_get_products_by_category(category_id):
    """Test getting products filtered by category"""
    print("\n" + "=" * 60)
    print(f"Step 3: Getting Products for Category ID {category_id}")
    print("=" * 60)
    
    try:
        response = requests.get(f"{PRODUCTS_ENDPOINT}?category_id={category_id}")
        
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                products = data['data']
                print(f"✓ Found {len(products)} products:")
                for product in products:
                    print(f"  • {product['sku']} - ${product['price']} - {product['category']}")
            else:
                print(f"✗ Error: {data.get('error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
        
    except Exception as e:
        print(f"✗ Exception: {str(e)}")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("BULK PRODUCT UPLOAD API TEST (New Structure)")
    print("=" * 60)
    print("\nThis test demonstrates the new API structure with:")
    print("  • category_id instead of category string")
    print("  • Auto-generated SKU")
    print("  • purchase_month in MMYY format")
    print()
    
    # Step 1: Get categories
    categories = test_get_categories()
    
    if not categories:
        print("\n⚠ WARNING: No categories found!")
        print("Please run the migration script first:")
        print("  python scripts/add_category_and_sku.py")
        print("\nOr create categories manually using the example script:")
        print("  python scripts/example_category_usage.py")
        return
    
    # Step 2: Test bulk upload
    test_bulk_upload(categories)
    
    # Step 3: Test filtering by category
    if categories:
        test_get_products_by_category(categories[0]['id'])
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()

