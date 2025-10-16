# Product Management Backend API

A Flask-based REST API for managing product uploads from an Android application with AWS S3 integration.

## Features

- **Product Management**: Create, read, update, and delete products
- **Bulk Upload**: Create multiple products in a single API call
- **AI Image Enhancement**: Automatic image enhancement using Google Gemini AI
- **Background Processing**: SQS-based queue with background worker thread
- **S3 Integration**: Generate presigned URLs for direct image uploads to AWS S3
- **PostgreSQL Database**: Robust data storage with SQLAlchemy ORM
- **Automatic Status Management**: Products automatically set to "pending" status on creation
- **Input Validation**: Comprehensive validation using Marshmallow schemas
- **RESTful Design**: Clean and intuitive API endpoints

## Tech Stack

- **Framework**: Flask 3.0
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cloud Storage**: AWS S3 with boto3
- **Message Queue**: AWS SQS
- **AI/ML**: Google Gemini AI
- **Image Processing**: Pillow
- **Validation**: Marshmallow
- **CORS**: Flask-CORS
- **Database Migrations**: Flask-Migrate

## Project Structure

The project follows a modular architecture with clear separation of concerns:

```
src/
├── models/          # Database models (SQLAlchemy ORM)
├── schemas/         # Validation schemas (Marshmallow)
├── services/        # Business logic & external services (S3, SQS, Gemini)
├── workers/         # Background workers (Image enhancement)
└── routes/          # API endpoints (Flask Blueprints)
```

See [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) for detailed documentation.

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd kivoa-controlhub-backend
```

2. **Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your actual configuration
```

5. **Initialize the database**
```bash
python scripts/init_db.py
```

6. **Seed the database (optional)**
```bash
python scripts/seed_data.py
```

## Configuration

Edit the `.env` file with your configuration:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/product_db

# AWS S3
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name

# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# S3 Presigned URL Expiration (in seconds)
PRESIGNED_URL_EXPIRATION=3600
```

## Running the Application

**Development mode:**
```bash
python run.py
```

**Production mode with Gunicorn:**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
```

The API will be available at `http://localhost:5000`

## API Endpoints

### Health Check
```
GET /api/health
```

### Generate Presigned URL
```
POST /api/presigned-url
Content-Type: application/json

{
    "filename": "product_image.jpg",
    "content_type": "image/jpeg"
}

Response:
{
    "success": true,
    "data": {
        "presigned_url": "https://...",
        "file_url": "https://...",
        "expires_in": 3600
    }
}
```

### Create Product
```
POST /api/products
Content-Type: application/json

{
    "category": "Electronics",
    "raw_image": "https://bucket.s3.region.amazonaws.com/products/uuid.jpg",
    "mrp": 1000.00,
    "price": 850.00,
    "discount": 150.00,
    "gst": 18.00
}

Response:
{
    "success": true,
    "message": "Product created successfully",
    "data": {
        "id": 1,
        "category": "Electronics",
        "raw_image": "https://...",
        "mrp": 1000.00,
        "price": 850.00,
        "discount": 150.00,
        "gst": 18.00,
        "status": "pending",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
}
```

### Get All Products
```
GET /api/products?status=pending&category=Electronics&page=1&per_page=10

Response:
{
    "success": true,
    "data": [...],
    "pagination": {
        "page": 1,
        "per_page": 10,
        "total": 100,
        "pages": 10
    }
}
```

### Get Single Product
```
GET /api/products/{product_id}

Response:
{
    "success": true,
    "data": {...}
}
```

### Update Product
```
PUT /api/products/{product_id}
Content-Type: application/json

{
    "price": 800.00,
    "discount": 200.00
}

Response:
{
    "success": true,
    "message": "Product updated successfully",
    "data": {...}
}
```

### Delete Product
```
DELETE /api/products/{product_id}

Response:
{
    "success": true,
    "message": "Product deleted successfully"
}
```

## Android Integration Flow

1. **Upload Image**:
   - Call `POST /api/presigned-url` with filename and content type
   - Receive presigned URL and file URL
   - Upload image directly to S3 using the presigned URL (PUT request)
   - Store the `file_url` for product creation

2. **Create Product**:
   - Call `POST /api/products` with product data including the S3 `file_url`
   - Product is automatically created with "pending" status

## Database Schema

### Products Table
- `id`: Integer (Primary Key)
- `category`: String(100)
- `raw_image`: String(500) - S3 URL
- `mrp`: Numeric(10, 2) - Maximum Retail Price
- `price`: Numeric(10, 2) - Selling Price
- `discount`: Numeric(10, 2)
- `gst`: Numeric(10, 2)
- `status`: String(20) - Default: "pending" → "pending_review" → "approved"/"rejected"
- `created_at`: DateTime
- `updated_at`: DateTime

### Product Images Table
- `id`: Integer (Primary Key)
- `product_id`: Integer (Foreign Key → products.id)
- `image_url`: String(500) - S3 URL of enhanced image
- `status`: String(20) - "pending", "approved", "rejected"
- `created_at`: DateTime
- `updated_at`: DateTime

## AI Image Enhancement

The system includes automatic image enhancement using Google Gemini AI:

1. **Bulk Upload** → Products created with status "pending"
2. **SQS Queue** → Product IDs sent to queue for processing
3. **Background Worker** → Processes each product asynchronously:
   - Downloads raw image from S3
   - Uses Gemini AI to analyze and generate enhancement prompts
   - Creates multiple enhanced images (configurable)
   - Uploads enhanced images to S3
   - Saves to `product_images` table
   - Updates product status to "pending_review"

**Setup Guide:** See [QUICK_START_IMAGE_ENHANCEMENT.md](QUICK_START_IMAGE_ENHANCEMENT.md)

**Full Documentation:** See [IMAGE_ENHANCEMENT_SETUP.md](IMAGE_ENHANCEMENT_SETUP.md)

## Error Handling

All endpoints return consistent error responses:

```json
{
    "success": false,
    "error": "Error message",
    "details": {...}  // Optional validation details
}
```

## Security Considerations

- Store sensitive credentials in environment variables
- Use HTTPS in production
- Implement authentication/authorization as needed
- Set appropriate CORS policies
- Use presigned URLs with reasonable expiration times
- Validate all input data

## License

MIT

