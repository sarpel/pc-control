@echo off
REM PC Voice Controller - PC Agent Startup Script for Windows
REM This script starts the PC backend service with proper configuration

setlocal enabledelayedexpansion

REM Configuration
set PYTHON_MIN_VERSION=3.10
set SERVICE_NAME=pc-agent
set DEFAULT_HOST=0.0.0.0
set DEFAULT_PORT=8765
set CONFIG_DIR=%USERPROFILE%\.pc-voice-control
set CERT_DIR=%CONFIG_DIR%\certificates
set LOG_DIR=%CONFIG_DIR%\logs

set SCRIPT_DIR=%~dp0
for %%a in ("%~dp0..\pc-agent\src") do set "SRC_DIR=%%~fa"

REM Colors for output
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
for /F "delims=" %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"

set "BLUE=%ESC%[94m"
set "NC=%ESC%[0m"

REM Program flow
goto :main

REM Helper functions
:log_info
echo %BLUE%[INFO]%NC% %~1
goto :eof

:log_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:log_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:log_error
echo %RED%[ERROR]%NC% %~1
goto :eof

REM Check Python version
:check_python
call :log_info "Checking Python version..."

python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        call :log_error "Python is not installed. Please install Python %PYTHON_MIN_VERSION% or later."
        pause
        exit /b 1
    )
    set PYTHON_CMD=python3
) else (
    set PYTHON_CMD=python
)

for /f "tokens=2" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set MAJOR_VERSION=%%a
    set MINOR_VERSION=%%b
)

if %MAJOR_VERSION% gtr 3 goto version_ok
if %MAJOR_VERSION% lss 3 goto version_error
if %MINOR_VERSION% geq 10 goto version_ok

:version_error
call :log_error "Python %PYTHON_MIN_VERSION% or later is required. Found version %PYTHON_VERSION%"
pause
exit /b 1

:version_ok
call :log_success "Python %PYTHON_VERSION% detected"
goto :eof

REM Create necessary directories
:create_directories
call :log_info "Creating necessary directories..."

if not exist "%CERT_DIR%" mkdir "%CERT_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%CONFIG_DIR%\backups" mkdir "%CONFIG_DIR%\backups"

call :log_success "Directories created"
goto :eof

REM Install dependencies
:install_dependencies
call :log_info "Checking dependencies..."

REM Check if virtual environment exists
if not exist "%CONFIG_DIR%\venv" (
    call :log_warning "No virtual environment detected. Creating one..."
    %PYTHON_CMD% -m venv "%CONFIG_DIR%\venv"
)

REM Activate virtual environment
call "%CONFIG_DIR%\venv\Scripts\activate.bat"

REM Upgrade pip
%PYTHON_CMD% -m pip install --upgrade pip

REM Install requirements if requirements.txt exists
if exist "%~dp0..\pc-agent\requirements.txt" (
    call :log_info "Installing Python dependencies..."
    %PYTHON_CMD% -m pip install -r "%~dp0..\pc-agent\requirements.txt"
) else (
    call :log_warning "requirements.txt not found. Installing basic dependencies..."
    pip install fastapi uvicorn python-multipart websockets python-jose[cryptography] passlib[bcrypt]
)

call :log_success "Dependencies installed"
goto :eof

REM Generate certificates if they don't exist
:check_certificates
echo SRC_DIR=%SRC_DIR%

call :log_info "Checking SSL certificates..."

if not exist "%CERT_DIR%\server.crt" (
    call :log_warning "SSL certificates not found. Generating new certificates..."

    %PYTHON_CMD% -c "import os, sys; sys.path.append(r'%SRC_DIR%'); from utils.certificate_generator import CertificateGenerator as CG; g = CG(r'%CERT_DIR%'); g.generate_all_certificates(); print('Certificates generated successfully!')"

    if errorlevel 1 (
        call :log_error "Failed to generate SSL certificates"
        pause
        exit /b 1
    )

    call :log_success "SSL certificates generated"
) else (
    call :log_success "SSL certificates found"
)
goto :eof


REM Start the service
:start_service
call :log_info "Starting PC Voice Controller service..."

REM Get command line arguments
set HOST=%1
if "%HOST%"=="" set HOST=%DEFAULT_HOST%

set PORT=%2
if "%PORT%"=="" set PORT=%DEFAULT_PORT%

REM Change to the src directory
cd /d "%~dp0..\pc-agent\src"

REM Set environment variables
set PYTHONPATH=%PYTHONPATH%;%CD%\..
set PC_VOICE_HOST=%HOST%
set PC_VOICE_PORT=%PORT%
set PC_VOICE_CONFIG_DIR=%CONFIG_DIR%
set PC_VOICE_CERT_DIR=%CERT_DIR%

REM Set PC Agent specific environment variables
set PC_AGENT_HOST=%HOST%
set PC_AGENT_PORT=%PORT%
set PC_AGENT_CERTIFICATES_DIR=%CERT_DIR%
set PC_AGENT_CERT_FILE=%CERT_DIR%\server.crt
set PC_AGENT_KEY_FILE=%CERT_DIR%\server.key

REM Start the service
call :log_info "Starting server on %HOST%:%PORT%"
call :log_info "Logs directory: %LOG_DIR%"
call :log_info "Press Ctrl+C to stop the service"

%PYTHON_CMD% -m uvicorn api.main:app ^
    --host "%HOST%" ^
    --port "%PORT%" ^
    --ssl-keyfile "%CERT_DIR%\server.key" ^
    --ssl-certfile "%CERT_DIR%\server.crt" ^
    --log-level info

goto :eof

REM Main execution
:main
echo PC Voice Controller - PC Agent Startup Script for Windows
echo ==============================================

call :check_python
if errorlevel 1 goto end

call :create_directories
if errorlevel 1 goto end

call :install_dependencies
if errorlevel 1 goto end

call :check_certificates
if errorlevel 1 goto end

call :start_service %*

:end
pause