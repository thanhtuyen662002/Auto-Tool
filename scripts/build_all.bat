@echo off
setlocal
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"

echo Building Auto Tool Studio...
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

call "%ROOT%\scripts\build_frontend.bat"
if errorlevel 1 exit /b 1

call "%ROOT%\scripts\check_system.bat"
if errorlevel 1 exit /b 1
call "%ROOT%\scripts\check_production_build.bat"
if errorlevel 1 exit /b 1

echo Build completed.
