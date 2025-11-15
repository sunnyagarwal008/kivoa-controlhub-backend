from marshmallow import Schema, fields, validate, validates, ValidationError


class AddressSchema(Schema):
    """Schema for customer address validation"""
    
    address1 = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    city = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    province = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    country = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    zip = fields.Str(required=True, validate=validate.Length(min=1, max=20))


class PlaceOrderSchema(Schema):
    """Schema for place order request validation"""
    
    sku = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    quantity = fields.Int(required=True, validate=validate.Range(min=1))
    per_unit_price = fields.Decimal(required=True, as_string=False, places=2)
    shipping_charges = fields.Decimal(required=True, as_string=False, places=2)
    customer_name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    customer_phone = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    customer_address = fields.Nested(AddressSchema, required=True)
    
    @validates('per_unit_price')
    def validate_per_unit_price(self, value, **kwargs):
        if value <= 0:
            raise ValidationError('Per unit price must be greater than 0')
    
    @validates('shipping_charges')
    def validate_shipping_charges(self, value, **kwargs):
        if value < 0:
            raise ValidationError('Shipping charges cannot be negative')

