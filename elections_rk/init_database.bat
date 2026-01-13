@echo off
echo ====================================
echo Database Initialization Script
echo ====================================
echo.

set /p DB_USER="Enter PostgreSQL username (default: postgres): "
if "%DB_USER%"=="" set DB_USER=postgres

set /p DB_NAME="Enter database name (default: elections_rk): "
if "%DB_NAME%"=="" set DB_NAME=elections_rk

echo.
echo [1/3] Creating database...
psql -U %DB_USER% -c "CREATE DATABASE %DB_NAME%;"
if errorlevel 1 (
    echo Database may already exist or check your credentials
)
echo.

echo [2/3] Initializing schema...
psql -U %DB_USER% -d %DB_NAME% -f database\init.sql
if errorlevel 1 (
    echo ERROR: Failed to initialize schema
    pause
    exit /b 1
)
echo Schema initialized successfully!
echo.

echo [3/3] Loading test data...
psql -U %DB_USER% -d %DB_NAME% -f database\seed_data.sql
if errorlevel 1 (
    echo ERROR: Failed to load test data
    pause
    exit /b 1
)
echo Test data loaded successfully!
echo.

echo ====================================
echo Database setup completed!
echo ====================================
echo.
echo You can now start the server with: start_server.bat
echo.
pause
