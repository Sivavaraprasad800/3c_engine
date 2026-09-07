@echo off
:: FRS 3C Engine — One-time Setup
:: Run this ONCE on the client PC to create the Python venv and install packages.
:: After this, run service_install.cmd (as Administrator) to make it auto-start.

setlocal
set APP_DIR=%~dp0

echo.
echo ========================================
echo  FRS 3C Engine — First-Time Setup
echo ========================================
echo.

:: ── Check Python ────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.10-3.12 from python.org
    echo        Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

:: ── Check .env exists ───────────────────────────────────────────────────────
if not exist "%APP_DIR%.env" (
    echo ERROR: .env file not found!
    echo Copy .env.example to .env and fill in your DB credentials and ORG_ID.
    pause
    exit /b 1
)

echo .env found — OK
echo.

:: ── Create venv ─────────────────────────────────────────────────────────────
if not exist "%APP_DIR%venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv "%APP_DIR%venv"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create venv.
        pause
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists — skipping.
)
echo.

:: ── Install packages ────────────────────────────────────────────────────────
echo Installing Python packages (this may take 5-10 minutes)...
"%APP_DIR%venv\Scripts\pip" install --upgrade pip --quiet
"%APP_DIR%venv\Scripts\pip" install -r "%APP_DIR%requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Package installation failed. Check requirements.txt.
    pause
    exit /b 1
)

:: ── Create data dir ─────────────────────────────────────────────────────────
if not exist "%APP_DIR%data" mkdir "%APP_DIR%data"

echo.
echo ========================================
echo  Setup complete!
echo ========================================
echo.
echo  Next step: Run service_install.cmd as Administrator
echo  to register the 24/7 Windows auto-start service.
echo.
echo  OR to run manually right now:
echo    venv\Scripts\python start.py
echo  Then open: http://localhost:8000
echo.
pause
