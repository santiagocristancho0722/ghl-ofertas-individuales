# GHL Dashboard de Ofertas — Guía Claude Code

## ¿Qué hace este proyecto?
Extrae las ofertas activas de 43 hoteles GHL (ES + EN + PT),
las analiza contra buenas prácticas CRS y genera un dashboard
HTML interactivo con pestañas por hotel.

## Instalación (una sola vez)

```bash
# 1. Instalar dependencias
pip install playwright
playwright install chromium

# 2. Verificar instalación
python ghl_scraper_v2.py --test
```

## Correr manualmente con Claude Code

```bash
# Desde la carpeta del proyecto:
claude

# Luego escribe:
> Ejecuta el scraper GHL y genera el dashboard
```

## Programar automático cada semana

### Windows (PowerShell como Administrador):
```powershell
$action  = New-ScheduledTaskAction -Execute "python" -Argument "C:\ruta\ghl_scraper_v2.py"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 8am
Register-ScheduledTask -TaskName "GHL_Dashboard" -Action $action -Trigger $trigger -RunLevel Highest
```

### Mac/Linux (Terminal):
```bash
crontab -e
# Agregar esta línea:
0 8 * * 1 cd /ruta/del/proyecto && python3 ghl_scraper_v2.py >> reportes_ghl/cron.log 2>&1
```

## Archivos generados

```
reportes_ghl/
  ghl_dashboard_latest.html     ← siempre el más reciente (abrir este)
  ghl_dashboard_FECHA_HORA.html ← historial por semana
  ghl_ofertas_FECHA_HORA.json   ← datos en crudo
  cron.log                      ← log de ejecuciones automáticas
```

## Estructura del dashboard

Cada hotel tiene 4 sub-pestañas:
- 📋 Ofertas        → Cards con título, descripción, categoría, descuento, fechas
- 🔄 Comparativo    → Tabla ES vs EN campo por campo
- 🔍 Observaciones  → Notas de buenas prácticas CRS
- 📊 Resumen        → Métricas de completitud y errores

## Solución de problemas

| Problema | Solución |
|----------|----------|
| `playwright not found` | `pip install playwright && playwright install chromium` |
| Hotel devuelve 0 ofertas | El sitio puede estar en mantenimiento — revisar URL manualmente |
| Error de timeout | Aumentar `timeout=30000` a `timeout=45000` en `ghl_scraper_v2.py` |
