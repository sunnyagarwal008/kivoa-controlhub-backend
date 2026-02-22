import os
from dotenv import load_dotenv

# Load .env file and override system environment variables
load_dotenv(override=True)


class Config:
    """Base configuration class"""

    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    CDN_DOMAIN = os.getenv('CDN_DOMAIN')

    # S3 Presigned URL Configuration
    PRESIGNED_URL_EXPIRATION = int(os.getenv('PRESIGNED_URL_EXPIRATION', 3600))

    # AWS SQS Configuration
    SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')
    CATALOG_SYNC_QUEUE_URL = os.getenv('CATALOG_SYNC_QUEUE_URL')

    # Gemini API Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')

    # Image Enhancement Configuration
    ENHANCED_IMAGES_COUNT = int(os.getenv('ENHANCED_IMAGES_COUNT', 3))

    # Shopify Configuration
    SHOPIFY_STORE_URL = os.getenv('SHOPIFY_STORE_URL')
    SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
    SHOPIFY_API_VERSION = os.getenv('SHOPIFY_API_VERSION', '2024-07')

    # Amazon Seller Central Configuration (India)
    AMAZON_SELLER_ID = os.getenv('AMAZON_SELLER_ID')
    AMAZON_MARKETPLACE_ID = os.getenv('AMAZON_MARKETPLACE_ID', 'A21TJRUUN4KGV')  # India marketplace
    AMAZON_LWA_CLIENT_ID = os.getenv('AMAZON_LWA_CLIENT_ID')
    AMAZON_LWA_CLIENT_SECRET = os.getenv('AMAZON_LWA_CLIENT_SECRET')
    AMAZON_LWA_REFRESH_TOKEN = os.getenv('AMAZON_LWA_REFRESH_TOKEN')
    AMAZON_AWS_ACCESS_KEY = os.getenv('AMAZON_AWS_ACCESS_KEY')
    AMAZON_AWS_SECRET_KEY = os.getenv('AMAZON_AWS_SECRET_KEY')
    AMAZON_REGION = os.getenv('AMAZON_REGION', 'eu-west-1')  # Europe region for India marketplace
    AMAZON_ENDPOINT = os.getenv('AMAZON_ENDPOINT', 'https://sellingpartnerapi-eu.amazon.com')

    # JSON Configuration
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
