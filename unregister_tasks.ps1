# Elimina las tareas programadas del Mundial 2026 (deshace register_tasks.ps1).
Unregister-ScheduledTask -TaskName "MundialModelo_Daily"    -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "MundialModelo_Snapshot" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Tareas MundialModelo_* eliminadas (si existían)."
