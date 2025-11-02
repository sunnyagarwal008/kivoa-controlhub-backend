#!/usr/bin/env python
"""
Database migration script to add price_code column to products table
Run this script to add the price_code VARCHAR(20) column
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_price_code_column():
    """Add price_code column to products table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='price_code'
            """))
            
            if result.fetchone():
                print("✓ Column 'price_code' already exists. No migration needed.")
                return
            
            print("Adding 'price_code' column to products table...")
            
            # Add the price_code column (nullable)
            db.session.execute(text("""
                ALTER TABLE products 
                ADD COLUMN price_code VARCHAR(20)
            """))
            
            db.session.commit()
            print("✓ Successfully added 'price_code' column to products table!")
            
            # Verify the column was added
            result = db.session.execute(text("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='price_code'
            """))
            
            col_name, data_type, max_length, is_nullable = result.fetchone()
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"\nColumn details:")
            print(f"  • {col_name}: {data_type}({max_length}) ({nullable})")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe price_code column is now available for products.")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_price_code_column()

