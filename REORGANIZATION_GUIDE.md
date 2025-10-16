# Code Reorganization Guide

## Summary

The `src/` folder has been reorganized into a modular structure for better maintainability and scalability.

## What Changed

### File Movements

| Old Location | New Location | Purpose |
|-------------|--------------|---------|
| `src/models.py` | `src/models/product.py` | Database models |
| `src/schemas.py` | `src/schemas/product.py` + `src/schemas/s3.py` | Validation schemas |
| `src/s3_service.py` | `src/services/s3_service.py` | S3 service |
| `src/sqs_service.py` | `src/services/sqs_service.py` | SQS service |
| `src/gemini_service.py` | `src/services/gemini_service.py` | Gemini AI service |
| `src/worker_thread.py` | `src/workers/image_enhancement.py` | Background worker |

### New Folder Structure

```
src/
├── models/          # Database models (ORM)
├── schemas/         # Validation schemas
├── services/        # Business logic & external services
├── workers/         # Background workers
└── routes/          # API endpoints (already existed)
```

## Import Changes

### Before
```python
from src.models import Product, ProductImage
from src.schemas import ProductSchema, PresignedUrlRequestSchema
from src.s3_service import s3_service
from src.sqs_service import sqs_service
from src.gemini_service import gemini_service
from src.worker_thread import start_worker, stop_worker
```

### After
```python
from src.models import Product, ProductImage
from src.schemas import ProductSchema, PresignedUrlRequestSchema
from src.services import s3_service, sqs_service, gemini_service
from src.workers import start_worker, stop_worker
```

## Updated Files

All imports have been automatically updated in:

✅ `src/app.py`  
✅ `src/routes/products.py`  
✅ `src/routes/s3.py`  
✅ `src/workers/image_enhancement.py`  
✅ `run.py`  
✅ `scripts/test_image_enhancement.py`  

## Benefits

### 1. **Better Organization**
- Related files are grouped together
- Clear separation of concerns
- Easier to navigate the codebase

### 2. **Scalability**
- Easy to add new models, services, or workers
- Clear patterns for where new code belongs
- Supports team growth

### 3. **Maintainability**
- Changes are localized to specific modules
- Easier to understand dependencies
- Simpler to test individual components

### 4. **Professional Structure**
- Follows Flask best practices
- Similar to popular open-source projects
- Industry-standard organization

## No Breaking Changes

The reorganization maintains backward compatibility through `__init__.py` files:

```python
# Both work:
from src.models import Product
from src.models.product import Product

# Both work:
from src.services import s3_service
from src.services.s3_service import s3_service
```

## Testing

To verify everything works:

1. **Check imports:**
   ```bash
   source .venv/bin/activate
   python -c "from src.app import create_app; print('✓ Imports OK')"
   ```

2. **Run tests:**
   ```bash
   python scripts/test_image_enhancement.py
   ```

3. **Start application:**
   ```bash
   python run.py
   ```

## Adding New Code

### New Model
```python
# src/models/user.py
from src.database import db

class User(db.Model):
    # ...

# src/models/__init__.py
from src.models.user import User
__all__ = ['Product', 'ProductImage', 'User']
```

### New Service
```python
# src/services/email_service.py
class EmailService:
    # ...

email_service = EmailService()

# src/services/__init__.py
from src.services.email_service import EmailService, email_service
__all__ = [..., 'EmailService', 'email_service']
```

### New Worker
```python
# src/workers/email_worker.py
class EmailWorker:
    # ...

# src/workers/__init__.py
from src.workers.email_worker import EmailWorker
__all__ = [..., 'EmailWorker']
```

### New Route
```python
# src/routes/users.py
from flask import Blueprint

users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['GET'])
def get_users():
    # ...

# src/routes/__init__.py
from src.routes.users import users_bp
api.register_blueprint(users_bp)
```

## Rollback (If Needed)

If you need to rollback to the old structure:

1. The old files were removed, but you can restore from git:
   ```bash
   git checkout HEAD -- src/models.py src/schemas.py src/*_service.py src/worker_thread.py
   ```

2. Remove new folders:
   ```bash
   rm -rf src/models src/schemas src/services src/workers
   ```

3. Revert import changes:
   ```bash
   git checkout HEAD -- src/app.py src/routes/ run.py scripts/
   ```

## Documentation

See [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) for detailed documentation on:
- Complete folder structure
- Import examples
- Best practices
- Adding new components

## Questions?

The reorganization follows standard Flask application patterns. Each folder has a clear purpose:

- **models/** = Database tables
- **schemas/** = Validation rules
- **services/** = Business logic
- **workers/** = Background tasks
- **routes/** = API endpoints

All imports work through `__init__.py` files for clean, simple imports.

