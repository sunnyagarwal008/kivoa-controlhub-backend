#!/usr/bin/env python
"""
Database migration script to add sku_sequence_number column to products table
This script:
1. Adds the sku_sequence_number column to products table
2. Populates existing products by reverse mapping from their SKU values
   (SKU format: <prefix>-<sequence>-<purchase_month>, e.g., ELEC-0001-0124)
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text


def migrate_add_sku_sequence_number():
    """Add sku_sequence_number column and populate from existing SKUs"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='sku_sequence_number'
            """))
            
            if result.fetchone():
                print("✓ Column 'sku_sequence_number' already exists. No migration needed.")
                return
            
            print("\n" + "=" * 60)
            print("MIGRATION: Add sku_sequence_number column to products")
            print("=" * 60)
            
            # Step 1: Add the column (nullable initially)
            print("\n[1/3] Adding 'sku_sequence_number' column to products table...")
            db.session.execute(text("""
                ALTER TABLE products 
                ADD COLUMN sku_sequence_number INTEGER
            """))
            db.session.commit()
            print("✓ Column added successfully!")
            
            # Step 2: Populate the column by reverse mapping from SKUs
            print("\n[2/3] Populating sku_sequence_number from existing SKUs...")
            
            # Get all products with their SKUs
            result = db.session.execute(text("""
                SELECT id, sku 
                FROM products 
                ORDER BY id
            """))
            products = result.fetchall()
            
            if not products:
                print("   No products found. Skipping population step.")
            else:
                print(f"   Found {len(products)} products to process")
                
                success_count = 0
                error_count = 0
                
                for product_id, sku in products:
                    try:
                        # Parse SKU format: <prefix>-<sequence>-<purchase_month>
                        # Example: ELEC-0001-0124
                        parts = sku.split('-')
                        
                        if len(parts) != 3:
                            print(f"   ⚠ Warning: Product ID {product_id} has invalid SKU format: {sku}")
                            error_count += 1
                            continue
                        
                        # Extract sequence number (second part)
                        sequence_str = parts[1]
                        
                        # Convert to integer (remove leading zeros)
                        sequence_number = int(sequence_str)
                        
                        # Update the product
                        db.session.execute(text("""
                            UPDATE products 
                            SET sku_sequence_number = :seq_num 
                            WHERE id = :product_id
                        """), {'seq_num': sequence_number, 'product_id': product_id})
                        
                        success_count += 1
                        
                    except (ValueError, IndexError) as e:
                        print(f"   ⚠ Warning: Failed to parse SKU for product ID {product_id} (SKU: {sku}): {str(e)}")
                        error_count += 1
                        continue
                
                db.session.commit()
                print(f"   ✓ Successfully populated {success_count} products")
                if error_count > 0:
                    print(f"   ⚠ {error_count} products had errors and were skipped")
            
            # Step 3: Make the column NOT NULL
            print("\n[3/3] Setting sku_sequence_number as NOT NULL...")
            
            # Check if there are any NULL values
            result = db.session.execute(text("""
                SELECT COUNT(*) 
                FROM products 
                WHERE sku_sequence_number IS NULL
            """))
            null_count = result.fetchone()[0]
            
            if null_count > 0:
                print(f"   ⚠ Warning: {null_count} products still have NULL sku_sequence_number")
                print("   Cannot set column to NOT NULL. Please fix these products manually.")
                print("\n   Products with NULL sku_sequence_number:")
                result = db.session.execute(text("""
                    SELECT id, sku 
                    FROM products 
                    WHERE sku_sequence_number IS NULL
                    LIMIT 10
                """))
                for product_id, sku in result.fetchall():
                    print(f"     - Product ID {product_id}: {sku}")
            else:
                db.session.execute(text("""
                    ALTER TABLE products 
                    ALTER COLUMN sku_sequence_number SET NOT NULL
                """))
                db.session.commit()
                print("✓ Column set to NOT NULL successfully!")
            
            # Verify the column was added
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='sku_sequence_number'
            """))
            
            col_name, data_type, is_nullable = result.fetchone()
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"\nColumn details:")
            print(f"  • {col_name}: {data_type} ({nullable})")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nThe sku_sequence_number column has been added and populated")
            print("from existing SKU values.")
            print("=" * 60 + "\n")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error during migration: {str(e)}")
            raise


if __name__ == '__main__':
    migrate_add_sku_sequence_number()

