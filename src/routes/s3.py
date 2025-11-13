from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from src.schemas import PresignedUrlRequestSchema, PresignedUrlResponseSchema
from src.services import s3_service

s3_bp = Blueprint('s3', __name__)

presigned_url_request_schema = PresignedUrlRequestSchema()
presigned_url_response_schema = PresignedUrlResponseSchema()


@s3_bp.route('/presigned-url', methods=['POST'])
def generate_presigned_url():
    """
    Generate a presigned URL for uploading images to S3
    
    Request Body:
        {
            "filename": "product_image.jpg",
            "content_type": "image/jpeg"
        }
    
    Response:
        {
            "presigned_url": "https://...",
            "file_url": "https://...",
            "expires_in": 3600
        }
    """
    try:
        # Validate request data
        data = presigned_url_request_schema.load(request.get_json())
        
        # Generate presigned URL
        result = s3_service.generate_presigned_url(
            filename=data['filename'],
            content_type=data['content_type']
        )
        
        # Validate and return response
        response_data = presigned_url_response_schema.dump(result)
        
        return jsonify({
            'success': True,
            'data': response_data
        }), 200
        
    except ValidationError as e:
        current_app.logger.warning(f"Validation error generating presigned URL: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400

    except Exception as e:
        current_app.logger.error(f"Error generating presigned URL: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

