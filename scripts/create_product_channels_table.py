#!/usr/bin/env python
"""
Database migration script to create product_channels table
Run this script to create the table for tracking product syncs across different sales channels
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from sqlalchemy import text

def create_product_channels_table():
    """Create product_channels table"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("Starting migration: Creating product_channels table")
            print("=" * 60)
            
            # Check if the table already exists
            result = db.session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='product_channels'
            """))
            
            if result.fetchone():
                print("✓ Table 'product_channels' already exists. No migration needed.")
                return
            
            print("\nCreating 'product_channels' table...")
            
            # Create the product_channels table
            db.session.execute(text("""
                CREATE TABLE product_channels (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    channel_name VARCHAR(50) NOT NULL,
                    channel_product_id VARCHAR(255),
                    channel_listing_id VARCHAR(255),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    sync_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    last_synced_at TIMESTAMP,
                    error_message TEXT,
                    channel_data JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_product_channel UNIQUE (product_id, channel_name)
                )
            """))
            
            # Create indexes for better query performance
            db.session.execute(text("""
                CREATE INDEX idx_product_channels_product_id ON product_channels(product_id)
            """))
            
            db.session.execute(text("""
                CREATE INDEX idx_product_channels_channel_name ON product_channels(channel_name)
            """))
            
            db.session.execute(text("""
                CREATE INDEX idx_product_channels_status ON product_channels(status)
            """))
            
            db.session.execute(text("""
                CREATE INDEX idx_product_channels_sync_status ON product_channels(sync_status)
            """))
            
            db.session.commit()
            print("✓ Successfully created 'product_channels' table!")
            
            # Verify the table was created
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name='product_channels'
                ORDER BY ordinal_position
            """))
            
            print("\n" + "=" * 60)
            print("Table structure:")
            print("=" * 60)
            
            for row in result:
                col_name, data_type, is_nullable, col_default = row
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                default = f" DEFAULT {col_default}" if col_default else ""
                print(f"  • {col_name}: {data_type} ({nullable}){default}")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("=" * 60)
            print("\nThe product_channels table is now ready to track product syncs.")
            print("\nSupported channels:")
            print("  • shopify - Shopify store")
            print("  • amazon - Amazon Seller Central")
            print("  • flipkart - Flipkart Seller Hub")
            print("  • (add more channels as needed)")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    create_product_channels_table()
