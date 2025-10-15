#!/usr/bin/env python
"""
Database seeding script
Run this script to populate the database with sample data
"""

from src.app import create_app
from src.database import db
from src.models import Product
from decimal import Decimal

def seed_database():
    """Seed the database with sample products"""
    app = create_app()
    
    with app.app_context():
        # Check if data already exists
        if Product.query.first():
            print("Database already contains data. Skipping seed.")
            return
        
        print("Seeding database with sample products...")
        
        sample_products = [
            {
                'category': 'Electronics',
                'raw_image': 'https://example.com/images/laptop.jpg',
                'mrp': Decimal('1200.00'),
                'price': Decimal('999.00'),
                'discount': Decimal('201.00'),
                'gst': Decimal('18.00'),
                'status': 'pending'
            },
            {
                'category': 'Clothing',
                'raw_image': 'https://example.com/images/tshirt.jpg',
                'mrp': Decimal('500.00'),
                'price': Decimal('399.00'),
                'discount': Decimal('101.00'),
                'gst': Decimal('12.00'),
                'status': 'pending'
            },
            {
                'category': 'Books',
                'raw_image': 'https://example.com/images/book.jpg',
                'mrp': Decimal('300.00'),
                'price': Decimal('250.00'),
                'discount': Decimal('50.00'),
                'gst': Decimal('5.00'),
                'status': 'approved'
            },
            {
                'category': 'Home & Kitchen',
                'raw_image': 'https://example.com/images/blender.jpg',
                'mrp': Decimal('2500.00'),
                'price': Decimal('1999.00'),
                'discount': Decimal('501.00'),
                'gst': Decimal('18.00'),
                'status': 'pending'
            },
            {
                'category': 'Sports',
                'raw_image': 'https://example.com/images/football.jpg',
                'mrp': Decimal('800.00'),
                'price': Decimal('650.00'),
                'discount': Decimal('150.00'),
                'gst': Decimal('18.00'),
                'status': 'rejected'
            }
        ]
        
        for product_data in sample_products:
            product = Product(**product_data)
            db.session.add(product)
        
        db.session.commit()
        
        print(f"✓ Successfully seeded {len(sample_products)} products!")
        
        # Display seeded products
        print("\nSeeded products:")
        for product in Product.query.all():
            print(f"  - ID: {product.id}, Category: {product.category}, Status: {product.status}")

if __name__ == '__main__':
    seed_database()

