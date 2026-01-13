@echo off
echo ====================================
echo RK Elections System - Setup Script
echo ====================================
echo.

cd /d "%~dp0"

REM 1. Создание виртуального окружения
echo [1/5] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created successfully!
echo.

REM 2. Активация виртуального окружения
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM 3. Установка зависимостей
echo [3/5] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

REM 4. Создание директорий
echo [4/5] Creating directories...
if not exist "uploads\protocols" mkdir "uploads\protocols"
echo Directories created successfully!
echo.

REM 5. Настройка .env
echo [5/5] Setting up environment variables...
if not exist ".env" (
    copy .env.example .env
    echo .env file created. Please edit it with your PostgreSQL credentials.
) else (
    echo .env file already exists.
)
echo.

echo ====================================
echo Setup completed successfully!
echo ====================================
echo.
echo Next steps:
echo 1. Edit .env file with your PostgreSQL credentials
echo 2. Create database: psql -U postgres -c "CREATE DATABASE elections_rk;"
echo 3. Initialize schema: psql -U postgres -d elections_rk -f database\init.sql
echo 4. Load test data: psql -U postgres -d elections_rk -f database\seed_data.sql
echo 5. Run server: start_server.bat
echo.
pause
