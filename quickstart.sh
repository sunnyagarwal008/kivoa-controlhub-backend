#!/bin/bash

# Quick Start Script for Product Management API
# This script sets up the development environment

set -e

echo "🚀 Product Management API - Quick Start"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL is not installed. Please install PostgreSQL 12 or higher."
    echo "   macOS: brew install postgresql"
    echo "   Ubuntu: sudo apt-get install postgresql"
    exit 1
fi

echo "✓ PostgreSQL found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚙️  Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file with your actual configuration:"
    echo "   - Database credentials"
    echo "   - AWS S3 credentials"
    echo "   - Secret key"
    echo ""
    read -p "Press Enter after you've configured .env file..."
else
    echo "✓ .env file already exists"
fi

# Create database (optional)
echo ""
read -p "Do you want to create the PostgreSQL database? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter database name (default: product_db): " db_name
    db_name=${db_name:-product_db}
    
    read -p "Enter database user (default: product_user): " db_user
    db_user=${db_user:-product_user}
    
    read -sp "Enter database password: " db_password
    echo ""
    
    echo "Creating database..."
    psql postgres -c "CREATE DATABASE $db_name;" 2>/dev/null || echo "Database may already exist"
    psql postgres -c "CREATE USER $db_user WITH PASSWORD '$db_password';" 2>/dev/null || echo "User may already exist"
    psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;" 2>/dev/null
    echo "✓ Database setup complete"
fi

# Initialize database tables
echo ""
read -p "Do you want to initialize database tables? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Initializing database..."
    python scripts/init_db.py
fi

# Seed database
echo ""
read -p "Do you want to seed the database with sample data? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Seeding database..."
    python scripts/seed_data.py
fi

# Done
echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the development server, run:"
echo "  source venv/bin/activate"
echo "  python run.py"
echo ""
echo "The API will be available at: http://localhost:5000"
echo ""
echo "📚 Documentation:"
echo "  - README.md - General information"
echo "  - SETUP_GUIDE.md - Detailed setup instructions"
echo "  - API_DOCUMENTATION.md - API endpoint documentation"
echo ""

