#!/usr/bin/env python
"""
Database migration script to add weight, dimensions, and size columns to products table
Run this script to add:
- weight INTEGER (in grams)
- dimensions_length INTEGER (in mm)
- dimensions_breadth INTEGER (in mm)
- dimensions_height INTEGER (in mm)
- size VARCHAR(50)
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_add_product_dimensions_and_size():
    """Add weight, dimensions, and size columns to products table"""
    app = create_app()
    
    with app.app_context():
        try:
            columns_to_add = {
                'weight': ('INTEGER', 'Weight in grams'),
                'dimensions_length': ('INTEGER', 'Length in mm'),
                'dimensions_breadth': ('INTEGER', 'Breadth in mm'),
                'dimensions_height': ('INTEGER', 'Height in mm'),
                'size': ('VARCHAR(50)', 'Size')
            }
            
            columns_added = []
            columns_existing = []
            
            for column_name, (data_type, description) in columns_to_add.items():
                # Check if the column already exists
                result = db.session.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='{column_name}'
                """))
                
                column_exists = result.fetchone() is not None
                
                if not column_exists:
                    print(f"Adding '{column_name}' column to products table...")
                    db.session.execute(text(f"""
                        ALTER TABLE products 
                        ADD COLUMN {column_name} {data_type}
                    """))
                    columns_added.append((column_name, description))
                    print(f"✓ Successfully added '{column_name}' column!")
                else:
                    columns_existing.append(column_name)
                    print(f"✓ Column '{column_name}' already exists.")
            
            if not columns_added and columns_existing:
                print("\n✓ All columns already exist. No migration needed.")
                return
            
            db.session.commit()
            
            # Verify the columns were added
            if columns_added:
                print("\nVerifying newly added columns...")
                
                for column_name, description in columns_added:
                    result = db.session.execute(text(f"""
                        SELECT column_name, data_type, character_maximum_length, is_nullable
                        FROM information_schema.columns 
                        WHERE table_name='products' AND column_name='{column_name}'
                    """))
                    
                    row = result.fetchone()
                    if row:
                        col_name, data_type, max_length, is_nullable = row
                        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                        if max_length:
                            print(f"  • {col_name}: {data_type}({max_length}) ({nullable}) - {description}")
                        else:
                            print(f"  • {col_name}: {data_type} ({nullable}) - {description}")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe following columns are now available for products:")
            print("  - weight: Integer (in grams)")
            print("  - dimensions_length: Integer (in mm)")
            print("  - dimensions_breadth: Integer (in mm)")
            print("  - dimensions_height: Integer (in mm)")
            print("  - size: String (max 50 characters)")
            print("\nUsage in API:")
            print("  POST /api/products/bulk")
            print("  PUT /api/products/<id>")
            print("  {")
            print('    "weight": 500,')
            print('    "dimensions_length": 100,')
            print('    "dimensions_breadth": 50,')
            print('    "dimensions_height": 30,')
            print('    "size": "Medium"')
            print("  }")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_product_dimensions_and_size()

