@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Auto Tool Studio Launcher

set "APP_NAME=Auto Tool Studio"
set "APP_URL=http://127.0.0.1:8000"
set "API_HOST=127.0.0.1"
set "API_PORT=8000"
set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "LOG_DIR=%PROJECT_ROOT%\logs\launcher"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "DIAGNOSTICS=%PROJECT_ROOT%\launcher\launcher_diagnostics.py"

if not defined AUTO_TOOL_LAUNCHER_DEBUG set "AUTO_TOOL_LAUNCHER_DEBUG=0"
if not defined AUTO_TOOL_LAUNCHER_NO_BROWSER set "AUTO_TOOL_LAUNCHER_NO_BROWSER=0"
if not defined AUTO_TOOL_LAUNCHER_NO_PAUSE set "AUTO_TOOL_LAUNCHER_NO_PAUSE=0"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul`) do set "TIMESTAMP=%%I"
if not defined TIMESTAMP set "TIMESTAMP=%RANDOM%_%RANDOM%"
set "LOG_FILE=%LOG_DIR%\launcher_%TIMESTAMP%.log"

echo ============================================================
echo   Auto Tool Studio - Windows One-Click Launcher
echo ============================================================
echo.
call :log "Launcher started"
call :log "Project root: %PROJECT_ROOT%"
call :log "App URL: %APP_URL%"

echo [INFO] Checking Python...
set "BOOTSTRAP_PYTHON="
set "BOOTSTRAP_PYTHON_ARGS="
set "PYTHON_VERSION="
set "PYTHON_UNSUPPORTED_VERSION="
call :detect_python python ""
if defined BOOTSTRAP_PYTHON goto :python_found
call :detect_python py "-3"
if defined BOOTSTRAP_PYTHON goto :python_found
if defined PYTHON_UNSUPPORTED_VERSION goto :python_unsupported
goto :python_missing

:python_found
echo [OK] Python !PYTHON_VERSION!
call :log "Python check OK: !PYTHON_VERSION! via %BOOTSTRAP_PYTHON% %BOOTSTRAP_PYTHON_ARGS%"

set "FRONTEND_READY=0"
if exist "%PROJECT_ROOT%\frontend\dist\index.html" set "FRONTEND_READY=1"
set "NODE_READY=0"
where node >nul 2>nul
if errorlevel 1 goto :node_unavailable
where npm >nul 2>nul
if errorlevel 1 goto :node_unavailable
set "NODE_READY=1"
for /f "delims=" %%V in ('node --version 2^>nul') do set "NODE_VERSION=%%V"
for /f "delims=" %%V in ('npm --version 2^>nul') do set "NPM_VERSION=%%V"
echo [OK] Node !NODE_VERSION! / npm !NPM_VERSION!
call :log "Node check OK: !NODE_VERSION!, npm !NPM_VERSION!"
goto :node_done

:node_unavailable
if "!FRONTEND_READY!"=="1" goto :node_optional
call :fail "Node.js or npm was not found." "Node.js LTS is required to build the frontend for the first run."
exit /b 1

:node_optional
echo [WARN] Node.js or npm is missing. Existing frontend build will be used.
call :log "WARN: Node/npm missing; frontend build already exists"

:node_done
if exist "%VENV_PYTHON%" goto :venv_ready
echo [INFO] Creating Python environment .venv...
call :log "Creating .venv"
if /i "%AUTO_TOOL_LAUNCHER_DEBUG%"=="1" (
  %BOOTSTRAP_PYTHON% %BOOTSTRAP_PYTHON_ARGS% -m venv "%PROJECT_ROOT%\.venv"
) else (
  %BOOTSTRAP_PYTHON% %BOOTSTRAP_PYTHON_ARGS% -m venv "%PROJECT_ROOT%\.venv" >>"%LOG_FILE%" 2>&1
)
if errorlevel 1 goto :venv_create_failed

:venv_ready
if not exist "%VENV_PYTHON%" goto :venv_missing
echo [OK] Python environment ready.
call :log "Virtual environment ready: %VENV_PYTHON%"

echo [INFO] Checking backend packages. This may take a few minutes on first run...
call :log "Installing backend requirements"
if /i "%AUTO_TOOL_LAUNCHER_DEBUG%"=="1" (
  "%VENV_PYTHON%" -m pip install -r "%PROJECT_ROOT%\backend\requirements.txt"
) else (
  "%VENV_PYTHON%" -m pip install -r "%PROJECT_ROOT%\backend\requirements.txt" >>"%LOG_FILE%" 2>&1
)
if errorlevel 1 goto :pip_failed
echo [OK] Backend packages ready.
call :log "Backend requirements OK"

set "FFMPEG_PATH="
set "FFPROBE_PATH="
for /f "delims=" %%I in ('""%VENV_PYTHON%" "%DIAGNOSTICS%" managed-tool "%PROJECT_ROOT%" ffmpeg"') do set "FFMPEG_PATH=%%I"
for /f "delims=" %%I in ('""%VENV_PYTHON%" "%DIAGNOSTICS%" managed-tool "%PROJECT_ROOT%" ffprobe"') do set "FFPROBE_PATH=%%I"
if defined FFMPEG_PATH goto :ffmpeg_ready
echo [WARN] FFmpeg is not ready. The app can open, but video rendering may fail.
call :log "WARN: FFmpeg not found"
goto :ffmpeg_done

:ffmpeg_ready
echo [OK] FFmpeg found.
call :log "FFmpeg check OK: !FFMPEG_PATH!"

:ffmpeg_done
if defined FFPROBE_PATH goto :ffprobe_ready
echo [WARN] ffprobe is not ready. Video metadata checks may fail.
call :log "WARN: ffprobe not found"
goto :ffprobe_done

:ffprobe_ready
echo [OK] ffprobe found.
call :log "ffprobe check OK: !FFPROBE_PATH!"

:ffprobe_done
if exist "%PROJECT_ROOT%\frontend\dist\index.html" goto :frontend_ready
if not "!NODE_READY!"=="1" goto :frontend_node_missing
echo [INFO] Frontend build is missing. Building it now...
call :log "Frontend build missing; running npm install"
pushd "%PROJECT_ROOT%\frontend"
if /i "%AUTO_TOOL_LAUNCHER_DEBUG%"=="1" (
  call npm install
) else (
  call npm install >>"%LOG_FILE%" 2>&1
)
if errorlevel 1 goto :npm_install_failed
if /i "%AUTO_TOOL_LAUNCHER_DEBUG%"=="1" (
  call npm run build
) else (
  call npm run build >>"%LOG_FILE%" 2>&1
)
if errorlevel 1 goto :npm_build_failed
popd

:frontend_ready
if not exist "%PROJECT_ROOT%\frontend\dist\index.html" goto :frontend_output_missing
echo [OK] Frontend build ready.
call :log "Frontend build OK"

"%VENV_PYTHON%" "%DIAGNOSTICS%" health "%APP_URL%" >nul 2>nul
if not errorlevel 1 goto :existing_server
"%VENV_PYTHON%" "%DIAGNOSTICS%" port-busy "%API_HOST%" %API_PORT% >nul 2>nul
if not errorlevel 1 goto :port_busy

set "AUTO_TOOL_ROOT=%PROJECT_ROOT%"
set "AUTO_TOOL_HOST=%API_HOST%"
set "AUTO_TOOL_PORT=%API_PORT%"
set "AUTO_TOOL_STRICT_PORT=1"
set "AUTO_TOOL_OPEN_BROWSER=0"
set "AUTO_TOOL_LOG_FILE=%LOG_FILE%"
call :log "Backend start command: python -m app.launcher with AUTO_TOOL_HOST=%API_HOST%, AUTO_TOOL_PORT=%API_PORT%"
if /i "%AUTO_TOOL_LAUNCHER_DEBUG%"=="1" goto :debug_server

echo [INFO] Starting local server...
start "Auto Tool Studio Server" cmd /k call "%PROJECT_ROOT%\launcher\_run_server.bat"
"%VENV_PYTHON%" "%DIAGNOSTICS%" wait-health "%APP_URL%" --timeout 45 >nul 2>nul
if errorlevel 1 goto :server_not_ready
echo [OK] Local server is ready.
call :log "Backend health check OK"
call :open_browser
goto :success

:existing_server
echo [OK] Auto Tool Studio is already running.
call :log "Existing Auto Tool server detected"
call :open_browser
goto :success

:debug_server
echo [INFO] Debug mode: server output will stay in this window.
echo [INFO] Open %APP_URL% after the server reports it is ready.
call :log "Starting backend in debug foreground mode"
pushd "%PROJECT_ROOT%\backend"
"%VENV_PYTHON%" -m app.launcher
set "SERVER_RESULT=!ERRORLEVEL!"
popd
if not "!SERVER_RESULT!"=="0" goto :debug_server_failed
echo [INFO] Backend stopped normally.
call :pause_if_needed
exit /b 0

:python_missing
call :fail "Python was not found." "Install Python 3.11 or newer and enable Add Python to PATH."
exit /b 1

:python_unsupported
call :fail "Python 3.11 or newer is required." "Install a supported Python version, close this window, and run the launcher again."
exit /b 1

:venv_create_failed
call :fail "Could not create .venv." "Check the Python installation and write permission for the project folder."
exit /b 1

:venv_missing
call :fail "The .venv Python executable is missing." "Delete the incomplete .venv folder and run the launcher again."
exit /b 1

:pip_failed
call :fail "Backend package installation failed." "Check internet access, then run start_auto_tool_studio_debug.bat for details."
exit /b 1

:frontend_node_missing
call :fail "Frontend build is missing and Node.js is unavailable." "Install Node.js LTS and run the launcher again."
exit /b 1

:npm_install_failed
popd
call :fail "npm install failed." "Check Node.js, npm, internet access, and the launcher log."
exit /b 1

:npm_build_failed
popd
call :fail "Frontend build failed." "Run build_frontend.bat to inspect TypeScript or Vite errors."
exit /b 1

:frontend_output_missing
call :fail "Frontend build did not create dist\index.html." "Open the launcher log and run build_frontend.bat."
exit /b 1

:port_busy
call :fail "Port 8000 is already in use by another program." "Close that program or the old server window, then run this launcher again."
exit /b 1

:server_not_ready
call :fail "The local server did not become ready." "Check the server window and log file for the first ERROR line."
exit /b 1

:debug_server_failed
call :fail "The backend stopped with exit code !SERVER_RESULT!." "Review the error above and the launcher log."
exit /b !SERVER_RESULT!

:success
echo.
echo ============================================================
echo   Auto Tool Studio is running
echo   %APP_URL%
echo ============================================================
echo Close the server window to stop the app.
echo Launcher log: %LOG_FILE%
call :log "Launcher completed successfully"
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" timeout /t 5 /nobreak >nul
exit /b 0

:open_browser
if /i "%AUTO_TOOL_LAUNCHER_NO_BROWSER%"=="1" goto :browser_skipped
start "" "%APP_URL%"
if errorlevel 1 goto :browser_failed
echo [OK] Browser opened.
call :log "Browser open command OK"
exit /b 0

:browser_skipped
call :log "Browser open skipped by AUTO_TOOL_LAUNCHER_NO_BROWSER"
exit /b 0

:browser_failed
echo [WARN] Browser could not be opened automatically. Open %APP_URL% manually.
call :log "WARN: Browser open command failed"
exit /b 0

:fail
echo.
echo [ERROR] %~1
echo %~2
echo.
echo Log file: %LOG_FILE%
echo Try: launcher\start_auto_tool_studio_debug.bat
call :log "ERROR: %~1"
call :log "FIX: %~2"
call :pause_if_needed
exit /b 1

:pause_if_needed
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
exit /b 0

:log
echo [%date% %time%] %~1>>"%LOG_FILE%"
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
set "BOOTSTRAP_PYTHON=%CANDIDATE_PYTHON%"
set "BOOTSTRAP_PYTHON_ARGS=%CANDIDATE_ARGS%"
set "PYTHON_VERSION=%CANDIDATE_VERSION%"
exit /b 0
