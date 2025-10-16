from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from src.database import db
from src.models import Product
from src.schemas import ProductSchema
from src.services import sqs_service

products_bp = Blueprint('products', __name__)

product_schema = ProductSchema()
products_schema = ProductSchema(many=True)


@products_bp.route('/products/bulk', methods=['POST'])
def bulk_create_products():
    """
    Create multiple products in a single request

    Note: This is an all-or-nothing operation. If any product fails validation,
    the entire request will fail and no products will be created.

    Request Body:
        {
            "products": [
                {
                    "category": "Electronics",
                    "raw_image": "https://bucket.s3.region.amazonaws.com/products/uuid1.jpg",
                    "mrp": 1000.00,
                    "price": 850.00,
                    "discount": 150.00,
                    "gst": 18.00
                },
                {
                    "category": "Clothing",
                    "raw_image": "https://bucket.s3.region.amazonaws.com/products/uuid2.jpg",
                    "mrp": 500.00,
                    "price": 400.00,
                    "discount": 100.00,
                    "gst": 12.00
                }
            ]
        }

    Response (Success):
        {
            "success": true,
            "message": "Successfully created 2 products",
            "data": {
                "created": 2,
                "total": 2,
                "products": [...]
            }
        }

    Response (Error):
        {
            "success": false,
            "error": "Validation error or exception message"
        }
    """
    try:
        request_data = request.get_json()

        if not request_data or 'products' not in request_data:
            return jsonify({
                'success': False,
                'error': 'Missing "products" array in request body'
            }), 400

        products_data = request_data['products']

        if not isinstance(products_data, list):
            return jsonify({
                'success': False,
                'error': '"products" must be an array'
            }), 400

        if len(products_data) == 0:
            return jsonify({
                'success': False,
                'error': '"products" array cannot be empty'
            }), 400

        if len(products_data) > 100:
            return jsonify({
                'success': False,
                'error': 'Maximum 100 products allowed per bulk upload'
            }), 400

        created_products = []
        product_ids = []

        for index, product_data in enumerate(products_data):
            # Validate product data
            validated_data = product_schema.load(product_data)

            # Create new product with status set to 'pending'
            product = Product(
                category=validated_data['category'],
                raw_image=validated_data['raw_image'],
                mrp=validated_data['mrp'],
                price=validated_data['price'],
                discount=validated_data['discount'],
                gst=validated_data['gst'],
                status='pending'
            )

            db.session.add(product)
            db.session.flush()  # Get the ID without committing

            created_products.append(product_schema.dump(product))
            product_ids.append(product.id)

        # Commit all products
        db.session.commit()

        # Send each product_id to SQS queue for image enhancement processing
        for product_id in product_ids:
            try:
                sqs_service.send_message(product_id)
            except Exception as e:
                # Log the error but don't fail the entire request
                # The products are already created
                current_app.logger.error(f"Failed to send product_id {product_id} to SQS: {str(e)}")

        return jsonify({
            'success': True,
            'message': f'Successfully created {len(created_products)} products and queued for processing',
            'data': {
                'created': len(created_products),
                'total': len(products_data),
                'products': created_products
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products', methods=['GET'])
def get_products():
    """
    Get all products with optional filtering
    
    Query Parameters:
        - status: Filter by status (e.g., pending, approved, rejected)
        - category: Filter by category
        - page: Page number (default: 1)
        - per_page: Items per page (default: 10)
    
    Response:
        {
            "success": true,
            "data": [...],
            "pagination": {
                "page": 1,
                "per_page": 10,
                "total": 100,
                "pages": 10
            }
        }
    """
    try:
        # Get query parameters
        status = request.args.get('status')
        category = request.args.get('category')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Build query
        query = Product.query
        
        if status:
            query = query.filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        # Paginate results
        pagination = query.order_by(Product.created_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'success': True,
            'data': products_schema.dump(pagination.items),
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """
    Get a single product by ID
    
    Response:
        {
            "success": true,
            "data": {...}
        }
    """
    try:
        product = Product.query.get_or_404(product_id)
        
        return jsonify({
            'success': True,
            'data': product_schema.dump(product)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404


@products_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """
    Update a product
    
    Request Body:
        {
            "category": "Electronics",
            "price": 800.00,
            ...
        }
    """
    try:
        product = Product.query.get_or_404(product_id)
        
        # Validate request data (partial update allowed)
        data = product_schema.load(request.get_json(), partial=True)
        
        # Update product fields
        for key, value in data.items():
            setattr(product, key, value)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Product updated successfully',
            'data': product_schema.dump(product)
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """
    Delete a product
    
    Response:
        {
            "success": true,
            "message": "Product deleted successfully"
        }
    """
    try:
        product = Product.query.get_or_404(product_id)
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Product deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

