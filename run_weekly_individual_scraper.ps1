# Corre el scraper de ofertas de webs individuales y sube los cambios a GitHub.
# Pensado para ejecutarse solo (Windows Task Scheduler), sin abrir Claude Code.

$proj = "C:\Users\santiago.cristancho\OneDrive - Holding Hotelera GHL\Documentos\Automatizaciones"
$py   = "C:\Users\santiago.cristancho\AppData\Local\Programs\Python\Python312\python.exe"
$log  = Join-Path $proj "reportes_ghl\cron_individual.log"
$stderrFile = Join-Path $proj "reportes_ghl\_last_stderr.txt"

Set-Location $proj
$fecha = Get-Date -Format "yyyy-MM-dd HH:mm"
Add-Content $log "`n=== $fecha ==="

# Auto-repara el navegador de Playwright: se ha visto desaparecer entre corridas (Playwright
# se auto-actualiza o algo lo remueve), lo que hacia fallar el escaneo con "Executable doesn't
# exist ... chrome-headless-shell.exe". Reinstalar es idempotente: no-op rapido si ya esta,
# lo descarga si falta. Se corre en el MISMO entorno de la tarea, justo antes de escanear.
& $py -m playwright install chromium 1>$null 2>$null
Add-Content $log "playwright install chromium -> exit $LASTEXITCODE"

# Nota: no se combina stdout/stderr con 2>&1 (eso envuelve cada linea de stderr como
# NativeCommandError en PowerShell 5.1 aunque el proceso termine bien). En su lugar,
# stderr se redirige a un archivo aparte (redireccion nativa, no merge de streams) para
# poder ver el traceback real si el scraper falla.
if (Test-Path $stderrFile) { Remove-Item $stderrFile -Force }
& $py "ghl_scraper_individual_v3.py" 2> $stderrFile | Tee-Object -Append -FilePath $log
$exitCode = $LASTEXITCODE

if (Test-Path $stderrFile) {
    $stderrContent = Get-Content $stderrFile -Raw
    if ($stderrContent) { Add-Content $log "`n--- STDERR ---`n$stderrContent" }
    Remove-Item $stderrFile -Force
}

if ($exitCode -eq 3) {
    Add-Content $log "Escaneo con demasiados errores tecnicos/red - NO se publica este cambio (ver JSON _FAILED_* para detalle)."
    exit 0
} elseif ($exitCode -ne 0) {
    Add-Content $log "ERROR: el scraper terminó con código $exitCode"
    exit 1
}

# 1) Versiona datos y dashboards en el repo de codigo (ghl-ofertas-individuales)
git add reportes_ghl/_individual_bil.json reportes_ghl/estado_ofertas_individual.json `
        reportes_ghl/ghl_dashboard_individual_latest.html reportes_ghl/ghl_dashboard_individual_*.html
$changes = git diff --cached --name-only
if ($changes) {
    git commit -m "Escaneo semanal ofertas individuales - $fecha" | Tee-Object -Append -FilePath $log
    git push | Tee-Object -Append -FilePath $log
    if ($LASTEXITCODE -ne 0) { Add-Content $log "ERROR: git push (repo codigo) codigo $LASTEXITCODE" }
} else {
    Add-Content $log "Datos de ofertas sin cambios en el repo de codigo."
}

# 2) Publica en el repo UNICO de dashboards (ghl-planes-y-ofertas), como ofertas.html
$combinedRepo = Join-Path $proj "ghl-planes-y-ofertas-pages"
Copy-Item "reportes_ghl\ghl_dashboard_individual_latest.html" (Join-Path $combinedRepo "ofertas.html") -Force
Set-Location $combinedRepo
git add ofertas.html
$pchanges = git diff --cached --name-only
if ($pchanges) {
    git commit -m "Dashboard ofertas actualizado - $fecha" | Tee-Object -Append -FilePath $log
    git push | Tee-Object -Append -FilePath $log
    if ($LASTEXITCODE -eq 0) {
        Add-Content $log "Ofertas publicado en https://santiagocristancho0722.github.io/ghl-planes-y-ofertas/ofertas.html"
    } else {
        Add-Content $log "ERROR: git push (repo combinado) codigo $LASTEXITCODE"
    }
} else {
    Add-Content $log "Dashboard de ofertas sin cambios, no se publico."
}
Set-Location $proj
