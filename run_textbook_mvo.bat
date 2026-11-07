@echo off
cd /d "%~dp0"
echo Starting Pure Textbook MVO & Institutional Workbench on http://127.0.0.1:8005 ...
start http://127.0.0.1:8005
"C:\Users\LENOVO\AppData\Local\Programs\Python\Python314\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005 --reload
pause
