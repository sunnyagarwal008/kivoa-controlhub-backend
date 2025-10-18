from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from sqlalchemy.orm import joinedload
from src.database import db
from src.models import Category, Product, ProductImage
from src.schemas import ProductSchema
from src.services import sqs_service

products_bp = Blueprint('products', __name__)

product_schema = ProductSchema()
products_schema = ProductSchema(many=True)


@products_bp.route('/products/bulk', methods=['POST'])
def bulk_create_products():
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

        # Build query with eager loading of category and images
        query = Product.query.options(
            joinedload(Product.category_ref),
            joinedload(Product.product_images)
        )

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

        # Convert products to dict with category details and images
        products_data = [
            product.to_dict(include_category_details=True, include_images=True)
            for product in pagination.items
        ]

        return jsonify({
            'success': True,
            'data': products_data,
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
    Get a single product by ID with category details and images

    Response:
        {
            "success": true,
            "data": {
                "id": 1,
                "category_id": 1,
                "category": "Electronics",
                "category_details": {...},
                "images": [...],
                ...
            }
        }
    """
    try:
        # Query with eager loading of category and images
        product = Product.query.options(
            joinedload(Product.category_ref),
            joinedload(Product.product_images)
        ).get_or_404(product_id)

        return jsonify({
            'success': True,
            'data': product.to_dict(include_category_details=True, include_images=True)
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


@products_bp.route('/products/<int:product_id>/images/<int:image_id>/approve', methods=['PUT'])
def approve_product_image(product_id, image_id):
    """
    Approve a product image

    Response:
        {
            "success": true,
            "message": "Image approved successfully",
            "data": {
                "id": 1,
                "product_id": 1,
                "image_url": "https://...",
                "status": "approved",
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        # Verify product exists
        product = Product.query.get_or_404(product_id)

        # Get the image and verify it belongs to this product
        image = ProductImage.query.filter_by(
            id=image_id,
            product_id=product_id
        ).first()

        if not image:
            return jsonify({
                'success': False,
                'error': f'Image {image_id} not found for product {product_id}'
            }), 404

        # Update image status
        image.status = 'approved'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Image approved successfully',
            'data': image.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/<int:product_id>/images/<int:image_id>/reject', methods=['PUT'])
def reject_product_image(product_id, image_id):
    """
    Reject a product image

    Response:
        {
            "success": true,
            "message": "Image rejected successfully",
            "data": {
                "id": 1,
                "product_id": 1,
                "image_url": "https://...",
                "status": "rejected",
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        # Verify product exists
        product = Product.query.get_or_404(product_id)

        # Get the image and verify it belongs to this product
        image = ProductImage.query.filter_by(
            id=image_id,
            product_id=product_id
        ).first()

        if not image:
            return jsonify({
                'success': False,
                'error': f'Image {image_id} not found for product {product_id}'
            }), 404

        # Update image status
        image.status = 'rejected'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Image rejected successfully',
            'data': image.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/<int:product_id>/images/<int:image_id>/status', methods=['PUT'])
def update_image_status(product_id, image_id):
    """
    Update product image status (generic endpoint)

    Request Body:
        {
            "status": "approved" | "rejected" | "pending"
        }

    Response:
        {
            "success": true,
            "message": "Image status updated successfully",
            "data": {
                "id": 1,
                "product_id": 1,
                "image_url": "https://...",
                "status": "approved",
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        # Verify product exists
        product = Product.query.get_or_404(product_id)

        # Get the image and verify it belongs to this product
        image = ProductImage.query.filter_by(
            id=image_id,
            product_id=product_id
        ).first()

        if not image:
            return jsonify({
                'success': False,
                'error': f'Image {image_id} not found for product {product_id}'
            }), 404

        # Get request data
        data = request.get_json()

        if not data or 'status' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing "status" field in request body'
            }), 400

        new_status = data['status'].lower()

        # Validate status
        valid_statuses = ['pending', 'approved', 'rejected']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400

        # Update image status
        image.status = new_status
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Image status updated to "{new_status}" successfully',
            'data': image.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@products_bp.route('/products/<int:product_id>/status', methods=['PUT'])
def update_product_status(product_id):
    """
    Update product status to 'live' or 'rejected'

    Request Body:
        {
            "status": "live" | "rejected"
        }

    Response:
        {
            "success": true,
            "message": "Product status updated to 'live' successfully",
            "data": {
                "id": 1,
                "status": "live",
                ...
            }
        }
    """
    try:
        product = Product.query.get_or_404(product_id)

        # Get request data
        data = request.get_json()

        if not data or 'status' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing "status" field in request body'
            }), 400

        new_status = data['status'].lower()

        # Validate status
        valid_statuses = ['live', 'rejected']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400

        # Update product status
        product.status = new_status
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Product status updated to "{new_status}" successfully',
            'data': product_schema.dump(product)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/<int:product_id>/stock', methods=['PUT'])
def update_product_stock(product_id):
    """
    Update product stock status (in_stock or out_of_stock)

    Request Body:
        {
            "in_stock": true | false
        }

    Response:
        {
            "success": true,
            "message": "Product marked as in stock successfully",
            "data": {
                "id": 1,
                "in_stock": true,
                ...
            }
        }
    """
    try:
        product = Product.query.get_or_404(product_id)

        # Get request data
        data = request.get_json()

        if not data or 'in_stock' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing "in_stock" field in request body'
            }), 400

        in_stock = data['in_stock']

        # Validate in_stock is boolean
        if not isinstance(in_stock, bool):
            return jsonify({
                'success': False,
                'error': '"in_stock" must be a boolean value (true or false)'
            }), 400

        # Update product stock status
        product.in_stock = in_stock
        db.session.commit()

        stock_status = 'in stock' if in_stock else 'out of stock'
        return jsonify({
            'success': True,
            'message': f'Product marked as {stock_status} successfully',
            'data': product_schema.dump(product)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
