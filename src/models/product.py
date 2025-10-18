from datetime import datetime
from src.database import db


class Category(db.Model):
    """Category model for product categorization"""

    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    prefix = db.Column(db.String(10), nullable=False, unique=True)
    sku_sequence_number = db.Column(db.Integer, nullable=False, default=0)
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
            str: Generated SKU
        """
        self.sku_sequence_number += 1
        sequence = str(self.sku_sequence_number).zfill(4)
        return f"{self.prefix}-{sequence}-{purchase_month}"

    def to_dict(self):
        """Convert category object to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'prefix': self.prefix,
            'sku_sequence_number': self.sku_sequence_number,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Product(db.Model):
    """Product model for storing product information"""

    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    sku = db.Column(db.String(50), nullable=False, unique=True)
    purchase_month = db.Column(db.String(4), nullable=False)
    raw_image = db.Column(db.String(500), nullable=False)
    mrp = db.Column(db.Numeric(10, 2), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False)
    gst = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with ProductImage
    product_images = db.relationship('ProductImage', backref='product', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Product {self.id} - {self.sku}>'

    def to_dict(self):
        """Convert product object to dictionary"""
        return {
            'id': self.id,
            'category_id': self.category_id,
            'category': self.category_ref.name if self.category_ref else None,
            'sku': self.sku,
            'purchase_month': self.purchase_month,
            'raw_image': self.raw_image,
            'mrp': float(self.mrp),
            'price': float(self.price),
            'discount': float(self.discount),
            'gst': float(self.gst),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


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

