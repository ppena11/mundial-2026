@echo off
REM Sube el proyecto a GitHub. La primera vez se abrira el navegador para iniciar sesion.
cd /d "%~dp0"
echo Subiendo a GitHub (https://github.com/ppena11/mundial-2026)...
echo Si se abre una ventana del navegador, inicia sesion en GitHub y autoriza.
git push -u origin main
echo.
echo === Si ves "main -> main" arriba, listo. ===
pause
