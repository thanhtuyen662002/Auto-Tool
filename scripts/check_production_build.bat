@echo off
setlocal
set "ROOT=%~dp0.."
set "FAILED=0"

if exist "%ROOT%\frontend\dist" (echo [OK] frontend/dist found) else (echo [FAIL] frontend/dist missing & set "FAILED=1")
if exist "%ROOT%\frontend\dist\index.html" (echo [OK] index.html found) else (echo [FAIL] index.html missing & set "FAILED=1")
if exist "%ROOT%\frontend\dist\assets" (echo [OK] assets folder found) else (echo [FAIL] assets folder missing & set "FAILED=1")

set "PYTHONPATH=%ROOT%\backend"
set "PYTHON_CMD=python"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON_CMD=%ROOT%\.venv\Scripts\python.exe"
"%PYTHON_CMD%" -c "from app.main import app; assert app is not None"
if errorlevel 1 (echo [FAIL] backend app import failed & set "FAILED=1") else (echo [OK] backend app import success)

findstr /l /c:"VITE_API_BASE_URL=/api" "%ROOT%\frontend\.env.production" >nul 2>nul
if errorlevel 1 (echo [FAIL] production API base URL is not /api & set "FAILED=1") else (echo [OK] production API base URL is /api)

exit /b %FAILED%
