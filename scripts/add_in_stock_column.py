#!/usr/bin/env python
"""
Database migration script to add in_stock column to products table
Run this script to add the in_stock boolean column with default value True
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_in_stock_column():
    """Add in_stock column to products table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='in_stock'
            """))
            
            if result.fetchone():
                print("✓ Column 'in_stock' already exists. No migration needed.")
                return
            
            print("Adding 'in_stock' column to products table...")
            
            # Add the in_stock column with default value True
            db.session.execute(text("""
                ALTER TABLE products 
                ADD COLUMN in_stock BOOLEAN NOT NULL DEFAULT TRUE
            """))
            
            db.session.commit()
            print("✓ Successfully added 'in_stock' column to products table!")
            
            # Verify the column was added
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='in_stock'
            """))
            
            col_name, data_type, is_nullable = result.fetchone()
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"\nColumn details:")
            print(f"  • {col_name}: {data_type} ({nullable}) DEFAULT TRUE")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nAll existing products will have in_stock=True by default.")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_in_stock_column()

