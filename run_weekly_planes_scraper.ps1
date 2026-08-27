# Corre el scraper de PLANES de las webs individuales, versiona los datos en el repo
# principal y publica el dashboard en el repo de GitHub Pages ghl-planes-individuales.
# Pensado para Windows Task Scheduler (sin abrir Claude Code).

$proj      = "C:\Users\santiago.cristancho\OneDrive - Holding Hotelera GHL\Documentos\Automatizaciones"
$pagesRepo = Join-Path $proj "ghl-planes-y-ofertas-pages"
$py        = "C:\Users\santiago.cristancho\AppData\Local\Programs\Python\Python312\python.exe"
$log       = Join-Path $proj "reportes_ghl\cron_planes.log"
$stderrFile = Join-Path $proj "reportes_ghl\_last_stderr_planes.txt"

Set-Location $proj
$fecha = Get-Date -Format "yyyy-MM-dd HH:mm"
Add-Content $log "`n=== $fecha ==="

# stderr a archivo aparte (no 2>&1: en PS 5.1 eso envuelve stderr como NativeCommandError)
if (Test-Path $stderrFile) { Remove-Item $stderrFile -Force }
& $py "ghl_scraper_planes.py" 2> $stderrFile | Tee-Object -Append -FilePath $log
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
    Add-Content $log "ERROR: el scraper termino con codigo $exitCode"
    exit 1
}

# 1) Versiona datos + estado + dashboards en el repo principal (ghl-ofertas-individuales)
git add reportes_ghl/_planes_bil.json reportes_ghl/estado_planes.json `
        reportes_ghl/planes_dashboard_latest.html reportes_ghl/planes_dashboard_*.html
$changes = git diff --cached --name-only
if ($changes) {
    git commit -m "Escaneo semanal planes - $fecha" | Tee-Object -Append -FilePath $log
    git push | Tee-Object -Append -FilePath $log
    if ($LASTEXITCODE -ne 0) { Add-Content $log "ERROR: git push (repo principal) codigo $LASTEXITCODE" }
} else {
    Add-Content $log "Datos de planes sin cambios en el repo principal."
}

# 2) Publica el dashboard en el repo de GitHub Pages de planes
Copy-Item "reportes_ghl\planes_dashboard_latest.html" (Join-Path $pagesRepo "index.html") -Force
Set-Location $pagesRepo
git add index.html
$pchanges = git diff --cached --name-only
if ($pchanges) {
    git commit -m "Dashboard planes actualizado - $fecha" | Tee-Object -Append -FilePath $log
    git push | Tee-Object -Append -FilePath $log
    if ($LASTEXITCODE -eq 0) {
        Add-Content $log "Dashboard de planes publicado en https://santiagocristancho0722.github.io/ghl-planes-y-ofertas/"
    } else {
        Add-Content $log "ERROR: git push (pages planes) codigo $LASTEXITCODE"
    }
} else {
    Add-Content $log "Dashboard de planes sin cambios, no se publico."
}
Set-Location $proj
