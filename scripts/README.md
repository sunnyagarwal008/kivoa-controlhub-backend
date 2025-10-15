# Database Scripts

This folder contains database management and utility scripts.

## Scripts

### 1. `init_db.py`
**Purpose:** Initialize the database and create all tables

**Usage:**
```bash
python scripts/init_db.py
```

**Description:**
- Creates all database tables based on SQLAlchemy models
- Displays created tables and their columns
- Safe to run multiple times (won't recreate existing tables)

---

### 2. `seed_data.py`
**Purpose:** Populate the database with sample data for testing

**Usage:**
```bash
python scripts/seed_data.py
```

**Description:**
- Adds 5 sample products to the database
- Includes various categories and statuses
- Checks if data already exists before seeding
- Useful for development and testing

**Sample Data:**
- Electronics (pending)
- Clothing (pending)
- Books (approved)
- Home & Kitchen (pending)
- Sports (rejected)

---

### 3. `migrate_image_to_raw_image.py`
**Purpose:** Database migration to rename 'image' column to 'raw_image'

**Usage:**
```bash
python scripts/migrate_image_to_raw_image.py
```

**Description:**
- Renames the `image` column to `raw_image` in the products table
- Includes safety checks to prevent errors
- Checks if migration is needed before executing
- Safe to run multiple times

**When to use:**
- When upgrading from an older version that used 'image' field
- After pulling code changes that renamed the field

---

## Running Scripts

All scripts should be run from the project root directory:

```bash
# From project root
cd /path/to/kivoa-controlhub-backend

# Run any script
python scripts/init_db.py
python scripts/seed_data.py
python scripts/migrate_image_to_raw_image.py
```

## Prerequisites

Before running any script, ensure:
1. Virtual environment is activated
2. Dependencies are installed (`pip install -r requirements.txt`)
3. `.env` file is configured with database credentials
4. PostgreSQL database is running and accessible

## Typical Setup Flow

For a fresh setup:
```bash
# 1. Initialize database
python scripts/init_db.py

# 2. Seed with sample data (optional)
python scripts/seed_data.py
```

For migration from old schema:
```bash
# 1. Run migration
python scripts/migrate_image_to_raw_image.py
```

