from datetime import datetime
from src.database import db


class Category(db.Model):
    """Category model for product categorization"""

    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    prefix = db.Column(db.String(10), nullable=False, unique=True)
    sku_sequence_number = db.Column(db.Integer, nullable=False, default=0)
    tags = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with Product
    products = db.relationship('Product', backref='category_ref', lazy=True)

    def __repr__(self):
        return f'<Category {self.id} - {self.name}>'

    def generate_sku(self, purchase_month):
        """
        Generate SKU for a product in format: <prefix>-<sequence>-<purchase_month>
        Example: ELEC-0001-0124 (Electronics, sequence 1, January 2024)

        Args:
            purchase_month (str): Purchase month in MMYY format (e.g., '0124' for January 2024)

        Returns:
            tuple: (sku, sequence_number) - Generated SKU and the sequence number
        """
        self.sku_sequence_number += 1
        sequence = str(self.sku_sequence_number).zfill(4)
        sku = f"{self.prefix}-{sequence}-{purchase_month}"
        return sku, self.sku_sequence_number

    def to_dict(self):
        """Convert category object to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'prefix': self.prefix,
            'sku_sequence_number': self.sku_sequence_number,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Product(db.Model):
    """Product model for storing product information"""

    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    sku = db.Column(db.String(50), nullable=False, unique=True)
    sku_sequence_number = db.Column(db.Integer, nullable=False)
    purchase_month = db.Column(db.String(4), nullable=False)
    raw_image = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    handle = db.Column(db.String(255), nullable=True)
    mrp = db.Column(db.Numeric(10, 2), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False)
    gst = db.Column(db.Numeric(10, 2), nullable=False)
    price_code = db.Column(db.String(20), nullable=True)
    tags = db.Column(db.String(500), nullable=True)
    box_number = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Integer, nullable=True)
    dimensions_length = db.Column(db.Integer, nullable=True)
    dimensions_breadth = db.Column(db.Integer, nullable=True)
    dimensions_height = db.Column(db.Integer, nullable=True)
    size = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    inventory = db.Column(db.Integer, nullable=False, default=1)
    flagged = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with ProductImage
    product_images = db.relationship('ProductImage', backref='product', lazy=True, cascade='all, delete-orphan')

    @property
    def in_stock(self):
        """Computed property for backward compatibility - returns True if inventory > 0"""
        return self.inventory > 0

    def __repr__(self):
        return f'<Product {self.id} - {self.sku}>'

    def to_dict(self, include_category_details=False, include_images=False, exclude_fields=None):
        """
        Convert product object to dictionary

        Args:
            include_category_details (bool): Include full category object
            include_images (bool): Include product images
            exclude_fields (list): List of field names to exclude from the result
        """
        result = {
            'id': self.id,
            'category_id': self.category_id,
            'category': self.category_ref.name if self.category_ref else None,
            'sku': self.sku,
            'sku_sequence_number': self.sku_sequence_number,
            'purchase_month': self.purchase_month,
            'raw_image': self.raw_image,
            'title': self.title,
            'description': self.description,
            'handle': self.handle,
            'mrp': float(self.mrp),
            'price': float(self.price),
            'discount': float(self.discount),
            'gst': float(self.gst),
            'price_code': self.price_code,
            'tags': self.tags,
            'box_number': self.box_number,
            'weight': self.weight,
            'dimensions': {
                'length': self.dimensions_length,
                'breadth': self.dimensions_breadth,
                'height': self.dimensions_height
            } if any([self.dimensions_length, self.dimensions_breadth, self.dimensions_height]) else None,
            'size': self.size,
            'status': self.status,
            'in_stock': self.in_stock,
            'flagged': self.flagged,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

        # Remove excluded fields if specified
        if exclude_fields:
            for field in exclude_fields:
                result.pop(field, None)

        # Include full category details if requested
        if include_category_details and self.category_ref:
            result['category_details'] = self.category_ref.to_dict()

        # Include product images if requested, sorted by priority (lower number = higher priority)
        if include_images:
            sorted_images = sorted(self.product_images, key=lambda img: img.priority)
            result['images'] = [img.to_dict() for img in sorted_images]

        return result


class ProductImage(db.Model):
    """Product image model for storing enhanced product images"""

    __tablename__ = 'product_images'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected
    priority = db.Column(db.Integer, nullable=False, default=0)  # Lower number = higher priority
    prompt_id = db.Column(db.Integer, db.ForeignKey('prompts.id'), nullable=True)  # Reference to the prompt used for AI generation
    is_white_background = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with Prompt
    prompt = db.relationship('Prompt', backref='product_images', lazy=True)

    def __repr__(self):
        return f'<ProductImage {self.id} - Product {self.product_id}>'

    def to_dict(self):
        """Convert product image object to dictionary"""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'image_url': self.image_url,
            'status': self.status,
            'priority': self.priority,
            'prompt_id': self.prompt_id,
            'is_white_background': self.is_white_background,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class RawImage(db.Model):
    """Raw image model for storing raw image URLs"""

    __tablename__ = 'raw_images'

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<RawImage {self.id} - {self.image_url}>'

    def to_dict(self):
        """Convert raw image object to dictionary"""
        return {
            'id': self.id,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class PDFCatalog(db.Model):
    """PDF Catalog model for storing generated product catalogs"""

    __tablename__ = 'pdf_catalogs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    s3_url = db.Column(db.String(500), nullable=False)
    filter_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PDFCatalog {self.id} - {self.name}>'

    def to_dict(self):
        """Convert PDF catalog object to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            's3_url': self.s3_url,
            'filter_json': self.filter_json,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

