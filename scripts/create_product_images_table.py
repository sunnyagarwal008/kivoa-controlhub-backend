#!/usr/bin/env python
"""
Database migration script to create product_images table
Run this script to add the product_images table to your database
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models import Product, ProductImage

def create_product_images_table():
    """Create the product_images table"""
    app = create_app()
    
    with app.app_context():
        print("Creating product_images table...")
        db.create_all()
        print("✓ product_images table created successfully!")
        
        # Print table information
        print("\nTable structure:")
        for table in db.metadata.sorted_tables:
            if table.name == 'product_images':
                print(f"  Table: {table.name}")
                for column in table.columns:
                    print(f"    • {column.name}: {column.type}")

if __name__ == '__main__':
    create_product_images_table()

