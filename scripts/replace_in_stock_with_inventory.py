#!/usr/bin/env python
"""
Database migration script to replace in_stock column with inventory column
This script:
1. Adds the inventory column (integer, default=1)
2. Migrates data: in_stock=True -> inventory=1, in_stock=False -> inventory=0
3. Drops the in_stock column
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_replace_in_stock_with_inventory():
    """Replace in_stock boolean column with inventory integer column"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if inventory column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='inventory'
            """))
            
            if result.fetchone():
                print("✓ Column 'inventory' already exists.")
                
                # Check if in_stock still exists
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='in_stock'
                """))
                
                if not result.fetchone():
                    print("✓ Column 'in_stock' has already been removed. Migration already completed.")
                    return
                else:
                    print("⚠ Both 'inventory' and 'in_stock' columns exist. Completing migration...")
            else:
                # Check if in_stock column exists
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='in_stock'
                """))
                
                if not result.fetchone():
                    print("✗ Column 'in_stock' does not exist. Cannot perform migration.")
                    return
                
                print("Step 1: Adding 'inventory' column to products table...")
                
                # Add the inventory column with default value 1
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD COLUMN inventory INTEGER NOT NULL DEFAULT 1
                """))
                
                db.session.commit()
                print("✓ Successfully added 'inventory' column!")
            
            print("\nStep 2: Migrating data from 'in_stock' to 'inventory'...")
            
            # Migrate data: in_stock=True -> inventory=1, in_stock=False -> inventory=0
            db.session.execute(text("""
                UPDATE products 
                SET inventory = CASE 
                    WHEN in_stock = TRUE THEN 1 
                    ELSE 0 
                END
            """))
            
            db.session.commit()
            print("✓ Successfully migrated data!")
            
            # Get count of products by inventory status
            result = db.session.execute(text("""
                SELECT 
                    COUNT(*) FILTER (WHERE inventory > 0) as in_stock_count,
                    COUNT(*) FILTER (WHERE inventory = 0) as out_of_stock_count,
                    COUNT(*) as total_count
                FROM products
            """))
            
            in_stock_count, out_of_stock_count, total_count = result.fetchone()
            print(f"  • Total products: {total_count}")
            print(f"  • In stock (inventory > 0): {in_stock_count}")
            print(f"  • Out of stock (inventory = 0): {out_of_stock_count}")
            
            print("\nStep 3: Dropping 'in_stock' column...")
            
            # Drop the in_stock column
            db.session.execute(text("""
                ALTER TABLE products 
                DROP COLUMN in_stock
            """))
            
            db.session.commit()
            print("✓ Successfully dropped 'in_stock' column!")
            
            # Verify the final state
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='inventory'
            """))
            
            col_name, data_type, is_nullable, col_default = result.fetchone()
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"\nFinal column details:")
            print(f"  • {col_name}: {data_type} ({nullable}) DEFAULT {col_default}")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe 'in_stock' column has been replaced with 'inventory'.")
            print("Products with in_stock=True now have inventory=1")
            print("Products with in_stock=False now have inventory=0")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_replace_in_stock_with_inventory()

