@echo off
setlocal
title Auto Tool Studio Debug Launcher
set "AUTO_TOOL_LAUNCHER_DEBUG=1"
call "%~dp0start_auto_tool_studio.bat"
set "RESULT=%ERRORLEVEL%"
if /i not "%AUTO_TOOL_LAUNCHER_NO_PAUSE%"=="1" pause
exit /b %RESULT%
