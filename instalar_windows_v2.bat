@echo off
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  GHL Dashboard Ofertas — Instalacion     ║
echo  ╚══════════════════════════════════════════╝
echo.

echo [1/3] Instalando dependencias...
pip install playwright --quiet
playwright install chromium
echo     OK

echo.
echo [2/3] Ejecutando primera extraccion...
python ghl_scraper_v2.py
echo     OK

echo.
echo [3/3] Programando tarea semanal (lunes 8AM)...
set "DIR=%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
schtasks /create /tn "GHL_Dashboard_Ofertas" /tr "\"%PY%\" \"%DIR%ghl_scraper_v2.py\"" /sc WEEKLY /d MON /st 08:00 /f

echo.
echo  ✅ Listo! El dashboard se actualizara cada lunes a las 8AM.
echo  📁 Reportes en: %DIR%reportes_ghl\
echo  📄 Ultima version: %DIR%reportes_ghl\ghl_dashboard_latest.html
echo.
pause
