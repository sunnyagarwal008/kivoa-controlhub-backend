#!/usr/bin/env python
"""
Database migration script to add prompt_type column to product_images table
Run this script to add the prompt_type VARCHAR(100) column
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_prompt_type_column():
    """Add prompt_type column to product_images table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='prompt_type'
            """))
            
            if result.fetchone():
                print("✓ Column 'prompt_type' already exists. No migration needed.")
                return
            
            print("Adding 'prompt_type' column to product_images table...")
            
            # Add the prompt_type column (nullable)
            db.session.execute(text("""
                ALTER TABLE product_images 
                ADD COLUMN prompt_type VARCHAR(100)
            """))
            
            db.session.commit()
            print("✓ Successfully added 'prompt_type' column to product_images table!")
            
            # Verify the column was added
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='prompt_type'
            """))
            
            col_info = result.fetchone()
            if col_info:
                col_name, data_type, is_nullable, max_length = col_info
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"\nColumn details:")
                print(f"  • {col_name}: {data_type}({max_length}) ({nullable})")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe prompt_type column stores the type of prompt used for AI image generation.")
            print("Examples: 'model_hand', 'satin', 'mirror', etc.")
            print("Existing product images will have NULL prompt_type.")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_prompt_type_column()

