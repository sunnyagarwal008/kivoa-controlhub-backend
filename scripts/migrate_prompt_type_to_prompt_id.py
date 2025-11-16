#!/usr/bin/env python
"""
Database migration script to replace prompt_type column with prompt_id in product_images table
This script:
1. Adds prompt_id column (foreign key to prompts.id)
2. Removes prompt_type column
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_prompt_type_to_prompt_id():
    """Replace prompt_type column with prompt_id in product_images table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if prompt_id column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='prompt_id'
            """))
            
            if result.fetchone():
                print("✓ Column 'prompt_id' already exists.")
                
                # Check if prompt_type still exists
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='product_images' AND column_name='prompt_type'
                """))
                
                if not result.fetchone():
                    print("✓ Column 'prompt_type' already removed. No migration needed.")
                    return
                else:
                    print("Removing 'prompt_type' column...")
                    db.session.execute(text("""
                        ALTER TABLE product_images 
                        DROP COLUMN prompt_type
                    """))
                    db.session.commit()
                    print("✓ Successfully removed 'prompt_type' column!")
                    return
            
            print("Starting migration: prompt_type -> prompt_id...")
            
            # Step 1: Add prompt_id column (nullable, foreign key to prompts.id)
            print("Step 1: Adding 'prompt_id' column...")
            db.session.execute(text("""
                ALTER TABLE product_images 
                ADD COLUMN prompt_id INTEGER
            """))
            db.session.commit()
            print("✓ Added 'prompt_id' column")
            
            # Step 2: Add foreign key constraint
            print("Step 2: Adding foreign key constraint...")
            db.session.execute(text("""
                ALTER TABLE product_images 
                ADD CONSTRAINT fk_product_images_prompt_id 
                FOREIGN KEY (prompt_id) REFERENCES prompts(id)
            """))
            db.session.commit()
            print("✓ Added foreign key constraint")
            
            # Step 3: Check if prompt_type column exists before dropping
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='prompt_type'
            """))
            
            if result.fetchone():
                print("Step 3: Removing 'prompt_type' column...")
                db.session.execute(text("""
                    ALTER TABLE product_images 
                    DROP COLUMN prompt_type
                """))
                db.session.commit()
                print("✓ Removed 'prompt_type' column")
            else:
                print("✓ Column 'prompt_type' does not exist, skipping removal")
            
            # Verify the changes
            print("\nVerifying migration...")
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='prompt_id'
            """))
            
            col_info = result.fetchone()
            if col_info:
                col_name, data_type, is_nullable = col_info
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"\nNew column details:")
                print(f"  • {col_name}: {data_type} ({nullable})")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe prompt_id column now stores a reference to the prompt used for AI image generation.")
            print("It is a foreign key to the prompts table.")
            print("Existing product images will have NULL prompt_id.")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_prompt_type_to_prompt_id()

