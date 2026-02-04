@echo off
chcp 65001 >nul
:: DataHubSync Windows Service Installation Script
:: Requires nssm to be installed (https://nssm.cc/download)
:: Run as Administrator

echo ==========================================
echo DataHubSync Service Installation
echo ==========================================

:: Check if running as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Check if nssm is available
where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo WARNING: nssm not found in PATH
    echo Please ensure nssm is installed and in PATH
    echo Download from: https://nssm.cc/download
    pause
    exit /b 1
)

:: Configuration
set "SERVICE_NAME=DataHubSync"
set "WORK_DIR=C:\DataHubSync"
set "LOG_DIR=%WORK_DIR%\logs"
set "LOG_FILE=%LOG_DIR%\service.log"

:: Check if working directory exists
if not exist "%WORK_DIR%" (
    echo ERROR: Working directory does not exist: %WORK_DIR%
    echo Please deploy DataHubSync to %WORK_DIR% first
    pause
    exit /b 1
)

:: Create logs directory if not exists
if not exist "%LOG_DIR%" (
    echo Creating logs directory...
    mkdir "%LOG_DIR%"
)

:: Check if service already exists
nssm status %SERVICE_NAME% >nul 2>&1
if %errorLevel% equ 0 (
    echo Service %SERVICE_NAME% already exists
    echo Stopping existing service...
    nssm stop %SERVICE_NAME%
    timeout /t 2 >nul
    echo Removing existing service...
    nssm remove %SERVICE_NAME% confirm
)

:: Install service
echo.
echo Installing service %SERVICE_NAME%...
nssm install %SERVICE_NAME% "%WORK_DIR%\python.exe"
nssm set %SERVICE_NAME% AppDirectory "%WORK_DIR%"
nssm set %SERVICE_NAME% AppParameters "server.py"
nssm set %SERVICE_NAME% DisplayName "DataHubSync Service"
nssm set %SERVICE_NAME% Description "DataHubSync - Data synchronization service for hub endpoints"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

:: Configure logging
nssm set %SERVICE_NAME% AppStdout "%LOG_FILE%"
nssm set %SERVICE_NAME% AppStderr "%LOG_FILE%"
nssm set %SERVICE_NAME% AppStdoutCreationDisposition 2
nssm set %SERVICE_NAME% AppStderrCreationDisposition 2
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateOnline 0
nssm set %SERVICE_NAME% AppRotateSeconds 86400
nssm set %SERVICE_NAME% AppRotateBytes 10485760

:: Configure process
nssm set %SERVICE_NAME% AppNoConsole 1
nssm set %SERVICE_NAME% AppPriority NORMAL_PRIORITY_CLASS

if %errorLevel% neq 0 (
    echo ERROR: Failed to install service
    pause
    exit /b 1
)

echo.
echo Service installed successfully!

:: Start service
echo Starting service...
nssm start %SERVICE_NAME%

if %errorLevel% neq 0 (
    echo WARNING: Service installed but failed to start
    echo Check logs at: %LOG_FILE%
) else (
    echo Service started successfully!
)

echo.
echo ==========================================
echo Installation Complete
echo ==========================================
echo Service Name: %SERVICE_NAME%
echo Working Dir:  %WORK_DIR%
echo Log File:     %LOG_FILE%
echo.
echo To manage the service:
echo   - View status: nssm status %SERVICE_NAME%
echo   - Stop:        nssm stop %SERVICE_NAME%
echo   - Start:       nssm start %SERVICE_NAME%
echo   - Restart:     nssm restart %SERVICE_NAME%
echo   - Remove:      run uninstall_service.bat
echo.
pause
