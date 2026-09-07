@echo off
:: FRS 3C Engine — Windows Service Installer
:: Run this ONCE as Administrator on the client PC.
:: After this, the FRS server starts automatically on every Windows boot.

setlocal

:: ── Config ──────────────────────────────────────────────────────────────────
set SERVICE_NAME=FRS_3C_Engine
set APP_DIR=%~dp0
set PYTHON_EXE=%APP_DIR%venv\Scripts\python.exe
set START_SCRIPT=%APP_DIR%start.py
set NSSM_URL=https://nssm.cc/release/nssm-2.24.zip
set NSSM_DIR=%APP_DIR%nssm

:: ── Check Admin ─────────────────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Run this script as Administrator.
    echo Right-click service_install.cmd ^> Run as Administrator
    pause
    exit /b 1
)

echo.
echo ========================================
echo  FRS 3C Engine — Service Installer
echo ========================================
echo.
echo APP DIR  : %APP_DIR%
echo SERVICE  : %SERVICE_NAME%
echo PYTHON   : %PYTHON_EXE%
echo.

:: ── Check venv exists ───────────────────────────────────────────────────────
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python venv not found at %PYTHON_EXE%
    echo Run install.cmd first to set up the environment.
    pause
    exit /b 1
)

:: ── Download NSSM if not present ────────────────────────────────────────────
if not exist "%NSSM_DIR%\nssm.exe" (
    echo Downloading NSSM service manager...
    mkdir "%NSSM_DIR%" 2>nul
    powershell -Command "Invoke-WebRequest -Uri '%NSSM_URL%' -OutFile '%NSSM_DIR%\nssm.zip'"
    powershell -Command "Expand-Archive -Path '%NSSM_DIR%\nssm.zip' -DestinationPath '%NSSM_DIR%' -Force"
    copy /Y "%NSSM_DIR%\nssm-2.24\win64\nssm.exe" "%NSSM_DIR%\nssm.exe" >nul
    echo NSSM downloaded.
)

set NSSM=%NSSM_DIR%\nssm.exe

:: ── Remove old service if exists ────────────────────────────────────────────
sc query "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo Removing existing service...
    "%NSSM%" stop "%SERVICE_NAME%" >nul 2>&1
    "%NSSM%" remove "%SERVICE_NAME%" confirm >nul 2>&1
)

:: ── Install service ─────────────────────────────────────────────────────────
echo Installing Windows service...
"%NSSM%" install "%SERVICE_NAME%" "%PYTHON_EXE%" "%START_SCRIPT%"
"%NSSM%" set "%SERVICE_NAME%" AppDirectory "%APP_DIR%"
"%NSSM%" set "%SERVICE_NAME%" AppStdout "%APP_DIR%data\frs_service.log"
"%NSSM%" set "%SERVICE_NAME%" AppStderr "%APP_DIR%data\frs_service_err.log"
"%NSSM%" set "%SERVICE_NAME%" AppRotateFiles 1
"%NSSM%" set "%SERVICE_NAME%" AppRotateBytes 10485760
"%NSSM%" set "%SERVICE_NAME%" Start SERVICE_AUTO_START
"%NSSM%" set "%SERVICE_NAME%" ObjectName LocalSystem

:: ── Start service ────────────────────────────────────────────────────────────
echo Starting service...
"%NSSM%" start "%SERVICE_NAME%"

echo.
echo ========================================
echo  Service installed and started!
echo ========================================
echo.
echo  Dashboard: http://localhost:8000
echo  Status:    sc query %SERVICE_NAME%
echo  Logs:      %APP_DIR%data\frs_service.log
echo  Stop:      sc stop %SERVICE_NAME%
echo  Start:     sc start %SERVICE_NAME%
echo  Uninstall: %NSSM% remove %SERVICE_NAME% confirm
echo.
pause
