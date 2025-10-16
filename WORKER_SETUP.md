# SQS Worker Setup Guide

This guide explains the SQS worker that processes product image enhancements.

## Overview

The worker runs as a **background thread** within the Flask application. It automatically starts when the application starts and listens to an AWS SQS queue for product IDs, processing each product by:
1. Fetching the product from the database
2. Downloading the raw image
3. Using Gemini AI to generate enhancement prompts
4. Creating enhanced images (configurable count)
5. Uploading enhanced images to S3
6. Saving image URLs to the `product_images` table
7. Updating product status to `pending_review`

## Prerequisites

1. **AWS SQS Queue**: Create an SQS queue in AWS
2. **Gemini API Key**: Get an API key from Google AI Studio
3. **Database**: Ensure the `product_images` table exists

## Setup Steps

### 1. Create AWS SQS Queue

```bash
# Using AWS CLI
aws sqs create-queue --queue-name product-image-processing

# Note the QueueUrl from the response
```

Or create it through the AWS Console:
- Go to AWS SQS
- Click "Create queue"
- Choose "Standard" queue type
- Name it `product-image-processing`
- Configure visibility timeout (recommended: 300 seconds)
- Configure message retention (recommended: 4 days)
- Copy the Queue URL

### 2. Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the API key

### 3. Update Environment Variables

Add the following to your `.env` file:

```env
# AWS SQS Configuration
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/product-image-processing

# Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-1.5-flash

# Image Enhancement Configuration
ENHANCED_IMAGES_COUNT=3
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Create Product Images Table

```bash
python scripts/create_product_images_table.py
```

### 6. Configure IAM Permissions

Ensure your AWS IAM user/role has the following SQS permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sqs:SendMessage",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes"
            ],
            "Resource": "arn:aws:sqs:us-east-1:123456789012:product-image-processing"
        }
    ]
}
```

## Running the Worker

The worker runs automatically as a background thread when you start the Flask application.

### Development Mode

```bash
python run.py
```

The worker thread will start automatically and you'll see log messages like:
```
Worker thread started
Queue URL: https://sqs...
Enhanced images count: 3
```

### Production Mode with Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
```

**Important:** Each Gunicorn worker process will have its own background thread processing SQS messages. This provides:
- **Automatic scaling**: More workers = more concurrent processing
- **Fault tolerance**: If one worker crashes, others continue processing
- **Load distribution**: SQS automatically distributes messages across workers

### Production Mode with systemd

Create a systemd service file `/etc/systemd/system/flask-app.service`:

```ini
[Unit]
Description=Flask Product Management API
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/kivoa-controlhub-backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable flask-app
sudo systemctl start flask-app
sudo systemctl status flask-app
```

## Monitoring

### Check Worker Logs

The worker logs are part of the Flask application logs:

```bash
# Development mode
# Check console output for messages like:
# "Worker thread started"
# "Received message for product_id: 123"
# "Successfully processed product 123"

# Production with Gunicorn
tail -f /var/log/gunicorn/error.log

# If using systemd
sudo journalctl -u flask-app -f

# Filter for worker-specific logs
sudo journalctl -u flask-app -f | grep -i worker
```

### Check SQS Queue

```bash
# Get queue attributes
aws sqs get-queue-attributes \
    --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/product-image-processing \
    --attribute-names All
```

### Monitor Database

```sql
-- Check products being processed
SELECT id, category, status, created_at 
FROM products 
WHERE status = 'pending_review';

-- Check enhanced images
SELECT pi.id, pi.product_id, pi.image_url, pi.status, pi.created_at
FROM product_images pi
JOIN products p ON pi.product_id = p.id
ORDER BY pi.created_at DESC
LIMIT 10;
```

## Configuration Options

### ENHANCED_IMAGES_COUNT

Controls how many enhanced images to generate per product.

- Default: `3`
- Recommended: `3-5`
- Maximum: `10` (to avoid excessive API costs)

### GEMINI_MODEL

The Gemini model to use for image analysis.

- Default: `gemini-1.5-flash` (faster, cheaper)
- Alternative: `gemini-1.5-pro` (more accurate, more expensive)

## Troubleshooting

### Worker Not Receiving Messages

1. Check SQS queue URL is correct
2. Verify AWS credentials have SQS permissions
3. Check queue has messages: `aws sqs get-queue-attributes --queue-url <url> --attribute-names ApproximateNumberOfMessages`

### Gemini API Errors

1. Verify API key is correct
2. Check API quota limits
3. Ensure billing is enabled in Google Cloud

### S3 Upload Failures

1. Verify S3 bucket exists
2. Check IAM permissions for S3
3. Ensure bucket region matches configuration

### Database Errors

1. Verify database connection
2. Check `product_images` table exists
3. Ensure foreign key constraints are satisfied

## Scaling

### Multiple Workers with Gunicorn

Simply increase the number of Gunicorn workers:

```bash
# 8 workers = 8 background threads processing messages
gunicorn -w 8 -b 0.0.0.0:5000 "src.app:create_app()"
```

Each worker process has its own background thread, so:
- 4 workers = 4 concurrent message processors
- 8 workers = 8 concurrent message processors

SQS automatically distributes messages among all threads.

### Auto-scaling with Docker

Use Docker Compose to scale the application:

```yaml
version: '3.8'

services:
  app:
    build: .
    command: gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
    env_file:
      - .env
    ports:
      - "5000:5000"
    deploy:
      replicas: 3
```

Then:
```bash
docker-compose up --scale app=3
```

This gives you 3 containers × 4 workers = 12 concurrent message processors!

## Cost Considerations

- **SQS**: ~$0.40 per million requests
- **Gemini API**: Varies by model and usage
- **S3**: Storage + data transfer costs

Monitor your usage and set up billing alerts in AWS and Google Cloud.

