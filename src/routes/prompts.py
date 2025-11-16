from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from sqlalchemy.orm import joinedload
from src.database import db
from src.models.prompt import Prompt
from src.models.product import Category
from src.schemas.prompt import PromptSchema, PromptCreateUpdateSchema, PromptFilterSchema

prompts_bp = Blueprint('prompts', __name__)

prompt_schema = PromptSchema()
prompts_schema = PromptSchema(many=True)
prompt_create_update_schema = PromptCreateUpdateSchema()
prompt_filter_schema = PromptFilterSchema()


@prompts_bp.route('/prompts', methods=['GET'])
def get_prompts():
    """
    Get all prompts with optional filtering and sorting

    Query Parameters:
        - category: Filter by category name (e.g., 'necklace', 'ring', 'earring')
        - category_id: Filter by category ID
        - type: Filter by type (e.g., 'model_hand', 'satin', 'mirror')
        - is_active: Filter by active status (true/false)
        - tags: Filter by tags (comma-separated)
        - sortBy: Sort field (id, category_id, type, created_at) (default: created_at)
        - sortOrder: Sort order (asc, desc) (default: desc)

    Response:
        {
            "success": true,
            "data": [...],
            "total": 50
        }
    """
    try:
        # Build query with eager loading of category
        query = Prompt.query.options(joinedload(Prompt.category))

        # Apply filters
        category_name = request.args.get('category')
        if category_name:
            # Join with Category table to filter by name
            query = query.join(Prompt.category).filter(Category.name == category_name)

        category_id = request.args.get('category_id')
        if category_id:
            query = query.filter(Prompt.category_id == category_id)

        prompt_type = request.args.get('type')
        if prompt_type:
            query = query.filter(Prompt.type == prompt_type)

        is_active = request.args.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            query = query.filter(Prompt.is_active == is_active_bool)

        tags = request.args.get('tags')
        if tags:
            # Filter by tags (comma-separated)
            tag_list = [tag.strip() for tag in tags.split(',')]
            for tag in tag_list:
                query = query.filter(Prompt.tags.like(f'%{tag}%'))

        # Sorting
        sort_by = request.args.get('sortBy', 'created_at')
        sort_order = request.args.get('sortOrder', 'desc')

        valid_sort_fields = ['id', 'category_id', 'type', 'created_at', 'updated_at']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'

        if sort_order == 'asc':
            query = query.order_by(getattr(Prompt, sort_by).asc())
        else:
            query = query.order_by(getattr(Prompt, sort_by).desc())

        # Get all results
        prompts = query.all()

        return jsonify({
            'success': True,
            'data': [prompt.to_dict() for prompt in prompts],
            'total': len(prompts)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching prompts: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompts_bp.route('/prompts/<int:prompt_id>', methods=['GET'])
def get_prompt(prompt_id):
    """
    Get a single prompt by ID

    Response:
        {
            "success": true,
            "data": {
                "id": 1,
                "text": "...",
                "category_id": 1,
                "category": "necklace",
                "type": null,
                "tags": "fashion,luxury",
                "is_active": true,
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        prompt = Prompt.query.options(joinedload(Prompt.category)).get_or_404(prompt_id)

        return jsonify({
            'success': True,
            'data': prompt.to_dict(include_category_details=True)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching prompt {prompt_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404


@prompts_bp.route('/prompts', methods=['POST'])
def create_prompt():
    """
    Create a new prompt

    Request Body:
        {
            "text": "A high-resolution fashion photography...",
            "category": "necklace",  // category name (will be converted to category_id)
            "type": "model_hand",  // optional
            "tags": "fashion,luxury,editorial",  // optional
            "is_active": true  // optional, default: true
        }

    Response:
        {
            "success": true,
            "message": "Prompt created successfully",
            "data": {...}
        }
    """
    try:
        # Get request data and sanitize text field
        request_data = request.get_json()
        if 'text' in request_data and request_data['text']:
            request_data['text'] = request_data['text'].replace('\x00', '')

        data = prompt_create_update_schema.load(request_data)

        # Look up category by name
        category = Category.query.filter_by(name=data['category']).first()
        if not category:
            return jsonify({
                'success': False,
                'error': f'Category "{data["category"]}" not found'
            }), 404

        # Create new prompt
        prompt = Prompt(
            text=data['text'],
            category_id=category.id,
            type=data.get('type'),
            tags=data.get('tags'),
            is_active=data.get('is_active', True)
        )

        db.session.add(prompt)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Prompt created successfully',
            'data': prompt.to_dict()
        }), 201

    except ValidationError as e:
        current_app.logger.warning(f"Validation error creating prompt: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating prompt: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompts_bp.route('/prompts/<int:prompt_id>', methods=['PUT'])
def update_prompt(prompt_id):
    """
    Update an existing prompt

    Request Body (all fields optional):
        {
            "text": "Updated prompt text...",
            "category": "ring",  // category name (will be converted to category_id)
            "type": "satin",
            "tags": "updated,tags",
            "is_active": false
        }

    Response:
        {
            "success": true,
            "message": "Prompt updated successfully",
            "data": {...}
        }
    """
    try:
        prompt = Prompt.query.get_or_404(prompt_id)

        # Get request data and sanitize text field
        request_data = request.get_json()
        if 'text' in request_data and request_data['text']:
            request_data['text'] = request_data['text'].replace('\x00', '')

        current_app.logger.info(f"Updating prompt: {request_data}")
        data = prompt_create_update_schema.load(request_data, partial=True)

        # Update fields
        if 'text' in data:
            prompt.text = data['text']
        if 'category' in data:
            # Look up category by name
            category = Category.query.filter_by(name=data['category']).first()
            if not category:
                return jsonify({
                    'success': False,
                    'error': f'Category "{data["category"]}" not found'
                }), 404
            prompt.category_id = category.id
        if 'type' in data:
            prompt.type = data['type']
        if 'tags' in data:
            prompt.tags = data['tags']
        if 'is_active' in data:
            prompt.is_active = data['is_active']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Prompt updated successfully',
            'data': prompt.to_dict()
        }), 200

    except ValidationError as e:
        current_app.logger.warning(f"Validation error updating prompt: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating prompt {prompt_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompts_bp.route('/prompts/<int:prompt_id>', methods=['DELETE'])
def delete_prompt(prompt_id):
    """
    Delete a prompt

    Response:
        {
            "success": true,
            "message": "Prompt deleted successfully"
        }
    """
    try:
        prompt = Prompt.query.get_or_404(prompt_id)

        db.session.delete(prompt)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Prompt deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting prompt {prompt_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompts_bp.route('/prompts/<int:prompt_id>/set-default', methods=['POST'])
def set_default_prompt(prompt_id):
    """
    Set a prompt as the default for its category
    Only one prompt can be default per category

    Response:
        {
            "success": true,
            "message": "Prompt set as default for category 'necklace'",
            "data": {...}
        }
    """
    try:
        prompt = Prompt.query.get_or_404(prompt_id)

        # Unset any existing default prompt for this category
        Prompt.query.filter(
            Prompt.category_id == prompt.category_id,
            Prompt.is_default == True,
            Prompt.id != prompt_id
        ).update({'is_default': False})

        # Set this prompt as default
        prompt.is_default = True

        db.session.commit()

        category_name = prompt.category.name if prompt.category else 'Unknown'

        return jsonify({
            'success': True,
            'message': f'Prompt set as default for category \'{category_name}\'',
            'data': prompt.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error setting prompt {prompt_id} as default: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompts_bp.route('/prompts/<int:prompt_id>/unset-default', methods=['POST'])
def unset_default_prompt(prompt_id):
    """
    Unset a prompt as the default for its category

    Response:
        {
            "success": true,
            "message": "Prompt unset as default",
            "data": {...}
        }
    """
    try:
        prompt = Prompt.query.get_or_404(prompt_id)

        # Unset this prompt as default
        prompt.is_default = False

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Prompt unset as default',
            'data': prompt.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unsetting prompt {prompt_id} as default: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompts_bp.route('/prompts/bulk', methods=['POST'])
def bulk_create_prompts():
    """
    Bulk create prompts

    Request Body:
        {
            "prompts": [
                {
                    "text": "Prompt 1...",
                    "category": "necklace",  // category name
                    "type": null,
                    "tags": "tag1,tag2"
                },
                ...
            ]
        }

    Response:
        {
            "success": true,
            "message": "Successfully created 10 prompts",
            "data": {
                "created": 10,
                "total": 10
            }
        }
    """
    try:
        request_data = request.get_json()

        if not request_data or 'prompts' not in request_data:
            return jsonify({
                'success': False,
                'error': 'Missing "prompts" array in request body'
            }), 400

        prompts_data = request_data['prompts']

        if not isinstance(prompts_data, list):
            return jsonify({
                'success': False,
                'error': '"prompts" must be an array'
            }), 400

        if len(prompts_data) == 0:
            return jsonify({
                'success': False,
                'error': '"prompts" array cannot be empty'
            }), 400

        if len(prompts_data) > 1000:
            return jsonify({
                'success': False,
                'error': 'Maximum 1000 prompts allowed per bulk upload'
            }), 400

        # Pre-load all categories for efficiency
        categories = {cat.name: cat.id for cat in Category.query.all()}

        created_prompts = []

        for index, prompt_data in enumerate(prompts_data):
            # Sanitize text field
            if 'text' in prompt_data and prompt_data['text']:
                prompt_data['text'] = prompt_data['text'].replace('\x00', '')

            # Validate prompt data
            validated_data = prompt_create_update_schema.load(prompt_data)

            # Look up category by name
            category_name = validated_data['category']
            if category_name not in categories:
                return jsonify({
                    'success': False,
                    'error': f'Category "{category_name}" not found at index {index}'
                }), 404

            # Create new prompt
            prompt = Prompt(
                text=validated_data['text'],
                category_id=categories[category_name],
                type=validated_data.get('type'),
                tags=validated_data.get('tags'),
                is_active=validated_data.get('is_active', True)
            )

            db.session.add(prompt)
            db.session.flush()  # Get the ID without committing

            created_prompts.append(prompt.to_dict())

        # Commit all prompts
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully created {len(created_prompts)} prompts',
            'data': {
                'created': len(created_prompts),
                'total': len(prompts_data),
                'prompts': created_prompts
            }
        }), 201

    except ValidationError as e:
        db.session.rollback()
        current_app.logger.warning(f"Validation error in bulk create: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk create prompts: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

