#!/usr/bin/env python
"""
Migration script to generate titles and descriptions for existing products
that are live or pending_review and don't have title/description yet.

This script:
1. Finds all products with status 'live' or 'pending_review'
2. Filters products that don't have title or description
3. Downloads their raw images
4. Uses Gemini AI to generate title and description
5. Updates the products with generated content

Usage:
    python scripts/migrate_generate_titles_descriptions.py [--dry-run] [--batch-size N] [--limit N]

Options:
    --dry-run       Show what would be updated without making changes
    --batch-size N  Process N products at a time (default: 10)
    --limit N       Limit total number of products to process (default: no limit)
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models import Product
from src.services.gemini_service import gemini_service, download_image
from flask import current_app


def generate_handle_from_title(title):
    """Generate a URL-friendly handle from title"""
    if not title:
        return None
    # Convert to lowercase, replace spaces and slashes with hyphens
    handle = title.lower().replace(' ', '-').replace('/', '-')
    # Remove any characters that aren't alphanumeric or hyphens
    handle = ''.join(c for c in handle if c.isalnum() or c == '-')
    # Remove consecutive hyphens
    while '--' in handle:
        handle = handle.replace('--', '-')
    # Trim hyphens from start and end
    handle = handle.strip('-')
    # Limit to 255 characters
    return handle[:255]


def process_product(product, dry_run=False):
    """
    Process a single product to generate title and description
    
    Args:
        product: Product object to process
        dry_run: If True, don't save changes to database
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing product {product.id} (SKU: {product.sku})...")
        print(f"  Status: {product.status}")
        print(f"  Current title: {product.title or '(none)'}")
        print(f"  Current description: {product.description[:50] + '...' if product.description else '(none)'}")
        print(f"  Raw image: {product.raw_image}")
        
        # Download the raw image
        print(f"  Downloading image...")
        try:
            raw_image_path = download_image(product.raw_image)
            print(f"  Downloaded to: {raw_image_path}")
        except Exception as e:
            error_msg = f"Failed to download image: {str(e)}"
            print(f"  ❌ {error_msg}")
            return False, error_msg
        
        # Generate title and description using Gemini
        print(f"  Generating title and description with Gemini AI...")
        try:
            title_desc = gemini_service.generate_title_and_description(raw_image_path)
            generated_title = title_desc['title']
            generated_description = title_desc['description']
            generated_handle = generate_handle_from_title(generated_title)
            
            print(f"  ✓ Generated title: {generated_title}")
            print(f"  ✓ Generated description: {generated_description[:100]}...")
            print(f"  ✓ Generated handle: {generated_handle}")
            
        except Exception as e:
            error_msg = f"Failed to generate title/description: {str(e)}"
            print(f"  ❌ {error_msg}")
            return False, error_msg
        finally:
            # Clean up downloaded image
            if os.path.exists(raw_image_path):
                os.remove(raw_image_path)
                print(f"  Cleaned up temporary file: {raw_image_path}")
        
        # Update the product
        if not dry_run:
            product.title = generated_title
            product.description = generated_description
            product.handle = generated_handle
            db.session.commit()
            print(f"  ✓ Product {product.id} updated successfully")
        else:
            print(f"  [DRY RUN] Would update product {product.id}")
        
        return True, "Success"
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Unexpected error: {str(e)}"
        print(f"  ❌ {error_msg}")
        return False, error_msg


def migrate_products(dry_run=False, batch_size=10, limit=None):
    """
    Main migration function to process products
    
    Args:
        dry_run: If True, don't save changes to database
        batch_size: Number of products to process in each batch
        limit: Maximum number of products to process (None for all)
    """
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("Product Title & Description Migration Script")
        print("=" * 80)
        
        if dry_run:
            print("\n⚠️  DRY RUN MODE - No changes will be saved to database\n")
        
        # Find products that need title/description generation
        print("\nQuerying products...")
        query = Product.query.filter(
            Product.status.in_(['live', 'pending_review']),
            db.or_(
                Product.title.is_(None),
                Product.title == '',
                Product.description.is_(None),
                Product.description == ''
            )
        ).order_by(Product.id)
        
        if limit:
            query = query.limit(limit)
        
        products = query.all()
        
        total_products = len(products)
        print(f"\nFound {total_products} products that need title/description generation")
        
        if total_products == 0:
            print("\n✓ No products to process. All products already have titles and descriptions!")
            return
        
        # Show summary
        print(f"\nProducts to process:")
        print(f"  - Status: live or pending_review")
        print(f"  - Missing: title and/or description")
        print(f"  - Total: {total_products}")
        print(f"  - Batch size: {batch_size}")
        
        if not dry_run:
            response = input("\nProceed with migration? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Migration cancelled.")
                return
        
        # Process products
        print("\n" + "=" * 80)
        print("Processing products...")
        print("=" * 80)
        
        success_count = 0
        failure_count = 0
        failures = []
        
        for idx, product in enumerate(products, 1):
            print(f"\n[{idx}/{total_products}]", end=" ")
            
            success, message = process_product(product, dry_run)
            
            if success:
                success_count += 1
            else:
                failure_count += 1
                failures.append({
                    'product_id': product.id,
                    'sku': product.sku,
                    'error': message
                })
            
            # Pause between batches to avoid rate limiting
            if idx % batch_size == 0 and idx < total_products:
                print(f"\n  Processed {idx} products. Pausing for 2 seconds...")
                import time
                time.sleep(2)
        
        # Print summary
        print("\n" + "=" * 80)
        print("Migration Summary")
        print("=" * 80)
        print(f"\nTotal products processed: {total_products}")
        print(f"  ✓ Successful: {success_count}")
        print(f"  ❌ Failed: {failure_count}")
        
        if failures:
            print(f"\nFailed products:")
            for failure in failures:
                print(f"  - Product {failure['product_id']} (SKU: {failure['sku']}): {failure['error']}")
        
        if dry_run:
            print("\n⚠️  This was a DRY RUN - no changes were saved to database")
        else:
            print(f"\n✓ Migration completed! {success_count} products updated.")
        
        print("=" * 80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate titles and descriptions for existing products using Gemini AI'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of products to process in each batch (default: 10)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit total number of products to process (default: no limit)'
    )
    
    args = parser.parse_args()
    
    try:
        migrate_products(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=args.limit
        )
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

