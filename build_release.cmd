@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_mywidgetbox.ps1"
if errorlevel 1 (
  echo.
  echo [build] failed
  exit /b 1
)
echo.
echo [build] complete
endlocal
