from flask import Blueprint, request, jsonify, current_app, Response
from marshmallow import ValidationError
from sqlalchemy.orm import joinedload, contains_eager
from collections import defaultdict
import os
import json
import io
import csv
from src.database import db
from src.models import Category, Product, PDFCatalog
from src.schemas import PDFCatalogSchema
from src.services import pdf_service, s3_service, csv_service

catalogs_bp = Blueprint('catalogs', __name__)

pdf_catalog_schema = PDFCatalogSchema()
pdf_catalogs_schema = PDFCatalogSchema(many=True)


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


def _build_products_query_for_update(status=None, category_name=None, tags_param=None,
                                     exclude_out_of_stock=False, min_price=None, max_price=None,
                                     box_number=None, flagged=None, min_discount=None, max_discount=None):
    """
    Build a SQLAlchemy query for bulk updates (without joins or eager loading)

    Args:
        status: Filter by product status
        category_name: Filter by category name
        tags_param: Comma-separated tags to filter by
        exclude_out_of_stock: Whether to exclude out of stock products
        min_price: Minimum price filter
        max_price: Maximum price filter
        box_number: Filter by box number
        flagged: Filter by flagged status (True/False)
        min_discount: Minimum discount percentage filter
        max_discount: Maximum discount percentage filter

    Returns:
        SQLAlchemy query object suitable for bulk updates
    """
    # Start with a simple query (no joins, no eager loading)
    query = Product.query

    # Apply filters
    if status:
        query = query.filter(Product.status == status)

    if category_name:
        # Use a subquery to filter by category name without joining
        category_subquery = db.session.query(Category.id).filter(Category.name == category_name).scalar_subquery()
        query = query.filter(Product.category_id.in_(category_subquery))

    if tags_param:
        # Split comma-separated tags and filter products that contain any of the tags
        tags_list = [tag.strip() for tag in tags_param.split(',') if tag.strip()]
        if tags_list:
            # Build OR condition for each tag
            tag_filters = [Product.tags.like(f'%{tag}%') for tag in tags_list]
            query = query.filter(db.or_(*tag_filters))

    if exclude_out_of_stock:
        query = query.filter(Product.inventory > 0)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if box_number is not None:
        query = query.filter(Product.box_number == box_number)

    if flagged is not None:
        query = query.filter(Product.flagged == flagged)

    if min_discount is not None:
        query = query.filter(Product.discount >= min_discount)

    if max_discount is not None:
        query = query.filter(Product.discount <= max_discount)

    return query


def _build_products_query(status=None, category_name=None, tags_param=None,
                         exclude_out_of_stock=False, min_price=None, max_price=None,
                         box_number=None, flagged=None, min_discount=None, max_discount=None,
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
        box_number: Filter by box number
        flagged: Filter by flagged status (True/False)
        min_discount: Minimum discount percentage filter
        max_discount: Maximum discount percentage filter
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
        query = query.filter(Product.inventory > 0)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if box_number is not None:
        query = query.filter(Product.box_number == box_number)

    if flagged is not None:
        query = query.filter(Product.flagged == flagged)

    if min_discount is not None:
        query = query.filter(Product.discount >= min_discount)

    if max_discount is not None:
        query = query.filter(Product.discount <= max_discount)

    # Apply sorting
    sort_column = getattr(Product, sort_by)
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    return query


def _extract_filter_params(request_args):
    """
    Extract filter parameters from request arguments

    Args:
        request_args: Flask request.args object

    Returns:
        dict: Dictionary of filter parameters
    """
    flagged_param = request_args.get('flagged')
    flagged = None
    if flagged_param is not None:
        flagged = flagged_param.lower() == 'true'

    return {
        'status': request_args.get('status'),
        'category': request_args.get('category'),
        'tags': request_args.get('tags'),
        'excludeOutOfStock': request_args.get('excludeOutOfStock', 'false').lower() == 'true',
        'minPrice': request_args.get('minPrice', type=float),
        'maxPrice': request_args.get('maxPrice', type=float),
        'boxNumber': request_args.get('boxNumber', type=int),
        'flagged': flagged,
        'minDiscount': request_args.get('minDiscount', type=float),
        'maxDiscount': request_args.get('maxDiscount', type=float),
        'sortBy': request_args.get('sortBy', 'created_at'),
        'sortOrder': request_args.get('sortOrder', 'desc').lower()
    }


def _extract_filter_params_from_body(data):
    """
    Extract filter parameters from request body

    Args:
        data: Request JSON body

    Returns:
        dict: Dictionary of filter parameters
    """
    return {
        'status': data.get('status'),
        'category': data.get('category'),
        'tags': data.get('tags'),
        'excludeOutOfStock': data.get('excludeOutOfStock', False),
        'minPrice': data.get('minPrice'),
        'maxPrice': data.get('maxPrice'),
        'boxNumber': data.get('boxNumber'),
        'flagged': data.get('flagged'),
        'minDiscount': data.get('minDiscount'),
        'maxDiscount': data.get('maxDiscount'),
        'sortBy': data.get('sortBy', 'created_at'),
        'sortOrder': data.get('sortOrder', 'desc').lower()
    }


def _generate_catalog_pdf(filter_params):
    """
    Generate a PDF catalog based on filter parameters

    Args:
        filter_params: Dictionary of filter parameters

    Returns:
        tuple: (catalog_url, total_products, num_categories) or raises exception
    """
    # Validate sort parameters
    is_valid, error_message = _validate_sort_parameters(
        filter_params['sortBy'],
        filter_params['sortOrder']
    )
    if not is_valid:
        raise ValueError(error_message)

    # Build query using common method
    query = _build_products_query(
        status=filter_params['status'],
        category_name=filter_params['category'],
        tags_param=filter_params['tags'],
        exclude_out_of_stock=filter_params['excludeOutOfStock'],
        min_price=filter_params['minPrice'],
        max_price=filter_params['maxPrice'],
        box_number=filter_params['boxNumber'],
        flagged=filter_params['flagged'],
        min_discount=filter_params['minDiscount'],
        max_discount=filter_params['maxDiscount'],
        sort_by=filter_params['sortBy'],
        sort_order=filter_params['sortOrder']
    )

    # Get all matching products (no pagination)
    products = query.all()

    if not products:
        raise ValueError('No products found matching the specified filters')

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

    return catalog_url, len(products), len(products_by_category)


@catalogs_bp.route('/catalogs', methods=['POST'])
def generate_product_catalog():
    """
    Generate a PDF catalog of filtered products and upload to S3

    This endpoint:
    1. Accepts a name and all filter parameters from get_products API (except pagination)
    2. Filters products based on provided parameters
    3. Groups products by category
    4. Generates a PDF with:
       - Cover page with dark green background and KIVOA branding
       - Products organized by category
       - 2-column grid layout
       - Each product shows: SKU (as title) and first image only
    5. Uploads the PDF to S3
    6. Saves the catalog metadata to database
    7. Returns the catalog details

    Request Body:
        {
            "name": "Winter Collection 2024",  // required
            "status": "live",  // optional - Filter by status (e.g., pending, live, rejected)
            "category": "Electronics",  // optional - Filter by category name
            "tags": "wireless,bluetooth",  // optional - Filter by tags (comma-separated)
            "excludeOutOfStock": false,  // optional - Filter out products that are out of stock
            "minPrice": 10.0,  // optional - Filter products with price >= minPrice
            "maxPrice": 100.0,  // optional - Filter products with price <= maxPrice
            "boxNumber": 1,  // optional - Filter by box number (integer)
            "sortBy": "created_at",  // optional - Sort field (sku_sequence_number, price, created_at)
            "sortOrder": "desc"  // optional - Sort order (asc, desc)
        }

    Response:
        {
            "success": true,
            "message": "Catalog generated successfully",
            "data": {
                "id": 1,
                "name": "Winter Collection 2024",
                "s3_url": "https://...",
                "filter_json": "{...}",
                "total_products": 50,
                "categories": 5,
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        # Get request body
        data = request.get_json()
        if not data:
            error_msg = 'Request body is required'
            current_app.logger.error(f"Catalog generation failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400

        # Get name parameter
        name = data.get('name')
        if not name:
            error_msg = 'Missing required field: name'
            current_app.logger.error(f"Catalog generation failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400

        # Extract filter parameters from request body
        filter_params = _extract_filter_params_from_body(data)

        # Generate the PDF catalog
        catalog_url, total_products, num_categories = _generate_catalog_pdf(filter_params)

        # Save catalog to database
        pdf_catalog = PDFCatalog(
            name=name,
            s3_url=catalog_url,
            filter_json=json.dumps(filter_params)
        )
        db.session.add(pdf_catalog)
        db.session.commit()

        # Prepare response
        response_data = pdf_catalog.to_dict()
        response_data['total_products'] = total_products
        response_data['categories'] = num_categories

        return jsonify({
            'success': True,
            'message': 'Catalog generated successfully',
            'data': response_data
        }), 201

    except ValueError as e:
        error_msg = str(e)
        current_app.logger.error(f"Catalog generation validation error: {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg
        }), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generating catalog: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@catalogs_bp.route('/catalogs', methods=['GET'])
def get_all_catalogs():
    """
    Get all PDF catalogs (non-paginated)

    Response:
        {
            "success": true,
            "data": [
                {
                    "id": 1,
                    "name": "Winter Collection 2024",
                    "s3_url": "https://...",
                    "filter_json": "{...}",
                    "created_at": "...",
                    "updated_at": "..."
                },
                ...
            ],
            "count": 10
        }
    """
    try:
        # Get all catalogs ordered by created_at descending
        catalogs = PDFCatalog.query.order_by(PDFCatalog.created_at.desc()).all()

        # Convert to dict
        catalogs_data = [catalog.to_dict() for catalog in catalogs]

        return jsonify({
            'success': True,
            'data': catalogs_data,
            'count': len(catalogs_data)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching catalogs: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@catalogs_bp.route('/catalogs/<int:catalog_id>/refresh', methods=['POST'])
def refresh_catalog(catalog_id):
    """
    Refresh a PDF catalog by regenerating it with the stored filter criteria

    This endpoint:
    1. Retrieves the catalog by ID
    2. Parses the stored filter_json
    3. Regenerates the PDF with the same filters
    4. Updates the s3_url with the new PDF
    5. Returns the updated catalog details

    Response:
        {
            "success": true,
            "message": "Catalog refreshed successfully",
            "data": {
                "id": 1,
                "name": "Winter Collection 2024",
                "s3_url": "https://...",
                "filter_json": "{...}",
                "total_products": 52,
                "categories": 5,
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        # Get the catalog by ID
        catalog = PDFCatalog.query.get_or_404(catalog_id)

        # Parse the stored filter JSON
        filter_params = json.loads(catalog.filter_json)

        current_app.logger.info(f"Refreshing catalog {catalog_id} with filters: {filter_params}")

        # Generate the new PDF catalog
        catalog_url, total_products, num_categories = _generate_catalog_pdf(filter_params)

        # Update the catalog with new S3 URL
        catalog.s3_url = catalog_url
        db.session.commit()

        # Prepare response
        response_data = catalog.to_dict()
        response_data['total_products'] = total_products
        response_data['categories'] = num_categories

        return jsonify({
            'success': True,
            'message': 'Catalog refreshed successfully',
            'data': response_data
        }), 200

    except ValueError as e:
        error_msg = str(e)
        current_app.logger.error(f"Catalog refresh validation error for catalog {catalog_id}: {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg
        }), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error refreshing catalog {catalog_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@catalogs_bp.route('/catalogs/<int:catalog_id>', methods=['DELETE'])
def delete_catalog(catalog_id):
    """
    Delete a PDF catalog

    This endpoint:
    1. Retrieves the catalog by ID
    2. Deletes the PDF file from S3
    3. Deletes the catalog record from the database
    4. Returns success message

    Response:
        {
            "success": true,
            "message": "Catalog deleted successfully"
        }
    """
    try:
        # Get the catalog by ID
        catalog = PDFCatalog.query.get_or_404(catalog_id)

        current_app.logger.info(f"Deleting catalog {catalog_id}: {catalog.name}")

        # Delete the PDF file from S3
        try:
            s3_service.delete_file(catalog.s3_url)
            current_app.logger.info(f"Deleted PDF from S3: {catalog.s3_url}")
        except Exception as e:
            # Log the error but continue with database deletion
            current_app.logger.error(f"Failed to delete PDF from S3: {str(e)}")

        # Delete the catalog from database
        db.session.delete(catalog)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Catalog deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting catalog {catalog_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500





@catalogs_bp.route('/catalogs/apply-discount', methods=['POST'])
def apply_discount_to_filtered_products():
    """
    Apply a percentage discount to all products matching the specified filters

    This endpoint:
    1. Accepts filter parameters similar to generate_product_catalog API
    2. Accepts a discount percentage value
    3. Filters products based on provided parameters
    4. Updates the discount field with the percentage value
    5. Recalculates the price field as: price = mrp - (mrp × discount / 100)
    6. Returns the count of updated products

    Request Body:
        {
            "discount": 20,  // required - Discount percentage (0-100)
            "status": "live",  // optional - Filter by status (e.g., pending, live, rejected)
            "category": "Electronics",  // optional - Filter by category name
            "tags": "wireless,bluetooth",  // optional - Filter by tags (comma-separated)
            "excludeOutOfStock": false,  // optional - Filter out products that are out of stock
            "minPrice": 10.0,  // optional - Filter products with price >= minPrice
            "maxPrice": 100.0,  // optional - Filter products with price <= maxPrice
            "boxNumber": 1,  // optional - Filter by box number (integer)
            "flagged": false,  // optional - Filter by flagged status
            "minDiscount": 0,  // optional - Filter products with discount >= minDiscount
            "maxDiscount": 50  // optional - Filter products with discount <= maxDiscount
        }

    Response:
        {
            "success": true,
            "message": "Discount of 20% applied successfully to 50 products",
            "data": {
                "updated_count": 50,
                "discount_percentage": 20
            }
        }
    """
    try:
        # Get request body
        data = request.get_json()
        if not data:
            error_msg = 'Request body is required'
            current_app.logger.error(f"Apply discount failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400

        # Get discount parameter
        discount = data.get('discount')
        if discount is None:
            error_msg = 'Missing required field: discount'
            current_app.logger.error(f"Apply discount failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400

        # Validate discount value
        try:
            discount = float(discount)
            if discount < 0 or discount > 100:
                raise ValueError('Discount percentage must be between 0 and 100')
        except (ValueError, TypeError) as e:
            error_msg = f'Invalid discount value: {str(e)}'
            current_app.logger.error(f"Apply discount failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400

        # Extract filter parameters from request body
        filter_params = _extract_filter_params_from_body(data)

        # Build query for bulk update (without joins or eager loading)
        query = _build_products_query_for_update(
            status=filter_params['status'],
            category_name=filter_params['category'],
            tags_param=filter_params['tags'],
            exclude_out_of_stock=filter_params['excludeOutOfStock'],
            min_price=filter_params['minPrice'],
            max_price=filter_params['maxPrice'],
            box_number=filter_params['boxNumber'],
            flagged=filter_params['flagged'],
            min_discount=filter_params['minDiscount'],
            max_discount=filter_params['maxDiscount']
        )

        current_app.logger.info(f"Applying {discount}% discount to matching products")

        # Use bulk update with SQL expression to:
        # 1. Set discount field to the percentage value
        # 2. Recalculate price as: mrp - (mrp * discount / 100)
        updated_count = query.update(
            {
                Product.discount: discount,
                Product.price: Product.mrp - (Product.mrp * (discount / 100))
            },
            synchronize_session=False
        )

        if updated_count == 0:
            error_msg = 'No products found matching the specified filters'
            current_app.logger.warning(f"Apply discount: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400

        db.session.commit()

        current_app.logger.info(f"Successfully applied {discount}% discount to {updated_count} products")

        return jsonify({
            'success': True,
            'message': f'Discount of {discount}% applied successfully to {updated_count} products',
            'data': {
                'updated_count': updated_count,
                'discount_percentage': discount
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error applying discount: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@catalogs_bp.route('/catalogs/shopify-export', methods=['GET'])
def export_shopify_csv():
    """
    Export products as Shopify-compatible CSV file

    This endpoint:
    1. Accepts filter parameters as query parameters
    2. Filters products based on provided parameters
    3. Generates a CSV file in Shopify product import format
    4. Returns the CSV file directly as a download

    Query Parameters:
        status: optional - Filter by status (e.g., pending, live, rejected)
        category: optional - Filter by category name
        tags: optional - Filter by tags (comma-separated)
        excludeOutOfStock: optional - Filter out products that are out of stock (true/false)
        minPrice: optional - Filter products with price >= minPrice
        maxPrice: optional - Filter products with price <= maxPrice
        boxNumber: optional - Filter by box number (integer)
        sortBy: optional - Sort field (sku_sequence_number, price, created_at)
        sortOrder: optional - Sort order (asc, desc)

    Response:
        CSV file download with Shopify-compatible product data
    """
    try:
        # Extract filter parameters from query parameters
        filter_params = _extract_filter_params(request.args)

        # Validate sort parameters
        is_valid, error_message = _validate_sort_parameters(
            filter_params['sortBy'],
            filter_params['sortOrder']
        )
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_message
            }), 400

        # Build query using common method
        query = _build_products_query(
            status=filter_params['status'],
            category_name=filter_params['category'],
            tags_param=filter_params['tags'],
            exclude_out_of_stock=filter_params['excludeOutOfStock'],
            min_price=filter_params['minPrice'],
            max_price=filter_params['maxPrice'],
            box_number=filter_params['boxNumber'],
            flagged=filter_params['flagged'],
            min_discount=filter_params['minDiscount'],
            max_discount=filter_params['maxDiscount'],
            sort_by=filter_params['sortBy'],
            sort_order=filter_params['sortOrder']
        )

        # Get all matching products (no pagination)
        products = query.all()

        if not products:
            return jsonify({
                'success': False,
                'error': 'No products found matching the specified filters'
            }), 400

        current_app.logger.info(f"Generating Shopify CSV export with {len(products)} products")

        # Generate CSV in memory
        output = io.StringIO()

        # Define Shopify CSV headers
        headers = [
            'Handle', 'Title', 'Body (HTML)', 'Vendor', 'Type', 'Product Category', 'Tags', 'Published',
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

        writer = csv.DictWriter(output, fieldnames=headers)
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

            # Determine inventory quantity
            inventory_qty = product.inventory if product.inventory is not None else 0

            # First row with product details
            row = {
                'Handle': handle,
                'Title': title,
                'Body (HTML)': description,
                'Vendor': 'KIVOA',
                'Type': category_name,
                'Product Category': 'Apparel & Accessories > Jewelry',
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
                'SEO Description': description[:160] if description else title,
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
                'Variant Weight Unit': '',
                'Variant Tax Code': '',
                'Cost per item': '',
                'Status': 'active' if product.status == 'live' else 'draft'
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

        # Get CSV content
        csv_content = output.getvalue()
        output.close()

        # Return CSV as downloadable file
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=shopify_export.csv'
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error generating Shopify CSV export: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
