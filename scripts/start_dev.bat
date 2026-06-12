@echo off
setlocal
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"

if not exist "%VENV%\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv "%VENV%"
  ) else (
    python -m venv "%VENV%"
  )
)
if errorlevel 1 exit /b 1

"%VENV%\Scripts\python.exe" -m pip install -r "%ROOT%\backend\requirements.txt"
if errorlevel 1 exit /b 1

pushd "%ROOT%\frontend"
if not exist "node_modules" call npm install
if errorlevel 1 exit /b 1
popd

set "AUTO_TOOL_ROOT=%ROOT%"
start "Auto Tool Backend" /D "%ROOT%\backend" "%VENV%\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
start "Auto Tool Frontend" /D "%ROOT%\frontend" cmd /k npm run dev
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5173
