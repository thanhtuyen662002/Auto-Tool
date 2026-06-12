@echo off
setlocal EnableExtensions
title Auto Tool Studio - Build Frontend
set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"

echo ============================================================
echo   Auto Tool Studio - Build Frontend
echo ============================================================
echo.
where node >nul 2>nul
if errorlevel 1 goto :node_error
where npm >nul 2>nul
if errorlevel 1 goto :node_error

pushd "%PROJECT_ROOT%\frontend"
echo [INFO] Installing frontend packages...
call npm install
if errorlevel 1 (
  popd
  echo [ERROR] npm install failed. Check Node.js, npm, and internet access.
  goto :failed
)
echo [INFO] Building production frontend...
call npm run build
if errorlevel 1 (
  popd
  echo [ERROR] Frontend build failed. Review the TypeScript or Vite error above.
  goto :failed
)
popd
if not exist "%PROJECT_ROOT%\frontend\dist\index.html" (
  echo [ERROR] Build completed without frontend\dist\index.html.
  goto :failed
)
echo [OK] Frontend build ready.
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
exit /b 0

:node_error
echo [ERROR] Node.js and npm are required to build the frontend.
echo Install Node.js LTS, then run this file again.
:failed
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
exit /b 1
