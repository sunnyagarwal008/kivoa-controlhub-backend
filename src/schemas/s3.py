from marshmallow import Schema, fields, validate


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

