"""
Transformation Prompts Service

This service fetches prompts from the database.
Prompts are organized by category and type.
"""

from flask import current_app
from sqlalchemy.orm import joinedload
from src.models.prompt import Prompt
from src.models.product import Category


def get_prompts_by_category(category: str, prompt_type: str = None):
    """
    Get prompts by category and optionally by type from database

    Args:
        category: Category name ('necklace', 'ring', 'earring', 'default', etc.)
        prompt_type: Optional type filter (e.g., 'model_hand', 'satin', 'mirror' for rings)

    Returns:
        List of lists of prompt texts grouped by type for the specified category
        For backward compatibility with existing code that expects nested lists
    """
    try:
        # Look up category by name
        category_obj = Category.query.filter_by(name=category).first()
        if not category_obj:
            current_app.logger.warning(f"Category not found: {category}")
            return [[""]]  # Return empty prompt for backward compatibility

        # Query active prompts for the category
        query = Prompt.query.filter(
            Prompt.category_id == category_obj.id,
            Prompt.is_active == True
        )

        # If specific type requested, filter by type
        if prompt_type:
            query = query.filter(Prompt.type == prompt_type)

        prompts = query.all()

        if not prompts:
            current_app.logger.warning(f"No prompts found for category: {category}, type: {prompt_type}")
            return [[""]]  # Return empty prompt for backward compatibility

        # Group prompts by type for backward compatibility
        # This maintains the structure expected by existing code
        prompts_by_type = {}
        for prompt in prompts:
            type_key = prompt.type if prompt.type else 'default'
            if type_key not in prompts_by_type:
                prompts_by_type[type_key] = []
            prompts_by_type[type_key].append(prompt.text)

        # Return as list of lists
        return list(prompts_by_type.values())

    except Exception as e:
        current_app.logger.error(f"Error fetching prompts for category {category}: {str(e)}")
        # Return empty prompt as fallback
        return [[""]]


def get_all_prompts():
    """
    Get all active prompts from database
    
    Returns:
        List of all available prompt texts
    """
    try:
        prompts = Prompt.query.filter(Prompt.is_active == True).all()
        return [prompt.text for prompt in prompts]
    except Exception as e:
        current_app.logger.error(f"Error fetching all prompts: {str(e)}")
        return [""]


def get_available_categories():
    """
    Get list of available prompt categories from database

    Returns:
        List of unique category names
    """
    try:
        # Get categories that have prompts
        categories = Category.query.join(Prompt).distinct().all()
        return [category.name for category in categories]
    except Exception as e:
        current_app.logger.error(f"Error fetching categories: {str(e)}")
        return ['default']


def get_prompts_flat(category: str, prompt_type: str = None):
    """
    Get prompts as a flat list (new simplified interface)

    Args:
        category: Category name ('necklace', 'ring', 'earring', 'default', etc.)
        prompt_type: Optional type filter (e.g., 'model_hand', 'satin', 'mirror' for rings)

    Returns:
        List of prompt texts
    """
    try:
        # Look up category by name
        category_obj = Category.query.filter_by(name=category.lower()).first()
        if not category_obj:
            current_app.logger.warning(f"Category not found: {category}")
            return [""]

        query = Prompt.query.filter(
            Prompt.category_id == category_obj.id,
            Prompt.is_active == True
        )

        if prompt_type:
            query = query.filter(Prompt.type == prompt_type)

        prompts = query.all()
        return [prompt.text for prompt in prompts] if prompts else [""]

    except Exception as e:
        current_app.logger.error(f"Error fetching prompts: {str(e)}")
        return [""]

