from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from src.database import db
from src.models import RawImage
from src.schemas import RawImageSchema

raw_images_bp = Blueprint('raw_images', __name__)

raw_image_schema = RawImageSchema()
raw_images_schema = RawImageSchema(many=True)


@raw_images_bp.route('/raw-images', methods=['GET'])
def get_raw_images():
    """
    Get all raw images with pagination and sorting

    Query Parameters:
        - sortBy: Sort field (id, created_at) (default: created_at)
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
        sort_by = request.args.get('sortBy', 'created_at')
        sort_order = request.args.get('sortOrder', 'desc').lower()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Validate sort parameters
        valid_sort_fields = ['id', 'created_at']
        if sort_by not in valid_sort_fields:
            return jsonify({
                'success': False,
                'error': f'Invalid sortBy parameter. Must be one of: {", ".join(valid_sort_fields)}'
            }), 400

        valid_sort_orders = ['asc', 'desc']
        if sort_order not in valid_sort_orders:
            return jsonify({
                'success': False,
                'error': f'Invalid sortOrder parameter. Must be one of: {", ".join(valid_sort_orders)}'
            }), 400

        # Build query
        query = RawImage.query

        # Apply sorting
        sort_column = getattr(RawImage, sort_by)
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Paginate results
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        # Convert raw images to dict
        raw_images_data = [raw_image_schema.dump(raw_image) for raw_image in pagination.items]

        return jsonify({
            'success': True,
            'data': raw_images_data,
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


@raw_images_bp.route('/raw-images/bulk', methods=['POST'])
def bulk_create_raw_images():
    """
    Bulk create raw images

    Request Body:
        {
            "raw_images": [
                {"image_url": "https://example.com/image1.jpg"},
                {"image_url": "https://example.com/image2.jpg"},
                ...
            ]
        }

    Response:
        {
            "success": true,
            "message": "Successfully created 10 raw images",
            "data": {
                "created": 10,
                "total": 10,
                "skipped": 0,
                "raw_images": [...]
            }
        }
    """
    try:
        request_data = request.get_json()

        if not request_data or 'raw_images' not in request_data:
            return jsonify({
                'success': False,
                'error': 'Missing "raw_images" array in request body'
            }), 400

        raw_images_data = request_data['raw_images']

        if not isinstance(raw_images_data, list):
            return jsonify({
                'success': False,
                'error': '"raw_images" must be an array'
            }), 400

        if len(raw_images_data) == 0:
            return jsonify({
                'success': False,
                'error': '"raw_images" array cannot be empty'
            }), 400

        if len(raw_images_data) > 1000:
            return jsonify({
                'success': False,
                'error': 'Maximum 1000 raw images allowed per bulk upload'
            }), 400

        created_raw_images = []
        skipped_count = 0

        for index, raw_image_data in enumerate(raw_images_data):
            # Validate raw image data
            validated_data = raw_image_schema.load(raw_image_data)

            # Check if image_url already exists
            existing_raw_image = RawImage.query.filter_by(image_url=validated_data['image_url']).first()
            if existing_raw_image:
                skipped_count += 1
                continue

            # Create new raw image
            raw_image = RawImage(
                image_url=validated_data['image_url']
            )

            db.session.add(raw_image)
            db.session.flush()  # Get the ID without committing

            created_raw_images.append(raw_image_schema.dump(raw_image))

        # Commit all raw images
        db.session.commit()

        message = f'Successfully created {len(created_raw_images)} raw images'
        if skipped_count > 0:
            message += f' ({skipped_count} skipped due to duplicate URLs)'

        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'created': len(created_raw_images),
                'total': len(raw_images_data),
                'skipped': skipped_count,
                'raw_images': created_raw_images
            }
        }), 201

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

