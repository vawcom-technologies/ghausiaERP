@echo off
echo ============================================
echo Textile Factory ERP - Windows Setup
echo ============================================

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.12 or newer from https://www.python.org/
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing requirements...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
)

if not exist logs mkdir logs
if not exist backups mkdir backups

echo Running migrations...
python manage.py migrate
if errorlevel 1 (
    echo ERROR: Migrations failed.
    pause
    exit /b 1
)

echo Collecting static files...
python manage.py collectstatic --noinput

echo.
echo ============================================
echo Setup complete!
echo ============================================
echo.
echo Next steps:
echo   1. Create a superuser: python manage.py createsuperuser
echo   2. Optional demo data:  python manage.py seed_demo_data
echo   3. Start the system:    start_windows.bat
echo.
echo To allow other factory computers to connect:
echo   Edit .env and add your PC IP to ALLOWED_HOSTS
echo   Example: ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
echo.
set /p CREATE_SUPER="Create superuser now? (y/n): "
if /i "%CREATE_SUPER%"=="y" (
    python manage.py createsuperuser
)

pause
