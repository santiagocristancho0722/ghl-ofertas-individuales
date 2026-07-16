#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo " ╔══════════════════════════════════════════╗"
echo " ║  GHL Dashboard Ofertas — Instalacion     ║"
echo " ╚══════════════════════════════════════════╝"
echo ""
echo "[1/3] Instalando dependencias..."
pip3 install playwright --quiet
python3 -m playwright install chromium
echo "    OK"
echo ""
echo "[2/3] Ejecutando primera extraccion..."
cd "$SCRIPT_DIR"
python3 ghl_scraper_v2.py
echo "    OK"
echo ""
echo "[3/3] Programando cron semanal (lunes 8AM)..."
CRON="0 8 * * 1 cd \"$SCRIPT_DIR\" && python3 ghl_scraper_v2.py >> \"$SCRIPT_DIR/reportes_ghl/cron.log\" 2>&1"
(crontab -l 2>/dev/null | grep -v "ghl_scraper"; echo "$CRON") | crontab -
echo "    OK"
echo ""
echo " ✅ Listo! El dashboard se actualizara cada lunes a las 8AM."
echo " 📁 Reportes en: $SCRIPT_DIR/reportes_ghl/"
echo " 📄 Ultima version: $SCRIPT_DIR/reportes_ghl/ghl_dashboard_latest.html"
echo ""
