#!/usr/bin/env python
"""
Database initialization script
Run this script to create all database tables
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models import Product

def init_database():
    """Initialize the database with all tables"""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully!")
        
        # Print table information
        print("\nCreated tables:")
        for table in db.metadata.sorted_tables:
            print(f"  - {table.name}")
            for column in table.columns:
                print(f"    • {column.name}: {column.type}")

if __name__ == '__main__':
    init_database()

