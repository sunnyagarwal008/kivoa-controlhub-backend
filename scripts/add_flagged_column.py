#!/usr/bin/env python
"""
Database migration script to add flagged column to products table
Run this script to add the flagged boolean column with default value False
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_flagged_column():
    """Add flagged column to products table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='flagged'
            """))
            
            if result.fetchone():
                print("✓ Column 'flagged' already exists. No migration needed.")
                return
            
            print("Adding 'flagged' column to products table...")
            
            # Add the flagged column with default value False
            db.session.execute(text("""
                ALTER TABLE products 
                ADD COLUMN flagged BOOLEAN NOT NULL DEFAULT FALSE
            """))
            
            db.session.commit()
            print("✓ Successfully added 'flagged' column to products table!")
            
            # Verify the column was added
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='flagged'
            """))
            
            col_name, data_type, is_nullable = result.fetchone()
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"\nColumn details:")
            print(f"  • {col_name}: {data_type} ({nullable}) DEFAULT FALSE")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nAll existing products will have flagged=False by default.")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_flagged_column()

