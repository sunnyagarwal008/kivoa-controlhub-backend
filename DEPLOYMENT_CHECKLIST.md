# Deployment Checklist: Image Enhancement System

Use this checklist to ensure proper setup and deployment of the image enhancement system.

## Pre-Deployment Setup

### 1. Dependencies
- [ ] Install Python dependencies: `pip install -r requirements.txt`
- [ ] Verify all packages installed successfully
- [ ] Check Python version (3.8+)

### 2. Database Setup
- [ ] PostgreSQL database is running
- [ ] Database connection string in `.env` is correct
- [ ] Run: `python scripts/create_product_images_table.py`
- [ ] Verify `product_images` table exists:
  ```sql
  \dt product_images
  ```

### 3. AWS SQS Setup
- [ ] AWS credentials configured in `.env`
- [ ] Run: `python scripts/setup_sqs_queue.py`
- [ ] Copy SQS Queue URL to `.env`
- [ ] Verify IAM permissions for SQS (SendMessage, ReceiveMessage, DeleteMessage)
- [ ] Test queue access:
  ```bash
  aws sqs get-queue-attributes --queue-url YOUR_QUEUE_URL --attribute-names All
  ```

### 4. AWS S3 Setup
- [ ] S3 bucket exists
- [ ] S3 bucket name in `.env` is correct
- [ ] IAM permissions for S3 (PutObject, GetObject)
- [ ] Test S3 access:
  ```bash
  aws s3 ls s3://YOUR_BUCKET_NAME
  ```

### 5. Gemini API Setup
- [ ] Visit: https://makersuite.google.com/app/apikey
- [ ] Create API key
- [ ] Add `GEMINI_API_KEY` to `.env`
- [ ] Verify billing is enabled (if required)
- [ ] Test API access (run test script)

### 6. Environment Variables
Verify all required variables in `.env`:
- [ ] `DATABASE_URL`
- [ ] `AWS_ACCESS_KEY_ID`
- [ ] `AWS_SECRET_ACCESS_KEY`
- [ ] `AWS_REGION`
- [ ] `S3_BUCKET_NAME`
- [ ] `SQS_QUEUE_URL`
- [ ] `GEMINI_API_KEY`
- [ ] `GEMINI_MODEL` (default: gemini-1.5-flash)
- [ ] `ENHANCED_IMAGES_COUNT` (default: 3)
- [ ] `SECRET_KEY`

### 7. Configuration Test
- [ ] Run: `python scripts/test_image_enhancement.py`
- [ ] All tests pass (Configuration, Database, SQS, S3, Gemini)
- [ ] Review any warnings or errors

## Development Testing

### 1. Start Application
- [ ] Run: `python run.py`
- [ ] Application starts without errors
- [ ] See log: "Worker thread started"
- [ ] See log: "Queue URL: https://sqs..."

### 2. Test Bulk Upload API
- [ ] Create test product via API
- [ ] API returns success response
- [ ] Product created in database with status "pending"
- [ ] Message sent to SQS queue

### 3. Monitor Worker Processing
- [ ] Worker receives message (check logs)
- [ ] Worker processes product (check logs)
- [ ] Enhanced images uploaded to S3
- [ ] Records created in `product_images` table
- [ ] Product status updated to "pending_review"
- [ ] Message deleted from queue

### 4. Verify Results
- [ ] Check database:
  ```sql
  SELECT * FROM products WHERE status = 'pending_review';
  SELECT * FROM product_images ORDER BY created_at DESC LIMIT 10;
  ```
- [ ] Check S3 bucket for enhanced images
- [ ] Verify image URLs are accessible

## Production Deployment

### 1. Server Setup
- [ ] Production server provisioned
- [ ] Python 3.8+ installed
- [ ] PostgreSQL client installed
- [ ] Git installed
- [ ] Firewall configured (allow port 5000 or your port)

### 2. Application Deployment
- [ ] Clone repository to server
- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Copy `.env` file with production values
- [ ] Test database connection
- [ ] Run configuration test

### 3. Gunicorn Setup
- [ ] Install Gunicorn: `pip install gunicorn`
- [ ] Test Gunicorn:
  ```bash
  gunicorn -w 4 -b 0.0.0.0:5000 "src.app:create_app()"
  ```
- [ ] Verify worker threads start (check logs)
- [ ] Test API endpoints

### 4. Systemd Service (Recommended)
- [ ] Create service file: `/etc/systemd/system/flask-app.service`
- [ ] Configure service (see WORKER_SETUP.md)
- [ ] Enable service: `sudo systemctl enable flask-app`
- [ ] Start service: `sudo systemctl start flask-app`
- [ ] Check status: `sudo systemctl status flask-app`
- [ ] Verify logs: `sudo journalctl -u flask-app -f`

### 5. Nginx/Reverse Proxy (Optional)
- [ ] Install Nginx
- [ ] Configure reverse proxy to Gunicorn
- [ ] Setup SSL/TLS certificate
- [ ] Test HTTPS access

### 6. Monitoring Setup
- [ ] Configure application logging
- [ ] Setup log rotation
- [ ] Configure monitoring alerts
- [ ] Setup health check endpoint monitoring
- [ ] Configure SQS queue monitoring (CloudWatch)

## Post-Deployment Verification

### 1. Application Health
- [ ] Application is running
- [ ] Health endpoint responds: `GET /api/health`
- [ ] Worker thread is active (check logs)
- [ ] No errors in logs

### 2. Functionality Test
- [ ] Create test products via bulk API
- [ ] Verify products created in database
- [ ] Verify messages sent to SQS
- [ ] Verify worker processes messages
- [ ] Verify enhanced images created
- [ ] Verify product status updated

### 3. Performance Check
- [ ] API response time acceptable
- [ ] Worker processing time reasonable
- [ ] Database queries optimized
- [ ] S3 upload/download speed acceptable

### 4. Error Handling
- [ ] Test with invalid product data
- [ ] Test with invalid image URL
- [ ] Test with network issues
- [ ] Verify error logging
- [ ] Verify SQS message retry

## Scaling Considerations

### 1. Horizontal Scaling
- [ ] Determine optimal number of Gunicorn workers
- [ ] Test with multiple workers
- [ ] Verify message distribution across workers
- [ ] Monitor resource usage (CPU, memory)

### 2. Queue Management
- [ ] Set appropriate SQS visibility timeout
- [ ] Configure dead letter queue (optional)
- [ ] Monitor queue depth
- [ ] Set up CloudWatch alarms

### 3. Cost Optimization
- [ ] Review Gemini API usage and costs
- [ ] Review SQS costs
- [ ] Review S3 storage costs
- [ ] Optimize image sizes if needed
- [ ] Consider caching strategies

## Maintenance

### 1. Regular Checks
- [ ] Monitor application logs daily
- [ ] Check SQS queue depth
- [ ] Review error rates
- [ ] Monitor API response times
- [ ] Check disk space

### 2. Database Maintenance
- [ ] Regular backups configured
- [ ] Backup restoration tested
- [ ] Database vacuum/analyze scheduled
- [ ] Monitor database size

### 3. Updates
- [ ] Keep dependencies updated
- [ ] Monitor security advisories
- [ ] Test updates in staging first
- [ ] Document changes

## Troubleshooting Reference

### Worker Not Processing
1. Check application logs
2. Verify SQS_QUEUE_URL is correct
3. Check AWS credentials
4. Verify IAM permissions
5. Check queue has messages

### Gemini API Errors
1. Verify API key is valid
2. Check quota limits
3. Review error messages in logs
4. Check billing status

### S3 Upload Failures
1. Verify bucket exists
2. Check IAM permissions
3. Verify bucket region
4. Check network connectivity

### Database Issues
1. Check connection string
2. Verify database is running
3. Check table exists
4. Review database logs

## Emergency Contacts

- [ ] Document on-call contacts
- [ ] Document escalation procedures
- [ ] Document rollback procedures
- [ ] Document backup restoration procedures

## Sign-off

- [ ] Development testing complete
- [ ] Production deployment complete
- [ ] Post-deployment verification complete
- [ ] Documentation updated
- [ ] Team trained on new system

**Deployed by:** _______________  
**Date:** _______________  
**Version:** _______________  

---

For detailed information, refer to:
- [IMAGE_ENHANCEMENT_SETUP.md](IMAGE_ENHANCEMENT_SETUP.md)
- [WORKER_SETUP.md](WORKER_SETUP.md)
- [QUICK_START_IMAGE_ENHANCEMENT.md](QUICK_START_IMAGE_ENHANCEMENT.md)

