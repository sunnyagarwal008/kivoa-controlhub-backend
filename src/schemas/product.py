from marshmallow import Schema, fields, validate, validates, ValidationError, EXCLUDE, post_load
import re


class CategorySchema(Schema):
    """Schema for category details"""

    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)
    prefix = fields.Str(dump_only=True)
    sku_sequence_number = fields.Int(dump_only=True)
    tags = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CategoryCreateUpdateSchema(Schema):
    """Schema for category create/update operations"""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    prefix = fields.Str(required=True, validate=validate.Length(min=1, max=10))
    tags = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    sku_sequence_number = fields.Int(required=False, validate=validate.Range(min=0))

    @validates('prefix')
    def validate_prefix(self, value, **kwargs):
        """Validate prefix contains only alphanumeric characters and no spaces"""
        if not value.replace('-', '').replace('_', '').isalnum():
            raise ValidationError('Prefix must contain only alphanumeric characters, hyphens, and underscores')
        if ' ' in value:
            raise ValidationError('Prefix cannot contain spaces')


class ProductImageSchema(Schema):
    """Schema for product image validation"""

    id = fields.Int(dump_only=True)
    product_id = fields.Int(required=True)
    image_url = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    status = fields.Str(dump_only=True)
    priority = fields.Int(required=False, load_default=0)
    prompt_id = fields.Int(required=False, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ProductSchema(Schema):
    """Schema for product validation"""

    class Meta:
        unknown = EXCLUDE  # Ignore unknown fields during deserialization

    id = fields.Int(dump_only=True)
    category_id = fields.Int(dump_only=True)  # Computed from category name
    category = fields.Str(required=True, validate=validate.Length(min=1, max=100))  # Input field
    category_details = fields.Nested(CategorySchema, dump_only=True)  # Full category object
    sku = fields.Str(dump_only=True)  # Auto-generated
    sku_sequence_number = fields.Int(dump_only=True)  # Auto-generated from category sequence
    purchase_month = fields.Str(required=True, validate=validate.Length(equal=4))
    raw_image = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    is_raw_image = fields.Bool(required=False, load_default=True)  # Flag to indicate if raw_image needs AI processing
    prompt_id = fields.Int(required=False, allow_none=True)  # Optional prompt ID for AI image generation
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    description = fields.Str(required=False, allow_none=True)
    handle = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    mrp = fields.Decimal(required=True, as_string=False, places=2)
    price = fields.Decimal(required=True, as_string=False, places=2)
    discount = fields.Decimal(required=True, as_string=False, places=2)
    gst = fields.Decimal(required=True, as_string=False, places=2)
    price_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    tags = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    box_number = fields.Int(required=False, allow_none=True)
    weight = fields.Int(required=False, allow_none=True)
    # Accept both 'length' and 'dimensions_length' as input field names
    length = fields.Int(required=False, allow_none=True, load_only=True)
    dimensions_length = fields.Int(required=False, allow_none=True)
    # Accept both 'breadth' and 'dimensions_breadth' as input field names
    breadth = fields.Int(required=False, allow_none=True, load_only=True)
    dimensions_breadth = fields.Int(required=False, allow_none=True)
    # Accept both 'height' and 'dimensions_height' as input field names
    height = fields.Int(required=False, allow_none=True, load_only=True)
    dimensions_height = fields.Int(required=False, allow_none=True)
    dimensions = fields.Dict(dump_only=True)
    size = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    status = fields.Str(dump_only=True)
    in_stock = fields.Bool(dump_only=True)
    flagged = fields.Bool(dump_only=True)
    images = fields.Nested(ProductImageSchema, many=True, dump_only=True)  # Product images
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    
    @validates('mrp')
    def validate_mrp(self, value, **kwargs):
        if value <= 0:
            raise ValidationError('MRP must be greater than 0')

    @validates('price')
    def validate_price(self, value, **kwargs):
        if value <= 0:
            raise ValidationError('Price must be greater than 0')

    @validates('discount')
    def validate_discount(self, value, **kwargs):
        if value < 0:
            raise ValidationError('Discount cannot be negative')

    @validates('gst')
    def validate_gst(self, value, **kwargs):
        if value < 0:
            raise ValidationError('GST cannot be negative')

    @validates('purchase_month')
    def validate_purchase_month(self, value, **kwargs):
        """Validate purchase_month is in MMYY format"""
        if not re.match(r'^(0[1-9]|1[0-2])\d{2}$', value):
            raise ValidationError('purchase_month must be in MMYY format (e.g., 0124 for January 2024)')

    @validates('weight')
    def validate_weight(self, value, **kwargs):
        """Validate weight is positive"""
        if value is not None and value <= 0:
            raise ValidationError('Weight must be greater than 0')

    @validates('length')
    def validate_length(self, value, **kwargs):
        """Validate length is positive"""
        if value is not None and value <= 0:
            raise ValidationError('Length must be greater than 0')

    @validates('dimensions_length')
    def validate_dimensions_length(self, value, **kwargs):
        """Validate dimensions_length is positive"""
        if value is not None and value <= 0:
            raise ValidationError('Dimensions length must be greater than 0')

    @validates('breadth')
    def validate_breadth(self, value, **kwargs):
        """Validate breadth is positive"""
        if value is not None and value <= 0:
            raise ValidationError('Breadth must be greater than 0')

    @validates('dimensions_breadth')
    def validate_dimensions_breadth(self, value, **kwargs):
        """Validate dimensions_breadth is positive"""
        if value is not None and value <= 0:
            raise ValidationError('Dimensions breadth must be greater than 0')

    @validates('height')
    def validate_height(self, value, **kwargs):
        """Validate height is positive"""
        if value is not None and value <= 0:
            raise ValidationError('Height must be greater than 0')

    @validates('dimensions_height')
    def validate_dimensions_height(self, value, **kwargs):
        """Validate dimensions_height is positive"""
        if value is not None and value <= 0:
            raise ValidationError('Dimensions height must be greater than 0')

    @post_load
    def map_dimension_fields(self, data, **kwargs):
        """Map short field names (length, breadth, height) to full field names (dimensions_length, etc.)"""
        # Map length -> dimensions_length if provided
        if 'length' in data and data['length'] is not None:
            data['dimensions_length'] = data.pop('length')

        # Map breadth -> dimensions_breadth if provided
        if 'breadth' in data and data['breadth'] is not None:
            data['dimensions_breadth'] = data.pop('breadth')

        # Map height -> dimensions_height if provided
        if 'height' in data and data['height'] is not None:
            data['dimensions_height'] = data.pop('height')

        return data


class RawImageSchema(Schema):
    """Schema for raw image validation"""

    id = fields.Int(dump_only=True)
    image_url = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class PDFCatalogSchema(Schema):
    """Schema for PDF catalog validation"""

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    s3_url = fields.Str(dump_only=True)
    filter_json = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

