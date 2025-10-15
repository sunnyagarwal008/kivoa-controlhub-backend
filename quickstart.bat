@echo off
REM Quick Start Script for Product Management API (Windows)

echo ========================================
echo Product Management API - Quick Start
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3 is not installed. Please install Python 3.8 or higher.
    exit /b 1
)

echo [OK] Python 3 found
python --version

REM Create virtual environment
if not exist "venv" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo Installing dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo [OK] Dependencies installed

REM Check if .env exists
if not exist ".env" (
    echo.
    echo Creating .env file from template...
    copy .env.example .env
    echo [OK] .env file created
    echo.
    echo [WARNING] IMPORTANT: Please edit .env file with your actual configuration:
    echo    - Database credentials
    echo    - AWS S3 credentials
    echo    - Secret key
    echo.
    pause
) else (
    echo [OK] .env file already exists
)

REM Initialize database tables
echo.
set /p init_db="Do you want to initialize database tables? (y/n): "
if /i "%init_db%"=="y" (
    echo Initializing database...
    python scripts\init_db.py
)

REM Seed database
echo.
set /p seed_db="Do you want to seed the database with sample data? (y/n): "
if /i "%seed_db%"=="y" (
    echo Seeding database...
    python scripts\seed_data.py
)

REM Done
echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To start the development server, run:
echo   venv\Scripts\activate.bat
echo   python run.py
echo.
echo The API will be available at: http://localhost:5000
echo.
echo Documentation:
echo   - README.md - General information
echo   - SETUP_GUIDE.md - Detailed setup instructions
echo   - API_DOCUMENTATION.md - API endpoint documentation
echo.
pause

