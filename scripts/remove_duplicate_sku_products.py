#!/usr/bin/env python
"""
Migration script to remove duplicate SKU products from Shopify
This script:
1. Fetches all products from Shopify
2. Identifies products with duplicate SKUs
3. Keeps the first product for each SKU (oldest by creation date)
4. Deletes all duplicate products
"""

import sys
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from dotenv import load_dotenv

load_dotenv()


class ShopifyDuplicateRemover:
    """Service to remove duplicate SKU products from Shopify"""

    def __init__(self):
        self.store_url = None
        self.access_token = None
        self.api_version = None
        self._get_config()

    def _get_config(self):
        """Get Shopify configuration from environment variables"""
        self.store_url = os.getenv('SHOPIFY_STORE_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = os.getenv('SHOPIFY_API_VERSION', '2024-04')

        if self.store_url and not self.store_url.startswith(('http://', 'https://')):
            self.store_url = f'https://{self.store_url}'

        if not self.store_url or not self.access_token:
            raise ValueError('Shopify configuration is missing. Please set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN in .env file')

    def _get_headers(self):
        """Get headers for Shopify API requests"""
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        }

    def _get_api_url(self, endpoint):
        """Construct full API URL for a given endpoint"""
        base_url = self.store_url.rstrip('/')
        return f"{base_url}/admin/api/{self.api_version}/{endpoint}"

    def get_all_products(self):
        """
        Fetch all products from Shopify using pagination
        
        Returns:
            list: List of all product objects with their variants
        """
        all_products = []
        url = self._get_api_url('products.json?limit=250')
        headers = self._get_headers()

        print("\n📦 Fetching all products from Shopify...")
        page_count = 0

        while url:
            page_count += 1
            response = requests.get(url, headers=headers)

            if response.status_code not in [200, 201]:
                error_msg = f"Shopify API error: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)

            data = response.json()
            products = data.get('products', [])
            all_products.extend(products)

            print(f"   Page {page_count}: Fetched {len(products)} products (total: {len(all_products)})")

            link_header = response.headers.get('Link', '')
            if link_header:
                print(f"   Link header: {link_header[:200]}...")
            
            url = self._parse_next_page_url(link_header)
            if url:
                print(f"   Next page URL found: {url[:100]}...")
            else:
                print(f"   No more pages to fetch")

        print(f"✅ Fetched total of {len(all_products)} products from Shopify across {page_count} pages\n")
        return all_products

    def _parse_next_page_url(self, link_header):
        """
        Parse Shopify's Link header to get next page URL
        
        Args:
            link_header (str): Link header from Shopify response
            
        Returns:
            str: Next page URL or None if no more pages
        """
        if not link_header:
            return None

        links = link_header.split(',')
        for link in links:
            parts = link.strip().split(';')
            if len(parts) == 2:
                url_part = parts[0].strip('<> ')
                rel_part = parts[1].strip()
                if 'rel="next"' in rel_part:
                    return url_part

        return None

    def find_duplicate_skus(self, products):
        """
        Identify products with duplicate SKUs
        
        Args:
            products (list): List of Shopify product objects
            
        Returns:
            dict: Dictionary mapping SKU to list of products with that SKU
        """
        sku_to_products = defaultdict(list)

        for product in products:
            for variant in product.get('variants', []):
                sku = variant.get('sku') or ''
                sku = sku.strip()
                if sku:
                    sku_to_products[sku].append({
                        'product_id': product['id'],
                        'product_title': product['title'],
                        'variant_id': variant['id'],
                        'variant_sku': sku,
                        'created_at': product.get('created_at', ''),
                        'product': product
                    })

        duplicates = {sku: products_list for sku, products_list in sku_to_products.items() 
                     if len(products_list) > 1}

        return duplicates

    def delete_product(self, product_id):
        """
        Delete a product from Shopify
        
        Args:
            product_id (int): Product ID to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        url = self._get_api_url(f'products/{product_id}.json')
        headers = self._get_headers()

        response = requests.delete(url, headers=headers)

        if response.status_code == 200:
            return True
        else:
            print(f"   ⚠️  Failed to delete product {product_id}: {response.status_code} - {response.text}")
            return False

    def remove_duplicates(self, duplicates, dry_run=False):
        """
        Remove duplicate products, keeping the first (oldest) one for each SKU
        
        Args:
            duplicates (dict): Dictionary mapping SKU to list of products
            dry_run (bool): If True, only show what would be deleted
            
        Returns:
            tuple: (deleted_count, failed_count)
        """
        deleted_count = 0
        failed_count = 0

        print(f"\n{'=' * 80}")
        print(f"{'DRY RUN MODE - NO CHANGES WILL BE MADE' if dry_run else 'REMOVING DUPLICATE PRODUCTS'}")
        print(f"{'=' * 80}\n")

        for sku, products_list in duplicates.items():
            products_list.sort(key=lambda x: x['created_at'])

            print(f"\n🔍 SKU: {sku} (found {len(products_list)} products)")
            
            keeper = products_list[0]
            print(f"   ✅ KEEPING: Product ID {keeper['product_id']} - '{keeper['product_title']}'")
            print(f"      Created: {keeper['created_at']}")

            to_delete = products_list[1:]
            for product_info in to_delete:
                product_id = product_info['product_id']
                title = product_info['product_title']
                created_at = product_info['created_at']

                print(f"   🗑️  {'WOULD DELETE' if dry_run else 'DELETING'}: Product ID {product_id} - '{title}'")
                print(f"      Created: {created_at}")

                if not dry_run:
                    if self.delete_product(product_id):
                        deleted_count += 1
                        print(f"      ✅ Successfully deleted")
                    else:
                        failed_count += 1
                        print(f"      ❌ Failed to delete")
                else:
                    deleted_count += 1

        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total duplicate SKUs found: {len(duplicates)}")
        print(f"Total products to keep: {len(duplicates)}")
        print(f"Total products {'would be deleted' if dry_run else 'deleted'}: {deleted_count}")
        if not dry_run and failed_count > 0:
            print(f"Failed deletions: {failed_count}")
        print(f"{'=' * 80}\n")

        return deleted_count, failed_count


def main():
    """Main function to run the migration"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Remove duplicate SKU products from Shopify',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview what would be deleted)
  python scripts/remove_duplicate_sku_products.py --dry-run
  
  # Actually delete duplicate products
  python scripts/remove_duplicate_sku_products.py
  
  # Delete duplicates for specific SKU only
  python scripts/remove_duplicate_sku_products.py --sku "ABC123"
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without deleting products'
    )

    parser.add_argument(
        '--sku',
        type=str,
        help='Only process duplicates for this specific SKU'
    )

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("SHOPIFY DUPLICATE SKU REMOVER")
    print("=" * 80)

    try:
        remover = ShopifyDuplicateRemover()

        products = remover.get_all_products()

        if not products:
            print("⚠️  No products found in Shopify")
            sys.exit(0)

        duplicates = remover.find_duplicate_skus(products)

        if not duplicates:
            print("✅ No duplicate SKUs found!")
            sys.exit(0)

        if args.sku:
            if args.sku in duplicates:
                duplicates = {args.sku: duplicates[args.sku]}
                print(f"\n🎯 Filtering to only process SKU: {args.sku}")
            else:
                print(f"\n⚠️  SKU '{args.sku}' not found in duplicates")
                sys.exit(0)

        print(f"\n⚠️  Found {len(duplicates)} SKUs with duplicates:")
        for sku, products_list in duplicates.items():
            print(f"   - {sku}: {len(products_list)} products")

        if not args.dry_run:
            print("\n⚠️  WARNING: This will permanently delete products from Shopify!")
            response = input("\nAre you sure you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                print("\n❌ Operation cancelled by user")
                sys.exit(0)

        deleted, failed = remover.remove_duplicates(duplicates, dry_run=args.dry_run)

        if args.dry_run:
            print("\n💡 This was a dry run. To actually delete products, run without --dry-run flag")
        else:
            if failed > 0:
                print(f"\n⚠️  Completed with {failed} failed deletions")
                sys.exit(1)
            else:
                print("\n✅ All duplicate products removed successfully!")

        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
