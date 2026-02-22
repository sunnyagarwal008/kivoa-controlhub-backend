"""
Routes for managing product channels (Amazon, Shopify, etc.)
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from src.database import db
from src.models import Product, ProductChannel
from src.services import amazon_service

channels_bp = Blueprint('channels', __name__)


@channels_bp.route('/products/<int:product_id>/channels', methods=['GET'])
def get_product_channels(product_id):
    """
    Get all channel sync information for a product
    
    GET /api/products/<product_id>/channels
    """
    try:
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404
        
        channels = ProductChannel.query.filter_by(product_id=product_id).all()
        
        return jsonify({
            'success': True,
            'product_id': product_id,
            'sku': product.sku,
            'channels': [channel.to_dict() for channel in channels]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching product channels: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@channels_bp.route('/products/<int:product_id>/channels/amazon/sync', methods=['POST'])
def sync_product_to_amazon(product_id):
    """
    Manually sync a product to Amazon India
    
    POST /api/products/<product_id>/channels/amazon/sync
    
    Request body (optional):
    {
        "brand": "Your Brand Name",
        "category": "JEWELRY",
        "attributes": {
            "metal_type": "Gold",
            "stone_type": "Diamond"
        }
    }
    """
    try:
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404
        
        # Check if product has required fields
        if not product.title or not product.description:
            return jsonify({
                'success': False,
                'error': 'Product must have title and description before syncing to Amazon'
            }), 400
        
        # Get images — white background image must come first (Amazon requirement)
        sorted_images = sorted(product.product_images, key=lambda x: x.priority or 999)
        white_bg_images = [img for img in sorted_images if img.is_white_background]
        other_images = [img for img in sorted_images if not img.is_white_background]

        if not white_bg_images:
            return jsonify({
                'success': False,
                'error': 'Product must have at least one white background image for Amazon (main image requirement)'
            }), 400

        # White background image(s) first, then the rest
        approved_images = [img.image_url for img in white_bg_images + other_images]

        # Get optional parameters from request
        data = request.get_json() or {}
        brand = data.get('brand', 'KIVOA')
        category = data.get('category', 'JEWELRY_SET')
        custom_attributes = data.get('attributes', {})
        bullet_points = data.get('bullet_points', None)
        weight = data.get('weight', None) or product.weight

        # Remove keys that are handled as dedicated params so they don't
        # leak into the Amazon payload as raw/malformed attributes
        for key in ('weight', 'bullet_points', 'brand', 'category'):
            custom_attributes.pop(key, None)
        
        # Check if product is already synced to Amazon
        existing_channel = ProductChannel.query.filter_by(
            product_id=product_id,
            channel_name='amazon'
        ).first()
        
        try:
            if existing_channel:
                # Update existing listing
                current_app.logger.info(f"Updating existing Amazon listing for product {product_id}")
                
                amazon_result = amazon_service.update_product_listing(
                    sku=product.sku,
                    title=product.title,
                    description=product.description,
                    price=float(product.price),
                    quantity=product.inventory,
                    images=approved_images,
                    attributes=custom_attributes,
                    category=category,
                    brand=brand,
                    mrp=float(product.mrp) if product.mrp else None,
                    weight=weight,
                    bullet_points=bullet_points
                )

                # Update channel record
                existing_channel.status = 'active'
                existing_channel.sync_status = 'synced'
                existing_channel.last_synced_at = datetime.utcnow()
                existing_channel.error_message = None
                existing_channel.channel_data = {
                    'brand': brand,
                    'category': category,
                    'attributes': custom_attributes,
                    'last_sync_response': amazon_result
                }
                
            else:
                # Create new listing
                current_app.logger.info(f"Creating new Amazon listing for product {product_id}")
                
                amazon_result = amazon_service.create_product_listing(
                    sku=product.sku,
                    title=product.title,
                    description=product.description,
                    price=float(product.price),
                    quantity=product.inventory,
                    brand=brand,
                    category=category,
                    images=approved_images,
                    attributes=custom_attributes,
                    mrp=float(product.mrp) if product.mrp else None,
                    weight=weight,
                    bullet_points=bullet_points
                )
                
                # Create channel record
                new_channel = ProductChannel(
                    product_id=product_id,
                    channel_name='amazon',
                    channel_product_id=None,  # Amazon doesn't return product ID immediately
                    channel_listing_id=product.sku,
                    status='active',
                    sync_status='synced',
                    last_synced_at=datetime.utcnow(),
                    channel_data={
                        'brand': brand,
                        'category': category,
                        'attributes': custom_attributes,
                        'last_sync_response': amazon_result
                    }
                )
                db.session.add(new_channel)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f"Product {product.sku} successfully synced to Amazon",
                'product_id': product_id,
                'sku': product.sku,
                'channel': 'amazon',
                'amazon_response': amazon_result
            }), 200
            
        except Exception as amazon_error:
            # Log the error and update channel status
            error_msg = str(amazon_error)
            current_app.logger.error(f"Amazon API error for product {product_id}: {error_msg}")
            
            if existing_channel:
                existing_channel.sync_status = 'failed'
                existing_channel.error_message = error_msg
                existing_channel.last_synced_at = datetime.utcnow()
            else:
                # Create failed channel record
                failed_channel = ProductChannel(
                    product_id=product_id,
                    channel_name='amazon',
                    status='error',
                    sync_status='failed',
                    error_message=error_msg,
                    last_synced_at=datetime.utcnow(),
                    channel_data={
                        'brand': brand,
                        'category': category,
                        'attributes': custom_attributes
                    }
                )
                db.session.add(failed_channel)
            
            db.session.commit()
            
            return jsonify({
                'success': False,
                'error': f"Failed to sync to Amazon: {error_msg}",
                'product_id': product_id,
                'sku': product.sku
            }), 500
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error syncing product to Amazon: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@channels_bp.route('/products/<int:product_id>/channels/amazon', methods=['DELETE'])
def remove_product_from_amazon(product_id):
    """
    Remove a product from Amazon India
    
    DELETE /api/products/<product_id>/channels/amazon
    """
    try:
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404
        
        # Get channel record
        channel = ProductChannel.query.filter_by(
            product_id=product_id,
            channel_name='amazon'
        ).first()
        
        if not channel:
            return jsonify({
                'success': False,
                'error': 'Product is not synced to Amazon'
            }), 404
        
        try:
            # Delete from Amazon
            amazon_service.delete_product_listing(product.sku)
            
            # Delete channel record
            db.session.delete(channel)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f"Product {product.sku} removed from Amazon",
                'product_id': product_id,
                'sku': product.sku
            }), 200
            
        except Exception as amazon_error:
            error_msg = str(amazon_error)
            current_app.logger.error(f"Amazon API error deleting product {product_id}: {error_msg}")
            
            # Update channel status to error
            channel.status = 'error'
            channel.sync_status = 'failed'
            channel.error_message = f"Failed to delete: {error_msg}"
            db.session.commit()
            
            return jsonify({
                'success': False,
                'error': f"Failed to remove from Amazon: {error_msg}",
                'product_id': product_id,
                'sku': product.sku
            }), 500
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing product from Amazon: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@channels_bp.route('/products/<int:product_id>/channels/amazon/status', methods=['GET'])
def get_amazon_listing_status(product_id):
    """
    Get the current status of a product listing on Amazon
    
    GET /api/products/<product_id>/channels/amazon/status
    """
    try:
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404
        
        # Get channel record
        channel = ProductChannel.query.filter_by(
            product_id=product_id,
            channel_name='amazon'
        ).first()
        
        if not channel:
            return jsonify({
                'success': False,
                'error': 'Product is not synced to Amazon'
            }), 404
        
        try:
            # Fetch current listing from Amazon
            amazon_listing = amazon_service.get_product_listing(product.sku)
            
            if amazon_listing:
                # Update channel record with latest info
                channel.sync_status = 'synced'
                channel.last_synced_at = datetime.utcnow()
                channel.error_message = None
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'product_id': product_id,
                    'sku': product.sku,
                    'channel': channel.to_dict(),
                    'amazon_listing': amazon_listing
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Listing not found on Amazon',
                    'product_id': product_id,
                    'sku': product.sku,
                    'channel': channel.to_dict()
                }), 404
                
        except Exception as amazon_error:
            error_msg = str(amazon_error)
            current_app.logger.error(f"Amazon API error fetching status for product {product_id}: {error_msg}")
            
            return jsonify({
                'success': False,
                'error': f"Failed to fetch Amazon status: {error_msg}",
                'product_id': product_id,
                'sku': product.sku,
                'channel': channel.to_dict()
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Error fetching Amazon listing status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@channels_bp.route('/channels/amazon/product-types/<product_type>', methods=['GET'])
def get_amazon_product_type(product_type):
    """
    Get Amazon product type definition to understand required fields
    
    GET /api/channels/amazon/product-types/NECKLACE
    """
    try:
        definition = amazon_service.get_product_type_definition(product_type)
        
        return jsonify({
            'success': True,
            'product_type': product_type,
            'definition': definition
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching product type definition: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@channels_bp.route('/channels/stats', methods=['GET'])
def get_channel_stats():
    """
    Get statistics about product channel syncs
    
    GET /api/channels/stats
    """
    try:
        stats = {
            'amazon': {
                'total': ProductChannel.query.filter_by(channel_name='amazon').count(),
                'active': ProductChannel.query.filter_by(channel_name='amazon', status='active').count(),
                'pending': ProductChannel.query.filter_by(channel_name='amazon', sync_status='pending').count(),
                'failed': ProductChannel.query.filter_by(channel_name='amazon', sync_status='failed').count(),
                'synced': ProductChannel.query.filter_by(channel_name='amazon', sync_status='synced').count()
            },
            'shopify': {
                'total': ProductChannel.query.filter_by(channel_name='shopify').count(),
                'active': ProductChannel.query.filter_by(channel_name='shopify', status='active').count(),
                'pending': ProductChannel.query.filter_by(channel_name='shopify', sync_status='pending').count(),
                'failed': ProductChannel.query.filter_by(channel_name='shopify', sync_status='failed').count(),
                'synced': ProductChannel.query.filter_by(channel_name='shopify', sync_status='synced').count()
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching channel stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
