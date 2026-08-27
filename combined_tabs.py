# -*- coding: utf-8 -*-
"""Une los dashboards de Planes y Ofertas en una sola experiencia: modifica el titulo
propio de cada dashboard a "Dashboard Planes y ofertas" e inyecta, al inicio del area
blanca de contenido (arriba de los KPIs), una barra de dos pestañas a todo el ancho
(Planes | Ofertas) que enlazan al otro dashboard.

Se importa desde ghl_scraper_individual_v3.py (active="ofertas") y ghl_scraper_planes.py
(active="planes") para que cada corrida semanal conserve las pestañas.

Ambos dashboards se publican en UN SOLO repo (ghl-planes-y-ofertas): index.html = planes,
ofertas.html = ofertas. Por eso las pills usan enlaces relativos dentro del mismo repo.
"""
import re

# Rutas relativas dentro del repo unico ghl-planes-y-ofertas:
#   index.html   -> Planes    (se enlaza como "./")
#   ofertas.html -> Ofertas
HREF_PLANES = "./"
HREF_OFERTAS = "ofertas.html"

COMBINED_TITLE = "Dashboard Planes y ofertas"

# Se inyecta al inicio del area blanca de contenido (justo despues de abrir .wrap).
_ANCHOR = '<div class="wrap">'

_STYLE = """
<style>
.poc-tabs{display:flex;gap:8px;margin:2px 0 18px}
.poc-tabs a{flex:1;text-align:center;text-decoration:none;font-size:13px;font-weight:600;
  letter-spacing:.2px;padding:9px 0;border-radius:8px;line-height:1;transition:.15s;
  background:#fff;color:var(--navy);border:1px solid var(--line)}
.poc-tabs a:hover{border-color:var(--blue);color:var(--mid)}
.poc-tabs a.active{background:var(--navy);color:#fff;border-color:var(--navy);cursor:default}
.foot-note{margin-top:46px;padding-top:22px;border-top:1px solid var(--line)}
</style>"""

# Quita cualquier barra .poc-tabs inyectada previamente (hace la funcion idempotente y
# permite mover la ubicacion sin re-generar desde cero).
_OLD_BLOCK_RE = re.compile(r'\s*<style>\s*\.poc-tabs.*?</div>', re.DOTALL)


def _pills(active):
    cp = ' class="active"' if active == "planes" else ""
    co = ' class="active"' if active == "ofertas" else ""
    hp = "#" if active == "planes" else HREF_PLANES
    ho = "#" if active == "ofertas" else HREF_OFERTAS
    return (f'{_STYLE}'
            f'<div class="poc-tabs">'
            f'<a href="{hp}"{cp}>Planes</a>'
            f'<a href="{ho}"{co}>Ofertas</a>'
            f'</div>')


def inject_combined_tabs(html, active):
    """active: "planes" | "ofertas". Devuelve el HTML con el titulo unificado y la barra
    de pestañas a todo el ancho al inicio del area blanca."""
    # 0) Quita cualquier barra previa (idempotente).
    html = _OLD_BLOCK_RE.sub("", html)
    # 1) Titulo visible (h1) — solo uno de los dos estara presente segun el dashboard.
    html = html.replace("<h1>Dashboard de Ofertas <b>·", f"<h1>{COMBINED_TITLE} <b>·")
    html = html.replace("<h1>Dashboard de Planes <b>·", f"<h1>{COMBINED_TITLE} <b>·")
    # 2) Titulo de la pestaña del navegador.
    html = html.replace("<title>Dashboard Ofertas GHL", f"<title>{COMBINED_TITLE} GHL")
    html = html.replace("<title>Dashboard Planes GHL", f"<title>{COMBINED_TITLE} GHL")
    # 3) Barra de pestañas a todo el ancho, al inicio del area blanca (arriba de los KPIs).
    html = html.replace(_ANCHOR, _ANCHOR + _pills(active), 1)
    return html
