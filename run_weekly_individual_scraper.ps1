# Corre el scraper de ofertas de webs individuales y sube los cambios a GitHub.
# Pensado para ejecutarse solo (Windows Task Scheduler), sin abrir Claude Code.

$proj = "C:\Users\santiago.cristancho\OneDrive - Holding Hotelera GHL\Documentos\Automatizaciones"
$py   = "C:\Users\santiago.cristancho\AppData\Local\Programs\Python\Python312\python.exe"
$log  = Join-Path $proj "reportes_ghl\cron_individual.log"

Set-Location $proj
$fecha = Get-Date -Format "yyyy-MM-dd HH:mm"
Add-Content $log "`n=== $fecha ==="

# Nota: no se combinan stdout/stderr de los ejecutables nativos (python/git) con 2>&1 -
# en PowerShell 5.1 eso envuelve cada linea de stderr como NativeCommandError aunque
# el proceso termine con exito, lo que ensucia el log. Se deja stderr fluir aparte.
& $py "ghl_scraper_individual_v3.py" | Tee-Object -Append -FilePath $log
if ($LASTEXITCODE -ne 0) {
    Add-Content $log "ERROR: el scraper terminó con código $LASTEXITCODE"
    exit 1
}

git add reportes_ghl/_individual_bil.json reportes_ghl/estado_ofertas_individual.json `
        reportes_ghl/ghl_dashboard_individual_latest.html reportes_ghl/ghl_dashboard_individual_*.html

$changes = git diff --cached --name-only
if ($changes) {
    git commit -m "Escaneo semanal ofertas individuales - $fecha" | Tee-Object -Append -FilePath $log
    git push | Tee-Object -Append -FilePath $log
    if ($LASTEXITCODE -eq 0) {
        Add-Content $log "Cambios subidos a GitHub."
    } else {
        Add-Content $log "ERROR: git push termino con codigo $LASTEXITCODE"
    }
} else {
    Add-Content $log "Sin cambios detectados, no se hizo commit."
}
