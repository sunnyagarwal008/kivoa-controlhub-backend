from marshmallow import Schema, fields, validate, validates, ValidationError, EXCLUDE
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
    mrp = fields.Decimal(required=True, as_string=False, places=2)
    price = fields.Decimal(required=True, as_string=False, places=2)
    discount = fields.Decimal(required=True, as_string=False, places=2)
    gst = fields.Decimal(required=True, as_string=False, places=2)
    price_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    tags = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    box_number = fields.Int(required=False, allow_none=True)
    status = fields.Str(dump_only=True)
    in_stock = fields.Bool(dump_only=True)
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


class RawImageSchema(Schema):
    """Schema for raw image validation"""

    id = fields.Int(dump_only=True)
    image_url = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

