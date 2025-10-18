from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from src.database import db
from src.models import Category, Product
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
                    "purchase_month": "0124",
                    "raw_image": "https://bucket.s3.region.amazonaws.com/products/uuid1.jpg",
                    "mrp": 1000.00,
                    "price": 850.00,
                    "discount": 150.00,
                    "gst": 18.00
                },
                {
                    "category": "Clothing",
                    "purchase_month": "0124",
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

            # Get category by name and validate it exists
            category_name = validated_data['category']
            category = Category.query.filter_by(name=category_name).first()
            if not category:
                return jsonify({
                    'success': False,
                    'error': f'Category "{category_name}" not found at index {index}. Please create the category first.'
                }), 400

            # Generate SKU for the product
            sku = category.generate_sku(validated_data['purchase_month'])

            # Create new product with status set to 'pending'
            product = Product(
                category_id=category.id,
                sku=sku,
                purchase_month=validated_data['purchase_month'],
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


@products_bp.route('/categories', methods=['GET'])
def get_categories():
    """
    Get all categories

    Response:
        {
            "success": true,
            "data": [
                {
                    "id": 1,
                    "name": "Electronics",
                    "prefix": "ELEC",
                    "sku_sequence_number": 5,
                    "created_at": "...",
                    "updated_at": "..."
                },
                ...
            ]
        }
    """
    try:
        categories = Category.query.order_by(Category.name).all()

        return jsonify({
            'success': True,
            'data': [category.to_dict() for category in categories]
        }), 200

    except Exception as e:
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
        - category_id: Filter by category ID
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
        category_id = request.args.get('category_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Build query
        query = Product.query

        if status:
            query = query.filter_by(status=status)

        if category_id:
            query = query.filter_by(category_id=category_id)
        
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
            "purchase_month": "0124",
            "price": 800.00,
            ...
        }

    Note: SKU is auto-generated and cannot be updated directly.
    """
    try:
        product = Product.query.get_or_404(product_id)

        # Validate request data (partial update allowed)
        data = product_schema.load(request.get_json(), partial=True)

        # Check if category or purchase_month is being updated
        category_changed = False
        new_category_id = product.category_id

        if 'category' in data:
            # Look up category by name
            category_name = data['category']
            category = Category.query.filter_by(name=category_name).first()
            if not category:
                return jsonify({
                    'success': False,
                    'error': f'Category "{category_name}" not found. Please create the category first.'
                }), 400

            if category.id != product.category_id:
                category_changed = True
                new_category_id = category.id

        purchase_month_changed = 'purchase_month' in data and data['purchase_month'] != product.purchase_month

        # If category or purchase_month changes, regenerate SKU
        if category_changed or purchase_month_changed:
            new_purchase_month = data.get('purchase_month', product.purchase_month)

            # Get the category
            category = Category.query.get(new_category_id)

            # Generate new SKU
            new_sku = category.generate_sku(new_purchase_month)
            product.sku = new_sku
            product.category_id = new_category_id
            product.purchase_month = new_purchase_month

        # Update other product fields (excluding category, category_id, sku, purchase_month as they're handled above)
        for key, value in data.items():
            if key not in ['category', 'category_id', 'sku', 'purchase_month']:
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

