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
    mrp = db.Column(db.Numeric(10, 2), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False)
    gst = db.Column(db.Numeric(10, 2), nullable=False)
    price_code = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    in_stock = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with ProductImage
    product_images = db.relationship('ProductImage', backref='product', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Product {self.id} - {self.sku}>'

    def to_dict(self, include_category_details=False, include_images=False):
        """
        Convert product object to dictionary

        Args:
            include_category_details (bool): Include full category object
            include_images (bool): Include product images
        """
        result = {
            'id': self.id,
            'category_id': self.category_id,
            'category': self.category_ref.name if self.category_ref else None,
            'sku': self.sku,
            'sku_sequence_number': self.sku_sequence_number,
            'purchase_month': self.purchase_month,
            'raw_image': self.raw_image,
            'mrp': float(self.mrp),
            'price': float(self.price),
            'discount': float(self.discount),
            'gst': float(self.gst),
            'price_code': self.price_code,
            'status': self.status,
            'in_stock': self.in_stock,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

        # Include full category details if requested
        if include_category_details and self.category_ref:
            result['category_details'] = self.category_ref.to_dict()

        # Include product images if requested
        if include_images:
            result['images'] = [img.to_dict() for img in self.product_images]

        return result


class ProductImage(db.Model):
    """Product image model for storing enhanced product images"""

    __tablename__ = 'product_images'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ProductImage {self.id} - Product {self.product_id}>'

    def to_dict(self):
        """Convert product image object to dictionary"""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'image_url': self.image_url,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

