@echo off
setlocal
cd /d "%~dp0"

echo === MessageLog Build ===
echo.

:: Clean previous build artifacts (keeps dist\messages.json)
if exist build rd /s /q build
if exist MessageLog.spec del MessageLog.spec

echo Building MessageLog.exe ...
py -m PyInstaller --noconfirm --onefile --windowed --name MessageLog --icon messagelog.ico --add-data "messagelog.ico;." --distpath dist --workpath build --specpath . messages.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo *** Build FAILED ***
    pause
    exit /b 1
)

:: Clean up build artifacts
if exist build rd /s /q build
if exist MessageLog.spec del MessageLog.spec

echo.
echo Build complete: dist\MessageLog.exe
pause
