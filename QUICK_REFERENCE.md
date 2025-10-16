# Quick Reference: New Folder Structure

## 📁 Folder Overview

```
src/
├── models/          Database models (ORM)
├── schemas/         Validation schemas
├── services/        Business logic & external APIs
├── workers/         Background tasks
└── routes/          API endpoints
```

## 🔍 Where to Find Things

| What you need | Where to look |
|--------------|---------------|
| Database tables | `src/models/` |
| Validation rules | `src/schemas/` |
| S3 operations | `src/services/s3_service.py` |
| SQS operations | `src/services/sqs_service.py` |
| Gemini AI | `src/services/gemini_service.py` |
| Image worker | `src/workers/image_enhancement.py` |
| API endpoints | `src/routes/` |

## 📝 Import Cheat Sheet

### Models
```python
from src.models import Product, ProductImage
```

### Schemas
```python
from src.schemas import ProductSchema, ProductImageSchema
from src.schemas import PresignedUrlRequestSchema, PresignedUrlResponseSchema
```

### Services
```python
from src.services import s3_service, sqs_service, gemini_service
from src.services import S3Service, SQSService, GeminiService
```

### Workers
```python
from src.workers import start_worker, stop_worker, WorkerThread
```

### Routes
```python
from src.routes import api  # Combined blueprint
```

## 🆕 Adding New Components

### New Model
1. Create `src/models/your_model.py`
2. Add to `src/models/__init__.py`

### New Schema
1. Create `src/schemas/your_schema.py`
2. Add to `src/schemas/__init__.py`

### New Service
1. Create `src/services/your_service.py`
2. Add to `src/services/__init__.py`

### New Worker
1. Create `src/workers/your_worker.py`
2. Add to `src/workers/__init__.py`

### New Route
1. Create `src/routes/your_route.py`
2. Register in `src/routes/__init__.py`

## 🎯 Common Tasks

### Access Database
```python
from src.database import db
from src.models import Product

# Query
products = Product.query.all()

# Create
product = Product(category="Electronics", ...)
db.session.add(product)
db.session.commit()
```

### Validate Data
```python
from src.schemas import ProductSchema

schema = ProductSchema()
result = schema.load(data)  # Validates and deserializes
```

### Use S3
```python
from src.services import s3_service

url = s3_service.generate_presigned_url(filename, content_type)
s3_service.upload_file(file_obj, key)
```

### Use SQS
```python
from src.services import sqs_service

sqs_service.send_message(product_id)
messages = sqs_service.receive_messages()
sqs_service.delete_message(receipt_handle)
```

### Use Gemini AI

```python
from src.services import gemini_service

image = download_image(url)
prompt = gemini_service.generate_enhanced_image_url(image, product_category)
```

## 🔧 File Purposes

### Core Files
- `app.py` - Flask application factory
- `config.py` - Configuration settings
- `database.py` - Database initialization

### Models (`models/`)
- `product.py` - Product and ProductImage models

### Schemas (`schemas/`)
- `product.py` - Product validation schemas
- `s3.py` - S3 request/response schemas

### Services (`services/`)
- `s3_service.py` - AWS S3 operations
- `sqs_service.py` - AWS SQS operations
- `gemini_service.py` - Google Gemini AI operations

### Workers (`workers/`)
- `image_enhancement.py` - Background image processing

### Routes (`routes/`)
- `health.py` - Health check endpoint
- `products.py` - Product CRUD endpoints
- `s3.py` - S3 presigned URL endpoint

## 📚 Documentation

- **FOLDER_STRUCTURE.md** - Complete structure guide
- **REORGANIZATION_GUIDE.md** - Migration guide
- **REORGANIZATION_SUMMARY.md** - What changed
- **README.md** - Project overview

## ✅ Quick Test

```bash
# Activate environment
source .venv/bin/activate

# Test imports
python -c "from src.app import create_app; print('✓ OK')"

# Start app
python run.py
```

## 🎨 Color Code (Mental Model)

- 🟣 **models/** = Purple (Database)
- 🟡 **schemas/** = Yellow (Validation)
- 🟢 **services/** = Green (External APIs)
- 🔴 **workers/** = Red (Background)
- ⚪ **routes/** = White (Endpoints)

## 💡 Remember

1. Each folder has ONE responsibility
2. Use `__init__.py` for imports
3. Follow existing patterns
4. Keep files focused and small
5. Document new components

## 🚀 That's It!

The structure is simple:
- **models/** = What data looks like
- **schemas/** = How to validate data
- **services/** = How to do things
- **workers/** = What to do in background
- **routes/** = How users access it

Happy coding! 🎉

