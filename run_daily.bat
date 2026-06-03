@echo off
REM Pipeline diario del Mundial 2026 (lo ejecuta el Programador de tareas a las 8am).
REM Usa el Python del entorno virtual y guarda un log con fecha.
cd /d "%~dp0"
if not exist logs mkdir logs
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "STAMP=%%i"
echo ======== %date% %time% ======== >> "logs\daily_%STAMP%.log"
"%~dp0venv\Scripts\python.exe" run_all.py >> "logs\daily_%STAMP%.log" 2>&1
echo (exit code %ERRORLEVEL%) >> "logs\daily_%STAMP%.log"
