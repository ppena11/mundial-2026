@echo off
REM Snapshot de cuotas cada 2 horas (sharp money). Lo ejecuta el Programador de tareas.
cd /d "%~dp0"
if not exist logs mkdir logs
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "STAMP=%%i"
echo ======== %date% %time% ======== >> "logs\snapshot_%STAMP%.log"
"%~dp0venv\Scripts\python.exe" money_layer.py --snapshot >> "logs\snapshot_%STAMP%.log" 2>&1
echo (exit code %ERRORLEVEL%) >> "logs\snapshot_%STAMP%.log"
