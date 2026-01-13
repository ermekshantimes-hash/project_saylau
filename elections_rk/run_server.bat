@echo off
cd /d C:\elections_rk
set DATABASE_URL=postgresql://postgres:23june1970@localhost:5432/elections_rk
set PYTHONPATH=C:\elections_rk
C:\Users\777\AppData\Local\Microsoft\WindowsApps\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
