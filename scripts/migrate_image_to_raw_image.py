#!/usr/bin/env python
"""
Database migration script to rename 'image' column to 'raw_image'
Run this script to update existing database schema
"""

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_column():
    """Rename image column to raw_image in products table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='image'
            """))
            
            if result.fetchone():
                print("Found 'image' column. Renaming to 'raw_image'...")
                
                # Rename the column
                db.session.execute(text("""
                    ALTER TABLE products 
                    RENAME COLUMN image TO raw_image
                """))
                
                db.session.commit()
                print("✓ Successfully renamed 'image' column to 'raw_image'!")
            else:
                # Check if raw_image already exists
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='raw_image'
                """))
                
                if result.fetchone():
                    print("✓ Column 'raw_image' already exists. No migration needed.")
                else:
                    print("⚠ Neither 'image' nor 'raw_image' column found. Please check your database.")
                    
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_column()

