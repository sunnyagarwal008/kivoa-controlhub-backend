#!/usr/bin/env python
"""
Database migration script to add is_default column to prompts table
This script:
1. Adds is_default BOOLEAN column (default: false)
2. Ensures only one prompt per category can be marked as default
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def add_is_default_column():
    """Add is_default column to prompts table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if is_default column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='prompts' AND column_name='is_default'
            """))
            
            if result.fetchone():
                print("✓ Column 'is_default' already exists. No migration needed.")
                return
            
            print("Starting migration: Adding 'is_default' column to prompts table...")
            
            # Step 1: Add is_default column (default: false)
            print("Step 1: Adding 'is_default' column...")
            db.session.execute(text("""
                ALTER TABLE prompts 
                ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT false
            """))
            db.session.commit()
            print("✓ Added 'is_default' column")
            
            # Verify the changes
            print("\nVerifying migration...")
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name='prompts' AND column_name='is_default'
            """))
            
            col_info = result.fetchone()
            if col_info:
                col_name, data_type, is_nullable, col_default = col_info
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"\nNew column details:")
                print(f"  • {col_name}: {data_type} ({nullable})")
                print(f"  • Default: {col_default}")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe is_default column allows marking one prompt as default per category.")
            print("Use the API endpoint to set a prompt as default for its category.")
            print("=" * 60 + "\n")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    add_is_default_column()

