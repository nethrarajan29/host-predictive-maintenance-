@echo off
echo =========================================================
echo   Industrial Predictive Maintenance SCADA Platform
echo =========================================================
cd /d "%~dp0"

echo [1/2] Checking port availability...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo [2/2] Launching Full-Stack Dashboard (FastAPI + React)...
start "Predictive Maintenance Server" cmd /k "python main.py"

echo Opening browser at http://127.0.0.1:8000 ...
powershell -Command "Start-Sleep -Seconds 5; Start-Process 'http://127.0.0.1:8000'"

echo.
echo =========================================================
echo   System running at: http://127.0.0.1:8000
echo   Secure HTTPS at  : https://127.0.0.1:8443
echo =========================================================
