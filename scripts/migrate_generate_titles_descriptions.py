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
from src.models import Product, ProductImage
from src.services.gemini_service import gemini_service, download_image
from src.services.shopify_service import shopify_service
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


def process_product(product, dry_run=False, push_to_shopify=False):
    """
    Process a single product to generate title and description, optionally push to Shopify
    
    Args:
        product: Product object to process
        dry_run: If True, don't save changes to database
        push_to_shopify: If True, push product to Shopify after generating title/description
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Get category name from relationship
        category_name = product.category_ref.name if product.category_ref else 'jewelry'
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing product {product.id} (SKU: {product.sku})...")
        print(f"  Status: {product.status}")
        print(f"  Category: {category_name}")
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
        print(f"  Generating title and description with Gemini AI for category: {category_name}...")
        try:
            title_desc = gemini_service.generate_title_and_description(raw_image_path, category_name)
            generated_title = title_desc['title']
            generated_description = title_desc['description']
            #generated_handle = generate_handle_from_title(generated_title)
            
            print(f"  ✓ Generated title: {generated_title}")
            print(f"  ✓ Generated description: {generated_description}")
            #print(f"  ✓ Generated handle: {generated_handle}")
            
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
            #product.handle = generated_handle
            db.session.commit()
            print(f"  ✓ Product {product.id} updated successfully")
            
            # Push to Shopify if requested
            if push_to_shopify:
                try:
                    print(f"  Pushing product to Shopify...")
                    sync_success = push_product_to_shopify(product)
                    if sync_success:
                        print(f"  ✓ Successfully pushed to Shopify")
                    else:
                        print(f"  ⚠️  Failed to push to Shopify (see logs)")
                except Exception as e:
                    error_msg = f"Failed to push to Shopify: {str(e)}"
                    print(f"  ⚠️  {error_msg}")
                    # Don't fail the whole operation if Shopify sync fails
        else:
            print(f"  [DRY RUN] Would update product {product.id}")
            if push_to_shopify:
                print(f"  [DRY RUN] Would push to Shopify")
        
        return True, "Success"
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Unexpected error: {str(e)}"
        print(f"  ❌ {error_msg}")
        return False, error_msg


def push_product_to_shopify(product):
    """
    Push a product to Shopify catalog
    
    Args:
        product: Product object to push
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get product images (ordered by priority)
        product_images = ProductImage.query.filter_by(
            product_id=product.id
        ).order_by(ProductImage.priority.asc()).all()
        
        image_urls = [img.image_url for img in product_images]
        
        # Prepare product data
        title = product.title or f"Product {product.sku}"
        description = product.description or ""
        sku = product.sku
        price = float(product.price)
        inventory_quantity = product.inventory or 0
        weight = product.weight
        tags = product.tags or ""
        product_type = product.category_ref.name if product.category_ref else None
        
        current_app.logger.info(f"Pushing product {product.id} (SKU: {sku}) to Shopify")
        
        # Check if product already exists in Shopify
        existing_product = shopify_service.find_product_by_sku(sku)
        
        if existing_product:
            # Update existing product
            shopify_product_id = existing_product['id']
            current_app.logger.info(f"Updating existing Shopify product {shopify_product_id}")
            
            shopify_service.update_product(
                product_id=shopify_product_id,
                title=title,
                description=description,
                price=price,
                inventory_quantity=inventory_quantity,
                weight=weight,
                images=image_urls if image_urls else None,
                tags=tags,
                product_type=product_type
            )
            
            current_app.logger.info(f"Successfully updated Shopify product {shopify_product_id}")
        else:
            # Create new product
            pass
            # current_app.logger.info(f"Creating new Shopify product for SKU {sku}")
            #
            # shopify_product = shopify_service.create_product(
            #     title=title,
            #     description=description,
            #     sku=sku,
            #     price=price,
            #     inventory_quantity=inventory_quantity,
            #     weight=weight,
            #     images=image_urls if image_urls else None,
            #     tags=tags,
            #     vendor="Kivoa",
            #     product_type=product_type
            # )
            #
            # current_app.logger.info(f"Successfully created Shopify product {shopify_product['id']}")
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error pushing product {product.id} to Shopify: {str(e)}")
        return False


def migrate_products(dry_run=False, batch_size=10, limit=None, push_to_shopify=False, in_stock_only=False):
    """
    Main migration function to process products
    
    Args:
        dry_run: If True, don't save changes to database
        batch_size: Number of products to process in each batch
        limit: Maximum number of products to process (None for all)
        push_to_shopify: If True, push products to Shopify after generating title/description
        in_stock_only: If True, only process products with inventory > 0
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
        filters = [
            Product.status.in_(['live', 'pending_review']),
        ]
        
        # Add in-stock filter if requested
        if in_stock_only:
            filters.append(Product.inventory > 0)
        
        query = Product.query.filter(*filters).order_by(Product.id)
        
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
        if in_stock_only:
            print(f"  - Inventory: > 0 (in stock only)")
        print(f"  - Total: {total_products}")
        print(f"  - Batch size: {batch_size}")
        print(f"  - Push to Shopify: {'Yes' if push_to_shopify else 'No'}")
        
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
            
            success, message = process_product(product, dry_run, push_to_shopify)
            
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
    parser.add_argument(
        '--push-to-shopify',
        action='store_true',
        help='Push products to Shopify after generating title and description'
    )
    parser.add_argument(
        '--in-stock-only',
        action='store_true',
        help='Only process products with inventory > 0'
    )
    
    args = parser.parse_args()
    
    try:
        migrate_products(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=args.limit,
            push_to_shopify=args.push_to_shopify,
            in_stock_only=args.in_stock_only
        )
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

