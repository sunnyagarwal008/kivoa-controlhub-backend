from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from src.database import db
from src.models import Category, Product
from src.schemas import CategoryCreateUpdateSchema

categories_bp = Blueprint('categories', __name__)

category_create_update_schema = CategoryCreateUpdateSchema()


@categories_bp.route('/categories', methods=['GET'])
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
                    "tags": "tag1,tag2,tag3",
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
        current_app.logger.error(f"Error fetching categories: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/categories', methods=['POST'])
def create_category():
    """
    Create a new category

    Request Body:
        {
            "name": "Electronics",
            "prefix": "ELEC",
            "tags": "tag1,tag2,tag3"  // optional, comma-separated strings
        }

    Response:
        {
            "success": true,
            "message": "Category created successfully",
            "data": {
                "id": 1,
                "name": "Electronics",
                "prefix": "ELEC",
                "sku_sequence_number": 0,
                "tags": "tag1,tag2,tag3",
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        data = category_create_update_schema.load(request.get_json())

        # Check if category with same name already exists
        existing_category = Category.query.filter_by(name=data['name']).first()
        if existing_category:
            return jsonify({
                'success': False,
                'error': f'Category with name "{data["name"]}" already exists'
            }), 400

        # Check if category with same prefix already exists
        existing_prefix = Category.query.filter_by(prefix=data['prefix']).first()
        if existing_prefix:
            return jsonify({
                'success': False,
                'error': f'Category with prefix "{data["prefix"]}" already exists'
            }), 400

        # Create new category
        category = Category(
            name=data['name'],
            prefix=data['prefix'],
            tags=data.get('tags')
        )

        db.session.add(category)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Category created successfully',
            'data': category.to_dict()
        }), 201

    except ValidationError as e:
        current_app.logger.warning(f"Validation error creating category: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating category: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """
    Update an existing category

    Request Body:
        {
            "name": "Electronics",  // optional
            "prefix": "ELEC",  // optional
            "tags": "tag1,tag2,tag3",  // optional, comma-separated strings
            "sku_sequence_number": 10  // optional, must be >= 0
        }

    Response:
        {
            "success": true,
            "message": "Category updated successfully",
            "data": {
                "id": 1,
                "name": "Electronics",
                "prefix": "ELEC",
                "sku_sequence_number": 10,
                "tags": "tag1,tag2,tag3",
                "created_at": "...",
                "updated_at": "..."
            }
        }
    """
    try:
        category = Category.query.get_or_404(category_id)

        # Validate request data (partial update allowed)
        data = category_create_update_schema.load(request.get_json(), partial=True)

        # Check if name is being updated and if it conflicts with existing category
        if 'name' in data and data['name'] != category.name:
            existing_category = Category.query.filter_by(name=data['name']).first()
            if existing_category:
                return jsonify({
                    'success': False,
                    'error': f'Category with name "{data["name"]}" already exists'
                }), 400

        # Check if prefix is being updated and if it conflicts with existing category
        if 'prefix' in data and data['prefix'] != category.prefix:
            existing_prefix = Category.query.filter_by(prefix=data['prefix']).first()
            if existing_prefix:
                return jsonify({
                    'success': False,
                    'error': f'Category with prefix "{data["prefix"]}" already exists'
                }), 400

        # Update category fields
        for key, value in data.items():
            setattr(category, key, value)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Category updated successfully',
            'data': category.to_dict()
        }), 200

    except ValidationError as e:
        current_app.logger.warning(f"Validation error updating category {category_id}: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating category {category_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """
    Delete a category

    Response:
        {
            "success": true,
            "message": "Category deleted successfully"
        }

    Note: Cannot delete a category that has associated products
    """
    try:
        category = Category.query.get_or_404(category_id)

        # Check if category has associated products
        product_count = Product.query.filter_by(category_id=category_id).count()
        if product_count > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete category. It has {product_count} associated product(s). Please delete or reassign the products first.'
            }), 400

        db.session.delete(category)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Category deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting category {category_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

