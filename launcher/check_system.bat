@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Auto Tool Studio - Check System

set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "ERRORS=0"
set "WARNINGS=0"
set "DIST_READY=0"
set "CHECK_PYTHON="
set "CHECK_PYTHON_ARGS="
set "PYTHON_VERSION="
set "PYTHON_UNSUPPORTED_VERSION="
if exist "%PROJECT_ROOT%\frontend\dist\index.html" set "DIST_READY=1"

echo ============================================================
echo   Auto Tool Studio - System Check
echo ============================================================
echo.

call :detect_python python ""
if not defined CHECK_PYTHON call :detect_python py "-3"
if defined CHECK_PYTHON (
  echo [OK] Python: !PYTHON_VERSION!
) else if defined PYTHON_UNSUPPORTED_VERSION (
  echo [ERROR] Python !PYTHON_UNSUPPORTED_VERSION! found, but Auto Tool requires Python 3.11 or newer.
  set /a ERRORS+=1
) else (
  echo [ERROR] Python 3.11 or newer was not found.
  set /a ERRORS+=1
)

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
  echo [OK] .venv exists.
  set "CHECK_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
  set "CHECK_PYTHON_ARGS="
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

set "FFMPEG_PATH="
set "FFPROBE_PATH="
for /f "delims=" %%I in ('where ffmpeg 2^>nul') do if not defined FFMPEG_PATH set "FFMPEG_PATH=%%I"
for /f "delims=" %%I in ('where ffprobe 2^>nul') do if not defined FFPROBE_PATH set "FFPROBE_PATH=%%I"
if not defined FFMPEG_PATH if defined CHECK_PYTHON for /f "delims=" %%I in ('""%CHECK_PYTHON%" %CHECK_PYTHON_ARGS% "%PROJECT_ROOT%\launcher\launcher_diagnostics.py" managed-tool "%PROJECT_ROOT%" ffmpeg" 2^>nul') do set "FFMPEG_PATH=%%I"
if not defined FFPROBE_PATH if defined CHECK_PYTHON for /f "delims=" %%I in ('""%CHECK_PYTHON%" %CHECK_PYTHON_ARGS% "%PROJECT_ROOT%\launcher\launcher_diagnostics.py" managed-tool "%PROJECT_ROOT%" ffprobe" 2^>nul') do set "FFPROBE_PATH=%%I"
if defined FFMPEG_PATH (echo [OK] FFmpeg: !FFMPEG_PATH!) else (echo [WARN] FFmpeg missing; rendering will not work until runtime setup completes. & set /a WARNINGS+=1)
if defined FFPROBE_PATH (echo [OK] ffprobe: !FFPROBE_PATH!) else (echo [WARN] ffprobe missing; video metadata checks will fail. & set /a WARNINGS+=1)

call :check_dir "backend" "%PROJECT_ROOT%\backend"
call :check_dir "frontend" "%PROJECT_ROOT%\frontend"
call :check_file "backend requirements" "%PROJECT_ROOT%\backend\requirements.txt"
call :check_file "frontend package.json" "%PROJECT_ROOT%\frontend\package.json"
call :check_optional_file "local app config" "%PROJECT_ROOT%\config\local_app_config.json" "The main launcher will create this file on first run."
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

:check_optional_file
if exist "%~2" (echo [OK] File: %~1) else (echo [WARN] Missing optional file: %~1. %~3 & set /a WARNINGS+=1)
exit /b 0

:detect_python
set "CANDIDATE_PYTHON=%~1"
set "CANDIDATE_ARGS=%~2"
where "%CANDIDATE_PYTHON%" >nul 2>nul
if errorlevel 1 exit /b 1
set "CANDIDATE_VERSION="
for /f "delims=" %%V in ('%CANDIDATE_PYTHON% %CANDIDATE_ARGS% -c "import sys; print('%%d.%%d.%%d' %% sys.version_info[:3])" 2^>nul') do set "CANDIDATE_VERSION=%%V"
if not defined CANDIDATE_VERSION exit /b 1
%CANDIDATE_PYTHON% %CANDIDATE_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
  set "PYTHON_UNSUPPORTED_VERSION=%CANDIDATE_VERSION%"
  exit /b 2
)
set "CHECK_PYTHON=%CANDIDATE_PYTHON%"
set "CHECK_PYTHON_ARGS=%CANDIDATE_ARGS%"
set "PYTHON_VERSION=%CANDIDATE_VERSION%"
exit /b 0
