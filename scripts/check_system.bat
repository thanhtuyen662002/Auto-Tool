@echo off
setlocal
set "FAILED=0"
set "ROOT=%~dp0.."

echo Auto Tool local system check
echo ============================
where python >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%i in ('where python') do (
    echo [READY] Python: %%i
    goto :python_ready
  )
)
where py >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%i in ('where py') do (
    echo [READY] Python launcher: %%i
    goto :python_ready
  )
)
echo [MISS ] Python
set "FAILED=1"
:python_ready
call :check node "Node.js"
call :check npm "npm"
call :check_managed ffmpeg "FFmpeg"
call :check_managed ffprobe "ffprobe"

if exist "%~dp0..\frontend\dist\index.html" (
  echo [READY] Frontend build
) else (
  echo [WARN ] Frontend build missing. Run scripts\build_frontend.bat
)

if "%FAILED%"=="1" exit /b 1
exit /b 0

:check
where %~1 >nul 2>nul
if errorlevel 1 (
  echo [MISS ] %~2
  set "FAILED=1"
  exit /b 1
)
for /f "delims=" %%i in ('where %~1') do (
  echo [READY] %~2: %%i
  goto :eof
)

:check_managed
where %~1 >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%i in ('where %~1') do (
    echo [READY] %~2: %%i
    goto :eof
  )
)
set "PYTHONPATH=%ROOT%\backend"
python -c "from app.utils.dependency_manager import find_tool; import sys; p=find_tool('%~1'); print('[READY] %~2: '+str(p) if p else '[MISS ] %~2'); sys.exit(0 if p else 1)"
if errorlevel 1 set "FAILED=1"
goto :eof
