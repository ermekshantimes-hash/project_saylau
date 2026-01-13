@echo off
setlocal EnableExtensions
chcp 65001 >nul

echo ========================================
echo   Telegram Бот - Мониторинг Выборов РК
echo ========================================
echo.

cd /d "%~dp0"

REM Определить Python (venv или системный)
set "PY_EXE=python"
if exist "%~dp0venv\Scripts\python.exe" set "PY_EXE=%~dp0venv\Scripts\python.exe"
if exist "%~dp0venv\bin\python.exe" set "PY_EXE=%~dp0venv\bin\python.exe"

REM Установить переменные окружения
set "DATABASE_URL=postgresql://postgres:23june1970@localhost:5432/elections_rk"
set "PYTHONPATH=C:\elections_rk"

REM Проверить наличие токена (в окружении или в .env)
set "HAS_TOKEN="
if defined TELEGRAM_BOT_TOKEN set "HAS_TOKEN=1"
if not defined HAS_TOKEN if exist "%~dp0.env" findstr /b /c:"TELEGRAM_BOT_TOKEN=" "%~dp0.env" >nul 2>&1 && set "HAS_TOKEN=1"
if not defined HAS_TOKEN goto NO_TOKEN

echo [+] Запуск Telegram бота...
echo [+] API: http://127.0.0.1:8001/api
echo.

echo Checking API availability...
"%PY_EXE%" "%~dp0scripts\health_check.py" --api http://127.0.0.1:8001/api
if errorlevel 1 goto API_FAIL

"%PY_EXE%" "%~dp0telegram_bot.py"
if errorlevel 1 goto BOT_FAIL

goto END

:NO_TOKEN
echo [ВНИМАНИЕ] Токен Telegram бота не установлен!
echo.
echo Получите токен у @BotFather в Telegram и установите его:
echo.
echo 1. Создайте файл .env с содержимым:
echo    DATABASE_URL=postgresql://postgres:23june1970@localhost:5432/elections_rk
echo    TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
echo.
echo 2. Или установите переменную окружения (для текущей сессии PowerShell):
echo    set TELEGRAM_BOT_TOKEN=ваш_токен
echo.
pause
exit /b 1

:API_FAIL
echo.
echo [ОШИБКА] API недоступен. Сначала запустите сервер (start_server.bat) и проверьте http://127.0.0.1:8001/docs
echo.
pause
exit /b 1

:BOT_FAIL
echo.
echo [ОШИБКА] Бот завершился с ошибкой!
pause
exit /b 1

:END
