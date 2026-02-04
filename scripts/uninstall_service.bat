@echo off
chcp 65001 >nul
:: DataHubSync Windows Service Uninstallation Script
:: Run as Administrator

echo ==========================================
echo DataHubSync Service Uninstallation
echo ==========================================

:: Check if running as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Configuration
set "SERVICE_NAME=DataHubSync"

:: Check if service exists
nssm status %SERVICE_NAME% >nul 2>&1
if %errorLevel% neq 0 (
    echo Service %SERVICE_NAME% does not exist
    echo Nothing to uninstall
    pause
    exit /b 0
)

echo Found service: %SERVICE_NAME%

:: Get service status
for /f "tokens=*" %%a in ('nssm status %SERVICE_NAME%') do set "SERVICE_STATUS=%%a"
echo Current status: %SERVICE_STATUS%

:: Stop service if running
echo.
echo Stopping service...
nssm stop %SERVICE_NAME%
timeout /t 3 >nul

:: Remove service
echo Removing service...
nssm remove %SERVICE_NAME% confirm

if %errorLevel% neq 0 (
    echo ERROR: Failed to remove service
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Uninstallation Complete
echo ==========================================
echo Service %SERVICE_NAME% has been removed
echo.
pause
