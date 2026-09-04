@echo off
REM sync_to_drive.bat — Synchronize local NLP_rs to Google Drive NLP_rspaper

set "LOCAL_DIR=%~dp0..\.."
set "DRIVE_DIR=G:\My Drive\NLP_rspaper"

echo ======================================================================
echo IPC2BNS-Verify: Google Drive Synchronization Tool
echo Local : %LOCAL_DIR%
echo Target: %DRIVE_DIR%
echo ======================================================================

if not exist "%DRIVE_DIR%" (
    echo [ERROR] Google Drive folder not found at: %DRIVE_DIR%
    echo Please make sure Google Drive for Desktop is running and logged in.
    pause
    exit /b 1
)

echo Synchronizing files with robocopy (excluding temp & cache files)...
robocopy "%LOCAL_DIR%" "%DRIVE_DIR%" /MIR /XD .git .pytest_cache .qodo __pycache__ /XF *.tmp *.log

echo.
echo ======================================================================
echo [SUCCESS] Synchronization to Google Drive completed!
echo ======================================================================
pause
