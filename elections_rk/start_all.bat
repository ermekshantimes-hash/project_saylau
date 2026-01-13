@echo off
setlocal EnableExtensions
chcp 65001 >nul
echo ========================================
echo   RK Elections System - START ALL
echo   (Server + Telegram Bot)
echo ========================================
echo.

cd /d "%~dp0"

REM Ensure readable Python output under UTF-8 console
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM Ensure child windows inherit required environment
if not defined PYTHONPATH set "PYTHONPATH=%~dp0"
if not defined DATABASE_URL if not exist "%~dp0.env" (
	set "DATABASE_URL=postgresql://postgres:23june1970@localhost:5432/elections_rk"
)

REM Pick Python for health checks (venv preferred)
if exist "%~dp0venv\Scripts\python.exe" (
	set "PY_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "%~dp0venv\bin\python.exe" (
	set "PY_EXE=%~dp0venv\bin\python.exe"
) else (
	set "PY_EXE=python"
)

set "API_BASE=http://127.0.0.1:8001"

echo [+] Starting API server (port 8001) in a new window...
set "API_PID="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "try { (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction Stop | Select-Object -First 1 -ExpandProperty OwningProcess) } catch { '' }"`) do (
	set "API_PID=%%P"
)

REM Trim spaces
for /f "tokens=* delims= " %%A in ("%API_PID%") do set "API_PID=%%A"

if defined API_PID (
	echo [!] Port 8001 is already in use. Skipping server start.
	echo.
	echo     Diagnostics:
	echo     - PID: %API_PID%
	tasklist /FI "PID eq %API_PID%" /NH 2>nul
	echo     - To restart fresh: taskkill /PID %API_PID% /F
) else (
	start "RK Elections API (8001)" cmd /k ""%~dp0start_server.bat""
)

echo.
echo Waiting for API to become available: %API_BASE%
set "API_READY="
set "HC_LOG=%TEMP%\rk_elections_api_health.log"
for /L %%i in (1,1,30) do (
	"%PY_EXE%" "%~dp0scripts\health_check.py" --api %API_BASE% >"%HC_LOG%" 2>&1
	if not errorlevel 1 (
		if exist "%HC_LOG%" del /q "%HC_LOG%" >nul 2>&1
		set "API_READY=1"
		goto API_READY
	)
	timeout /t 1 /nobreak >nul
)

:API_NOT_READY
if not defined API_READY (
	echo [ОШИБКА] API не поднялся за 30 секунд.
	if exist "%HC_LOG%" (
		echo.
		echo Последняя ошибка health-check:
		type "%HC_LOG%"
	)
	echo - Проверьте окно сервера (возможна ошибка БД)
	echo - Либо откройте: http://127.0.0.1:8001/docs
	echo.
	pause
	exit /b 1
)

:API_READY
echo [OK] API доступен.

echo [+] Starting Telegram bot in a new window...
start "RK Elections Telegram Bot" cmd /k ""%~dp0start_bot.bat""

echo.
echo Done. Two windows were opened:
echo  - API server (FastAPI)
echo  - Telegram bot
echo.
echo If the bot says TOKEN is missing, add TELEGRAM_BOT_TOKEN to .env
echo.

exit /b 0
