#!/usr/bin/env python
"""
Migration script to update products from Shopify export CSV
This script:
1. Reads the Shopify products export CSV file
2. Uses Variant SKU to uniquely identify products
3. Updates handle, title, and description fields in the database
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models.product import Product


def parse_shopify_csv(csv_file_path):
    """
    Parse Shopify export CSV and extract product data
    
    Args:
        csv_file_path: Path to the Shopify export CSV file
        
    Returns:
        dict: Dictionary mapping SKU to product data (handle, title, description)
    """
    products_data = {}
    
    with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            variant_sku = row.get('Variant SKU', '').strip()
            
            # Skip rows without SKU
            if not variant_sku:
                continue
            
            # Only process rows that have product details (first row for each product)
            # Subsequent rows for the same product only have image data
            handle = row.get('Handle', '').strip()
            title = row.get('Title', '').strip()
            description = row.get('Body (HTML)', '').strip()
            
            # Only add/update if this row has product details
            if handle and title:
                products_data[variant_sku] = {
                    'handle': handle,
                    'title': title,
                    'description': description
                }
    
    return products_data


def update_products(products_data, dry_run=False):
    """
    Update products in the database
    
    Args:
        products_data: Dictionary mapping SKU to product data
        dry_run: If True, only show what would be updated without making changes
        
    Returns:
        tuple: (updated_count, not_found_count, skipped_count)
    """
    app = create_app()
    
    updated_count = 0
    not_found_count = 0
    skipped_count = 0
    not_found_skus = []
    
    with app.app_context():
        print(f"\n{'=' * 80}")
        print(f"{'DRY RUN MODE - NO CHANGES WILL BE MADE' if dry_run else 'UPDATING PRODUCTS'}")
        print(f"{'=' * 80}\n")
        
        for sku, data in products_data.items():
            # Find product by SKU
            product = Product.query.filter_by(sku=sku).first()
            
            if not product:
                not_found_count += 1
                not_found_skus.append(sku)
                print(f"⚠️  SKU not found in database: {sku}")
                continue
            
            # Check if any field needs updating
            needs_update = False
            changes = []
            
            if product.handle != data['handle']:
                needs_update = True
                changes.append(f"handle: '{product.handle}' → '{data['handle']}'")
            
            if product.title != data['title']:
                needs_update = True
                changes.append(f"title: '{product.title}' → '{data['title']}'")
            
            if product.description != data['description']:
                needs_update = True
                old_desc = product.description[:50] + '...' if product.description and len(product.description) > 50 else product.description
                new_desc = data['description'][:50] + '...' if data['description'] and len(data['description']) > 50 else data['description']
                changes.append(f"description: '{old_desc}' → '{new_desc}'")
            
            if not needs_update:
                skipped_count += 1
                print(f"⏭️  Skipped (no changes): {sku}")
                continue
            
            # Update the product
            if not dry_run:
                product.handle = data['handle']
                product.title = data['title']
                product.description = data['description']
            
            updated_count += 1
            print(f"\n✅ {'Would update' if dry_run else 'Updated'}: {sku}")
            print(f"   Product ID: {product.id}")
            for change in changes:
                print(f"   - {change}")
        
        # Commit changes if not dry run
        if not dry_run:
            db.session.commit()
            print(f"\n{'=' * 80}")
            print("✅ All changes committed to database")
            print(f"{'=' * 80}")
        
        # Print summary
        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total products in CSV: {len(products_data)}")
        print(f"{'Would be updated' if dry_run else 'Updated'}: {updated_count}")
        print(f"Skipped (no changes): {skipped_count}")
        print(f"Not found in database: {not_found_count}")
        
        if not_found_skus:
            print(f"\nSKUs not found in database:")
            for sku in not_found_skus:
                print(f"  - {sku}")
        
        print(f"{'=' * 80}\n")
    
    return updated_count, not_found_count, skipped_count


def main():
    """Main function to run the migration"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Update products from Shopify export CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview changes without updating)
  python scripts/migrate_shopify_products.py /path/to/products_export.csv --dry-run
  
  # Actually update the database
  python scripts/migrate_shopify_products.py /path/to/products_export.csv
        """
    )
    
    parser.add_argument(
        'csv_file',
        help='Path to the Shopify products export CSV file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating the database'
    )
    
    args = parser.parse_args()
    
    # Validate CSV file exists
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {args.csv_file}")
        sys.exit(1)
    
    print(f"\n📄 Reading CSV file: {args.csv_file}")
    
    # Parse CSV
    try:
        products_data = parse_shopify_csv(csv_path)
        print(f"✅ Found {len(products_data)} products in CSV file")
    except Exception as e:
        print(f"❌ Error parsing CSV file: {str(e)}")
        sys.exit(1)
    
    if not products_data:
        print("⚠️  No products found in CSV file")
        sys.exit(0)
    
    # Update products
    try:
        updated, not_found, skipped = update_products(products_data, dry_run=args.dry_run)
        
        if args.dry_run:
            print("\n💡 This was a dry run. To actually update the database, run without --dry-run flag")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error updating products: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

