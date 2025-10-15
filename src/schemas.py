from marshmallow import Schema, fields, validate, validates, ValidationError


class ProductSchema(Schema):
    """Schema for product validation"""
    
    id = fields.Int(dump_only=True)
    category = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    raw_image = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    mrp = fields.Decimal(required=True, as_string=False, places=2)
    price = fields.Decimal(required=True, as_string=False, places=2)
    discount = fields.Decimal(required=True, as_string=False, places=2)
    gst = fields.Decimal(required=True, as_string=False, places=2)
    status = fields.Str(dump_only=True)
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


class PresignedUrlRequestSchema(Schema):
    """Schema for presigned URL request validation"""
    
    filename = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    content_type = fields.Str(required=True, validate=validate.OneOf([
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/gif',
        'image/webp'
    ]))


class PresignedUrlResponseSchema(Schema):
    """Schema for presigned URL response"""
    
    presigned_url = fields.Str(required=True)
    file_url = fields.Str(required=True)
    expires_in = fields.Int(required=True)

