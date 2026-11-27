@echo off
rem ===================================================================
rem  Aura UI — Lab Station Requirements Check
rem  Double-click this on any Windows machine to verify it can run
rem  AuraUI.exe without issues.
rem ===================================================================
setlocal EnableDelayedExpansion

echo.
echo  ============================================
echo   Aura UI - Station Requirements Check
echo  ============================================
echo.

set PASS=0
set FAIL=0

rem ---- 1. Windows version ----
for /f "tokens=4-5 delims=. " %%i in ('ver') do set VERSION=%%i.%%j
echo  [check] Windows version: %VERSION%
if "%VERSION%"=="10.0" (
    echo   [ok]   Windows 10/11 detected
    set /a PASS+=1
) else (
    echo   [warn] Expected Windows 10 or 11 — may still work
)

rem ---- 2. Screen resolution ----
for /f "tokens=*" %%a in ('wmic path Win32_VideoController get CurrentHorizontalResolution /value 2^>nul ^| find "="') do (
    echo   [ok]   Display detected: %%a
    set /a PASS+=1
    goto :done_screen
)
echo   [warn] Could not detect display resolution
:done_screen

rem ---- 3. Audio output device ----
for /f "tokens=*" %%a in ('wmic path Win32_SoundDevice get Name /value 2^>nul ^| find "="') do (
    echo   [ok]   Audio device: %%a
    set /a PASS+=1
    goto :done_audio
)
echo   [FAIL] No audio output device found — volume control will not work
set /a FAIL+=1
:done_audio

rem ---- 4. Internet connectivity (Firestore) ----
echo.
echo  [check] Internet connectivity (Firebase)...
ping -n 1 -w 3000 firestore.googleapis.com >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   [ok]   Can reach firestore.googleapis.com
    set /a PASS+=1
) else (
    echo   [FAIL] Cannot reach firestore.googleapis.com
    echo          Sessions will be saved locally but NOT uploaded
    set /a FAIL+=1
)

rem ---- 5. Writable folder check ----
echo.
echo  [check] Folder write access...
set "TESTFILE=%~dp0_write_test.tmp"
echo test > "%TESTFILE%" 2>nul
if exist "%TESTFILE%" (
    del "%TESTFILE%"
    echo   [ok]   This folder is writable
    set /a PASS+=1
) else (
    echo   [FAIL] This folder is NOT writable
    echo          Move the AuraUI folder to Desktop or C:\AuraUI
    set /a FAIL+=1
)

rem ---- 6. VC++ Runtime check ----
echo.
echo  [check] Visual C++ Runtime...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Version >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   [ok]   VC++ 2015-2022 Redistributable found
    set /a PASS+=1
) else (
    echo   [warn] VC++ Redistributable not detected via registry
    echo          Usually already present on Windows 10/11
    echo          If AuraUI.exe fails to start, install from:
    echo          https://aka.ms/vs/17/release/vc_redist.x64.exe
)

rem ---- 7. Check if AuraUI.exe exists nearby ----
echo.
if exist "%~dp0AuraUI.exe" (
    echo   [ok]   AuraUI.exe found in this folder
    set /a PASS+=1
) else (
    for /d %%d in ("%~dp0AuraUI_*") do (
        if exist "%%d\AuraUI.exe" (
            echo   [ok]   Found: %%~nxd\AuraUI.exe
            set /a PASS+=1
            goto :done_exe
        )
    )
    echo   [info] AuraUI.exe not found in this folder
    echo          Copy a participant folder here first
)
:done_exe

rem ---- Summary ----
echo.
echo  ============================================
echo   Results: %PASS% passed, %FAIL% failed
echo  ============================================
if %FAIL%==0 (
    echo.
    echo   This station is ready to run AuraUI.exe
) else (
    echo.
    echo   Fix the [FAIL] items above before the study.
)
echo.
pause
