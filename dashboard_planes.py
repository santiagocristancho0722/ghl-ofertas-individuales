# -*- coding: utf-8 -*-
"""Generador de dashboard GHL de PLANES (bilingue), con el MISMO diseno visual que el
dashboard de ofertas (dashboard_v3.py): header degradado, KPIs, pestanas (Consolidado /
Detalle por hotel / Nuevos / Con cambios / Eliminados), filtros por pais/ciudad, tarjetas
con auditoria de buenas practicas y boton directo a cada plan.

Diferencias frente a ofertas: el dato estrella de cada plan es el PRECIO (no el descuento),
y las categorias son propias de planes (Romantico, Aniversario, Cumpleanos, ...).

Reutiliza de dashboard_v3.py todo lo que es identico (CSS, geografia, helpers, KPIs y
diffs de estado) para no divergir del diseno de ofertas.
"""
import json, re
from datetime import datetime
from pathlib import Path

import dashboard_v3 as dv3
from dashboard_v3 import (esc, safe_id, smart_title, fmt_vig, offer_title, estado_badge,
                          geo_of, GEO, COUNTRY_ORDER, group_by_hotel, CSS, _quality,
                          compute_kpis, stable_hash, offer_snapshot, change_summary, HASH_VERSION)

LANG_LABEL = {"es": "🇪🇸 Español", "en": "🇬🇧 English"}
LANG_OTHER = {"es": "español", "en": "inglés"}
TOTAL_PROPIEDADES = 45

# Colores por categoria de PLAN (mismo lenguaje visual que las categorias de ofertas)
CAT_COLORS = {
    "Romántico":        ("#fce8f3", "#8a1a5a"),
    "Aniversario":      ("#fef0e7", "#a8480b"),
    "Cumpleaños":       ("#fff3e0", "#8a4a00"),
    "Noche de bodas":   ("#f0eafb", "#5a2d9a"),
    "Fin de semana":    ("#e8f1fb", "#1a4a9a"),
    "Concierto/Evento": ("#eef0f4", "#3a4a6a"),
    "Familiar":         ("#e8f5ee", "#0f6e56"),
    "Gastronómico":     ("#e3f4f4", "#0d6b6b"),
    "Bienestar/Spa":    ("#e7f5ec", "#1a7a4a"),
    "Pasadía":          ("#e3f4f4", "#0d6b6b"),
    "Plan General":     ("#eef1f5", "#2A5E95"),
}

def cat_pill(cat):
    bg, fg = CAT_COLORS.get(cat, CAT_COLORS["Plan General"])
    return f'<span class="cat-pill" style="background:{bg};color:{fg}">{esc(cat)}</span>'

# Estilos propios de planes (columna T&Cs + bloque T&C en la tarjeta)
EXTRA_CSS = """<style>
.tbl-scroll{overflow-x:auto}
.master th:nth-child(7){min-width:200px}
.tyc-cell{display:block;max-width:280px;font-size:11px;color:#4a5a6a;line-height:1.45;
  max-height:66px;overflow:hidden;cursor:help}
.dtyc{margin-top:14px;background:#f8fafc;border:1px solid var(--line);border-left:3px solid var(--mid);
  border-radius:0 8px 8px 0;padding:12px 15px}
.dtyc-lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--mid);margin-bottom:6px}
.dtyc-txt{font-size:12.5px;color:#33414f;line-height:1.6}
</style>"""

def precio_val(o):
    if o.get("precio_desde"):
        return f'<span class="disc-pill">{esc(o["precio_desde"])}</span>'
    return '<span class="muted">Sin precio publicado</span>'

def desc_val(o):
    if o.get("descuento"):
        return f'<span class="ben-pill">{esc(o["descuento"])}</span>'
    return '<span class="muted">&mdash;</span>'

def tyc_val(o):
    """Celda de T&Cs para la tabla: texto compactado (con tooltip al texto completo)."""
    t = o.get("tyc")
    if not t:
        return '<span class="muted">&mdash;</span>'
    short = esc(t[:140]) + ("…" if len(t) > 140 else "")
    return f'<span class="tyc-cell" title="{esc(t)}">{short}</span>'

# ---------- Auditoria de buenas practicas (adaptada a planes) ----------
def bp_audit(u):
    es = u.get("es"); en = u.get("en"); base = es or en
    out = []
    titulo = base.get("titulo") or ""
    out.append(("ok" if len(titulo) >= 5 else "warn", "Título del plan",
                "Presente y descriptivo." if len(titulo) >= 5 else "Falta o demasiado corto."))
    c_ok = u["categoria"] != "Plan General"
    out.append(("ok" if c_ok else "warn", "Categoría definida",
                f'Clasificado como "{u["categoria"]}".' if c_ok else "Sin categoría específica (genérica)."))
    precio = (es or {}).get("precio_desde") or (en or {}).get("precio_desde")
    out.append(("ok" if precio else "warn", "Precio visible",
                f"El plan muestra precio ({precio})." if precio else "El plan no muestra un precio en la tarjeta."))
    desc_es = (es.get("descripcion") if es else "") or ""
    out.append(("ok" if len(desc_es) >= 15 else "warn", "Descripción del plan",
                "Incluye descripción de lo que ofrece el plan." if len(desc_es) >= 15 else "Descripción ausente o muy corta."))
    vig = (es or {}).get("vigencia") or (en or {}).get("vigencia")
    out.append(("ok" if vig else "warn", "Fechas de vigencia indicadas",
                "Indicadas en el plan." if vig else "No se indican fechas de vigencia (opcional en planes)."))
    out.append(("ok" if en else "err", "Versión en inglés disponible",
                "Existe versión en inglés." if en else "La página en inglés devuelve error 404."))
    for lang, o, etiqueta, gram_label in (("es", es, "español", "Redacción y gramática (español)"),
                                          ("en", en, "inglés", "Traducción y gramática (inglés)")):
        punct_label = f"Puntuación y espaciado ({etiqueta})"
        if not o:
            out.append(("warn", punct_label, f"No evaluable: no hay versión en {etiqueta}."))
            out.append(("warn", gram_label, f"No evaluable: no hay versión en {etiqueta}."))
            continue
        text = (o.get("titulo", "") + " " + o.get("titular", "") + " " + o.get("descripcion", ""))
        punct, grammar = _quality(text, lang)
        if punct:
            ej = ", ".join(p for p in punct if p.strip())
            out.append(("warn", punct_label, "Revisar espacios/puntuación pegada" + (f" (p. ej. «{ej}»)" if ej else "") + "."))
        else:
            out.append(("ok", punct_label, "Sin errores de puntuación o espaciado."))
        if grammar:
            out.append(("warn", gram_label, "Revisar — " + "; ".join(grammar) + "."))
        else:
            ok_txt = "Traducción correcta y bien estructurada." if lang == "en" else "Redacción correcta y bien estructurada."
            out.append(("ok", gram_label, ok_txt))
    return out

BP_ICON = {"ok": "✓", "warn": "!", "err": "✕"}

def render_bp(u):
    audit = bp_audit(u)
    items = ""
    for status, label, detail in audit:
        items += (f'<div class="bp-item bp-{status}"><span class="bp-ico">{BP_ICON[status]}</span>'
                  f'<span class="bp-txt"><b>{esc(label)}</b> &middot; <span>{esc(detail)}</span></span></div>')
    n_warn = sum(1 for s, _, _ in audit if s != "ok")
    chip = ('<span class="bp-chip bp-chip-ok">Cumple</span>' if n_warn == 0
            else f'<span class="bp-chip bp-chip-warn">{n_warn} observación(es)</span>')
    return f'<div class="bp"><div class="bp-title">Observaciones de buenas prácticas {chip}</div>{items}</div>'

# ---------- Tablas ----------
def render_master_table(plans, lang):
    body = ""
    for hotel, hofs in group_by_hotel(plans).items():
        code = hofs[0].get("hotel_code", "")
        country, city = geo_of(code)
        for i, u in enumerate(hofs):
            o = u.get(lang)
            ot = offer_title(u, o) if o else offer_title(u, u.get("es") or u.get("en"))
            search = esc(f"{hotel} {country} {city} {ot}".lower())
            rowattr = (f'data-hotelkey="{esc(code)}-{safe_id(hotel)}" data-country="{esc(country)}" '
                       f'data-city="{esc(city)}" data-search="{search}"')
            hcell = (f'<td class="hotel-group" rowspan="{len(hofs)}"><div class="hg-name">{esc(hotel)}</div>'
                     f'<div class="hg-loc">{esc(city)}, {esc(country)}</div>'
                     f'<div class="hg-count">{len(hofs)} plan(es)</div></td>') if i == 0 else ""
            if not o:
                body += (f'<tr {rowattr}>{hcell}<td><div class="m-offer">{esc(ot)}</div></td>'
                         f'<td>{cat_pill(u["categoria"])}</td>'
                         f'<td colspan="5" class="muted" style="text-align:center">No disponible en {LANG_OTHER[lang]} (página 404)</td>'
                         f'<td><span class="muted">&mdash;</span></td></tr>')
                continue
            vig = fmt_vig(o.get("vigencia")) or '<span class="muted">No publicada</span>'
            body += (f'<tr {rowattr}>{hcell}<td><div class="m-offer">{esc(ot)}</div></td>'
                     f'<td>{cat_pill(u["categoria"])}</td>'
                     f'<td><div class="date-main">{precio_val(o)}</div><div class="date-sub">Tarifa desde</div></td>'
                     f'<td>{desc_val(o)}</td>'
                     f'<td><div class="date-main">{vig}</div><div class="date-sub">Plan válido entre</div></td>'
                     f'<td>{tyc_val(o)}</td>'
                     f'<td>{estado_badge(u.get("_estado","nueva"))}</td>'
                     f'<td><a class="ver-link" href="{esc(o["url"])}" target="_blank">Ver plan &rarr;</a></td></tr>')
    return (f'<div class="tbl-card tbl-scroll"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Plan</th><th>Categoría</th><th>Precio desde</th><th>Descuento</th>'
            f'<th>Vigencia</th><th>T&amp;Cs</th><th>Estado</th><th>Detalle</th>'
            f'</tr></thead><tbody>{body}</tbody></table></div>')

def render_removed(removed):
    if not removed:
        return '<div class="empty-state">Aún no se han detectado planes eliminados. Aquí aparecerán los planes que dejen de estar activos en futuros escaneos.</div>'
    rows = ""
    for r in sorted(removed, key=lambda x: (x.get("fecha_baja", ""), x.get("hotel", "")), reverse=True):
        country = r.get("country", "—"); city = r.get("city", "—")
        search = esc(f'{r.get("hotel","")} {country} {city} {r.get("titulo","")}'.lower())
        rows += (f'<tr class="row-removed" data-country="{esc(country)}" data-city="{esc(city)}" data-search="{search}">'
                 f'<td><div class="m-offer">{esc(r.get("hotel",""))}</div>'
                 f'<div class="hg-loc">{esc(city)}, {esc(country)}</div></td>'
                 f'<td>{esc(r.get("titulo",""))}</td><td>{cat_pill(r.get("categoria","Plan General"))}</td>'
                 f'<td><span class="del-date">{esc(r.get("fecha_baja","—"))}</span></td></tr>')
    return (f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Plan</th><th>Categoría</th><th>Fecha de baja detectada</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def render_nuevas(nuevas):
    if not nuevas:
        return '<div class="empty-state">No se detectaron planes nuevos en el último escaneo.</div>'
    rows = ""
    for u in sorted(nuevas, key=lambda x: x.get("hotel", "")):
        country, city = geo_of(u.get("hotel_code", ""))
        base = u.get("es") or u.get("en") or {}
        ot = offer_title(u, base)
        fecha = u.get("_fecha_alta", "—")
        url = base.get("url", "")
        search = esc(f'{u.get("hotel","")} {country} {city} {ot}'.lower())
        ver = f'<a class="ver-link" href="{esc(url)}" target="_blank">Ver plan &rarr;</a>' if url else '<span class="muted">&mdash;</span>'
        rows += (f'<tr class="row-new" data-country="{esc(country)}" data-city="{esc(city)}" data-search="{search}">'
                 f'<td><div class="m-offer">{esc(u.get("hotel",""))}</div>'
                 f'<div class="hg-loc">{esc(city)}, {esc(country)}</div></td>'
                 f'<td>{esc(ot)}</td><td>{cat_pill(u.get("categoria","Plan General"))}</td>'
                 f'<td>{precio_val(base)}</td>'
                 f'<td><span class="add-date">{esc(fecha)}</span></td><td>{ver}</td></tr>')
    return (f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Plan</th><th>Categoría</th><th>Precio desde</th>'
            f'<th>Fecha de alta detectada</th><th>Detalle</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def render_cambios(cambiadas):
    if not cambiadas:
        return '<div class="empty-state">No se detectaron planes con cambios de contenido en el último escaneo.</div>'
    rows = ""
    for u in sorted(cambiadas, key=lambda x: x.get("hotel", "")):
        country, city = geo_of(u.get("hotel_code", ""))
        base = u.get("es") or u.get("en") or {}
        ot = offer_title(u, base)
        fecha = u.get("_fecha_cambio", "—")
        url = base.get("url", "")
        chips = "".join(f'<span class="chg-chip">{esc(c)}</span>' for c in (u.get("_cambios") or ["Contenido actualizado"]))
        search = esc(f'{u.get("hotel","")} {country} {city} {ot}'.lower())
        ver = f'<a class="ver-link" href="{esc(url)}" target="_blank">Ver plan &rarr;</a>' if url else '<span class="muted">&mdash;</span>'
        rows += (f'<tr class="row-chg" data-country="{esc(country)}" data-city="{esc(city)}" data-search="{search}">'
                 f'<td><div class="m-offer">{esc(u.get("hotel",""))}</div>'
                 f'<div class="hg-loc">{esc(city)}, {esc(country)}</div></td>'
                 f'<td>{esc(ot)}</td><td>{cat_pill(u.get("categoria","Plan General"))}</td>'
                 f'<td>{chips}</td>'
                 f'<td><span class="chg-date">{esc(fecha)}</span></td><td>{ver}</td></tr>')
    return (f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Plan</th><th>Categoría</th><th>Qué cambió</th>'
            f'<th>Fecha del cambio</th><th>Detalle</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def render_card(u, lang):
    o = u.get(lang)
    if not o:
        other = u.get("es") or u.get("en")
        return (f'<div class="na-card"><div class="na-ico">🌐</div>'
                f'<p>El plan <b>{esc(offer_title(u, other))}</b> no está publicado en <b>{LANG_OTHER[lang]}</b> en la web oficial '
                f'(la página devuelve error 404).</p>{render_bp(u)}</div>')
    precio = o.get("precio_desde") or "No publicado"
    disc = o.get("descuento") or "Sin descuento adicional"
    vig = fmt_vig(o.get("vigencia")) or "No publicada"
    tyc = o.get("tyc")
    tyc_html = (f'<div class="dtyc"><div class="dtyc-lbl">Términos y condiciones</div>'
                f'<div class="dtyc-txt">{esc(tyc)}</div></div>') if tyc else ""
    return f"""<div class="dcard">
  <div class="dcard-top">
    <div><h3>{esc(offer_title(u, o))}</h3>
      <div class="titular">{esc(o.get('titular') or '')}</div>
      <div style="margin-top:12px;display:flex;gap:8px;align-items:center">{cat_pill(u['categoria'])}{estado_badge(u.get('_estado','nueva'))}</div>
    </div>
    <div class="right"><div class="disc-big">{esc(precio)}</div><div class="disc-lbl">Precio desde</div></div>
  </div>
  <div class="dcard-body">
    <div class="ddesc">{esc(o.get('descripcion') or 'Sin descripción disponible.')}</div>
    <div class="dgrid">
      <div class="dfield"><div class="fl">Precio desde</div><div class="fv">{esc(precio)}</div></div>
      <div class="dfield"><div class="fl">Categoría del plan</div><div class="fv">{esc(u['categoria'])}</div></div>
      <div class="dfield"><div class="fl">Descuento en servicios (no es el precio del plan)</div><div class="fv">{esc(disc)}</div></div>
      <div class="dfield"><div class="fl">Vigencia · Plan válido entre</div><div class="fv">{vig}</div></div>
    </div>
    {tyc_html}
    {render_bp(u)}
    <div class="dfoot">
      <div class="muted" style="font-style:normal;color:var(--gray)">ID plan: <b>{esc(u['id'])}</b> · Fuente: web oficial GHL</div>
      <a class="btn-primary" href="{esc(o['url'])}" target="_blank">Ver este plan en la web &rarr;</a>
    </div>
  </div>
</div>"""

def build_html(plans, kpis, run_date, prev_date, removed=None):
    removed = removed or []
    nuevas = [o for o in plans if o.get("_estado") == "nueva"]
    cambiadas = [o for o in plans if o.get("_estado") == "cambio"]
    hoteles = group_by_hotel(plans)
    subtitle = list(hoteles.keys())[0] if len(hoteles) == 1 else f"{TOTAL_PROPIEDADES} propiedades"

    kpi_html = f"""
    <div class="kpi k-act"><div class="v">{kpis['activas']}</div><div class="l">Planes activos</div></div>
    <div class="kpi k-new"><div class="v">{kpis['nuevas']}</div><div class="l">Nuevos esta semana</div></div>
    <div class="kpi k-del"><div class="v">{kpis['eliminadas']}</div><div class="l">Eliminados esta semana</div></div>
    <div class="kpi k-chg"><div class="v">{kpis['cambios']}</div><div class="l">Con cambios</div></div>
    <div class="kpi k-scan"><div class="v">{kpis['escaneos']}</div><div class="l">Escaneos realizados</div></div>"""

    cons_tabs = "".join(
        f'<button class="langtab {"active" if i==0 else ""}" onclick="switchMasterLang(\'{l}\',this)">{LANG_LABEL[l]}</button>'
        for i, l in enumerate(("es", "en")))
    cons_views = "".join(
        f'<div class="langview {"active" if i==0 else ""}" id="master-{l}">{render_master_table(plans, l)}</div>'
        for i, l in enumerate(("es", "en")))

    geo_hotels = {u["hotel_code"]: geo_of(u["hotel_code"]) for u in plans}
    cities_by_country = {}
    for country, city in geo_hotels.values():
        cities_by_country.setdefault(country, set()).add(city)
    countries = [c for c in COUNTRY_ORDER if c in cities_by_country] + \
                sorted(c for c in cities_by_country if c not in COUNTRY_ORDER)
    cities_json = json.dumps({c: sorted(cities_by_country[c]) for c in countries}, ensure_ascii=False)
    all_cities = sorted({city for _, city in geo_hotels.values()})
    city_options = '<option value="all">Todas las ciudades</option>' + "".join(
        f'<option value="{esc(c)}">{esc(c)}</option>' for c in all_cities)

    def fbar(scope):
        ctabs = (f'<button class="ctab active" data-scope="{scope}" data-country="all" onclick="setCountry(this)">Todos</button>'
                 + "".join(f'<button class="ctab" data-scope="{scope}" data-country="{esc(c)}" onclick="setCountry(this)">{esc(c)}</button>' for c in countries))
        return (f'<div class="filterbar">'
                f'<div class="search-wrap"><input id="{scope}-search" placeholder="Buscar hotel, plan, ciudad o país…" oninput="applyScope(\'{scope}\')"></div>'
                f'<div class="country-tabs">{ctabs}</div>'
                f'<select id="{scope}-city" class="city-sel" onchange="applyScope(\'{scope}\')">{city_options}</select>'
                f'</div>')

    sections = ""
    for hotel, hofs in hoteles.items():
        hid = safe_id(hotel)
        hcountry, hcity = geo_of(hofs[0].get("hotel_code", ""))
        h_offers = " ".join(offer_title(u, u.get("es") or u.get("en")) for u in hofs)
        hsearch = esc(f"{hotel} {hcountry} {hcity} {h_offers}".lower())
        lang_tabs = "".join(
            f'<button class="langtab {"active" if li==0 else ""}" onclick="switchHotelLang(\'{hid}\',\'{l}\',this)">{LANG_LABEL[l]}</button>'
            for li, l in enumerate(("es", "en")))
        lang_views = ""
        for li, l in enumerate(("es", "en")):
            cards = "".join(render_card(u, l) for u in hofs)
            lang_views += f'<div class="langview {"active" if li==0 else ""}" id="hl-{hid}-{l}">{cards}</div>'
        sections += (f'<div class="hotel-section" data-country="{esc(hcountry)}" data-city="{esc(hcity)}" data-search="{hsearch}">'
                     f'<div class="hsec-head" onclick="toggleSec(this)">'
                     f'<div><div class="hsec-name">{esc(hotel)}</div><div class="hsec-loc">{esc(hcity)}, {esc(hcountry)}</div></div>'
                     f'<div class="hsec-meta"><span class="hsec-count">{len(hofs)} plan(es)</span><span class="hsec-chev">&#9656;</span></div>'
                     f'</div>'
                     f'<div class="hsec-body"><div class="langtabs">{lang_tabs}</div>{lang_views}</div></div>')

    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard Planes GHL — {esc(run_date)}</title>{CSS}{EXTRA_CSS}</head><body>
<div class="hdr"><div class="hdr-in">
  <h1>Dashboard de Planes <b>· {esc(subtitle)}</b></h1>
  <div class="meta">Último escaneo: <b>{esc(run_date)}</b><br>Análisis anterior: {esc(prev_date)}<br>Frecuencia: <b>Semanal</b></div>
</div></div>
<div class="wrap">
  <div class="kpis">{kpi_html}</div>

  <div class="maintabs">
    <button class="maintab active" onclick="switchMain('mp-consolidado',this)">Consolidado de planes activos <span class="tag">{len(plans)}</span></button>
    <button class="maintab" onclick="switchMain('mp-detalle',this)">Detalle por hotel <span class="tag">{TOTAL_PROPIEDADES}</span></button>
    <button class="maintab" onclick="switchMain('mp-nuevas',this)">Nuevos esta semana <span class="tag">{len(nuevas)}</span></button>
    <button class="maintab" onclick="switchMain('mp-cambios',this)">Con cambios <span class="tag">{len(cambiadas)}</span></button>
    <button class="maintab" onclick="switchMain('mp-eliminadas',this)">Planes eliminados <span class="tag">{len(removed)}</span></button>
  </div>

  <div class="mainpanel active" id="mp-consolidado">
    {fbar('cons')}
    <div class="langtabs">{cons_tabs}</div>
    {cons_views}
    <div class="no-results" id="cons-noresults">Sin resultados para los filtros seleccionados.</div>
  </div>

  <div class="mainpanel" id="mp-detalle">
    {fbar('det')}
    {sections}
    <div class="no-results" id="det-noresults">Ningún hotel coincide con los filtros seleccionados.</div>
  </div>

  <div class="mainpanel" id="mp-nuevas">
    <p style="color:var(--gray);font-size:12.5px;margin-bottom:14px">Planes que aparecieron por primera vez en el último escaneo (no estaban en el escaneo anterior).</p>
    {fbar('new')}
    {render_nuevas(nuevas)}
    <div class="no-results" id="new-noresults">Sin resultados para los filtros seleccionados.</div>
  </div>

  <div class="mainpanel" id="mp-cambios">
    <p style="color:var(--gray);font-size:12.5px;margin-bottom:14px">Planes que ya existían pero cuyo contenido cambió respecto al escaneo anterior (precio, título, titular o descripción).</p>
    {fbar('chg')}
    {render_cambios(cambiadas)}
    <div class="no-results" id="chg-noresults">Sin resultados para los filtros seleccionados.</div>
  </div>

  <div class="mainpanel" id="mp-eliminadas">
    <p style="color:var(--gray);font-size:12.5px;margin-bottom:14px">Planes que estaban activos en un escaneo anterior y dejaron de existir (página 404). Se registran de forma acumulada con la fecha en que se detectó la baja.</p>
    {fbar('del')}
    {render_removed(removed)}
    <div class="no-results" id="del-noresults">Sin resultados para los filtros seleccionados.</div>
  </div>

  <div class="foot-note">
    Dashboard de planes generado automáticamente desde las webs individuales de cada hotel GHL<br>
    El <b>precio</b> corresponde a la tarifa "desde" publicada en cada plan. Las observaciones de buenas prácticas son automáticas y orientativas.
  </div>
</div>
<script>
const GEO_CITIES = {cities_json};
function switchMain(id,btn){{
  document.querySelectorAll('.mainpanel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.maintab').forEach(b=>b.classList.remove('active'));
  document.getElementById(id).classList.add('active');btn.classList.add('active');
}}
const FSTATE = {{cons:{{country:'all'}}, det:{{country:'all'}}, new:{{country:'all'}}, chg:{{country:'all'}}, del:{{country:'all'}}}};
function toggleSec(head){{ head.parentElement.classList.toggle('open'); }}
function setCountry(btn){{
  const scope = btn.dataset.scope;
  btn.parentElement.querySelectorAll('.ctab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  FSTATE[scope].country = btn.dataset.country;
  const sel = document.getElementById(scope+'-city');
  let opts = '<option value="all">Todas las ciudades</option>';
  let cities = [];
  if(FSTATE[scope].country === 'all'){{ const s=new Set(); Object.values(GEO_CITIES).forEach(a=>a.forEach(c=>s.add(c))); cities=[...s].sort(); }}
  else {{ cities = GEO_CITIES[FSTATE[scope].country] || []; }}
  cities.forEach(c=>opts += '<option value="'+c+'">'+c+'</option>');
  sel.innerHTML = opts;
  applyScope(scope);
}}
function applyScope(scope){{
  const country = FSTATE[scope].country;
  const q = (document.getElementById(scope+'-search').value||'').toLowerCase().trim();
  const city = document.getElementById(scope+'-city').value;
  const match = (co,ci,text)=> (country==='all'||co===country)
              && (city==='all'||ci===city) && (q===''||(text||'').indexOf(q)>=0);
  if(scope === 'cons'){{
    let vis = 0;
    document.querySelectorAll('#mp-consolidado .master').forEach(tbl=>{{
      const groups = {{}};
      tbl.querySelectorAll('tbody tr').forEach(tr=>{{ (groups[tr.dataset.hotelkey] = groups[tr.dataset.hotelkey]||[]).push(tr); }});
      Object.values(groups).forEach(rows=>{{
        const r0 = rows[0];
        const ok = match(r0.dataset.country, r0.dataset.city, rows.map(r=>r.dataset.search||'').join(' '));
        rows.forEach(r=>r.style.display = ok?'':'none');
        if(ok && tbl.closest('.langview').classList.contains('active')) vis += rows.length;
      }});
    }});
    const n=document.getElementById('cons-noresults'); if(n) n.style.display = vis?'none':'block';
  }} else if(scope === 'det'){{
    let vis = 0;
    document.querySelectorAll('#mp-detalle .hotel-section').forEach(sec=>{{
      const ok = match(sec.dataset.country, sec.dataset.city, sec.dataset.search);
      sec.style.display = ok?'':'none'; if(ok) vis++;
    }});
    const n=document.getElementById('det-noresults'); if(n) n.style.display = vis?'none':'block';
  }} else {{
    const map = {{new:'#mp-nuevas', chg:'#mp-cambios', del:'#mp-eliminadas'}};
    let vis = 0;
    document.querySelectorAll(map[scope]+' .master tbody tr').forEach(tr=>{{
      const ok = match(tr.dataset.country, tr.dataset.city, tr.dataset.search);
      tr.style.display = ok?'':'none'; if(ok) vis++;
    }});
    const n=document.getElementById(scope+'-noresults'); if(n) n.style.display = vis?'none':'block';
  }}
}}
function switchMasterLang(lang,btn){{
  ['es','en'].forEach(l=>document.getElementById('master-'+l).classList.remove('active'));
  btn.parentElement.querySelectorAll('.langtab').forEach(b=>b.classList.remove('active'));
  document.getElementById('master-'+lang).classList.add('active');btn.classList.add('active');
}}
function switchHotelLang(hid,lang,btn){{
  ['es','en'].forEach(l=>{{const v=document.getElementById('hl-'+hid+'-'+l); if(v) v.classList.remove('active');}});
  btn.parentElement.querySelectorAll('.langtab').forEach(b=>b.classList.remove('active'));
  document.getElementById('hl-'+hid+'-'+lang).classList.add('active');btn.classList.add('active');
}}
</script></body></html>"""
