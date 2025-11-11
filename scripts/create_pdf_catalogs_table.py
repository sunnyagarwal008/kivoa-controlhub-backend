#!/usr/bin/env python
"""
Database migration script to create pdf_catalogs table
Run this script to add the pdf_catalogs table to your database
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models import PDFCatalog

def create_pdf_catalogs_table():
    """Create the pdf_catalogs table"""
    app = create_app()
    
    with app.app_context():
        print("Creating pdf_catalogs table...")
        db.create_all()
        print("✓ pdf_catalogs table created successfully!")
        
        # Print table information
        print("\nTable structure:")
        for table in db.metadata.sorted_tables:
            if table.name == 'pdf_catalogs':
                print(f"  Table: {table.name}")
                for column in table.columns:
                    print(f"    • {column.name}: {column.type}")

if __name__ == '__main__':
    create_pdf_catalogs_table()

