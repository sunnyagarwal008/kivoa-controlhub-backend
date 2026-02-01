#!/usr/bin/env python
"""
Database migration script to add is_white_background column to prompts and product_images tables
Run this script to add the is_white_background boolean column with default value False
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_is_white_background_columns():
    """Add is_white_background column to prompts and product_images tables"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("Starting migration: Adding is_white_background columns")
            print("=" * 60)
            
            # Migrate prompts table
            print("\n1. Checking prompts table...")
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='prompts' AND column_name='is_white_background'
            """))
            
            if result.fetchone():
                print("✓ Column 'is_white_background' already exists in prompts table.")
            else:
                print("Adding 'is_white_background' column to prompts table...")
                db.session.execute(text("""
                    ALTER TABLE prompts 
                    ADD COLUMN is_white_background BOOLEAN NOT NULL DEFAULT FALSE
                """))
                db.session.commit()
                print("✓ Successfully added 'is_white_background' column to prompts table!")
            
            # Migrate product_images table
            print("\n2. Checking product_images table...")
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='is_white_background'
            """))
            
            if result.fetchone():
                print("✓ Column 'is_white_background' already exists in product_images table.")
            else:
                print("Adding 'is_white_background' column to product_images table...")
                db.session.execute(text("""
                    ALTER TABLE product_images 
                    ADD COLUMN is_white_background BOOLEAN NOT NULL DEFAULT FALSE
                """))
                db.session.commit()
                print("✓ Successfully added 'is_white_background' column to product_images table!")
            
            # Verify the columns were added
            print("\n" + "=" * 60)
            print("Verifying migration...")
            print("=" * 60)
            
            # Verify prompts table
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name='prompts' AND column_name='is_white_background'
            """))
            
            row = result.fetchone()
            if row:
                col_name, data_type, is_nullable, col_default = row
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"\nPrompts table:")
                print(f"  • {col_name}: {data_type} ({nullable}) DEFAULT {col_default}")
            
            # Verify product_images table
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='is_white_background'
            """))
            
            row = result.fetchone()
            if row:
                col_name, data_type, is_nullable, col_default = row
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"\nProduct Images table:")
                print(f"  • {col_name}: {data_type} ({nullable}) DEFAULT {col_default}")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("=" * 60)
            print("\nAll existing records will have is_white_background=FALSE by default.")
            print("This field indicates whether the prompt/image uses a white background.")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_is_white_background_columns()
