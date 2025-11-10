#!/usr/bin/env python
"""
Database migration script to add priority column to product_images table
Run this script to add the priority integer column with default value 0
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_priority_column():
    """Add priority column to product_images table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='priority'
            """))
            
            if result.fetchone():
                print("✓ Column 'priority' already exists. No migration needed.")
                return
            
            print("Adding 'priority' column to product_images table...")
            
            # Add the priority column with default value 0
            db.session.execute(text("""
                ALTER TABLE product_images 
                ADD COLUMN priority INTEGER NOT NULL DEFAULT 0
            """))
            
            db.session.commit()
            print("✓ Successfully added 'priority' column to product_images table!")
            
            # Verify the column was added
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name='product_images' AND column_name='priority'
            """))
            
            col_name, data_type, is_nullable = result.fetchone()
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"\nColumn details:")
            print(f"  • {col_name}: {data_type} ({nullable}) DEFAULT 0")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nAll existing product images will have priority=0 by default.")
            print("Lower priority number = higher priority (0 is highest).")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_priority_column()

