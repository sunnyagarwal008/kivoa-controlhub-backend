#!/usr/bin/env python
"""
Database migration script to create raw_images table
Run this script to create the raw_images table with id and image_url (unique) columns
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db

def create_raw_images_table():
    """Create the raw_images table"""
    app = create_app()
    
    with app.app_context():
        print("Creating raw_images table...")
        db.create_all()
        print("✓ raw_images table created successfully!")
        
        # Print table information
        print("\nTable structure:")
        for table in db.metadata.sorted_tables:
            if table.name == 'raw_images':
                print(f"  Table: {table.name}")
                for column in table.columns:
                    print(f"    • {column.name}: {column.type}")

if __name__ == '__main__':
    create_raw_images_table()

