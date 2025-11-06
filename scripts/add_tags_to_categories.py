#!/usr/bin/env python
"""
Database migration script to add tags column to categories table
Run this script to add the tags VARCHAR(500) column
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_tags_column():
    """Add tags column to categories table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='categories' AND column_name='tags'
            """))
            
            if result.fetchone():
                print("✓ Column 'tags' already exists. No migration needed.")
                return
            
            print("Adding 'tags' column to categories table...")
            
            # Add the tags column (nullable)
            db.session.execute(text("""
                ALTER TABLE categories 
                ADD COLUMN tags VARCHAR(500)
            """))
            
            db.session.commit()
            print("✓ Successfully added 'tags' column to categories table!")
            
            # Verify the column was added
            result = db.session.execute(text("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns 
                WHERE table_name='categories' AND column_name='tags'
            """))
            
            col_name, data_type, max_length, is_nullable = result.fetchone()
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"\nColumn details:")
            print(f"  • {col_name}: {data_type}({max_length}) ({nullable})")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe tags column is now available for categories.")
            print("Tags should be stored as comma-separated strings (e.g., 'tag1,tag2,tag3')")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_tags_column()

