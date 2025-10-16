# Project Folder Structure

## Overview

The project has been reorganized into a modular structure following best practices for Flask applications. Files are now organized by their purpose and functionality.

## New Structure

```
src/
├── __init__.py                 # Package initialization
├── app.py                      # Flask application factory
├── config.py                   # Configuration settings
├── database.py                 # Database initialization
│
├── models/                     # Database models (ORM)
│   ├── __init__.py            # Exports: Product, ProductImage
│   └── product.py             # Product and ProductImage models
│
├── schemas/                    # Validation schemas (Marshmallow)
│   ├── __init__.py            # Exports all schemas
│   ├── product.py             # ProductSchema, ProductImageSchema
│   └── s3.py                  # PresignedUrlRequestSchema, PresignedUrlResponseSchema
│
├── services/                   # Business logic and external services
│   ├── __init__.py            # Exports all services
│   ├── s3_service.py          # AWS S3 operations
│   ├── sqs_service.py         # AWS SQS operations
│   └── gemini_service.py      # Google Gemini AI operations
│
├── workers/                    # Background workers
│   ├── __init__.py            # Exports worker functions
│   └── image_enhancement.py   # Image enhancement worker thread
│
└── routes/                     # API endpoints (Blueprints)
    ├── __init__.py            # Registers all blueprints
    ├── health.py              # Health check endpoint
    ├── products.py            # Product CRUD endpoints
    └── s3.py                  # S3 presigned URL endpoint
```

## Folder Descriptions

### `models/`
Contains SQLAlchemy database models representing database tables.

**Files:**
- `product.py` - Product and ProductImage models with relationships

**Usage:**
```python
from src.models import Product, ProductImage
```

### `schemas/`
Contains Marshmallow schemas for request/response validation and serialization.

**Files:**
- `product.py` - Product and ProductImage validation schemas
- `s3.py` - S3 presigned URL request/response schemas

**Usage:**
```python
from src.schemas import ProductSchema, ProductImageSchema
from src.schemas import PresignedUrlRequestSchema, PresignedUrlResponseSchema
```

### `services/`
Contains business logic and integrations with external services (AWS, Gemini AI).

**Files:**
- `s3_service.py` - AWS S3 operations (upload, presigned URLs)
- `sqs_service.py` - AWS SQS operations (send, receive, delete messages)
- `gemini_service.py` - Google Gemini AI operations (image analysis, enhancement)

**Usage:**
```python
from src.services import s3_service, sqs_service, gemini_service
from src.services import S3Service, SQSService, GeminiService
```

### `workers/`
Contains background worker threads for asynchronous processing.

**Files:**
- `image_enhancement.py` - Worker thread for processing product images with AI

**Usage:**
```python
from src.workers import start_worker, stop_worker, WorkerThread
```

### `routes/`
Contains Flask blueprints defining API endpoints.

**Files:**
- `health.py` - Health check endpoint
- `products.py` - Product CRUD and bulk upload endpoints
- `s3.py` - S3 presigned URL generation endpoint

**Usage:**
```python
from src.routes import api  # Combined blueprint
```

## Import Examples

### In Route Files
```python
# routes/products.py
from src.database import db
from src.models import Product
from src.schemas import ProductSchema
from src.services import sqs_service
```

### In Worker Files
```python
# workers/image_enhancement.py
from src.database import db
from src.models import Product, ProductImage
from src.services import sqs_service, gemini_service, S3Service
```

### In Scripts
```python
# scripts/test_image_enhancement.py
from src.app import create_app
from src.database import db
from src.models import Product, ProductImage
from src.services import sqs_service, gemini_service, S3Service
```

### In Application Factory
```python
# app.py
from src.config import config
from src.database import init_db
from src.routes import api
from src.workers import start_worker
```

## Benefits of This Structure

### 1. **Modularity**
- Each folder has a single, clear responsibility
- Easy to locate specific functionality
- Reduces cognitive load when navigating the codebase

### 2. **Scalability**
- Easy to add new models, schemas, services, or workers
- Clear patterns for where new code should go
- Supports team growth and collaboration

### 3. **Maintainability**
- Related code is grouped together
- Changes are localized to specific modules
- Easier to test individual components

### 4. **Separation of Concerns**
- **Models**: Data structure and database representation
- **Schemas**: Validation and serialization logic
- **Services**: Business logic and external integrations
- **Workers**: Background processing
- **Routes**: API endpoints and request handling

### 5. **Testability**
- Each module can be tested independently
- Easy to mock services in tests
- Clear boundaries between components

## Migration Notes

### What Changed

**Before:**
```
src/
├── models.py          → src/models/product.py
├── schemas.py         → src/schemas/product.py + src/schemas/s3.py
├── s3_service.py      → src/services/s3_service.py
├── sqs_service.py     → src/services/sqs_service.py
├── gemini_service.py  → src/services/gemini_service.py
└── worker_thread.py   → src/workers/image_enhancement.py
```

**After:**
- Files organized into logical folders
- Each folder has an `__init__.py` for clean imports
- All imports updated throughout the codebase

### Updated Files

The following files had their imports updated:
- `src/app.py`
- `src/routes/products.py`
- `src/routes/s3.py`
- `src/workers/image_enhancement.py`
- `run.py`
- `scripts/test_image_enhancement.py`

### No Breaking Changes

All imports still work through the `__init__.py` files:
```python
# Both of these work:
from src.models import Product
from src.models.product import Product
```

## Adding New Components

### Adding a New Model
1. Create file in `src/models/` (e.g., `user.py`)
2. Define model class
3. Export in `src/models/__init__.py`

### Adding a New Schema
1. Create file in `src/schemas/` (e.g., `user.py`)
2. Define schema class
3. Export in `src/schemas/__init__.py`

### Adding a New Service
1. Create file in `src/services/` (e.g., `email_service.py`)
2. Define service class and singleton instance
3. Export in `src/services/__init__.py`

### Adding a New Worker
1. Create file in `src/workers/` (e.g., `email_worker.py`)
2. Define worker class and functions
3. Export in `src/workers/__init__.py`

### Adding a New Route
1. Create file in `src/routes/` (e.g., `users.py`)
2. Define blueprint and endpoints
3. Register in `src/routes/__init__.py`

## Best Practices

1. **Keep files focused** - Each file should have a single responsibility
2. **Use clear names** - File and class names should be descriptive
3. **Export through __init__.py** - Makes imports cleaner
4. **Follow the pattern** - New code should follow existing structure
5. **Document changes** - Update this file when adding new folders

## Questions?

Refer to the existing code for examples of how to structure new components. The pattern is consistent throughout the codebase.

