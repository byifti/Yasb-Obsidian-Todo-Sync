@echo off
:: ============================================================
::  setup.bat — Obsidian ↔ YASB Todo Sync — First-time setup
::  Run this ONCE as Administrator to:
::    1. Install the watchdog Python dependency
::    2. Register sync.py as a Task Scheduler startup task
:: ============================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT=%SCRIPT_DIR%sync.py"
set "CONFIG=%SCRIPT_DIR%config.ini"
set "TASK_NAME=ObsidianYasbTodoSync"

echo.
echo  Obsidian ^<^-^> YASB Todo Sync — Setup
echo  ========================================
echo.

:: ── Check config.ini has been filled in ─────────────────────
for /f "eol=# tokens=*" %%A in ("%CONFIG%") do (
    echo %%A | findstr /C:"<username>" >nul 2>&1
    if !errorlevel! equ 0 goto :placeholder_found
    echo %%A | findstr /C:"C:\path\to\your" >nul 2>&1
    if !errorlevel! equ 0 goto :placeholder_found
)
goto :check_passed

:placeholder_found
echo  ERROR: config.ini still has placeholder paths.
echo  Please open config.ini and fill in your paths first.
echo  File location: %CONFIG%
echo.
pause
exit /b 1

:check_passed

:: ── 1. Install watchdog ──────────────────────────────────────
echo  [1/2] Checking Python dependency (watchdog)...
pip show watchdog >nul 2>&1
if %errorlevel% equ 0 (
    echo        Already installed, skipping.
) else (
    pip install watchdog --quiet
    if %errorlevel% neq 0 (
        echo  ERROR: pip install failed.
        echo  Make sure Python 3.7+ is installed and added to your PATH.
        echo  Download Python at https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo        Done.
)
echo.

:: ── 2. Register Task Scheduler task ─────────────────────────
echo  [2/2] Registering startup task in Task Scheduler...

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "pythonw \"%SCRIPT%\"" ^
  /sc ONLOGON ^
  /delay 0000:30 ^
  /rl HIGHEST ^
  /f >nul

if %errorlevel% neq 0 (
    echo  ERROR: Failed to create scheduled task.
    echo  Make sure you are running this script as Administrator.
    pause
    exit /b 1
)

echo        Done.
echo.
echo  ========================================
echo  Setup complete!
echo.
echo  The sync script will start automatically on next login.
echo  To start it right now without rebooting, run start_sync.bat
echo.
pause
endlocal
