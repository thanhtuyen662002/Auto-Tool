@echo off
setlocal
set "ROOT=%~dp0.."

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found. Install Node.js LTS and run this script again.
  exit /b 1
)

pushd "%ROOT%\frontend"
if not exist "node_modules" call npm install
if errorlevel 1 exit /b 1
call npm run build
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
