@echo off

REM Initialize database
python scripts/init_db.py

REM Start API server
start "Release Intelligence API" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000"

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Start data collector
start "Release Intelligence Collector" cmd /k "python scripts/collector.py"

echo Release Intelligence Platform started
echo API running on http://localhost:8000
echo.
echo Press any key to exit...
pause >nul

