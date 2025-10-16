# Product Image Enhancement System

## Overview

This system automatically enhances product images using AI when products are created via the bulk upload API. The workflow is:

1. **Bulk Create API** → Creates products and sends product IDs to SQS queue
2. **SQS Queue** → Holds product IDs for processing
3. **Worker Thread** → Runs as part of the Flask application, listens to queue, processes each product:
   - Fetches product from database
   - Downloads raw image
   - Uses Gemini AI to analyze and generate enhancement prompts
   - Creates configured number of enhanced images
   - Uploads enhanced images to S3
   - Saves image URLs to `product_images` table
   - Updates product status to `pending_review`

**Note:** The worker runs automatically as a background thread when the Flask application starts. No separate process needed!

## Architecture

```
┌─────────────────┐
│  Bulk Create    │
│      API        │
└────────┬────────┘
         │ Creates products
         │ Sends product_ids
         ▼
┌─────────────────┐
│   SQS Queue     │
│  (AWS SQS)      │
└────────┬────────┘
         │ Messages
         ▼
┌─────────────────┐
│  Worker Thread  │
│ (Background)    │
└────────┬────────┘
         │
         ├──► Fetch Product (Database)
         │
         ├──► Download Raw Image (S3)
         │
         ├──► Analyze with Gemini AI
         │
         ├──► Generate Enhanced Images
         │
         ├──► Upload to S3
         │
         └──► Save to product_images table
              Update product status
```

## Database Schema

### products table
- `id` (Primary Key)
- `category`
- `raw_image` (S3 URL)
- `mrp`, `price`, `discount`, `gst`
- `status` (pending → pending_review → approved/rejected)
- `created_at`, `updated_at`

### product_images table (NEW)
- `id` (Primary Key)
- `product_id` (Foreign Key → products.id)
- `image_url` (S3 URL of enhanced image)
- `status` (pending, approved, rejected)
- `created_at`, `updated_at`

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- `google-generativeai` - Gemini AI SDK
- `Pillow` - Image processing
- `requests` - HTTP requests

### 2. Create Product Images Table

```bash
python scripts/create_product_images_table.py
```

### 3. Set Up AWS SQS Queue

**Option A: Automatic (Recommended)**
```bash
python scripts/setup_sqs_queue.py
```

**Option B: Manual**
1. Go to AWS SQS Console
2. Create a new Standard queue named `product-image-processing`
3. Configure:
   - Visibility timeout: 300 seconds
   - Message retention: 4 days
   - Receive message wait time: 20 seconds
4. Copy the Queue URL

### 4. Get Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key

### 5. Update Environment Variables

Add to your `.env` file:

```env
# AWS SQS Configuration
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/product-image-processing

# Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-1.5-flash

# Image Enhancement Configuration
ENHANCED_IMAGES_COUNT=3
```

### 6. Start the Application

The worker thread starts automatically when you run the Flask application:

**Development:**
```bash
python run.py
```

**Production (with Gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
```

The worker thread will start automatically in the background and begin processing messages from the SQS queue.

## API Changes

### Bulk Create Products API

**Endpoint:** `POST /api/products/bulk`

**New Behavior:**
- Creates products with status `pending`
- Sends each product_id to SQS queue
- Returns immediately (doesn't wait for processing)
- Worker processes products asynchronously

**Response:**
```json
{
    "success": true,
    "message": "Successfully created 5 products and queued for processing",
    "data": {
        "created": 5,
        "total": 5,
        "products": [...]
    }
}
```

## Configuration Options

### ENHANCED_IMAGES_COUNT
Number of enhanced images to generate per product.
- Default: `3`
- Recommended: `3-5`
- Range: `1-10`

### GEMINI_MODEL
Gemini model to use for image analysis.
- `gemini-1.5-flash` - Faster, cheaper (default)
- `gemini-1.5-pro` - More accurate, more expensive

## Monitoring

### Check Worker Status

The worker runs as a background thread within the Flask application. Check the application logs:

```bash
# Development mode - check console output
# The worker will log messages like:
# "Worker thread started"
# "Received message for product_id: 123"
# "Successfully processed product 123"

# Production mode with Gunicorn - check logs
tail -f /var/log/gunicorn/error.log

# Or if using systemd
sudo journalctl -u your-flask-app -f
```

### Check Queue Status

```bash
aws sqs get-queue-attributes \
    --queue-url YOUR_QUEUE_URL \
    --attribute-names ApproximateNumberOfMessages
```

### Check Database

```sql
-- Products pending review
SELECT COUNT(*) FROM products WHERE status = 'pending_review';

-- Recent enhanced images
SELECT pi.*, p.category 
FROM product_images pi
JOIN products p ON pi.product_id = p.id
ORDER BY pi.created_at DESC
LIMIT 10;
```

## Workflow Example

1. **Client uploads products:**
```bash
curl -X POST http://localhost:5000/api/products/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {
        "category": "Electronics",
        "raw_image": "https://kivoa.s3.ap-south-1.amazonaws.com/raw/phone.jpg",
        "mrp": 50000,
        "price": 45000,
        "discount": 5000,
        "gst": 18
      }
    ]
  }'
```

2. **API Response (immediate):**
```json
{
  "success": true,
  "message": "Successfully created 1 products and queued for processing",
  "data": {
    "created": 1,
    "total": 1,
    "products": [{"id": 123, "status": "pending", ...}]
  }
}
```

3. **Worker processes (async):**
- Receives message from SQS
- Fetches product #123
- Downloads raw image
- Generates 3 enhanced images using Gemini
- Uploads to S3: `enhanced/123/uuid1.jpg`, `enhanced/123/uuid2.jpg`, `enhanced/123/uuid3.jpg`
- Creates 3 records in `product_images` table
- Updates product status to `pending_review`

4. **Result:**
```sql
-- Product updated
SELECT * FROM products WHERE id = 123;
-- status = 'pending_review'

-- Enhanced images created
SELECT * FROM product_images WHERE product_id = 123;
-- 3 rows with image URLs
```

## Troubleshooting

### Worker not processing messages
- Check SQS_QUEUE_URL is correct
- Verify AWS credentials have SQS permissions
- Check worker logs for errors

### Gemini API errors
- Verify GEMINI_API_KEY is valid
- Check API quota limits
- Ensure billing is enabled

### Images not uploading to S3
- Verify S3 bucket exists
- Check IAM permissions for S3
- Ensure bucket region matches AWS_REGION

## Cost Estimates

### AWS SQS
- ~$0.40 per million requests
- For 1000 products/day: ~$0.01/day

### Gemini API
- Varies by model and usage
- gemini-1.5-flash: ~$0.10 per 1000 images analyzed

### AWS S3
- Storage: ~$0.023 per GB/month
- For 1000 products × 3 images × 500KB: ~$0.03/month

## Next Steps

1. **Install dependencies:** `pip install -r requirements.txt`
2. **Create table:** `python scripts/create_product_images_table.py`
3. **Setup SQS:** `python scripts/setup_sqs_queue.py`
4. **Configure .env:** Add SQS_QUEUE_URL and GEMINI_API_KEY
5. **Start worker:** `python -m src.worker`
6. **Test:** Create products via bulk API

For detailed worker deployment, see [WORKER_SETUP.md](WORKER_SETUP.md)

