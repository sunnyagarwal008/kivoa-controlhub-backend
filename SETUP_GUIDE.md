# Setup Guide

This guide will walk you through setting up the Product Management Backend API from scratch.

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- AWS Account with S3 access
- pip (Python package manager)

---

## Step 1: Install Python Dependencies

1. **Create a virtual environment:**
```bash
python -m venv venv
```

2. **Activate the virtual environment:**

On macOS/Linux:
```bash
source venv/bin/activate
```

On Windows:
```bash
venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

---

## Step 2: Set Up PostgreSQL Database

1. **Install PostgreSQL** (if not already installed):

On macOS:
```bash
brew install postgresql
brew services start postgresql
```

On Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

2. **Create a database:**
```bash
# Login to PostgreSQL
psql postgres

# Create database
CREATE DATABASE product_db;

# Create user (optional)
CREATE USER product_user WITH PASSWORD 'your_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE product_db TO product_user;

# Exit
\q
```

---

## Step 3: Set Up AWS S3

1. **Create an S3 Bucket:**
   - Log in to AWS Console
   - Navigate to S3
   - Click "Create bucket"
   - Choose a unique bucket name (e.g., `your-app-products`)
   - Select a region (e.g., `us-east-1`)
   - Uncheck "Block all public access" if you want images to be publicly accessible
   - Create the bucket

2. **Configure CORS for S3 Bucket:**
   - Go to your bucket
   - Click on "Permissions" tab
   - Scroll to "Cross-origin resource sharing (CORS)"
   - Add the following CORS configuration:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
        "AllowedOrigins": ["*"],
        "ExposeHeaders": ["ETag"]
    }
]
```

3. **Create IAM User with S3 Access:**
   - Go to IAM in AWS Console
   - Click "Users" → "Add user"
   - Choose a username (e.g., `product-api-user`)
   - Select "Programmatic access"
   - Attach policy: `AmazonS3FullAccess` (or create a custom policy)
   - Save the Access Key ID and Secret Access Key

**Custom IAM Policy (Recommended):**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::your-bucket-name/*"
        }
    ]
}
```

---

## Step 4: Configure Environment Variables

1. **Copy the example environment file:**
```bash
cp .env.example .env
```

2. **Edit `.env` with your actual values:**
```env
# Database Configuration
DATABASE_URL=postgresql://product_user:your_password@localhost:5432/product_db

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-app-products

# Flask Configuration
FLASK_APP=src.app
FLASK_ENV=development
SECRET_KEY=generate-a-random-secret-key-here

# S3 Presigned URL Expiration (in seconds)
PRESIGNED_URL_EXPIRATION=3600
```

**Generate a secure SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Step 5: Initialize the Database

1. **Initialize Flask-Migrate:**
```bash
flask db init
```

2. **Create initial migration:**
```bash
flask db migrate -m "Initial migration - create products table"
```

3. **Apply migration:**
```bash
flask db upgrade
```

---

## Step 6: Run the Application

1. **Development mode:**
```bash
python run.py
```

The API will be available at `http://localhost:5000`

2. **Production mode with Gunicorn:**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
```

---

## Step 7: Test the API

1. **Test health endpoint:**
```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
    "status": "healthy",
    "message": "API is running"
}
```

2. **Test presigned URL generation:**
```bash
curl -X POST http://localhost:5000/api/presigned-url \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.jpg",
    "content_type": "image/jpeg"
  }'
```

3. **Test product creation:**
```bash
curl -X POST http://localhost:5000/api/products \
  -H "Content-Type: application/json" \
  -d '{
    "category": "Electronics",
    "image": "https://your-bucket.s3.us-east-1.amazonaws.com/products/test.jpg",
    "mrp": 1000.00,
    "price": 850.00,
    "discount": 150.00,
    "gst": 18.00
  }'
```

---

## Troubleshooting

### Database Connection Issues

**Error:** `could not connect to server: Connection refused`

**Solution:**
- Ensure PostgreSQL is running: `brew services list` (macOS) or `sudo systemctl status postgresql` (Linux)
- Check DATABASE_URL in `.env` file
- Verify database exists: `psql -l`

### AWS S3 Issues

**Error:** `An error occurred (InvalidAccessKeyId) when calling the PutObject operation`

**Solution:**
- Verify AWS credentials in `.env` file
- Check IAM user has S3 permissions
- Ensure bucket name is correct

**Error:** `An error occurred (AccessDenied) when calling the PutObject operation`

**Solution:**
- Check IAM policy allows `s3:PutObject`
- Verify bucket permissions

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

### Migration Issues

**Error:** `Can't locate revision identified by 'xxxxx'`

**Solution:**
```bash
# Remove migrations folder
rm -rf migrations/

# Reinitialize
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

---

## Production Deployment Checklist

- [ ] Set `FLASK_ENV=production` in `.env`
- [ ] Generate a strong `SECRET_KEY`
- [ ] Use a production-grade database (not SQLite)
- [ ] Set up HTTPS/SSL
- [ ] Configure proper CORS settings
- [ ] Set up database backups
- [ ] Configure logging
- [ ] Set up monitoring (e.g., Sentry)
- [ ] Use environment-specific configuration
- [ ] Set up CI/CD pipeline
- [ ] Configure firewall rules
- [ ] Set up rate limiting
- [ ] Implement authentication/authorization
- [ ] Use a reverse proxy (nginx)
- [ ] Set appropriate S3 bucket policies

---

## Next Steps

1. Implement authentication (JWT, OAuth, etc.)
2. Add rate limiting
3. Set up logging and monitoring
4. Add unit and integration tests
5. Create admin dashboard
6. Implement product approval workflow
7. Add image optimization
8. Set up CDN for images

---

## Support

For issues or questions, please refer to:
- API Documentation: `API_DOCUMENTATION.md`
- README: `README.md`

