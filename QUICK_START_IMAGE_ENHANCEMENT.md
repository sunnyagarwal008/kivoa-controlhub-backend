# Quick Start: Image Enhancement System

## 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Database Table
```bash
python scripts/create_product_images_table.py
```

### 3. Setup SQS Queue
```bash
python scripts/setup_sqs_queue.py
```
Copy the Queue URL to your `.env` file.

### 4. Get Gemini API Key
1. Visit: https://makersuite.google.com/app/apikey
2. Create API key
3. Add to `.env` file

### 5. Update .env File
```env
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/YOUR_ACCOUNT/product-image-processing
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash
ENHANCED_IMAGES_COUNT=3
```

### 6. Test Configuration
```bash
python scripts/test_image_enhancement.py
```

### 7. Start Application
```bash
python run.py
```

The worker thread starts automatically in the background!

### 8. Test the System
```bash
# Create products via API
curl -X POST http://localhost:5000/api/products/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {
        "category": "Electronics",
        "raw_image": "https://your-bucket.s3.amazonaws.com/test.jpg",
        "mrp": 1000,
        "price": 900,
        "discount": 100,
        "gst": 18
      }
    ]
  }'
```

Watch the application console to see the worker processing in real-time!

## What Happens?

1. **API creates product** → status: `pending`
2. **Sends to SQS queue** → product_id queued
3. **Worker picks up message** → starts processing
4. **Downloads raw image** → from S3
5. **Gemini analyzes** → generates enhancement prompts
6. **Creates 3 enhanced images** → uploads to S3
7. **Saves to database** → product_images table
8. **Updates product** → status: `pending_review`

## File Structure

```
src/
├── models.py              # Added ProductImage model
├── config.py              # Added SQS & Gemini config
├── sqs_service.py         # NEW: SQS operations
├── gemini_service.py      # NEW: Gemini AI integration
├── worker_thread.py       # NEW: Background worker thread
├── app.py                 # Updated: starts worker thread
└── routes/
    └── products.py        # Updated: sends to SQS

scripts/
├── create_product_images_table.py  # NEW: Create table
├── setup_sqs_queue.py              # NEW: Setup SQS
└── test_image_enhancement.py       # NEW: Test setup
```

## Common Commands

```bash
# Start application (worker starts automatically)
python run.py

# Test configuration
python scripts/test_image_enhancement.py

# Check queue status
aws sqs get-queue-attributes \
  --queue-url YOUR_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages

# Check database
psql $DATABASE_URL -c "SELECT * FROM product_images LIMIT 5;"
```

## Troubleshooting

### Worker not starting?
- Check `.env` has all required variables
- Run: `python scripts/test_image_enhancement.py`
- Look for "Worker thread started" in application logs

### No messages being processed?
- Check SQS_QUEUE_URL is correct
- Verify AWS credentials have SQS permissions
- Check application logs for worker errors

### Gemini errors?
- Verify API key is valid
- Check quota limits at Google AI Studio

### Images not uploading?
- Verify S3 bucket exists
- Check IAM permissions for S3

## Production Deployment

The worker runs as a background thread within the Flask application:

**With Gunicorn:**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
```

**Note:** Each Gunicorn worker will have its own background thread processing messages. This provides automatic scaling and fault tolerance.

## Full Documentation

- [IMAGE_ENHANCEMENT_SETUP.md](IMAGE_ENHANCEMENT_SETUP.md) - Complete system overview
- [WORKER_SETUP.md](WORKER_SETUP.md) - Worker deployment guide

