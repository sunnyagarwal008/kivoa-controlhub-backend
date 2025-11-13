"""
CSV Service for generating Shopify-compatible product export files
"""
import csv
import tempfile
import os
from datetime import datetime
import uuid
from flask import current_app
from src.services.s3_service import s3_service


class CSVService:
    """Service for generating CSV files for Shopify product import"""
    
    def generate_shopify_csv(self, products):
        """
        Generate a Shopify-compatible CSV file from products
        
        Shopify CSV format includes these columns:
        - Handle: Unique identifier for the product (URL-friendly)
        - Title: Product title
        - Body (HTML): Product description
        - Vendor: Product vendor/brand
        - Type: Product type/category
        - Tags: Comma-separated tags
        - Published: TRUE/FALSE
        - Option1 Name: First variant option name (e.g., "Size")
        - Option1 Value: First variant option value (e.g., "Medium")
        - Option2 Name: Second variant option name
        - Option2 Value: Second variant option value
        - Option3 Name: Third variant option name
        - Option3 Value: Third variant option value
        - Variant SKU: Product SKU
        - Variant Grams: Weight in grams
        - Variant Inventory Tracker: shopify/blank
        - Variant Inventory Qty: Stock quantity
        - Variant Inventory Policy: deny/continue
        - Variant Fulfillment Service: manual
        - Variant Price: Product price
        - Variant Compare At Price: Original price (MRP)
        - Variant Requires Shipping: TRUE/FALSE
        - Variant Taxable: TRUE/FALSE
        - Variant Barcode: Product barcode
        - Image Src: Image URL
        - Image Position: Image position (1, 2, 3, etc.)
        - Image Alt Text: Alt text for image
        - Gift Card: FALSE
        - SEO Title: SEO title
        - SEO Description: SEO description
        - Google Shopping / Google Product Category: Product category
        - Google Shopping / Gender: Gender
        - Google Shopping / Age Group: Age group
        - Google Shopping / MPN: Manufacturer Part Number
        - Google Shopping / AdWords Grouping: AdWords grouping
        - Google Shopping / AdWords Labels: AdWords labels
        - Google Shopping / Condition: new/used/refurbished
        - Google Shopping / Custom Product: TRUE/FALSE
        - Google Shopping / Custom Label 0-4: Custom labels
        - Variant Image: Variant-specific image
        - Variant Weight Unit: kg/g/lb/oz
        - Variant Tax Code: Tax code
        - Cost per item: Cost price
        - Status: active/draft/archived
        
        Args:
            products: List of Product model instances
            
        Returns:
            str: Path to the generated CSV file
        """
        # Create a temporary file for the CSV
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', newline='', encoding='utf-8')
        csv_path = temp_file.name
        
        try:
            # Define Shopify CSV headers
            headers = [
                'Handle', 'Title', 'Body (HTML)', 'Vendor', 'Type', 'Tags', 'Published',
                'Option1 Name', 'Option1 Value', 'Option2 Name', 'Option2 Value', 'Option3 Name', 'Option3 Value',
                'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Qty',
                'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price', 'Variant Compare At Price',
                'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode',
                'Image Src', 'Image Position', 'Image Alt Text',
                'Gift Card', 'SEO Title', 'SEO Description',
                'Google Shopping / Google Product Category', 'Google Shopping / Gender', 'Google Shopping / Age Group',
                'Google Shopping / MPN', 'Google Shopping / AdWords Grouping', 'Google Shopping / AdWords Labels',
                'Google Shopping / Condition', 'Google Shopping / Custom Product', 'Google Shopping / Custom Label 0',
                'Google Shopping / Custom Label 1', 'Google Shopping / Custom Label 2', 'Google Shopping / Custom Label 3',
                'Google Shopping / Custom Label 4', 'Variant Image', 'Variant Weight Unit', 'Variant Tax Code',
                'Cost per item', 'Status'
            ]
            
            writer = csv.DictWriter(temp_file, fieldnames=headers)
            writer.writeheader()
            
            # Process each product
            for product in products:
                # Get product images sorted by priority
                sorted_images = sorted(product.product_images, key=lambda img: img.priority) if product.product_images else []
                
                # Use handle if available, otherwise generate from SKU
                handle = product.handle if product.handle else product.sku.lower().replace(' ', '-')
                
                # Use title if available, otherwise use SKU
                title = product.title if product.title else product.sku
                
                # Use description if available, otherwise empty
                description = product.description if product.description else ''
                
                # Get category name
                category_name = product.category_ref.name if product.category_ref else ''
                
                # Determine published status based on product status
                published = 'TRUE' if product.status == 'live' else 'FALSE'
                
                # Determine inventory policy based on in_stock
                inventory_qty = 1 if product.in_stock else 0
                
                # Status mapping
                status_mapping = {
                    'pending': 'draft',
                    'live': 'active',
                    'rejected': 'draft'
                }
                status = status_mapping.get(product.status, 'draft')
                
                # First row with product details
                row = {
                    'Handle': handle,
                    'Title': title,
                    'Body (HTML)': description,
                    'Vendor': 'KIVOA',  # Default vendor
                    'Type': category_name,
                    'Tags': product.tags if product.tags else '',
                    'Published': published,
                    'Option1 Name': 'Default',
                    'Option1 Value': 'Default',
                    'Option2 Name': '',
                    'Option2 Value': '',
                    'Option3 Name': '',
                    'Option3 Value': '',
                    'Variant SKU': product.sku,
                    'Variant Grams': '',
                    'Variant Inventory Tracker': 'shopify',
                    'Variant Inventory Qty': inventory_qty,
                    'Variant Inventory Policy': 'deny',
                    'Variant Fulfillment Service': 'manual',
                    'Variant Price': float(product.price),
                    'Variant Compare At Price': float(product.mrp),
                    'Variant Requires Shipping': 'TRUE',
                    'Variant Taxable': 'TRUE',
                    'Variant Barcode': '',
                    'Image Src': sorted_images[0].image_url if sorted_images else product.raw_image,
                    'Image Position': '1',
                    'Image Alt Text': title,
                    'Gift Card': 'FALSE',
                    'SEO Title': title,
                    'SEO Description': description[:160] if description else title,  # Limit to 160 chars
                    'Google Shopping / Google Product Category': '',
                    'Google Shopping / Gender': '',
                    'Google Shopping / Age Group': '',
                    'Google Shopping / MPN': product.sku,
                    'Google Shopping / AdWords Grouping': '',
                    'Google Shopping / AdWords Labels': '',
                    'Google Shopping / Condition': 'new',
                    'Google Shopping / Custom Product': 'FALSE',
                    'Google Shopping / Custom Label 0': '',
                    'Google Shopping / Custom Label 1': '',
                    'Google Shopping / Custom Label 2': '',
                    'Google Shopping / Custom Label 3': '',
                    'Google Shopping / Custom Label 4': '',
                    'Variant Image': '',
                    'Variant Weight Unit': 'kg',
                    'Variant Tax Code': '',
                    'Cost per item': '',
                    'Status': status
                }
                writer.writerow(row)
                
                # Add additional rows for remaining images (if any)
                for idx, image in enumerate(sorted_images[1:], start=2):
                    image_row = {
                        'Handle': handle,
                        'Title': '',
                        'Body (HTML)': '',
                        'Vendor': '',
                        'Type': '',
                        'Tags': '',
                        'Published': '',
                        'Option1 Name': '',
                        'Option1 Value': '',
                        'Option2 Name': '',
                        'Option2 Value': '',
                        'Option3 Name': '',
                        'Option3 Value': '',
                        'Variant SKU': '',
                        'Variant Grams': '',
                        'Variant Inventory Tracker': '',
                        'Variant Inventory Qty': '',
                        'Variant Inventory Policy': '',
                        'Variant Fulfillment Service': '',
                        'Variant Price': '',
                        'Variant Compare At Price': '',
                        'Variant Requires Shipping': '',
                        'Variant Taxable': '',
                        'Variant Barcode': '',
                        'Image Src': image.image_url,
                        'Image Position': str(idx),
                        'Image Alt Text': title,
                        'Gift Card': '',
                        'SEO Title': '',
                        'SEO Description': '',
                        'Google Shopping / Google Product Category': '',
                        'Google Shopping / Gender': '',
                        'Google Shopping / Age Group': '',
                        'Google Shopping / MPN': '',
                        'Google Shopping / AdWords Grouping': '',
                        'Google Shopping / AdWords Labels': '',
                        'Google Shopping / Condition': '',
                        'Google Shopping / Custom Product': '',
                        'Google Shopping / Custom Label 0': '',
                        'Google Shopping / Custom Label 1': '',
                        'Google Shopping / Custom Label 2': '',
                        'Google Shopping / Custom Label 3': '',
                        'Google Shopping / Custom Label 4': '',
                        'Variant Image': '',
                        'Variant Weight Unit': '',
                        'Variant Tax Code': '',
                        'Cost per item': '',
                        'Status': ''
                    }
                    writer.writerow(image_row)
            
            temp_file.close()
            current_app.logger.info(f"Generated Shopify CSV with {len(products)} products at {csv_path}")
            return csv_path
            
        except Exception as e:
            temp_file.close()
            if os.path.exists(csv_path):
                os.remove(csv_path)
            current_app.logger.error(f"Error generating Shopify CSV: {str(e)}")
            raise
    
    def upload_csv_to_s3(self, csv_path, filename=None):
        """
        Upload a CSV file to S3 and return the public URL
        
        Args:
            csv_path: Local path to the CSV file
            filename: Optional custom filename for S3 (default: auto-generated)
            
        Returns:
            str: Public S3 URL of the uploaded CSV
        """
        bucket_name = current_app.config['S3_BUCKET_NAME']
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"shopify_export_{timestamp}_{uuid.uuid4().hex[:8]}.csv"
        
        # Create S3 key
        key = f"exports/{filename}"
        
        # Upload to S3
        file_url = s3_service.upload_file(csv_path, bucket_name=bucket_name, key=key)
        
        return file_url


# Create a singleton instance
csv_service = CSVService()

