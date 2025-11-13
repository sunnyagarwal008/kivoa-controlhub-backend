"""
Migration script to add Shopify export fields (title, description, handle) to products table
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def add_shopify_fields():
    """Add title, description, and handle columns to products table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('products')]
            
            columns_to_add = []
            if 'title' not in existing_columns:
                columns_to_add.append(('title', 'VARCHAR(255)'))
            if 'description' not in existing_columns:
                columns_to_add.append(('description', 'TEXT'))
            if 'handle' not in existing_columns:
                columns_to_add.append(('handle', 'VARCHAR(100)'))
            
            if not columns_to_add:
                print("All Shopify fields already exist in products table")
                return
            
            # Add columns
            for column_name, column_type in columns_to_add:
                print(f"Adding {column_name} column to products table...")
                db.session.execute(text(f'ALTER TABLE products ADD COLUMN {column_name} {column_type}'))
            
            db.session.commit()
            print(f"Successfully added {len(columns_to_add)} column(s) to products table")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error adding columns: {str(e)}")
            raise

if __name__ == '__main__':
    add_shopify_fields()

