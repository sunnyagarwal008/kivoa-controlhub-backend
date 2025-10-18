#!/usr/bin/env python
"""
Database migration script to add category table and update products table
This script:
1. Creates the categories table with id, name, prefix, and sku_sequence_number
2. Adds category_id, sku, and purchase_month columns to products table
3. Migrates existing category data to the new structure
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def migrate_database():
    """Add category table and update products table with new fields"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Starting database migration...")
            print("=" * 60)
            
            # Step 1: Check if categories table exists
            result = db.session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='categories'
            """))
            
            if not result.fetchone():
                print("\n[1/5] Creating categories table...")
                db.session.execute(text("""
                    CREATE TABLE categories (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        prefix VARCHAR(10) NOT NULL UNIQUE,
                        sku_sequence_number INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
                print("✓ Categories table created successfully!")
            else:
                print("\n[1/5] Categories table already exists. Skipping...")
            
            # Step 2: Check if new columns exist in products table
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='category_id'
            """))
            
            if not result.fetchone():
                print("\n[2/5] Adding category_id column to products table...")
                
                # First, get unique categories from existing products
                result = db.session.execute(text("""
                    SELECT DISTINCT category 
                    FROM products 
                    WHERE category IS NOT NULL
                """))
                existing_categories = [row[0] for row in result.fetchall()]
                
                # Create categories from existing product categories
                if existing_categories:
                    print(f"   Found {len(existing_categories)} unique categories to migrate")
                    for idx, cat_name in enumerate(existing_categories, 1):
                        # Generate a prefix from category name (first 4 chars, uppercase)
                        prefix = cat_name[:4].upper().replace(' ', '')
                        
                        # Check if category already exists
                        result = db.session.execute(text("""
                            SELECT id FROM categories WHERE name = :name
                        """), {'name': cat_name})
                        
                        if not result.fetchone():
                            db.session.execute(text("""
                                INSERT INTO categories (name, prefix, sku_sequence_number)
                                VALUES (:name, :prefix, 0)
                            """), {'name': cat_name, 'prefix': prefix})
                            print(f"   ✓ Created category: {cat_name} (prefix: {prefix})")
                    
                    db.session.commit()
                
                # Add category_id column (nullable initially for migration)
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD COLUMN category_id INTEGER
                """))
                db.session.commit()
                print("✓ category_id column added successfully!")
                
                # Update category_id for existing products
                if existing_categories:
                    print("   Updating category_id for existing products...")
                    for cat_name in existing_categories:
                        db.session.execute(text("""
                            UPDATE products p
                            SET category_id = c.id
                            FROM categories c
                            WHERE p.category = c.name AND p.category_id IS NULL
                        """))
                    db.session.commit()
                    print("   ✓ Updated category_id for existing products")
                
                # Add foreign key constraint
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD CONSTRAINT fk_products_category_id 
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                """))
                db.session.commit()
                print("   ✓ Foreign key constraint added")
                
                # Make category_id NOT NULL
                db.session.execute(text("""
                    ALTER TABLE products 
                    ALTER COLUMN category_id SET NOT NULL
                """))
                db.session.commit()
                print("   ✓ category_id set to NOT NULL")
            else:
                print("\n[2/5] category_id column already exists. Skipping...")
            
            # Step 3: Add sku column
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='sku'
            """))
            
            if not result.fetchone():
                print("\n[3/5] Adding sku column to products table...")
                
                # Add sku column (nullable initially)
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD COLUMN sku VARCHAR(50)
                """))
                db.session.commit()
                
                # Generate SKUs for existing products
                result = db.session.execute(text("""
                    SELECT COUNT(*) FROM products
                """))
                product_count = result.fetchone()[0]
                
                if product_count > 0:
                    print(f"   Generating SKUs for {product_count} existing products...")
                    
                    # Get all products with their categories
                    result = db.session.execute(text("""
                        SELECT p.id, p.category_id, c.prefix
                        FROM products p
                        JOIN categories c ON p.category_id = c.id
                        ORDER BY p.id
                    """))
                    products = result.fetchall()
                    
                    # Track sequence numbers per category
                    category_sequences = {}
                    
                    for product_id, category_id, prefix in products:
                        if category_id not in category_sequences:
                            category_sequences[category_id] = 0
                        
                        category_sequences[category_id] += 1
                        sequence = str(category_sequences[category_id]).zfill(4)
                        
                        # Use a default purchase month (current month/year) for existing products
                        from datetime import datetime
                        default_month = datetime.now().strftime('%m%y')
                        
                        sku = f"{prefix}-{sequence}-{default_month}"
                        
                        db.session.execute(text("""
                            UPDATE products 
                            SET sku = :sku 
                            WHERE id = :product_id
                        """), {'sku': sku, 'product_id': product_id})
                    
                    # Update category sequence numbers
                    for category_id, seq_num in category_sequences.items():
                        db.session.execute(text("""
                            UPDATE categories 
                            SET sku_sequence_number = :seq_num 
                            WHERE id = :category_id
                        """), {'seq_num': seq_num, 'category_id': category_id})
                    
                    db.session.commit()
                    print(f"   ✓ Generated SKUs for all existing products")
                
                # Make sku NOT NULL and UNIQUE
                db.session.execute(text("""
                    ALTER TABLE products 
                    ALTER COLUMN sku SET NOT NULL
                """))
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD CONSTRAINT uq_products_sku UNIQUE (sku)
                """))
                db.session.commit()
                print("✓ sku column added successfully (NOT NULL, UNIQUE)!")
            else:
                print("\n[3/5] sku column already exists. Skipping...")
            
            # Step 4: Add purchase_month column
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='products' AND column_name='purchase_month'
            """))
            
            if not result.fetchone():
                print("\n[4/5] Adding purchase_month column to products table...")
                
                # Add purchase_month column (nullable initially)
                db.session.execute(text("""
                    ALTER TABLE products 
                    ADD COLUMN purchase_month VARCHAR(4)
                """))
                db.session.commit()
                
                # Set default purchase_month for existing products
                from datetime import datetime
                default_month = datetime.now().strftime('%m%y')
                
                db.session.execute(text("""
                    UPDATE products 
                    SET purchase_month = :default_month 
                    WHERE purchase_month IS NULL
                """), {'default_month': default_month})
                db.session.commit()
                
                # Make purchase_month NOT NULL
                db.session.execute(text("""
                    ALTER TABLE products 
                    ALTER COLUMN purchase_month SET NOT NULL
                """))
                db.session.commit()
                print(f"✓ purchase_month column added successfully (default: {default_month})!")
            else:
                print("\n[4/5] purchase_month column already exists. Skipping...")
            
            # Step 5: Drop old category column
            result = db.session.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='products' AND column_name='category'
            """))

            if result.fetchone():
                print("\n[5/6] Dropping old category column from products table...")
                db.session.execute(text("""
                    ALTER TABLE products
                    DROP COLUMN category
                """))
                db.session.commit()
                print("✓ Old category column dropped successfully!")
            else:
                print("\n[5/6] Old category column already removed. Skipping...")

            # Step 6: Verify migration
            print("\n[6/6] Verifying migration...")
            
            # Check categories table
            result = db.session.execute(text("""
                SELECT COUNT(*) FROM categories
            """))
            category_count = result.fetchone()[0]
            print(f"   ✓ Categories table: {category_count} categories")
            
            # Check products table columns
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name='products' 
                AND column_name IN ('category_id', 'sku', 'purchase_month')
                ORDER BY column_name
            """))
            columns = result.fetchall()
            print("   ✓ Products table new columns:")
            for col_name, data_type, is_nullable in columns:
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"      • {col_name}: {data_type} ({nullable})")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nNext steps:")
            print("1. Review the migrated data")
            print("2. Update your application code to use the new structure")
            print("3. Test product creation with the new SKU generation")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error during migration: {str(e)}")
            print("\nMigration failed. Database rolled back.")
            raise

if __name__ == '__main__':
    migrate_database()

