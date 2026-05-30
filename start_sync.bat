@echo off
:: start_sync.bat — Start the sync script silently in the background
:: Run this manually any time, or let Task Scheduler call it on login.

set "SCRIPT=%~dp0sync.py"

:: Check config.ini exists before launching
if not exist "%~dp0config.ini" (
    echo ERROR: config.ini not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

:: pythonw runs Python without a console window
start "" /B pythonw "%SCRIPT%"

echo Sync started in background.
echo Log: %~dp0sync.log
timeout /t 2 >nul
