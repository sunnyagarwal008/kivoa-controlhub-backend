from marshmallow import Schema, fields, validate
from src.schemas.product import CategorySchema


class PromptSchema(Schema):
    """Schema for Prompt model serialization"""

    id = fields.Int(dump_only=True)
    text = fields.Str(required=True, validate=validate.Length(min=1))
    category_id = fields.Int(dump_only=True)
    category = fields.Str(dump_only=True)  # Category name for display
    category_details = fields.Nested(CategorySchema, dump_only=True)  # Full category object (optional)
    type = fields.Str(allow_none=True, validate=validate.Length(max=100))
    tags = fields.Str(allow_none=True, validate=validate.Length(max=500))
    is_active = fields.Bool(load_default=True)
    is_default = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class PromptCreateUpdateSchema(Schema):
    """Schema for creating/updating prompts"""

    text = fields.Str(required=True, validate=validate.Length(min=1))
    category = fields.Str(required=True, validate=validate.Length(min=1, max=100))  # Category name (will be converted to category_id)
    type = fields.Str(allow_none=True, validate=validate.Length(max=100))
    tags = fields.Str(allow_none=True, validate=validate.Length(max=500))
    is_active = fields.Bool(load_default=True)


class PromptFilterSchema(Schema):
    """Schema for filtering prompts"""

    category = fields.Str(allow_none=True)  # Category name for filtering
    category_id = fields.Int(allow_none=True)  # Or filter by category_id directly
    type = fields.Str(allow_none=True)
    is_active = fields.Bool(allow_none=True)
    tags = fields.Str(allow_none=True)  # Comma-separated tags to filter by

