@echo off
echo ============================================
echo Textile Factory ERP - Starting Server
echo ============================================

if not exist .venv (
    echo ERROR: Virtual environment not found. Run setup_windows.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo Starting Waitress on 0.0.0.0:8000 ...
echo.
echo Local access:    http://127.0.0.1:8000
echo Network access:  http://YOUR-PC-IP:8000
echo.
echo Press Ctrl+C to stop the server.
echo.

waitress-serve --listen=0.0.0.0:8000 config.wsgi:application
if errorlevel 1 (
    echo.
    echo ERROR: Server failed to start.
    pause
)
