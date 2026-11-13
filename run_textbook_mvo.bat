@echo off
cd /d "%~dp0"
echo Starting Pure Textbook MVO & Institutional Workbench on http://127.0.0.1:8005 ...
start http://127.0.0.1:8005
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005 --reload
pause
