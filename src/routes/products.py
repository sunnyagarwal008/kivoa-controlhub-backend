from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from sqlalchemy.orm import joinedload, contains_eager
from collections import defaultdict
import os
import random
from src.database import db
from src.models import Category, Product, ProductImage, Prompt
from src.schemas import ProductSchema
from src.services import sqs_service, pdf_service, s3_service, gemini_service
from src.services.gemini_service import download_image
from src.utils.raw_image_utils import delete_raw_image_by_url

products_bp = Blueprint('products', __name__)

product_schema = ProductSchema()
products_schema = ProductSchema(many=True)


def _validate_sort_parameters(sort_by, sort_order):
    """
    Validate sort parameters

    Args:
        sort_by: Field to sort by
        sort_order: Sort order - 'asc' or 'desc'

    Returns:
        tuple: (is_valid, error_message) - error_message is None if valid
    """
    valid_sort_fields = ['sku_sequence_number', 'price', 'created_at']
    if sort_by not in valid_sort_fields:
        return False, f'Invalid sortBy parameter. Must be one of: {", ".join(valid_sort_fields)}'

    valid_sort_orders = ['asc', 'desc']
    if sort_order not in valid_sort_orders:
        return False, f'Invalid sortOrder parameter. Must be one of: {", ".join(valid_sort_orders)}'

    return True, None


def _build_products_query(status=None, category_name=None, tags_param=None,
                         exclude_out_of_stock=False, min_price=None, max_price=None,
                         sort_by='created_at', sort_order='desc'):
    """
    Build a SQLAlchemy query for products with filters and sorting

    Args:
        status: Filter by product status
        category_name: Filter by category name
        tags_param: Comma-separated tags to filter by
        exclude_out_of_stock: Whether to exclude out of stock products
        min_price: Minimum price filter
        max_price: Maximum price filter
        sort_by: Field to sort by (default: created_at)
        sort_order: Sort order - 'asc' or 'desc' (default: desc)

    Returns:
        SQLAlchemy query object
    """
    # Build query with eager loading of category and images
    # If filtering by category, use join + contains_eager instead of joinedload
    if category_name:
        query = Product.query.join(Product.category_ref).options(
            contains_eager(Product.category_ref),
            joinedload(Product.product_images)
        ).filter(Category.name == category_name)
    else:
        query = Product.query.options(
            joinedload(Product.category_ref),
            joinedload(Product.product_images)
        )

    # Apply filters
    if status:
        query = query.filter(Product.status == status)

    if tags_param:
        # Split comma-separated tags and filter products that contain any of the tags
        tags_list = [tag.strip() for tag in tags_param.split(',') if tag.strip()]
        if tags_list:
            # Build OR condition for each tag
            tag_filters = [Product.tags.like(f'%{tag}%') for tag in tags_list]
            query = query.filter(db.or_(*tag_filters))

    if exclude_out_of_stock:
        query = query.filter(Product.in_stock == True)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    # Apply sorting
    sort_column = getattr(Product, sort_by)
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    return query


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
        product_ids_for_queue = []
        products_for_direct_upload = []

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
            sku, sequence_number = category.generate_sku(validated_data['purchase_month'])

            # Check if this is a raw image that needs AI processing
            is_raw_image = validated_data.get('is_raw_image', True)

            # Set status based on is_raw_image flag
            # If is_raw_image is True, status is 'pending' (needs AI processing)
            # If is_raw_image is False, status is 'pending_review' (ready-to-use image)
            status = 'pending' if is_raw_image else 'pending_review'

            # Create new product
            product = Product(
                category_id=category.id,
                sku=sku,
                sku_sequence_number=sequence_number,
                purchase_month=validated_data['purchase_month'],
                raw_image=validated_data['raw_image'],
                mrp=validated_data['mrp'],
                price=validated_data['price'],
                discount=validated_data['discount'],
                gst=validated_data['gst'],
                price_code=validated_data.get('price_code'),
                tags=validated_data.get('tags'),
                box_number=validated_data.get('box_number'),
                status=status
            )

            db.session.add(product)
            db.session.flush()  # Get the ID without committing

            created_products.append(product_schema.dump(product))

            # Track products based on processing type
            if is_raw_image:
                product_ids_for_queue.append(product.id)
            else:
                products_for_direct_upload.append({
                    'id': product.id,
                    'sku': product.sku,
                    'raw_image': product.raw_image
                })

        # Commit all products
        db.session.commit()

        # Process products with is_raw_image=False: copy image to S3
        for product_info in products_for_direct_upload:
            try:
                # Get file extension from the raw_image URL
                file_extension = os.path.splitext(product_info['raw_image'].split('?')[0])[1]
                if not file_extension:
                    file_extension = '.jpg'  # default extension

                # Create S3 key with format: product-images/<sku>-1<extension>
                key = f"product-images/{product_info['sku']}-1{file_extension}"

                # Copy image from URL to S3
                image_url = s3_service.copy_image_from_url_to_s3(product_info['raw_image'], key)

                # Create ProductImage entry
                product_image = ProductImage(
                    product_id=product_info['id'],
                    image_url=image_url,
                    status='approved'
                )
                db.session.add(product_image)

                current_app.logger.info(f"Copied image for product {product_info['id']} to S3: {image_url}")

                # Delete from raw_images table if the raw_image URL exists there
                delete_raw_image_by_url(product_info['raw_image'])

            except Exception as e:
                # Log the error but don't fail the entire request
                current_app.logger.error(f"Failed to copy image for product {product_info['id']}: {str(e)}")
                raise e

        # Commit product images and raw_image deletions
        db.session.commit()

        # Send products with is_raw_image=True to SQS queue for AI processing
        for product_id in product_ids_for_queue:
            try:
                sqs_service.send_message(product_id)
            except Exception as e:
                # Log the error but don't fail the entire request
                # The products are already created
                current_app.logger.error(f"Failed to send product_id {product_id} to SQS: {str(e)}")

        # Prepare response message
        if product_ids_for_queue and products_for_direct_upload:
            message = f'Successfully created {len(created_products)} products: {len(product_ids_for_queue)} queued for AI processing, {len(products_for_direct_upload)} marked as live'
        elif product_ids_for_queue:
            message = f'Successfully created {len(created_products)} products and queued for AI processing'
        else:
            message = f'Successfully created {len(created_products)} products and marked as live'

        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'created': len(created_products),
                'total': len(products_data),
                'queued_for_processing': len(product_ids_for_queue),
                'marked_as_live': len(products_for_direct_upload),
                'products': created_products
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/search', methods=['GET'])
def search_products():
    """
    Search products by SKU

    Query Parameters:
        - sku: SKU to search for (partial match supported)

    Response:
        {
            "success": true,
            "data": [...],
            "count": 5
        }
    """
    try:
        # Get SKU query parameter
        sku = request.args.get('sku')

        if not sku:
            return jsonify({
                'success': False,
                'error': 'Missing "sku" query parameter'
            }), 400

        # Build query with LIKE for partial matching
        query = Product.query.options(
            joinedload(Product.category_ref),
            joinedload(Product.product_images)
        ).filter(Product.sku.like(f'%{sku}%'))

        # Get all matching products
        products = query.order_by(Product.created_at.desc()).all()

        # Convert products to dict with category details and images
        products_data = [
            product.to_dict(include_category_details=True, include_images=True)
            for product in products
        ]

        return jsonify({
            'success': True,
            'data': products_data,
            'count': len(products_data)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products', methods=['GET'])
def get_products():
    """
    Get all products with optional filtering and sorting

    Query Parameters:
        - status: Filter by status (e.g., pending, approved, rejected)
        - category: Filter by category name
        - tags: Filter by tags (comma-separated, e.g., "wireless,bluetooth")
        - excludeOutOfStock: Filter out products that are out of stock (true/false)
        - minPrice: Filter products with price >= minPrice
        - maxPrice: Filter products with price <= maxPrice
        - sortBy: Sort field (sku_sequence_number, price) (default: created_at)
        - sortOrder: Sort order (asc, desc) (default: desc)
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
        category_name = request.args.get('category')
        tags_param = request.args.get('tags')
        exclude_out_of_stock = request.args.get('excludeOutOfStock', 'false').lower() == 'true'
        min_price = request.args.get('minPrice', type=float)
        max_price = request.args.get('maxPrice', type=float)
        sort_by = request.args.get('sortBy', 'created_at')
        sort_order = request.args.get('sortOrder', 'desc').lower()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Validate sort parameters
        is_valid, error_message = _validate_sort_parameters(sort_by, sort_order)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_message
            }), 400

        # Build query using common method
        query = _build_products_query(
            status=status,
            category_name=category_name,
            tags_param=tags_param,
            exclude_out_of_stock=exclude_out_of_stock,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Paginate results
        pagination = query.paginate(
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
    Update a product (partial update supported - send only fields you want to update)

    Request Body (all fields optional):
        {
            "category": "Electronics",           # Category name (will regenerate SKU if changed)
            "purchase_month": "0124",            # MMYY format (will regenerate SKU if changed)
            "raw_image": "https://...",          # S3 URL
            "mrp": 1000.00,                      # Maximum Retail Price
            "price": 800.00,                     # Selling Price
            "discount": 200.00,                  # Discount amount
            "gst": 18.00,                        # GST percentage
            "price_code": "ABC123",              # Optional price code
            "tags": "wireless,bluetooth,premium", # Comma-separated tags
            "box_number": 42                     # Box number (integer)
        }

    Response:
        {
            "success": true,
            "message": "Product updated successfully",
            "data": {
                "id": 1,
                "category": "Electronics",
                "sku": "ELEC-0001-0124",
                "tags": "wireless,bluetooth,premium",
                "box_number": 42,
                ...
            }
        }

    Note:
        - SKU is auto-generated and cannot be updated directly
        - Changing category or purchase_month will regenerate the SKU
        - status and in_stock have dedicated endpoints
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
            new_sku, sequence_number = category.generate_sku(new_purchase_month)
            product.sku = new_sku
            product.sku_sequence_number = sequence_number
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
            'data': product.to_dict(include_category_details=True, include_images=True)
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
    Delete a product and its associated images from S3

    Response:
        {
            "success": true,
            "message": "Product deleted successfully"
        }
    """
    try:
        product = Product.query.options(
            joinedload(Product.product_images)
        ).get_or_404(product_id)

        # Delete all product images from S3
        deleted_images_count = 0
        failed_images = []

        for product_image in product.product_images:
            try:
                s3_service.delete_file(product_image.image_url)
                deleted_images_count += 1
                current_app.logger.info(f"Deleted image from S3: {product_image.image_url}")
            except Exception as e:
                # Log the error but continue deleting other images
                current_app.logger.error(f"Failed to delete image {product_image.id} from S3: {str(e)}")
                failed_images.append(product_image.id)

        # Delete the product (cascade will delete ProductImage records)
        db.session.delete(product)
        db.session.commit()

        message = f'Product deleted successfully'
        if deleted_images_count > 0:
            message += f' ({deleted_images_count} image(s) deleted from S3)'
        if failed_images:
            message += f' (Warning: Failed to delete {len(failed_images)} image(s) from S3)'

        return jsonify({
            'success': True,
            'message': message
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


@products_bp.route('/products/<int:product_id>/images/<int:image_id>/reject', methods=['DELETE'])
def reject_product_image(product_id, image_id):
    """
    Reject and delete a product image from both database and S3

    Response:
        {
            "success": true,
            "message": "Image deleted successfully"
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

        # Store image_url for S3 deletion
        image_url = image.image_url

        # Delete from database first
        db.session.delete(image)
        db.session.commit()

        # Delete from S3
        try:
            s3_service.delete_file(image_url)
            current_app.logger.info(f"Deleted image from S3: {image_url}")
        except Exception as s3_error:
            # Log the error but don't fail the request since DB deletion succeeded
            current_app.logger.error(f"Failed to delete image from S3: {str(s3_error)}")

        return jsonify({
            'success': True,
            'message': 'Image deleted successfully'
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


@products_bp.route('/products/catalog', methods=['GET'])
def generate_product_catalog():
    """
    Generate a PDF catalog of filtered products and upload to S3

    This endpoint:
    1. Accepts all filter parameters from get_products API (except pagination)
    2. Filters products based on provided parameters
    3. Groups products by category
    4. Generates a PDF with:
       - Cover page with dark green background and KIVOA branding
       - Products organized by category
       - 2-column grid layout
       - Each product shows: SKU (as title) and first image only
    5. Uploads the PDF to S3
    6. Returns the public S3 URL

    Query Parameters:
        - status: Filter by status (e.g., pending, live, rejected)
        - category: Filter by category name
        - tags: Filter by tags (comma-separated, e.g., "wireless,bluetooth")
        - excludeOutOfStock: Filter out products that are out of stock (true/false)
        - minPrice: Filter products with price >= minPrice
        - maxPrice: Filter products with price <= maxPrice
        - sortBy: Sort field (sku_sequence_number, price, created_at) (default: created_at)
        - sortOrder: Sort order (asc, desc) (default: desc)

    Response:
        {
            "success": true,
            "message": "Catalog generated successfully",
            "data": {
                "catalog_url": "https://...",
                "total_products": 50,
                "categories": 5
            }
        }
    """
    try:
        # Get query parameters (same as get_products, excluding pagination)
        status = request.args.get('status')
        category_name = request.args.get('category')
        tags_param = request.args.get('tags')
        exclude_out_of_stock = request.args.get('excludeOutOfStock', 'false').lower() == 'true'
        min_price = request.args.get('minPrice', type=float)
        max_price = request.args.get('maxPrice', type=float)
        sort_by = request.args.get('sortBy', 'created_at')
        sort_order = request.args.get('sortOrder', 'desc').lower()

        # Validate sort parameters
        is_valid, error_message = _validate_sort_parameters(sort_by, sort_order)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_message
            }), 400

        # Build query using common method
        query = _build_products_query(
            status=status,
            category_name=category_name,
            tags_param=tags_param,
            exclude_out_of_stock=exclude_out_of_stock,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Get all matching products (no pagination)
        products = query.all()

        if not products:
            return jsonify({
                'success': False,
                'error': 'No products found matching the specified filters'
            }), 404

        # Group products by category
        products_by_category = defaultdict(list)
        for product in products:
            category_name = product.category_ref.name if product.category_ref else 'Uncategorized'
            products_by_category[category_name].append(product)

        # Convert defaultdict to regular dict for better handling
        products_by_category = dict(products_by_category)

        current_app.logger.info(f"Generating catalog with {len(products)} products across {len(products_by_category)} categories")

        # Generate PDF
        pdf_path = pdf_service.generate_product_catalog(products_by_category)

        # Upload to S3
        catalog_url = pdf_service.upload_pdf_to_s3(pdf_path)

        # Clean up temporary PDF file
        try:
            os.remove(pdf_path)
        except Exception as e:
            current_app.logger.warning(f"Failed to remove temporary PDF file: {str(e)}")

        return jsonify({
            'success': True,
            'message': 'Catalog generated successfully',
            'data': {
                'catalog_url': catalog_url,
                'total_products': len(products),
                'categories': len(products_by_category)
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error generating catalog: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/<int:product_id>/generate-image', methods=['POST'])
def generate_product_image(product_id):
    """
    Generate a new product image for a product using AI

    Request Body:
        {
            "prompt_type": "model_hand",  # Optional type filter for prompts (e.g., 'model_hand', 'satin', 'mirror')
            "prompt_text": "custom prompt"  # Optional custom prompt text. If provided, this will be used instead of DB prompts
        }

    Response:
        {
            "success": true,
            "message": "Product image generated successfully",
            "data": {
                "id": 1,
                "product_id": 1,
                "image_url": "https://...",
                "status": "pending",
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        # Get product and verify it exists
        product = Product.query.options(
            joinedload(Product.category_ref),
            joinedload(Product.product_images)
        ).get_or_404(product_id)

        # Get request body
        data = request.get_json() or {}
        prompt_type = data.get('prompt_type')
        prompt_text = data.get('prompt_text')

        # Determine which prompt to use
        if prompt_text:
            # Use the provided custom prompt
            selected_prompt = prompt_text
            current_app.logger.info(f"Using custom prompt for product {product_id}")
        else:
            # Get prompts from database based on product category and type
            category_name = product.category_ref.name if product.category_ref else 'default'

            # Query prompts from database
            query = Prompt.query.filter(
                Prompt.category_id == product.category_id,
                Prompt.is_active == True
            )

            # Filter by type if provided
            if prompt_type:
                query = query.filter(Prompt.type == prompt_type)

            prompts = query.all()

            if not prompts:
                return jsonify({
                    'success': False,
                    'error': f'No prompts found for category "{category_name}"' +
                            (f' and type "{prompt_type}"' if prompt_type else '')
                }), 404

            # Randomly select one prompt
            selected_prompt_obj = random.choice(prompts)
            selected_prompt = selected_prompt_obj.text
            current_app.logger.info(f"total prompts: {len(prompts)}, selected prompt {selected_prompt} for product {product_id}, type: {prompt_type}, category: {category_name}")

        # Validate product has a raw_image URL
        if not product.raw_image:
            return jsonify({
                'success': False,
                'error': 'Product does not have a raw_image URL'
            }), 400

        # Download the raw image
        current_app.logger.info(f"Downloading raw image for product {product_id}: {product.raw_image}")
        try:
            raw_image_path = download_image(product.raw_image)
            current_app.logger.info(f"Downloaded and validated image: {raw_image_path}")
        except Exception as download_error:
            current_app.logger.error(f"Failed to download/validate image from {product.raw_image}: {str(download_error)}")
            return jsonify({
                'success': False,
                'error': f'Failed to download or validate image from URL: {str(download_error)}',
                'image_url': product.raw_image
            }), 400

        # Generate output file path
        image_name = os.path.basename(raw_image_path)
        image_name_parts = os.path.splitext(image_name)

        # Count existing images to determine the next index
        existing_images_count = len(product.product_images)
        next_index = existing_images_count + 1

        output_image_name = f"{image_name_parts[0]}-{next_index:02d}{image_name_parts[1]}"
        output_file_path = os.path.join("/tmp", output_image_name)

        # Generate the image using Gemini
        current_app.logger.info(f"Generating image for product {product_id} with prompt: {selected_prompt}...")
        try:
            gemini_service._do_generate_image(raw_image_path, output_file_path, selected_prompt)
            current_app.logger.info(f"Successfully generated image: {output_file_path}")
        except Exception as gemini_error:
            current_app.logger.error(f"Gemini API error: {str(gemini_error)}")
            # Clean up downloaded file
            if os.path.exists(raw_image_path):
                os.remove(raw_image_path)
            return jsonify({
                'success': False,
                'error': f'Failed to generate image with AI: {str(gemini_error)}'
            }), 500

        # Upload to S3
        bucket_name = current_app.config['S3_BUCKET_NAME']
        file_extension = os.path.splitext(output_file_path)[1]
        s3_key = f"product-images/{product.sku}-{next_index}{file_extension}"

        current_app.logger.info(f"Uploading generated image to S3: {s3_key}")
        image_url = s3_service.upload_file(output_file_path, bucket_name=bucket_name, key=s3_key)

        # Save to product_images table with status 'pending'
        product_image = ProductImage(
            product_id=product_id,
            image_url=image_url,
            status='pending'
        )
        db.session.add(product_image)
        db.session.commit()

        current_app.logger.info(f"Successfully generated and saved image for product {product_id}: {image_url}")

        # Clean up temporary files
        try:
            if os.path.exists(raw_image_path):
                os.remove(raw_image_path)
            if os.path.exists(output_file_path):
                os.remove(output_file_path)
        except Exception as cleanup_error:
            current_app.logger.warning(f"Failed to clean up temporary files: {str(cleanup_error)}")

        return jsonify({
            'success': True,
            'message': 'Product image generated successfully',
            'data': product_image.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generating product image: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@products_bp.route('/products/<int:product_id>/images/update-priorities', methods=['PUT'])
def update_product_image_priorities(product_id):
    """
    Update priorities for multiple product images

    Request Body:
        {
            "priorities": [
                {"image_id": 1, "priority": 0},
                {"image_id": 2, "priority": 1},
                {"image_id": 3, "priority": 2}
            ]
        }

    Response:
        {
            "success": true,
            "message": "Updated priorities for 3 images",
            "data": [
                {
                    "id": 1,
                    "product_id": 1,
                    "image_url": "https://...",
                    "status": "approved",
                    "priority": 0,
                    "created_at": "...",
                    "updated_at": "..."
                },
                ...
            ]
        }
    """
    try:
        # Get product and verify it exists
        product = Product.query.get_or_404(product_id)

        # Get request body
        data = request.get_json()
        if not data or 'priorities' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: priorities'
            }), 400

        priorities = data['priorities']
        if not isinstance(priorities, list):
            return jsonify({
                'success': False,
                'error': 'priorities must be an array'
            }), 400

        if not priorities:
            return jsonify({
                'success': False,
                'error': 'priorities array cannot be empty'
            }), 400

        # Validate each priority entry
        for entry in priorities:
            if not isinstance(entry, dict):
                return jsonify({
                    'success': False,
                    'error': 'Each priority entry must be an object with image_id and priority'
                }), 400

            if 'image_id' not in entry or 'priority' not in entry:
                return jsonify({
                    'success': False,
                    'error': 'Each priority entry must have image_id and priority fields'
                }), 400

            if not isinstance(entry['image_id'], int) or not isinstance(entry['priority'], int):
                return jsonify({
                    'success': False,
                    'error': 'image_id and priority must be integers'
                }), 400

        # Update priorities
        updated_images = []
        for entry in priorities:
            image_id = entry['image_id']
            priority = entry['priority']

            # Get the image and verify it belongs to this product
            product_image = ProductImage.query.filter_by(
                id=image_id,
                product_id=product_id
            ).first()

            if not product_image:
                return jsonify({
                    'success': False,
                    'error': f'Image {image_id} not found for product {product_id}'
                }), 404

            # Update priority
            product_image.priority = priority
            updated_images.append(product_image)

        # Commit all changes
        db.session.commit()

        current_app.logger.info(f"Updated priorities for {len(updated_images)} images of product {product_id}")

        return jsonify({
            'success': True,
            'message': f'Updated priorities for {len(updated_images)} images',
            'data': [img.to_dict() for img in updated_images]
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating image priorities: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
