@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0scripts\start_app.ps1" (
  echo Deutschpath launcher error: scripts\start_app.ps1 was not found.
  pause
  exit /b 1
)
powershell.exe -NoProfile -File "%~dp0scripts\start_app.ps1"
if errorlevel 1 (
  echo.
  echo Deutschpath did not start. Read the error above; existing services were left untouched.
)
echo.
echo Service windows remain open. Press Ctrl+C in the Deutschpath service windows to stop them.
pause
