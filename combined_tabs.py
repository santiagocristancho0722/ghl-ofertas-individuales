# -*- coding: utf-8 -*-
"""Une los dashboards de Planes y Ofertas en una sola experiencia SIN un contenedor
aparte: modifica el titulo propio de cada dashboard a "Dashboard Planes y ofertas" e
inyecta, dentro del mismo header navy y debajo del titulo, dos pestañas tipo nube (pills)
que enlazan al otro dashboard.

Se importa desde ghl_scraper_individual_v3.py (active="ofertas") y ghl_scraper_planes.py
(active="planes") para que cada corrida semanal conserve las pestañas.
"""

URL_PLANES = "https://santiagocristancho0722.github.io/ghl-planes-individuales/"
URL_OFERTAS = "https://santiagocristancho0722.github.io/ghl-ofertas-individuales/"

COMBINED_TITLE = "Dashboard Planes y ofertas"

_ANCHOR = "Frecuencia: <b>Semanal</b></div>"

_STYLE = """
<style>
.poc-tabs{display:flex;gap:9px;margin-top:18px;flex-wrap:wrap;flex-basis:100%;width:100%}
.poc-tabs a{display:inline-block;text-decoration:none;font-size:13.5px;font-weight:600;
  padding:8px 24px;border-radius:999px;line-height:1;transition:.15s;
  background:rgba(255,255,255,.13);color:#eaf1f7;border:1px solid rgba(255,255,255,.32)}
.poc-tabs a:hover{background:rgba(255,255,255,.26);color:#fff}
.poc-tabs a.active{background:#fff;color:var(--navy);border-color:#fff;
  box-shadow:0 3px 10px rgba(0,0,0,.16);cursor:default}
</style>"""


def _pills(active):
    cp = ' class="active"' if active == "planes" else ""
    co = ' class="active"' if active == "ofertas" else ""
    hp = "#" if active == "planes" else URL_PLANES
    ho = "#" if active == "ofertas" else URL_OFERTAS
    return (f'{_STYLE}'
            f'<div class="poc-tabs">'
            f'<a href="{hp}"{cp}>Planes</a>'
            f'<a href="{ho}"{co}>Ofertas</a>'
            f'</div>')


def inject_combined_tabs(html, active):
    """active: "planes" | "ofertas". Devuelve el HTML con el titulo unificado y las pills."""
    # 1) Titulo visible (h1) — solo uno de los dos estara presente segun el dashboard.
    html = html.replace("<h1>Dashboard de Ofertas <b>·", f"<h1>{COMBINED_TITLE} <b>·")
    html = html.replace("<h1>Dashboard de Planes <b>·", f"<h1>{COMBINED_TITLE} <b>·")
    # 2) Titulo de la pestaña del navegador.
    html = html.replace("<title>Dashboard Ofertas GHL", f"<title>{COMBINED_TITLE} GHL")
    html = html.replace("<title>Dashboard Planes GHL", f"<title>{COMBINED_TITLE} GHL")
    # 3) Pills tipo nube, debajo del titulo (dentro del header navy).
    html = html.replace(_ANCHOR, _ANCHOR + _pills(active), 1)
    return html
