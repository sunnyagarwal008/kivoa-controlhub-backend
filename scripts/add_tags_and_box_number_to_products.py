#!/usr/bin/env python
"""
Database migration script to add tags and box_number columns to products table
Run this script to add the tags VARCHAR(500) and box_number INTEGER columns
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_tags_and_box_number():
    """Add tags and box_number columns to products table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the tags column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='tags'
            """))
            
            tags_exists = result.fetchone() is not None
            
            # Check if the box_number column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='box_number'
            """))
            
            box_number_exists = result.fetchone() is not None
            
            if tags_exists and box_number_exists:
                print("✓ Columns 'tags' and 'box_number' already exist. No migration needed.")
                return
            
            # Add the tags column if it doesn't exist
            if not tags_exists:
                print("Adding 'tags' column to products table...")
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD COLUMN tags VARCHAR(500)
                """))
                print("✓ Successfully added 'tags' column!")
            else:
                print("✓ Column 'tags' already exists.")
            
            # Add the box_number column if it doesn't exist
            if not box_number_exists:
                print("Adding 'box_number' column to products table...")
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD COLUMN box_number INTEGER
                """))
                print("✓ Successfully added 'box_number' column!")
            else:
                print("✓ Column 'box_number' already exists.")
            
            db.session.commit()
            
            # Verify the columns were added
            print("\nVerifying columns...")
            
            if not tags_exists:
                result = db.session.execute(text("""
                    SELECT column_name, data_type, character_maximum_length, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='tags'
                """))
                
                col_name, data_type, max_length, is_nullable = result.fetchone()
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"  • {col_name}: {data_type}({max_length}) ({nullable})")
            
            if not box_number_exists:
                result = db.session.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='box_number'
                """))
                
                col_name, data_type, is_nullable = result.fetchone()
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"  • {col_name}: {data_type} ({nullable})")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe tags and box_number columns are now available for products.")
            print("\nUsage:")
            print("  - tags: Comma-separated string (e.g., 'wireless,bluetooth,premium')")
            print("  - box_number: Integer value for box identification")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_tags_and_box_number()

