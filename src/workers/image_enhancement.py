"""
SQS Worker Thread for processing product image enhancement
Runs as a background thread within the Flask application
"""

import json
import os
import threading
import time

from flask import current_app

from src.database import db
from src.models import Product, ProductImage
from src.services import sqs_service, gemini_service, s3_service
from src.services.gemini_service import download_image


class WorkerThread(threading.Thread):
    """Background thread that processes SQS messages"""
    
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.running = False
    
    def stop(self):
        """Stop the worker thread"""
        self.running = False
    
    def process_product(self, product_id):
        """
        Process a single product: fetch from DB, generate enhanced images,
        upload to S3, save to product_images table, update product status
        
        Args:
            product_id: ID of the product to process
        """
        with self.app.app_context():
            try:
                # Fetch product from database
                product = Product.query.get(product_id)
                
                if not product:
                    current_app.logger.error(f"Product {product_id} not found")
                    return False

                # Get category name from relationship
                category_name = product.category_ref.name if product.category_ref else 'default'

                current_app.logger.info(f"Processing product {product_id} - {category_name}")

                # Download the raw image
                raw_image = download_image(product.raw_image)

                # Get the configured number of enhanced images to generate
                ai_images_count = current_app.config['ENHANCED_IMAGES_COUNT']

                ai_images = gemini_service.generate_images(raw_image, category_name, ai_images_count)
                created_image_urls = []

                # Generate enhanced images
                bucket_name = current_app.config['S3_BUCKET_NAME']
                for idx, ai_image in enumerate(ai_images, start=1):
                    # Get file extension from the AI-generated image
                    file_extension = os.path.splitext(ai_image)[1]

                    # Create S3 key with format: product-images/<sku>-<index>
                    key = f"product-images/{product.sku}-{idx}{file_extension}"

                    # Generate the S3 URL
                    image_url = s3_service.upload_file(ai_image, bucket_name=bucket_name, key=key)
                    created_image_urls.append(image_url)
                    current_app.logger.info(f"Created enhanced images for product {product_id}: {image_url}")

                for image_url in created_image_urls:
                    # Save to product_images table
                    product_image = ProductImage(
                        product_id=product_id,
                        image_url=image_url,
                        status='pending'
                    )
                    db.session.add(product_image)
                
                # Update product status to 'pending_review'
                product.status = 'pending_review'
                
                # Commit all changes
                db.session.commit()
                
                current_app.logger.info(f"Successfully processed product {product_id}. Created {len(created_image_urls)} enhanced images.")
                return True
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error processing product {product_id}: {str(e)}")
                return False
    
    def run(self):
        """Main worker loop"""
        self.running = True
        
        with self.app.app_context():
            current_app.logger.info("Worker thread started")
            current_app.logger.info(f"Queue URL: {current_app.config.get('SQS_QUEUE_URL')}")
            current_app.logger.info(f"Enhanced images count: {current_app.config.get('ENHANCED_IMAGES_COUNT')}")
            
            while self.running:
                try:
                    # Receive messages from SQS (long polling)
                    messages = sqs_service.receive_messages(max_messages=1, wait_time=20)
                    
                    if not messages:
                        current_app.logger.debug("No messages received, continuing to poll...")
                        continue
                    
                    for message in messages:
                        if not self.running:
                            break
                        
                        try:
                            # Parse message body
                            body = json.loads(message['Body'])
                            product_id = body.get('product_id')
                            
                            if not product_id:
                                current_app.logger.error(f"Invalid message format: {message['Body']}")
                                sqs_service.delete_message(message['ReceiptHandle'])
                                continue
                            
                            current_app.logger.info(f"Received message for product_id: {product_id}")
                            
                            # Process the product
                            success = self.process_product(product_id)
                            
                            if success:
                                # Delete message from queue after successful processing
                                sqs_service.delete_message(message['ReceiptHandle'])
                                current_app.logger.info(f"Successfully processed and deleted message for product {product_id}")
                            else:
                                # Message will be retried based on SQS configuration
                                current_app.logger.warning(f"Failed to process product {product_id}, message will be retried")
                        
                        except Exception as e:
                            current_app.logger.error(f"Error processing message: {str(e)}")
                            # Don't delete the message, let it be retried
                            continue
                
                except Exception as e:
                    current_app.logger.error(f"Error in worker loop: {str(e)}")
                    # Wait a bit before retrying
                    time.sleep(5)
            
            current_app.logger.info("Worker thread stopped")


# Global worker instance
_worker_thread = None


def start_worker(app):
    """Start the worker thread"""
    global _worker_thread
    
    # Check if worker should be enabled
    if not app.config.get('SQS_QUEUE_URL'):
        app.logger.warning("SQS_QUEUE_URL not configured, worker thread will not start")
        return
    
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = WorkerThread(app)
        _worker_thread.start()
        app.logger.info("Worker thread started successfully")


def stop_worker():
    """Stop the worker thread"""
    global _worker_thread
    
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.stop()
        _worker_thread.join(timeout=5)

