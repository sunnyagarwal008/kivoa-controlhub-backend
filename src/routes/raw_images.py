from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from src.database import db
from src.models import RawImage
from src.schemas import RawImageSchema

raw_images_bp = Blueprint('raw_images', __name__)

raw_image_schema = RawImageSchema()
raw_images_schema = RawImageSchema(many=True)


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

