@echo off
setlocal
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"

if not exist "%ROOT%\frontend\dist\index.html" (
  call "%ROOT%\scripts\build_frontend.bat"
  if errorlevel 1 exit /b 1
)

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

set "AUTO_TOOL_ROOT=%ROOT%"
pushd "%ROOT%\backend"
"%VENV%\Scripts\python.exe" -m app.launcher
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
