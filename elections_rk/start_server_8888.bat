@echo off
cd /d "%~dp0"
echo Запуск сервера на http://localhost:8888
echo.
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
pause
