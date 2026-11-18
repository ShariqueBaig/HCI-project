@echo off
rem Double-click, or:  tools\setup_station.bat -SaltFrom \\labshare\lab_salt.txt -Code P01
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_station.ps1" %*
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo.& echo Setup exited with code %RC%.
if "%~1"=="" pause
exit /b %RC%
