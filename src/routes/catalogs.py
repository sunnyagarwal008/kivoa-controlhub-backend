from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from sqlalchemy.orm import joinedload, contains_eager
from collections import defaultdict
import os
import json
from src.database import db
from src.models import Category, Product, PDFCatalog
from src.schemas import PDFCatalogSchema
from src.services import pdf_service

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


def _extract_filter_params(request_args):
    """
    Extract filter parameters from request arguments

    Args:
        request_args: Flask request.args object

    Returns:
        dict: Dictionary of filter parameters
    """
    return {
        'status': request_args.get('status'),
        'category': request_args.get('category'),
        'tags': request_args.get('tags'),
        'excludeOutOfStock': request_args.get('excludeOutOfStock', 'false').lower() == 'true',
        'minPrice': request_args.get('minPrice', type=float),
        'maxPrice': request_args.get('maxPrice', type=float),
        'sortBy': request_args.get('sortBy', 'created_at'),
        'sortOrder': request_args.get('sortOrder', 'desc').lower()
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

    Query Parameters:
        - name: Name for the catalog (required)
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
        # Get name parameter
        name = request.args.get('name')
        if not name:
            return jsonify({
                'success': False,
                'error': 'Missing required parameter: name'
            }), 400

        # Extract filter parameters
        filter_params = _extract_filter_params(request.args)

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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generating catalog: {str(e)}")
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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error refreshing catalog {catalog_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

