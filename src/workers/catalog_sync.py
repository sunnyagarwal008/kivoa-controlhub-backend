"""
SQS Worker Thread for syncing products to Shopify catalog
Runs as a background thread within the Flask application
"""

import json
import threading
import time

from flask import current_app

from src.database import db
from src.models import Product, ProductImage
from src.services import sqs_service, shopify_service


class CatalogSyncWorker(threading.Thread):
    """Background thread that processes catalog sync SQS messages"""
    
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.running = False
    
    def stop(self):
        """Stop the worker thread"""
        self.running = False
    
    def sync_product_to_shopify(self, product_id, action='create'):
        """
        Sync a product to Shopify catalog

        Args:
            product_id: ID of the product to sync
            action: Action to perform ('create' or 'update')

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Fetch product from database
            product = Product.query.get(product_id)

            if not product:
                current_app.logger.error(f"Product {product_id} not found")
                return False

            # Only sync products with 'live' status
            if product.status != 'live':
                current_app.logger.info(f"Product {product_id} status is '{product.status}', skipping Shopify sync")
                return True

            current_app.logger.info(f"Syncing product {product_id} to Shopify (action: {action})")

            # Get product images (approved images only, ordered by priority)
            product_images = ProductImage.query.filter_by(
                product_id=product_id
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

            # Check if product already exists in Shopify
            existing_product = shopify_service.find_product_by_sku(sku)

            if existing_product:
                # Update existing product
                shopify_product_id = existing_product['id']
                current_app.logger.info(f"Updating existing Shopify product {shopify_product_id} for SKU {sku}")

                shopify_service.update_product(
                    product_id=shopify_product_id,
                    title=title,
                    description=description,
                    price=price,
                    inventory_quantity=inventory_quantity,
                    weight=weight,
                    images=image_urls if image_urls else None,
                    tags=tags
                )

                current_app.logger.info(f"Successfully updated Shopify product {shopify_product_id}")

            else:
                # Create new product
                current_app.logger.info(f"Creating new Shopify product for SKU {sku}")

                shopify_product = shopify_service.create_product(
                    title=title,
                    description=description,
                    sku=sku,
                    price=price,
                    inventory_quantity=inventory_quantity,
                    weight=weight,
                    images=image_urls if image_urls else None,
                    tags=tags,
                    vendor="Kivoa"
                )

                current_app.logger.info(f"Successfully created Shopify product {shopify_product['id']}")

            return True

        except Exception as e:
            current_app.logger.error(f"Error syncing product {product_id} to Shopify: {str(e)}")
            return False
    
    def run(self):
        """Main worker loop - polls SQS and processes messages"""
        self.running = True

        with self.app.app_context():
            current_app.logger.info("Catalog sync worker thread started")
            current_app.logger.info(f"Catalog sync queue URL: {current_app.config.get('CATALOG_SYNC_QUEUE_URL')}")

            while self.running:
                try:
                    # Check if catalog sync queue is configured
                    if not current_app.config.get('CATALOG_SYNC_QUEUE_URL'):
                        current_app.logger.warning("CATALOG_SYNC_QUEUE_URL not configured, catalog sync worker sleeping")
                        time.sleep(60)
                        continue

                    # Receive messages from catalog sync queue
                    messages = sqs_service.receive_messages(
                        max_messages=1,
                        wait_time=20,
                        queue_type='catalog_sync'
                    )

                    if not messages:
                        continue

                    for message in messages:
                        if not self.running:
                            break

                        try:
                            # Parse message body
                            body = json.loads(message['Body'])
                            product_id = body.get('product_id')
                            action = body.get('action', 'create')

                            if not product_id:
                                current_app.logger.error("Message missing product_id")
                                sqs_service.delete_message(message['ReceiptHandle'], queue_type='catalog_sync')
                                continue

                            current_app.logger.info(f"Processing catalog sync message for product {product_id}")

                            # Process the product
                            success = self.sync_product_to_shopify(product_id, action)

                            if success:
                                # Delete message from queue
                                sqs_service.delete_message(message['ReceiptHandle'], queue_type='catalog_sync')
                                current_app.logger.info(f"Successfully processed catalog sync for product {product_id}")
                            else:
                                current_app.logger.error(f"Failed to sync product {product_id}, message will be retried")
                                # Don't delete message - it will be retried

                        except json.JSONDecodeError as e:
                            current_app.logger.error(f"Invalid JSON in message: {str(e)}")
                            sqs_service.delete_message(message['ReceiptHandle'], queue_type='catalog_sync')

                        except Exception as e:
                            current_app.logger.error(f"Error processing catalog sync message: {str(e)}")
                            # Don't delete message - it will be retried

                except Exception as e:
                    current_app.logger.error(f"Error in catalog sync worker loop: {str(e)}")
                    time.sleep(5)  # Wait before retrying

            current_app.logger.info("Catalog sync worker thread stopped")


def start_catalog_sync_worker(app):
    """
    Start the catalog sync worker thread
    
    Args:
        app: Flask application instance
    
    Returns:
        CatalogSyncWorker: The worker thread instance
    """
    worker = CatalogSyncWorker(app)
    worker.start()
    return worker

