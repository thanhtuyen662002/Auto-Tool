@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Auto Tool Studio - Reset Local App Cache
set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "RECENT_FILE=%PROJECT_ROOT%\config\recent_paths.json"
set "LOG_DIR=%PROJECT_ROOT%\logs\launcher"

echo This resets recent folders only.
echo It will NOT delete outputs, databases, source videos, or projects.
echo.
set /p "CONFIRM=Reset recent folders/local app cache? (Y/N): "
if /i not "!CONFIRM!"=="Y" (
  echo Cancelled.
  if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
  exit /b 0
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul`) do set "TIMESTAMP=%%I"
if not defined TIMESTAMP set "TIMESTAMP=%RANDOM%_%RANDOM%"
if exist "%RECENT_FILE%" (
  copy /y "%RECENT_FILE%" "%PROJECT_ROOT%\config\recent_paths.backup_!TIMESTAMP!.json" >nul
  if errorlevel 1 (
    echo [ERROR] Could not back up recent_paths.json. Nothing was deleted.
    if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
    exit /b 1
  )
  del /q "%RECENT_FILE%"
  echo [OK] Recent folders reset. Backup created in config\.
) else (
  echo [OK] No recent paths cache was present.
)

set /p "DELETE_LOGS=Delete old launcher .log files too? (Y/N): "
if /i "!DELETE_LOGS!"=="Y" (
  if exist "%LOG_DIR%\*.log" del /q "%LOG_DIR%\*.log"
  echo [OK] Launcher logs cleared.
)
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
exit /b 0
