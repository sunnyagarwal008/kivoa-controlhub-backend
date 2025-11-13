from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from src.database import db
from src.models import RawImage
from src.schemas import RawImageSchema
from src.services.s3_service import s3_service

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
        current_app.logger.error(f"Error fetching raw images: {str(e)}", exc_info=True)
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
        db.session.rollback()
        current_app.logger.warning(f"Validation error in bulk create raw images: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk create raw images: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@raw_images_bp.route('/raw-images/bulk', methods=['DELETE'])
def bulk_delete_raw_images():
    """
    Bulk delete raw images and remove them from S3

    Request Body:
        {
            "ids": [1, 2, 3, 4, 5]
        }

    Response:
        {
            "success": true,
            "message": "Successfully deleted 5 raw images",
            "data": {
                "deleted": 5,
                "total": 5,
                "failed": 0,
                "failed_ids": []
            }
        }
    """
    try:
        request_data = request.get_json()

        if not request_data or 'ids' not in request_data:
            return jsonify({
                'success': False,
                'error': 'Missing "ids" array in request body'
            }), 400

        raw_image_ids = request_data['ids']

        if not isinstance(raw_image_ids, list):
            return jsonify({
                'success': False,
                'error': '"ids" must be an array'
            }), 400

        if len(raw_image_ids) == 0:
            return jsonify({
                'success': False,
                'error': '"ids" array cannot be empty'
            }), 400

        if len(raw_image_ids) > 1000:
            return jsonify({
                'success': False,
                'error': 'Maximum 1000 raw images allowed per bulk delete'
            }), 400

        # Validate all IDs are integers
        if not all(isinstance(id, int) for id in raw_image_ids):
            return jsonify({
                'success': False,
                'error': 'All IDs must be integers'
            }), 400

        # Fetch all raw images to delete
        raw_images = RawImage.query.filter(RawImage.id.in_(raw_image_ids)).all()

        if not raw_images:
            return jsonify({
                'success': False,
                'error': 'No raw images found with the provided IDs'
            }), 404

        deleted_count = 0
        failed_count = 0
        failed_ids = []

        for raw_image in raw_images:
            try:
                # Delete from S3 if the image_url is an S3 URL
                if raw_image.image_url:
                    try:
                        s3_service.delete_file(raw_image.image_url)
                    except Exception as s3_error:
                        # Log S3 deletion error but continue with database deletion
                        # This handles cases where the file might not exist in S3
                        pass

                # Delete from database
                db.session.delete(raw_image)
                deleted_count += 1

            except Exception as e:
                failed_count += 1
                failed_ids.append(raw_image.id)
                db.session.rollback()
                continue

        # Commit all deletions
        db.session.commit()

        message = f'Successfully deleted {deleted_count} raw images'
        if failed_count > 0:
            message += f' ({failed_count} failed)'

        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'deleted': deleted_count,
                'total': len(raw_image_ids),
                'failed': failed_count,
                'failed_ids': failed_ids
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk delete raw images: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

