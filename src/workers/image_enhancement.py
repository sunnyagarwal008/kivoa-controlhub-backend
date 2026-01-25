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
from src.models import Product, ProductImage, Prompt
from src.services import sqs_service, gemini_service, s3_service
from src.services.gemini_service import download_image
from src.utils.raw_image_utils import delete_raw_image_by_url


class WorkerThread(threading.Thread):
    """Background thread that processes SQS messages"""
    
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.running = False
    
    def stop(self):
        """Stop the worker thread"""
        self.running = False
    
    def process_product(self, product_id, prompt_id=None, is_raw_image=True):
        """
        Process a single product:
        1. Generate title and description using Gemini
        2. If is_raw_image=True: generate AI-enhanced images
        3. If is_raw_image=False: copy raw image directly to S3
        4. Update product status

        Args:
            product_id: ID of the product to process
            prompt_id: Optional prompt ID for AI image generation
            is_raw_image: Whether to generate AI images (True) or use raw image directly (False)
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

                current_app.logger.info(f"Processing product {product_id} - {category_name} with prompt_id: {prompt_id}, is_raw_image: {is_raw_image}")

                # Download the raw image
                raw_image = download_image(product.raw_image)

                # Step 1: Generate title and description using Gemini
                current_app.logger.info(f"Generating title and description for product {product_id}")
                try:
                    title_desc = gemini_service.generate_title_and_description(raw_image, category_name)
                    product.title = title_desc['title']
                    product.description = title_desc['description']
                    # Generate handle from title (lowercase, replace spaces with hyphens)
                    product.handle = title_desc['title'].lower().replace(' ', '-').replace('/', '-')[:255]
                    current_app.logger.info(f"Generated title: {product.title}")
                except Exception as e:
                    current_app.logger.error(f"Failed to generate title/description for product {product_id}: {str(e)}")
                    # Continue processing even if title/description generation fails
                    product.title = product.sku
                    product.description = ""
                    product.handle = product.sku.lower()

                created_image_urls = []
                bucket_name = current_app.config['S3_BUCKET_NAME']

                # Step 2: Handle image processing based on is_raw_image flag
                if is_raw_image:
                    # Generate AI-enhanced images
                    current_app.logger.info(f"Generating AI-enhanced images for product {product_id}")

                    # Get the configured number of enhanced images to generate
                    ai_images_count = current_app.config['ENHANCED_IMAGES_COUNT']

                    # Determine which prompt to use
                    prompt_obj = None

                    if prompt_id:
                        # Use the specific prompt provided
                        prompt_obj = Prompt.query.filter(
                            Prompt.id == prompt_id,
                            Prompt.is_active == True
                        ).first()

                        if not prompt_obj:
                            current_app.logger.error(f"Prompt {prompt_id} not found or inactive")
                            return False
                    else:
                        # Check if there's a default prompt for this category
                        prompt_obj = Prompt.query.filter(
                            Prompt.category_id == product.category_id,
                            Prompt.is_default == True,
                            Prompt.is_active == True
                        ).first()

                        if prompt_obj:
                            current_app.logger.info(f"Using default prompt {prompt_obj.id} for category {category_name}")
                            prompt_id = prompt_obj.id  # Store the prompt_id for later use

                    # Generate images
                    if prompt_obj:
                        # Generate all images with the specific prompt
                        ai_images = []
                        for i in range(1, ai_images_count + 1):
                            base_name = os.path.splitext(os.path.basename(raw_image))[0]
                            extension = os.path.splitext(raw_image)[1]
                            output_image_name = f"{base_name}-0{i}{extension}"
                            output_file = os.path.join("/tmp", output_image_name)
                            gemini_service._do_generate_image(raw_image, output_file, prompt_obj.text)
                            ai_images.append(output_file)
                    else:
                        # No specific prompt and no default - use random selection from category prompts
                        current_app.logger.info(f"No default prompt found for category {category_name}, using random selection")
                        ai_images = gemini_service.generate_images(raw_image, category_name, ai_images_count, None)

                    # Upload AI-generated images to S3
                    for idx, ai_image in enumerate(ai_images, start=1):
                        # Get file extension from the AI-generated image
                        file_extension = os.path.splitext(ai_image)[1]

                        # Create S3 key with format: product-images/<sku>-<index>
                        key = f"product-images/{product.sku}-{idx}{file_extension}"

                        # Upload to S3
                        image_url = s3_service.upload_file(ai_image, bucket_name=bucket_name, key=key)
                        created_image_urls.append(image_url)
                        current_app.logger.info(f"Created enhanced image for product {product_id}: {image_url}")

                    # Save images to product_images table with 'pending' status
                    for image_url in created_image_urls:
                        product_image = ProductImage(
                            product_id=product_id,
                            image_url=image_url,
                            status='pending',
                            prompt_id=prompt_id
                        )
                        db.session.add(product_image)

                else:
                    # Copy raw image directly to S3 (no AI processing)
                    current_app.logger.info(f"Copying raw image directly for product {product_id}")

                    # Get file extension from the raw image
                    file_extension = os.path.splitext(raw_image)[1]
                    if not file_extension:
                        file_extension = '.jpg'  # default extension

                    # Create S3 key with format: product-images/<sku>-1<extension>
                    key = f"product-images/{product.sku}-1{file_extension}"

                    # Upload the raw image to S3
                    image_url = s3_service.upload_file(raw_image, bucket_name=bucket_name, key=key)
                    created_image_urls.append(image_url)
                    current_app.logger.info(f"Copied raw image for product {product_id}: {image_url}")

                    # Save image to product_images table with 'approved' status
                    product_image = ProductImage(
                        product_id=product_id,
                        image_url=image_url,
                        status='approved'
                    )
                    db.session.add(product_image)

                # Update product status to 'pending_review'
                product.status = 'pending_review'

                # Delete from raw_images table if the raw_image URL exists there
                delete_raw_image_by_url(product.raw_image)

                # Commit all changes
                db.session.commit()

                current_app.logger.info(f"Successfully processed product {product_id}. Created {len(created_image_urls)} image(s), title: {product.title}")
                return True

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error processing product {product_id}: {str(e)}", exc_info=True)
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
                        continue
                    
                    for message in messages:
                        if not self.running:
                            break

                        try:
                            # Parse message body
                            body = json.loads(message['Body'])
                            product_id = body.get('product_id')
                            prompt_id = body.get('prompt_id')
                            is_raw_image = body.get('is_raw_image', True)  # Default to True for backward compatibility

                            if not product_id:
                                current_app.logger.error(f"Invalid message format: {message['Body']}")
                                sqs_service.delete_message(message['ReceiptHandle'])
                                continue

                            current_app.logger.info(f"Received message for product_id: {product_id}, prompt_id: {prompt_id}, is_raw_image: {is_raw_image}")

                            # Process the product
                            success = self.process_product(product_id, prompt_id, is_raw_image)

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

