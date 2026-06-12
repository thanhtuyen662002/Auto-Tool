@echo off
setlocal
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"

echo Starting Auto Tool Studio Production Local Server...

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

if not exist "%ROOT%\frontend\dist\index.html" (
  echo Frontend build not found. Building frontend...
  call "%ROOT%\scripts\build_frontend.bat"
  if errorlevel 1 exit /b 1
)

call "%ROOT%\scripts\check_production_build.bat"
if errorlevel 1 exit /b 1

set "AUTO_TOOL_ROOT=%ROOT%"
set "AUTO_TOOL_PORT=8000"
set "AUTO_TOOL_STRICT_PORT=1"
pushd "%ROOT%\backend"
"%VENV%\Scripts\python.exe" -m app.launcher
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
