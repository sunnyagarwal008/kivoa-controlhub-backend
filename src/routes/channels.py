"""
Routes for managing product channels (Amazon, Shopify, etc.)
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from src.database import db
from src.models import Product, ProductChannel, ProductImage
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
    Manually sync a product to Amazon India.

    POST /api/products/<product_id>/channels/amazon/sync

    All fields are optional. When omitted, values fall back to what is stored
    on the product record. Provided values are saved to the product_channels
    table so subsequent syncs reuse them.

    Request body:
    {
        "title":        (str)   Channel-specific listing title.
                                Falls back to product.title if omitted.
        "description":  (str)   Channel-specific product description.
                                Falls back to product.description if omitted.
        "price":        (float) Selling / offer price sent to Amazon.
                                Falls back to product.price if omitted.
        "mrp":          (float) Maximum Retail Price (strike-through price).
                                Falls back to product.mrp if omitted.
        "weight":       (float) Item weight in grams. Falls back to product.weight
                                if omitted.
        "color":        (str)   Color of the product (e.g. "Gold", "Silver").
                                Falls back to KIVOA default ("Gold") if omitted.
        "dimensions":   (obj)   Item dimensions in millimeters.
                                e.g. {"length": 110.0, "width": 40.0, "height": 5.0}
                                Falls back to KIVOA defaults if omitted.
        "stones_data":  (list)  List of stone objects, each with:
                                  - "type": stone name ("Pearl", "Cubic Zirconia", "Ruby", "Sapphire", "Emerald")
                                  - "creation_method": e.g. "Simulated"
                                  - "treatment_method": e.g. "Not Treated"
                                Falls back to KIVOA defaults if omitted.
        "gem_types":    (list)  List of gem type strings
                                (e.g. ["Created Pearl", "Created Emerald", "Created Ruby", "Created Sapphire", "Cubic Zirconia", "Kundan", "Created Moissanite", "Artificial Stones"]).
                                Falls back to KIVOA defaults if omitted.
    }

    Images are sourced automatically from the product's approved images.
    White-background images are placed first to satisfy Amazon's main-image
    requirement. At least one white-background image must exist.
    """
    try:
        product = Product.query.get(product_id)

        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404

        # Get optional parameters from request
        data = request.get_json() or {}

        # Use channel-specific overrides if provided, otherwise fall back to product fields
        channel_title = data.get('title') or product.title
        channel_description = data.get('description') or product.description
        channel_price = data.get('price')
        channel_mrp = data.get('mrp')
        price = float(channel_price) if channel_price is not None else float(product.price)
        mrp = float(channel_mrp) if channel_mrp is not None else (float(product.mrp) if product.mrp else None)

        # Check if product has required fields
        if not channel_title or not channel_description:
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

        brand = data.get('brand', 'KIVOA')
        category = data.get('category', 'JEWELRY_SET')
        custom_attributes = data.get('attributes', {})
        bullet_points = data.get('bullet_points', None)
        weight = data.get('weight', None) or product.weight
        color = data.get('color', None)
        dimensions = data.get('dimensions', None)
        stones_data = data.get('stones_data', None)
        gem_types = data.get('gem_types', None)

        # Remove keys that are handled as dedicated params so they don't
        # leak into the Amazon payload as raw/malformed attributes
        for key in ('weight', 'bullet_points', 'brand', 'category',
                    'color', 'item_dimensions', 'stones', 'gem_type'):
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
                    title=channel_title,
                    description=channel_description,
                    price=price,
                    quantity=product.inventory,
                    images=approved_images,
                    attributes=custom_attributes,
                    category=category,
                    brand=brand,
                    mrp=mrp,
                    weight=weight,
                    bullet_points=bullet_points,
                    dimensions=dimensions,
                    color=color,
                    stones_data=stones_data,
                    gem_types=gem_types
                )

                # Update channel record
                existing_channel.title = channel_title
                existing_channel.description = channel_description
                existing_channel.price = price
                existing_channel.mrp = mrp
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
                    title=channel_title,
                    description=channel_description,
                    price=price,
                    quantity=product.inventory,
                    brand=brand,
                    category=category,
                    images=approved_images,
                    attributes=custom_attributes,
                    mrp=mrp,
                    weight=weight,
                    bullet_points=bullet_points,
                    dimensions=dimensions,
                    color=color,
                    stones_data=stones_data,
                    gem_types=gem_types
                )

                # Create channel record
                new_channel = ProductChannel(
                    product_id=product_id,
                    channel_name='amazon',
                    channel_product_id=None,  # Amazon doesn't return product ID immediately
                    channel_listing_id=product.sku,
                    title=channel_title,
                    description=channel_description,
                    price=price,
                    mrp=mrp,
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


@channels_bp.route('/channels/<string:channel_name>/listings', methods=['GET'])
def get_channel_listings(channel_name):
    """
    Get paginated minimal listings for a channel (e.g. amazon, shopify)

    GET /api/channels/<channel_name>/listings

    Query params:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)

    Response:
        {
            "success": true,
            "channel": "amazon",
            "data": [
                {
                    "product_id": 1,
                    "channel_listing_id": "ABC-0001-0124",
                    "product_image": "https://...",
                    "title": "Gold Ring",
                    "description": "Beautiful gold ring",
                    "price": 999.00,
                    "mrp": 1299.00
                }
            ],
            "pagination": {
                "page": 1,
                "per_page": 20,
                "total": 100,
                "pages": 5
            }
        }
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        pagination = (
            ProductChannel.query
            .filter_by(channel_name=channel_name)
            .options(db.joinedload(ProductChannel.product))
            .order_by(ProductChannel.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        # Batch-fetch the highest-priority white background image for each product
        product_ids = [pc.product_id for pc in pagination.items]
        image_map = {}
        if product_ids:
            white_bg_images = (
                ProductImage.query
                .filter(
                    ProductImage.product_id.in_(product_ids),
                    ProductImage.is_white_background == True
                )
                .order_by(ProductImage.product_id, ProductImage.priority)
                .all()
            )
            for img in white_bg_images:
                if img.product_id not in image_map:
                    image_map[img.product_id] = img.image_url

        data = [
            {
                'product_id': pc.product_id,
                'channel_listing_id': pc.channel_listing_id,
                'product_image': image_map.get(pc.product_id),
                'title': pc.title or (pc.product.title if pc.product else None),
                'description': pc.description or (pc.product.description if pc.product else None),
                'price': float(pc.price) if pc.price is not None else (float(pc.product.price) if pc.product and pc.product.price else None),
                'mrp': float(pc.mrp) if pc.mrp is not None else (float(pc.product.mrp) if pc.product and pc.product.mrp else None),
            }
            for pc in pagination.items
        ]

        return jsonify({
            'success': True,
            'channel': channel_name,
            'data': data,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching channel listings for {channel_name}: {str(e)}")
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
