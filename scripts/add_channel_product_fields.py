#!/usr/bin/env python
"""
Database migration script to add title, description, price, and mrp columns
to the product_channels table for storing channel-specific product data.
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text


def migrate_add_channel_product_fields():
    """Add title, description, price, mrp columns to product_channels table"""
    app = create_app()

    with app.app_context():
        try:
            columns_to_add = [
                ('title', 'VARCHAR(500)'),
                ('description', 'TEXT'),
                ('price', 'NUMERIC(10, 2)'),
                ('mrp', 'NUMERIC(10, 2)'),
            ]

            for col_name, col_type in columns_to_add:
                result = db.session.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='product_channels' AND column_name=:col
                """), {'col': col_name})

                if result.fetchone():
                    print(f"✓ Column '{col_name}' already exists. Skipping.")
                    continue

                print(f"Adding '{col_name}' column to product_channels table...")
                db.session.execute(text(
                    f"ALTER TABLE product_channels ADD COLUMN {col_name} {col_type}"
                ))
                print(f"✓ Added '{col_name}'.")

            db.session.commit()
            print("\n✓ Migration completed successfully!")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {str(e)}")
            raise


if __name__ == '__main__':
    migrate_add_channel_product_fields()

