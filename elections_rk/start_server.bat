@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
echo ====================================
echo Starting RK Elections System Server
echo ====================================
echo.

cd /d "%~dp0"

REM Ensure readable Python output under UTF-8 console
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PORT=8001"
set "FORCE_RESTART="
if /I "%~1"=="--force" set "FORCE_RESTART=1"
if /I "%~1"=="/force" set "FORCE_RESTART=1"

REM Определить Python из venv
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "%~dp0venv\bin\python.exe" (
    set "PY_EXE=%~dp0venv\bin\python.exe"
) else (
    set "PY_EXE=python"
)

REM Запуск сервера
echo.
echo Starting FastAPI server...
echo API will be available at: http://localhost:%PORT%
echo API Documentation: http://localhost:%PORT%/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Check if port is in use (LISTENING state only)
set "API_PID="
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /C:":%PORT% " ^| findstr /C:"LISTENING"') do (
    if "!API_PID!"=="" set "API_PID=%%P"
)

if defined API_PID (
    echo [!] Port %PORT% is already in use by PID !API_PID!
    tasklist /FI "PID eq !API_PID!" /NH 2>nul
    if defined FORCE_RESTART (
        echo     - Forcing restart...
        taskkill /PID !API_PID! /F >nul 2>&1
        timeout /t 2 /nobreak >nul
        set "API_PID="
    ) else (
        echo.
        echo [ОШИБКА] Порт занят. Закройте старый сервер или запустите:
        echo     start_server.bat --force
        echo.
        pause
        exit /b 1
    )
)

echo Checking database connection...
"%PY_EXE%" "%~dp0scripts\health_check.py" --db
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ОШИБКА] Нет подключения к базе данных. Проверьте DATABASE_URL и пароль postgres.
    echo.
    pause
    exit /b 1
)

"%PY_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

pause
