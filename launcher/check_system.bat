@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Auto Tool Studio - Check System

set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "ERRORS=0"
set "WARNINGS=0"
set "DIST_READY=0"
if exist "%PROJECT_ROOT%\frontend\dist\index.html" set "DIST_READY=1"

echo ============================================================
echo   Auto Tool Studio - System Check
echo ============================================================
echo.

where python >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%V in ('python --version 2^>^&1') do echo [OK] Python: %%V
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%V in ('py -3 --version 2^>^&1') do echo [OK] Python launcher: %%V
  ) else (
    echo [ERROR] Python 3.11 or newer was not found.
    set /a ERRORS+=1
  )
)

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
  echo [OK] .venv exists.
  "%PROJECT_ROOT%\.venv\Scripts\python.exe" -m pip --version >nul 2>nul
  if errorlevel 1 (echo [ERROR] pip is unavailable in .venv. & set /a ERRORS+=1) else echo [OK] pip is available in .venv.
) else (
  echo [WARN] .venv is missing. The main launcher will create it.
  set /a WARNINGS+=1
)

where node >nul 2>nul
if errorlevel 1 (
  if "!DIST_READY!"=="1" (echo [WARN] Node.js missing; existing frontend build can still run. & set /a WARNINGS+=1) else (echo [ERROR] Node.js missing and frontend build is unavailable. & set /a ERRORS+=1)
) else (
  for /f "delims=" %%V in ('node --version 2^>nul') do echo [OK] Node.js: %%V
)
where npm >nul 2>nul
if errorlevel 1 (
  if "!DIST_READY!"=="1" (echo [WARN] npm missing; existing frontend build can still run. & set /a WARNINGS+=1) else (echo [ERROR] npm missing and frontend build is unavailable. & set /a ERRORS+=1)
) else (
  for /f "delims=" %%V in ('npm --version 2^>nul') do echo [OK] npm: %%V
)

set "CHECK_PYTHON=python"
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" set "CHECK_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
for /f "delims=" %%I in ('""%CHECK_PYTHON%" "%PROJECT_ROOT%\launcher\launcher_diagnostics.py" managed-tool "%PROJECT_ROOT%" ffmpeg"') do set "FFMPEG_PATH=%%I"
for /f "delims=" %%I in ('""%CHECK_PYTHON%" "%PROJECT_ROOT%\launcher\launcher_diagnostics.py" managed-tool "%PROJECT_ROOT%" ffprobe"') do set "FFPROBE_PATH=%%I"
if defined FFMPEG_PATH (echo [OK] FFmpeg: !FFMPEG_PATH!) else (echo [WARN] FFmpeg missing; rendering will not work until runtime setup completes. & set /a WARNINGS+=1)
if defined FFPROBE_PATH (echo [OK] ffprobe: !FFPROBE_PATH!) else (echo [WARN] ffprobe missing; video metadata checks will fail. & set /a WARNINGS+=1)

call :check_dir "backend" "%PROJECT_ROOT%\backend"
call :check_dir "frontend" "%PROJECT_ROOT%\frontend"
call :check_file "backend requirements" "%PROJECT_ROOT%\backend\requirements.txt"
call :check_file "frontend package.json" "%PROJECT_ROOT%\frontend\package.json"
call :check_file "local app config" "%PROJECT_ROOT%\config\local_app_config.json"
if "!DIST_READY!"=="1" (echo [OK] Frontend production build exists.) else (echo [WARN] Frontend production build is missing. & set /a WARNINGS+=1)

echo.
echo Summary: !ERRORS! error(s), !WARNINGS! warning(s).
if !ERRORS! GTR 0 (
  echo Fix ERROR items before starting the app.
) else if !WARNINGS! GTR 0 (
  echo The app may open, but some functions may be unavailable.
) else (
  echo [OK] System is ready.
)
echo.
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
if !ERRORS! GTR 0 exit /b 1
exit /b 0

:check_dir
if exist "%~2\" (echo [OK] Folder: %~1) else (echo [ERROR] Missing folder: %~1 & set /a ERRORS+=1)
exit /b 0

:check_file
if exist "%~2" (echo [OK] File: %~1) else (echo [ERROR] Missing file: %~1 & set /a ERRORS+=1)
exit /b 0
