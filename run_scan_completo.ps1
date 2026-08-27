# Corre AMBOS escaneos (ofertas y planes) de forma secuencial y publica ambos dashboards
# en el repo unico ghl-planes-y-ofertas. Pensado para Windows Task Scheduler.
# Tarea: GHL_Escaneo_Completo (lunes y jueves 9am).
#
# Se ejecutan como procesos hijos separados para aislar el logging/exit code de cada uno;
# SECUENCIAL (no paralelo) para evitar conflictos de git al empujar al mismo repo.

$proj  = "C:\Users\santiago.cristancho\OneDrive - Holding Hotelera GHL\Documentos\Automatizaciones"
$ofe   = Join-Path $proj "run_weekly_individual_scraper.ps1"
$pla   = Join-Path $proj "run_weekly_planes_scraper.ps1"
$log   = Join-Path $proj "reportes_ghl\cron_completo.log"

Set-Location $proj
$fecha = Get-Date -Format "yyyy-MM-dd HH:mm"
Add-Content $log "`n===== ESCANEO COMPLETO $fecha ====="

# 1) Ofertas
Add-Content $log "--- Ofertas ---"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ofe
Add-Content $log "Ofertas termino con codigo $LASTEXITCODE"

# 2) Planes
Add-Content $log "--- Planes ---"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $pla
Add-Content $log "Planes termino con codigo $LASTEXITCODE"

Add-Content $log "===== FIN $fecha ====="
