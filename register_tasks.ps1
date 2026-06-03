# Registra las dos tareas programadas del Mundial 2026 en el Programador de tareas de Windows.
# Equivale al "cron" de Linux. Ejecutar UNA vez (doble clic o: powershell -File register_tasks.ps1).
# Corren con tu sesión iniciada; no piden contraseña.

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# --- Tarea 1: pipeline diario a las 08:00 ---
$accDaily = New-ScheduledTaskAction -Execute "$dir\run_daily.bat"
$trgDaily = New-ScheduledTaskTrigger -Daily -At 8:00am
Register-ScheduledTask -TaskName "MundialModelo_Daily" `
    -Action $accDaily -Trigger $trgDaily `
    -Description "Mundial 2026: pipeline completo (run_all.py) cada dia a las 8am" `
    -Force | Out-Null
Write-Host "OK  -> MundialModelo_Daily  (diario 08:00)"

# --- Tarea 2: snapshot de cuotas cada 2 horas ---
$accSnap = New-ScheduledTaskAction -Execute "$dir\run_snapshot.bat"
$trgSnap = New-ScheduledTaskTrigger -Once -At 12:00am `
    -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName "MundialModelo_Snapshot" `
    -Action $accSnap -Trigger $trgSnap `
    -Description "Mundial 2026: snapshot de cuotas (sharp money) cada 2 horas" `
    -Force | Out-Null
Write-Host "OK  -> MundialModelo_Snapshot  (cada 2 horas)"

Write-Host ""
Write-Host "Tareas registradas. Para verlas:  Get-ScheduledTask MundialModelo_*"
Write-Host "Para probar ya mismo:  Start-ScheduledTask -TaskName MundialModelo_Daily"
