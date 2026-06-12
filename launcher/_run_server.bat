@echo off
title Auto Tool Studio Server
set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
echo Auto Tool Studio server
echo URL: http://127.0.0.1:8000
echo Close this window to stop the app.
echo.
pushd "%PROJECT_ROOT%\backend"
"%PROJECT_ROOT%\.venv\Scripts\python.exe" -m app.launcher
set "RESULT=%ERRORLEVEL%"
popd
echo.
if not "%RESULT%"=="0" echo Server stopped with error code %RESULT%.
if "%RESULT%"=="0" echo Server stopped.
echo See launcher log: %AUTO_TOOL_LOG_FILE%
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
exit /b %RESULT%
