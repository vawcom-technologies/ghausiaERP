@echo off
echo ============================================
echo Textile Factory ERP - Database Backup
echo ============================================

if not exist backups mkdir backups

if not exist db.sqlite3 (
    echo WARNING: Database file db.sqlite3 not found!
    pause
    exit /b 1
)

for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set MYDATE=%%a-%%b-%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set MYTIME=%%a-%%b
set BACKUP_FILE=backups\db_backup_%MYDATE%_%MYTIME%.sqlite3

copy db.sqlite3 "%BACKUP_FILE%"
if errorlevel 1 (
    echo ERROR: Backup failed.
    pause
    exit /b 1
)

echo Backup saved to: %BACKUP_FILE%
echo The application can continue running during backup.
pause
