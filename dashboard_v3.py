# -*- coding: utf-8 -*-
"""Generador de dashboard GHL v3 (bilingüe) — KPIs, consolidado agrupado por hotel y detalle con auditoría de buenas prácticas."""
import json, re, html
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

CAT_COLORS = {
    "Fin de Semana":     ("#f0eafb", "#5a2d9a"),
    "Compra Anticipada": ("#e8f1fb", "#1a4a9a"),
    "Ultimo Minuto":     ("#fdecea", "#b0281a"),
    "Minima Estadia":    ("#e8f5ee", "#0f6e56"),
    "Descuento Directo": ("#e3f4f4", "#0d6b6b"),
    "Romance":           ("#fce8f3", "#8a1a5a"),
    "Corporativo":       ("#eef0f4", "#3a4a6a"),
    "Temporada":         ("#fff3e0", "#8a4a00"),
    "Promo Especial":    ("#fef0e7", "#a8480b"),
    "Oferta General":    ("#eef1f5", "#2A5E95"),
}
LANG_LABEL = {"es": "🇪🇸 Español", "en": "🇬🇧 English"}
LANG_OTHER = {"es": "español", "en": "inglés"}
TOTAL_PROPIEDADES = 45  # Portafolio GHL fijo; lo que varía son las ofertas, no las propiedades

# Geografía por código de hotel (estable). País, Ciudad.
GEO = {
    "antofagasta": ("Chile", "Antofagasta"), "arsenal": ("Colombia", "Cartagena"),
    "bastionlux": ("Colombia", "Cartagena"), "biohotelghl": ("Colombia", "Bogotá"),
    "bioxury": ("Colombia", "Bogotá"), "calama": ("Chile", "Calama"),
    "cali": ("Colombia", "Cali"), "ghlabadiaplaza": ("Colombia", "Pereira"),
    "ghlarmeriareal": ("Colombia", "Cartagena"), "ghlcapital": ("Colombia", "Bogotá"),
    "ghlcoralesindias": ("Colombia", "Cartagena"), "ghlcostazul": ("Colombia", "Santa Marta"),
    "ghlhjloja": ("Ecuador", "Loja"), "ghllagotiticaca": ("Perú", "Puno"),
    "ghlmonteria": ("Colombia", "Montería"), "ghlportonmedellin": ("Colombia", "Medellín"),
    "ghlrelaxsunrise": ("Colombia", "San Andrés"), "ghlsonarequipa": ("Perú", "Arequipa"),
    "ghlsonbogota": ("Colombia", "Bogotá"), "ghlsonbucara": ("Colombia", "Bucaramanga"),
    "ghlsoncartagena": ("Colombia", "Cartagena"), "ghlsoncusco": ("Perú", "Cusco"),
    "ghlsonincapuno": ("Perú", "Puno"), "ghlsonmfl": ("Perú", "Lima"),
    "ghlsonolivar": ("Perú", "Lima"), "ghlsonosorno": ("Chile", "Osorno"),
    "ghlsonpereira": ("Colombia", "Pereira"), "ghlsonvallesagrado": ("Perú", "Yucay"),
    "ghlstylehamilton": ("Colombia", "Bogotá"), "ghlstyleoccidente": ("Colombia", "Bogotá"),
    "ghlstyleyopal": ("Colombia", "Yopal"), "irodmr": ("Colombia", "Santa Marta"),
    "irodsl": ("Colombia", "Santa Marta"), "irohbb": ("Colombia", "Santa Marta"),
    "irolago": ("Colombia", "Santa Marta"), "irorvd": ("Colombia", "Santa Marta"),
    "iroxxl": ("Colombia", "Santa Marta"), "latamhotel": ("Guatemala", "Quetzaltenango"),
    "makani": ("Colombia", "Cartagena"), "pllh": ("Chile", "Villarrica"),
    "sanlazaro": ("Colombia", "Cartagena"), "sonestaibague": ("Colombia", "Ibagué"),
    "tequendama": ("Colombia", "Bogotá"),
    # Propiedades que pueden reaparecer con ofertas:
    "ghlsonbarranq": ("Colombia", "Barranquilla"), "ghlstyle93": ("Colombia", "Bogotá"),
    "ghlvillavicencio": ("Colombia", "Villavicencio"), "ghlvillavi": ("Colombia", "Villavicencio"),
    "ghlhotelneiva": ("Colombia", "Neiva"),
    "ghlstylebarrancabermeja": ("Colombia", "Barrancabermeja"),
    "ghlclubelpuente": ("Colombia", "Girardot"), "ghlsonvalledupar": ("Colombia", "Valledupar"),
}
COUNTRY_ORDER = ["Colombia", "Perú", "Chile", "Ecuador", "Guatemala"]

def geo_of(code):
    return GEO.get(code, ("Otro", "—"))

def esc(s): return html.escape(str(s)) if s is not None else ""
def safe_id(s): return re.sub(r'[^a-z0-9]', '_', str(s).lower())
def fmt_vig(v): return v.replace(" - ", " &rarr; ") if v else None

# Palabras que van en minúscula dentro de un título (salvo la primera)
_SMALL = {"de", "la", "el", "en", "y", "a", "del", "los", "las", "un", "una", "por", "con",
          "the", "of", "and", "in", "to", "for", "an", "with", "by", "una"}

def smart_title(s):
    if not s: return s
    words = s.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if w.isupper() or w.islower():           # normaliza MAYÚSCULAS o minúsculas
            if i > 0 and lw in _SMALL:
                out.append(lw)
            else:
                out.append(lw[:1].upper() + lw[1:])
        else:
            out.append(w)                        # respeta acrónimos / mixto (GHL, etc.)
    return " ".join(out)

def _strip_hotel(title, hotel):
    t = title or ""
    base = re.sub(r'\bhotel\b', '', hotel, flags=re.I).strip()
    for v in (hotel, "Hotel " + base, base + " Hotel", base):
        if v.strip():
            t = re.sub(re.escape(v), "", t, flags=re.I)
    t = re.sub(r'\bhotel\b', '', t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip(" ,-")
    return t or (title or "")

def offer_title(u, o):
    """Nombre limpio de la oferta, sin el nombre del hotel y con capitalización elegante."""
    name = (o or {}).get("nombre_corto") or ""
    if not name or name.startswith("+") or len(name) < 4:
        name = _strip_hotel((o or {}).get("titulo", ""), u["hotel"])
    return smart_title(name)

def cat_pill(cat):
    bg, fg = CAT_COLORS.get(cat, CAT_COLORS["Oferta General"])
    return f'<span class="cat-pill" style="background:{bg};color:{fg}">{esc(cat)}</span>'

def estado_badge(estado):
    if estado == "nueva":  return '<span class="estado e-new"><span class="e-dot"></span>Nueva</span>'
    if estado == "cambio": return '<span class="estado e-chg"><span class="e-dot"></span>Con cambios</span>'
    return '<span class="estado e-keep"><span class="e-dot"></span>Vigente</span>'

def desc_val(o):
    if o.get("descuento"): return f'<span class="disc-pill">{esc(o["descuento"])}</span>'
    if o.get("beneficio"): return f'<span class="ben-pill">{esc(o["beneficio"])}</span>'
    return '<span class="muted">Sin valor especificado</span>'

# ---------- Auditoría de buenas prácticas ----------
def _quality(text, lang):
    """Devuelve (problemas_puntuacion, problemas_gramatica) para el texto en el idioma dado."""
    punct = sorted(set(re.findall(r'[–—][A-Za-z]|%[A-Za-z]|GHL[A-Z][a-z]', text)))
    grammar = []
    if lang == "en":
        residue = sorted(set(re.findall(
            r'\b(d[ií]as?|noches?|estad[ií]a|descuento|gratis|reserva|anticipaci[oó]n|disfruta|nuestra|villa)\b', text, re.I)))
        if residue: grammar.append("español sin traducir: " + ", ".join(residue))
        if re.search(r'lives the|live the world', text, re.I):
            grammar.append("calco del español (p. ej. “lives the World Cup”)")
        if re.search(r'[a-z]\s+[A-Z][a-z]+\s+included|drink\s+[A-Z][a-z]+\s+[A-Z]', text):
            grammar.append("frases o lista sin conectores ni puntuación")
    else:  # español: detectar inglés sin traducir y listas sin estructura
        eng = sorted(set(w.lower() for w in re.findall(
            r'\b(the|and|because|your|you|with|from|while|when|our|better|enjoy|rest|unwind|every|each|'
            r'game|world|stay|book|save|off|for|is|are|night|nights|breakfast|welcome|paradise|the\s)\b', text, re.I)))
        if len(eng) >= 2:
            grammar.append("texto en inglés sin traducir: " + ", ".join(eng[:6]))
        if re.search(r'[a-záéíóúñ]+\s+(Desayuno|Check-?in|Late|Early|Welcome|Breakfast|Almuerzo|Cena|Spa)\b', text):
            grammar.append("frases o lista sin conectores ni puntuación")
    return punct, grammar

def bp_audit(u):
    es = u.get("es"); en = u.get("en"); base = es or en
    out = []
    titulo = base.get("titulo") or ""
    out.append(("ok" if len(titulo) >= 5 else "warn", "Título de oferta",
                "Presente y descriptivo." if len(titulo) >= 5 else "Falta o demasiado corto."))
    c_ok = u["categoria"] != "Oferta General"
    out.append(("ok" if c_ok else "warn", "Categoría definida",
                f'Clasificada como "{u["categoria"]}".' if c_ok else "Sin categoría específica (genérica)."))
    desc_es = (es.get("descripcion") if es else "") or ""
    pct = bool(re.search(r'\d+\s*%', desc_es)) or bool((es or {}).get("descuento"))
    benef = bool(re.search(r'gratis|incluye|cortes[ií]a|beneficio|upgrade|2x1|2-for-1|free', desc_es, re.I)) or bool((es or {}).get("beneficio"))
    out.append(("ok" if (pct or benef) else "warn", "Descripción con % o beneficio",
                "Menciona el descuento o beneficio." if (pct or benef) else "El texto no menciona descuento ni beneficio."))
    # Fechas de vigencia: basta con que aparezcan (en la descripción o en su párrafo aparte)
    vig = (es or {}).get("vigencia") or (en or {}).get("vigencia")
    out.append(("ok" if vig else "warn", "Fechas de vigencia indicadas",
                "Indicadas en el párrafo de vigencia de la oferta." if vig else "No se indican fechas de vigencia."))
    out.append(("ok" if en else "err", "Versión en inglés disponible",
                "Existe versión en inglés." if en else "La página en inglés devuelve error 404."))
    # Calidad de redacción: puntuación/espaciado y gramática, para ESPAÑOL e INGLÉS
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
    items = ""
    for status, label, detail in bp_audit(u):
        items += (f'<div class="bp-item bp-{status}"><span class="bp-ico">{BP_ICON[status]}</span>'
                  f'<span class="bp-txt"><b>{esc(label)}</b> &middot; <span>{esc(detail)}</span></span></div>')
    n_warn = sum(1 for s, _, _ in bp_audit(u) if s != "ok")
    chip = ('<span class="bp-chip bp-chip-ok">Cumple</span>' if n_warn == 0
            else f'<span class="bp-chip bp-chip-warn">{n_warn} observación(es)</span>')
    return f'<div class="bp"><div class="bp-title">Observaciones de buenas prácticas {chip}</div>{items}</div>'

CSS = """<style>
:root{--navy:#023859;--mid:#2A5E95;--blue:#6399BA;--ink:#1a2533;--gray:#6b7785;--line:#e4e9f0;--bg:#eef2f7;--white:#fff;
--ok:#1a7a4a;--ok-bg:#e7f5ec;--amber:#b87503;--amber-bg:#fdf3e3;--red:#b0281a;--red-bg:#fbeae8;--muted:#aab4c0;}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--ink);font-size:13px;line-height:1.5}
.wrap{max-width:1280px;margin:0 auto;padding:0 24px 64px}
.hdr{background:linear-gradient(135deg,#023859 0%,#04507e 100%);color:#fff;padding:52px 0 48px}
.hdr-in{max-width:1280px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:14px}
.hdr h1{font-family:'DM Serif Display',serif;font-size:42px;font-weight:400;line-height:1.12}
.hdr h1 b{color:#8fc1de;font-weight:400}
.hdr .meta{text-align:right;font-size:12px;color:#a9cbe0;line-height:1.7}.hdr .meta b{color:#fff;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:48px 0 28px;position:relative;z-index:5}
.kpi{background:var(--white);border-radius:12px;padding:18px;box-shadow:0 6px 22px rgba(2,56,89,.10);border-top:3px solid var(--line)}
.kpi .v{font-size:38px;font-weight:700;line-height:1;letter-spacing:-1px}
.kpi .l{font-size:10.5px;color:var(--gray);text-transform:uppercase;letter-spacing:.7px;margin-top:7px;font-weight:600}
.kpi.k-act{border-top-color:var(--navy)}.kpi.k-act .v{color:var(--navy)}
.kpi.k-new{border-top-color:var(--ok)}.kpi.k-new .v{color:var(--ok)}
.kpi.k-del{border-top-color:var(--red)}.kpi.k-del .v{color:var(--red)}
.kpi.k-chg{border-top-color:var(--amber)}.kpi.k-chg .v{color:var(--amber)}
.kpi.k-scan{border-top-color:var(--blue)}.kpi.k-scan .v{color:var(--blue)}
.sec-title{font-size:15px;font-weight:700;color:var(--navy);margin:30px 0 14px;display:flex;align-items:center;gap:9px}
.sec-title .tag{font-size:10px;font-weight:600;color:var(--gray);background:var(--white);border:1px solid var(--line);padding:2px 9px;border-radius:20px;text-transform:uppercase;letter-spacing:.5px}
.maintabs{display:flex;gap:6px;margin:34px 0 0;border-bottom:2px solid var(--line);flex-wrap:wrap}
.maintab{padding:13px 26px;font-size:14px;font-weight:700;color:var(--gray);background:none;border:none;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;transition:all .15s;display:flex;align-items:center;gap:9px}
.maintab:hover{color:var(--navy)}
.maintab.active{color:var(--navy);border-bottom-color:var(--navy)}
.maintab .tag{font-size:10px;font-weight:600;color:var(--gray);background:var(--bg);padding:2px 9px;border-radius:20px}
.maintab.active .tag{background:#dde8f2;color:var(--mid)}
.mainpanel{display:none;padding-top:26px}.mainpanel.active{display:block}
.langtabs{display:inline-flex;gap:4px;background:#e2e9f1;padding:4px;border-radius:10px;margin-bottom:16px}
.langtab{padding:7px 18px;font-size:12.5px;font-weight:600;color:var(--gray);background:none;border:none;border-radius:7px;cursor:pointer;transition:all .15s}
.langtab:hover{color:var(--navy)}
.langtab.active{background:var(--white);color:var(--navy);box-shadow:0 1px 4px rgba(2,56,89,.12)}
.langview{display:none}.langview.active{display:block}
.tbl-card{background:var(--white);border-radius:12px;border:1px solid var(--line);overflow:hidden;box-shadow:0 2px 10px rgba(2,56,89,.05)}
table.master{width:100%;border-collapse:collapse;font-size:12.5px}
.master thead th{background:#f6f9fc;color:var(--mid);font-size:10px;text-transform:uppercase;letter-spacing:.6px;font-weight:700;text-align:left;padding:12px 14px;border-bottom:2px solid var(--line);white-space:nowrap}
.master tbody td{padding:13px 14px;border-bottom:1px solid var(--line);vertical-align:middle}
.master tbody tr:last-child td{border-bottom:none}
.master tbody tr:hover td{background:#f9fbfd}
.hotel-group{background:#f1f6fb !important;border-right:2px solid var(--line);vertical-align:top !important}
.hg-name{font-weight:700;color:var(--navy);font-size:13.5px;line-height:1.3}
.hg-loc{font-size:11px;color:var(--mid);margin-top:2px}
.hg-count{font-size:10.5px;color:var(--gray);margin-top:3px;text-transform:uppercase;letter-spacing:.4px}
.filterbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:16px}
.search-wrap{position:relative;flex:1;min-width:230px}
.search-wrap input{width:100%;padding:10px 14px 10px 34px;font-size:13px;border:1.5px solid var(--line);border-radius:9px;background:var(--white) url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"15\" height=\"15\" fill=\"none\" stroke=\"%236b7785\" stroke-width=\"2\"><circle cx=\"6.5\" cy=\"6.5\" r=\"5\"/><path d=\"M14 14l-3.5-3.5\"/></svg>') no-repeat 11px center;font-family:inherit;color:var(--ink)}
.search-wrap input:focus{outline:none;border-color:var(--blue)}
.country-tabs{display:flex;gap:4px;flex-wrap:wrap}
.ctab{padding:7px 15px;font-size:12px;font-weight:600;color:var(--gray);background:var(--white);border:1.5px solid var(--line);border-radius:20px;cursor:pointer;transition:all .15s}
.ctab:hover{border-color:var(--blue);color:var(--navy)}
.ctab.active{background:var(--navy);color:#fff;border-color:var(--navy)}
.city-sel{padding:9px 12px;font-size:12.5px;border:1.5px solid var(--line);border-radius:9px;background:var(--white);color:var(--ink);font-family:inherit;cursor:pointer;min-width:160px}
.city-sel:focus{outline:none;border-color:var(--blue)}
.no-results{padding:30px;text-align:center;color:var(--gray);font-size:13px;display:none}
.empty-state{padding:36px;text-align:center;color:var(--gray);font-size:13px;background:var(--white);border-radius:12px;border:1px solid var(--line)}
.del-date{font-size:11.5px;color:var(--red);font-weight:600}
tr.row-removed td{background:#fdf7f6}
.add-date{font-size:11.5px;color:var(--ok);font-weight:600}
tr.row-new td{background:#f5faf6}
.chg-date{font-size:11.5px;color:var(--amber);font-weight:600}
tr.row-chg td{background:#fdfaf3}
.chg-chip{display:inline-block;background:var(--amber-bg);color:var(--amber);font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:5px;margin:2px 4px 2px 0}
.m-offer{font-weight:600;color:var(--navy);font-size:12.5px}
.cat-pill{display:inline-block;font-size:10px;font-weight:700;padding:3px 9px;border-radius:5px;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap}
.disc-pill{display:inline-block;background:var(--navy);color:#fff;font-size:12px;font-weight:700;padding:3px 10px;border-radius:6px}
.ben-pill{display:inline-block;background:var(--ok-bg);color:var(--ok);font-size:11px;font-weight:700;padding:3px 9px;border-radius:6px}
.muted{color:var(--muted);font-style:italic;font-size:11.5px}
.date-main{font-weight:600;color:var(--ink);font-size:12px}.date-sub{font-size:10.5px;color:var(--gray)}
.estado{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;font-weight:700;padding:3px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:.3px}
.e-new{background:var(--ok-bg);color:var(--ok)}.e-chg{background:var(--amber-bg);color:var(--amber)}.e-keep{background:#eef1f5;color:var(--gray)}
.e-dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.ver-link{display:inline-flex;align-items:center;gap:5px;color:var(--mid);font-weight:600;font-size:11.5px;text-decoration:none;white-space:nowrap;border:1px solid var(--line);padding:5px 11px;border-radius:7px;transition:all .15s}
.ver-link:hover{background:var(--navy);color:#fff;border-color:var(--navy)}
.hotel-section{border:1px solid var(--line);border-radius:12px;background:var(--white);margin-bottom:12px;overflow:hidden;box-shadow:0 1px 4px rgba(2,56,89,.04)}
.hsec-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 20px;cursor:pointer;transition:background .15s}
.hsec-head:hover{background:#f6f9fc}
.hsec-name{font-size:15px;font-weight:700;color:var(--navy)}
.hsec-loc{font-size:12px;color:var(--mid);margin-top:2px}
.hsec-meta{display:flex;align-items:center;gap:16px;flex:none}
.hsec-count{font-size:10.5px;color:var(--gray);text-transform:uppercase;letter-spacing:.4px;font-weight:600}
.hsec-chev{font-size:15px;color:var(--blue);transition:transform .18s;display:inline-block}
.hotel-section.open .hsec-chev{transform:rotate(90deg)}
.hsec-body{display:none;padding:18px 20px 20px;border-top:1px solid var(--line)}
.hotel-section.open .hsec-body{display:block}
.dcard{background:var(--white);border-radius:14px;border:1px solid var(--line);overflow:hidden;box-shadow:0 3px 14px rgba(2,56,89,.06);margin-bottom:18px}
.dcard-top{padding:20px 24px;background:linear-gradient(135deg,#f6f9fc,#eef4f9);border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:flex-start;gap:18px}
.dcard-top h3{font-size:19px;color:var(--navy);font-weight:700;line-height:1.25}
.dcard-top .titular{font-size:12px;color:var(--mid);font-weight:600;margin-top:6px;text-transform:uppercase;letter-spacing:.4px}
.dcard-top .right{text-align:right;flex:none}
.dcard-top .disc-big{font-size:28px;font-weight:800;color:var(--navy);line-height:1}
.dcard-top .disc-lbl{font-size:10px;color:var(--gray);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.dcard-body{padding:20px 24px}
.dgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:4px}
.dfield{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:12px 15px}
.dfield .fl{font-size:10px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px}
.dfield .fv{font-size:13px;color:var(--ink);font-weight:600}
.ddesc{font-size:13.5px;color:#33414f;line-height:1.65;background:#f8fafc;border-left:3px solid var(--blue);border-radius:0 8px 8px 0;padding:13px 17px;margin-bottom:16px}
.bp{margin-top:18px;border-top:1px solid var(--line);padding-top:14px}
.bp-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--mid);margin-bottom:10px;display:flex;align-items:center;gap:10px}
.bp-chip{font-size:10px;font-weight:700;padding:2px 9px;border-radius:20px;text-transform:none;letter-spacing:0}
.bp-chip-ok{background:var(--ok-bg);color:var(--ok)}.bp-chip-warn{background:var(--amber-bg);color:var(--amber)}
.bp-item{display:flex;gap:10px;align-items:flex-start;padding:7px 0;font-size:12.5px;border-bottom:1px dashed var(--line)}
.bp-item:last-child{border-bottom:none}
.bp-ico{flex:none;width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;margin-top:1px}
.bp-ok .bp-ico{background:var(--ok)}.bp-warn .bp-ico{background:var(--amber)}.bp-err .bp-ico{background:var(--red)}
.bp-txt b{color:var(--ink)}.bp-txt span{color:var(--gray)}
.dfoot{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-top:16px}
.btn-primary{display:inline-flex;align-items:center;gap:7px;background:var(--navy);color:#fff;text-decoration:none;font-weight:600;font-size:13px;padding:10px 18px;border-radius:9px;transition:all .15s}
.btn-primary:hover{background:#04507e}
.na-card{background:var(--white);border:1px dashed var(--line);border-radius:14px;padding:40px 26px;text-align:center;color:var(--gray);margin-bottom:18px}
.na-card .na-ico{font-size:28px;margin-bottom:8px}.na-card b{color:var(--ink)}
.foot-note{text-align:center;color:var(--gray);font-size:11px;margin-top:34px;line-height:1.7}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.dgrid{grid-template-columns:1fr}}
</style>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">"""

def group_by_hotel(offers):
    g = OrderedDict()
    for u in offers:
        g.setdefault(u["hotel"], []).append(u)
    return g

def render_master_table(offers, lang):
    body = ""
    for hotel, hofs in group_by_hotel(offers).items():
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
                     f'<div class="hg-count">{len(hofs)} oferta(s)</div></td>') if i == 0 else ""
            if not o:
                body += (f'<tr {rowattr}>{hcell}<td><div class="m-offer">{esc(ot)}</div></td>'
                         f'<td>{cat_pill(u["categoria"])}</td>'
                         f'<td colspan="4" class="muted" style="text-align:center">No disponible en {LANG_OTHER[lang]} (página 404)</td>'
                         f'<td><span class="muted">&mdash;</span></td></tr>')
                continue
            vig = fmt_vig(o.get("vigencia")) or '<span class="muted">No publicada</span>'
            precio = esc(o["precio_desde"]) if o.get("precio_desde") else '<span class="muted">&mdash;</span>'
            body += (f'<tr {rowattr}>{hcell}<td><div class="m-offer">{esc(ot)}</div></td>'
                     f'<td>{cat_pill(u["categoria"])}</td><td>{desc_val(o)}</td>'
                     f'<td><div class="date-main">{vig}</div><div class="date-sub">Oferta válida entre</div></td>'
                     f'<td><div class="date-main">{precio}</div><div class="date-sub">Tarifa desde</div></td>'
                     f'<td>{estado_badge(u.get("_estado","nueva"))}</td>'
                     f'<td><a class="ver-link" href="{esc(o["url"])}" target="_blank">Ver &rarr;</a></td></tr>')
    return (f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Oferta</th><th>Categoría</th><th>Descuento / Beneficio</th>'
            f'<th>Vigencia de la oferta</th><th>Tarifa desde</th><th>Estado</th><th>Detalle</th>'
            f'</tr></thead><tbody>{body}</tbody></table></div>')

def render_removed(removed):
    if not removed:
        return '<div class="empty-state">Aún no se han detectado ofertas eliminadas. Aquí aparecerán las ofertas que dejen de estar activas en futuros escaneos.</div>'
    rows = ""
    for r in sorted(removed, key=lambda x: (x.get("fecha_baja", ""), x.get("hotel", "")), reverse=True):
        country = r.get("country", "—"); city = r.get("city", "—")
        search = esc(f'{r.get("hotel","")} {country} {city} {r.get("titulo","")}'.lower())
        rows += (f'<tr class="row-removed" data-country="{esc(country)}" data-city="{esc(city)}" data-search="{search}">'
                 f'<td><div class="m-offer">{esc(r.get("hotel",""))}</div>'
                 f'<div class="hg-loc">{esc(city)}, {esc(country)}</div></td>'
                 f'<td>{esc(r.get("titulo",""))}</td><td>{cat_pill(r.get("categoria","Oferta General"))}</td>'
                 f'<td><span class="del-date">{esc(r.get("fecha_baja","—"))}</span></td></tr>')
    return (f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Oferta</th><th>Categoría</th><th>Fecha de baja detectada</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def render_nuevas(nuevas):
    if not nuevas:
        return '<div class="empty-state">No se detectaron ofertas nuevas en el último escaneo.</div>'
    rows = ""
    for u in sorted(nuevas, key=lambda x: x.get("hotel", "")):
        country, city = geo_of(u.get("hotel_code", ""))
        base = u.get("es") or u.get("en") or {}
        ot = offer_title(u, base)
        fecha = u.get("_fecha_alta", "—")
        url = base.get("url", "")
        search = esc(f'{u.get("hotel","")} {country} {city} {ot}'.lower())
        ver = f'<a class="ver-link" href="{esc(url)}" target="_blank">Ver &rarr;</a>' if url else '<span class="muted">&mdash;</span>'
        rows += (f'<tr class="row-new" data-country="{esc(country)}" data-city="{esc(city)}" data-search="{search}">'
                 f'<td><div class="m-offer">{esc(u.get("hotel",""))}</div>'
                 f'<div class="hg-loc">{esc(city)}, {esc(country)}</div></td>'
                 f'<td>{esc(ot)}</td><td>{cat_pill(u.get("categoria","Oferta General"))}</td>'
                 f'<td>{desc_val(base)}</td>'
                 f'<td><span class="add-date">{esc(fecha)}</span></td><td>{ver}</td></tr>')
    return (f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Oferta</th><th>Categoría</th><th>Descuento / Beneficio</th>'
            f'<th>Fecha de alta detectada</th><th>Detalle</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def render_cambios(cambiadas):
    if not cambiadas:
        return '<div class="empty-state">No se detectaron ofertas con cambios de contenido en el último escaneo.</div>'
    rows = ""
    for u in sorted(cambiadas, key=lambda x: x.get("hotel", "")):
        country, city = geo_of(u.get("hotel_code", ""))
        base = u.get("es") or u.get("en") or {}
        ot = offer_title(u, base)
        fecha = u.get("_fecha_cambio", "—")
        url = base.get("url", "")
        chips = "".join(f'<span class="chg-chip">{esc(c)}</span>' for c in (u.get("_cambios") or ["Contenido actualizado"]))
        search = esc(f'{u.get("hotel","")} {country} {city} {ot}'.lower())
        ver = f'<a class="ver-link" href="{esc(url)}" target="_blank">Ver &rarr;</a>' if url else '<span class="muted">&mdash;</span>'
        rows += (f'<tr class="row-chg" data-country="{esc(country)}" data-city="{esc(city)}" data-search="{search}">'
                 f'<td><div class="m-offer">{esc(u.get("hotel",""))}</div>'
                 f'<div class="hg-loc">{esc(city)}, {esc(country)}</div></td>'
                 f'<td>{esc(ot)}</td><td>{cat_pill(u.get("categoria","Oferta General"))}</td>'
                 f'<td>{chips}</td>'
                 f'<td><span class="chg-date">{esc(fecha)}</span></td><td>{ver}</td></tr>')
    return (f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Oferta</th><th>Categoría</th><th>Qué cambió</th>'
            f'<th>Fecha del cambio</th><th>Detalle</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def render_card(u, lang):
    o = u.get(lang)
    if not o:
        other = u.get("es") or u.get("en")
        return (f'<div class="na-card"><div class="na-ico">🌐</div>'
                f'<p>La oferta <b>{esc(offer_title(u, other))}</b> no está publicada en <b>{LANG_OTHER[lang]}</b> en la web oficial '
                f'(la página devuelve error 404).</p>{render_bp(u)}</div>')
    disc = o.get("descuento") or o.get("beneficio") or "—"
    vig = fmt_vig(o.get("vigencia")) or "No publicada"
    precio = o.get("precio_desde") or "No publicado"
    return f"""<div class="dcard">
  <div class="dcard-top">
    <div><h3>{esc(offer_title(u, o))}</h3>
      <div class="titular">{esc(o.get('titular') or '')}</div>
      <div style="margin-top:12px;display:flex;gap:8px;align-items:center">{cat_pill(u['categoria'])}{estado_badge(u.get('_estado','nueva'))}</div>
    </div>
    <div class="right"><div class="disc-big">{esc(disc)}</div><div class="disc-lbl">Descuento</div></div>
  </div>
  <div class="dcard-body">
    <div class="ddesc">{esc(o.get('descripcion') or 'Sin descripción disponible.')}</div>
    <div class="dgrid">
      <div class="dfield"><div class="fl">Vigencia · Oferta válida entre</div><div class="fv">{vig}</div></div>
      <div class="dfield"><div class="fl">Categoría de la oferta</div><div class="fv">{esc(u['categoria'])}</div></div>
      <div class="dfield"><div class="fl">Tarifa desde</div><div class="fv">{esc(precio)}</div></div>
      <div class="dfield"><div class="fl">Descuento / Beneficio</div><div class="fv">{esc(disc)}</div></div>
    </div>
    {render_bp(u)}
    <div class="dfoot">
      <div class="muted" style="font-style:normal;color:var(--gray)">ID oferta: <b>{esc(u['id'])}</b> · Fuente: web oficial GHL</div>
      <a class="btn-primary" href="{esc(o['url'])}" target="_blank">Ver esta oferta en la web &rarr;</a>
    </div>
  </div>
</div>"""

def build_html(offers, kpis, run_date, prev_date, removed=None):
    removed = removed or []
    nuevas = [o for o in offers if o.get("_estado") == "nueva"]
    cambiadas = [o for o in offers if o.get("_estado") == "cambio"]
    hoteles = group_by_hotel(offers)
    subtitle = list(hoteles.keys())[0] if len(hoteles) == 1 else f"{TOTAL_PROPIEDADES} propiedades"

    kpi_html = f"""
    <div class="kpi k-act"><div class="v">{kpis['activas']}</div><div class="l">Ofertas activas</div></div>
    <div class="kpi k-new"><div class="v">{kpis['nuevas']}</div><div class="l">Nuevas esta semana</div></div>
    <div class="kpi k-del"><div class="v">{kpis['eliminadas']}</div><div class="l">Eliminadas esta semana</div></div>
    <div class="kpi k-chg"><div class="v">{kpis['cambios']}</div><div class="l">Con cambios</div></div>
    <div class="kpi k-scan"><div class="v">{kpis['escaneos']}</div><div class="l">Escaneos realizados</div></div>"""

    cons_tabs = "".join(
        f'<button class="langtab {"active" if i==0 else ""}" onclick="switchMasterLang(\'{l}\',this)">{LANG_LABEL[l]}</button>'
        for i, l in enumerate(("es", "en")))
    cons_views = "".join(
        f'<div class="langview {"active" if i==0 else ""}" id="master-{l}">{render_master_table(offers, l)}</div>'
        for i, l in enumerate(("es", "en")))

    # Filtros geográficos del consolidado
    geo_hotels = {u["hotel_code"]: geo_of(u["hotel_code"]) for u in offers}
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
                f'<div class="search-wrap"><input id="{scope}-search" placeholder="Buscar hotel, oferta, ciudad o país…" oninput="applyScope(\'{scope}\')"></div>'
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
                     f'<div class="hsec-meta"><span class="hsec-count">{len(hofs)} oferta(s)</span><span class="hsec-chev">&#9656;</span></div>'
                     f'</div>'
                     f'<div class="hsec-body"><div class="langtabs">{lang_tabs}</div>{lang_views}</div></div>')

    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard Ofertas GHL — {esc(run_date)}</title>{CSS}</head><body>
<div class="hdr"><div class="hdr-in">
  <h1>Dashboard de Ofertas <b>· {esc(subtitle)}</b></h1>
  <div class="meta">Último escaneo: <b>{esc(run_date)}</b><br>Análisis anterior: {esc(prev_date)}<br>Frecuencia: <b>Semanal</b></div>
</div></div>
<div class="wrap">
  <div class="kpis">{kpi_html}</div>

  <div class="maintabs">
    <button class="maintab active" onclick="switchMain('mp-consolidado',this)">Consolidado de ofertas activas <span class="tag">{len(offers)}</span></button>
    <button class="maintab" onclick="switchMain('mp-detalle',this)">Detalle por hotel <span class="tag">{TOTAL_PROPIEDADES}</span></button>
    <button class="maintab" onclick="switchMain('mp-nuevas',this)">Nuevas esta semana <span class="tag">{len(nuevas)}</span></button>
    <button class="maintab" onclick="switchMain('mp-cambios',this)">Con cambios <span class="tag">{len(cambiadas)}</span></button>
    <button class="maintab" onclick="switchMain('mp-eliminadas',this)">Ofertas eliminadas <span class="tag">{len(removed)}</span></button>
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
    <p style="color:var(--gray);font-size:12.5px;margin-bottom:14px">Ofertas que aparecieron por primera vez en el último escaneo (no estaban en el escaneo anterior).</p>
    {fbar('new')}
    {render_nuevas(nuevas)}
    <div class="no-results" id="new-noresults">Sin resultados para los filtros seleccionados.</div>
  </div>

  <div class="mainpanel" id="mp-cambios">
    <p style="color:var(--gray);font-size:12.5px;margin-bottom:14px">Ofertas que ya existían pero cuyo contenido cambió respecto al escaneo anterior (descuento, título, titular o descripción).</p>
    {fbar('chg')}
    {render_cambios(cambiadas)}
    <div class="no-results" id="chg-noresults">Sin resultados para los filtros seleccionados.</div>
  </div>

  <div class="mainpanel" id="mp-eliminadas">
    <p style="color:var(--gray);font-size:12.5px;margin-bottom:14px">Ofertas que estaban activas en un escaneo anterior y dejaron de existir (página 404). Se registran de forma acumulada con la fecha en que se detectó la baja.</p>
    {fbar('del')}
    {render_removed(removed)}
    <div class="no-results" id="del-noresults">Sin resultados para los filtros seleccionados.</div>
  </div>

  <div class="foot-note">
    Dashboard generado automáticamente desde la web oficial GHL Hoteles · ghlhoteles.com/es/ofertas y /en/offers<br>
    La <b>vigencia</b> corresponde al rango "Oferta válida entre" publicado. Las observaciones de buenas prácticas son automáticas y orientativas.
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
  }} else if(scope === 'new'){{
    let vis = 0;
    document.querySelectorAll('#mp-nuevas .master tbody tr').forEach(tr=>{{
      const ok = match(tr.dataset.country, tr.dataset.city, tr.dataset.search);
      tr.style.display = ok?'':'none'; if(ok) vis++;
    }});
    const n=document.getElementById('new-noresults'); if(n) n.style.display = vis?'none':'block';
  }} else if(scope === 'chg'){{
    let vis = 0;
    document.querySelectorAll('#mp-cambios .master tbody tr').forEach(tr=>{{
      const ok = match(tr.dataset.country, tr.dataset.city, tr.dataset.search);
      tr.style.display = ok?'':'none'; if(ok) vis++;
    }});
    const n=document.getElementById('chg-noresults'); if(n) n.style.display = vis?'none':'block';
  }} else if(scope === 'del'){{
    let vis = 0;
    document.querySelectorAll('#mp-eliminadas .master tbody tr').forEach(tr=>{{
      const ok = match(tr.dataset.country, tr.dataset.city, tr.dataset.search);
      tr.style.display = ok?'':'none'; if(ok) vis++;
    }});
    const n=document.getElementById('del-noresults'); if(n) n.style.display = vis?'none':'block';
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

HASH_VERSION = 2  # v2: hash estable (excluye precio "Desde", que fluctúa a diario)

def stable_hash(o):
    """Hash de cambios basado solo en lo esencial de la oferta (no en el precio en vivo)."""
    import hashlib
    base = o.get("es") or o.get("en") or {}
    payload = [base.get("titulo"), base.get("titular"), base.get("descripcion"), base.get("descuento")]
    return hashlib.md5(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()

def offer_snapshot(o):
    """Instantánea enriquecida de una oferta, para el estado y el archivo de eliminadas."""
    base = o.get("es") or o.get("en") or {}
    country, city = geo_of(o.get("hotel_code", ""))
    return {"hash": o.get("_hash", ""), "hotel": o.get("hotel", ""), "hotel_code": o.get("hotel_code", ""),
            "titulo": offer_title(o, base), "categoria": o.get("categoria", "Oferta General"),
            "url": base.get("url", ""), "country": country, "city": city,
            "c_tit": base.get("titulo"), "c_sub": base.get("titular"),
            "c_desc": base.get("descripcion"), "c_disc": base.get("descuento") or base.get("beneficio")}

def change_summary(o, prevsnap):
    """Describe qué cambió entre el snapshot anterior y la oferta actual."""
    base = o.get("es") or o.get("en") or {}
    ch = []
    pd, cd = prevsnap.get("c_disc"), base.get("descuento") or base.get("beneficio")
    if (pd or "") != (cd or ""):
        ch.append(f"Descuento/beneficio: {pd or '—'} → {cd or '—'}")
    if (prevsnap.get("c_tit") or "") != (base.get("titulo") or ""):
        ch.append("Título modificado")
    if (prevsnap.get("c_sub") or "") != (base.get("titular") or ""):
        ch.append("Titular modificado")
    if (prevsnap.get("c_desc") or "") != (base.get("descripcion") or ""):
        ch.append("Descripción modificada")
    return ch or ["Contenido actualizado"]

def compute_kpis(offers, state):
    prev = state.get("offers", {})
    same_version = state.get("hash_version") == HASH_VERSION
    nuevas = cambios = 0
    cur_ids = set()
    for o in offers:
        oid = str(o["id"]); cur_ids.add(oid)
        o["_hash"] = stable_hash(o)
        if oid not in prev:
            o["_estado"] = "nueva"; nuevas += 1
        elif same_version and prev[oid].get("hash") != o["_hash"]:
            o["_estado"] = "cambio"; cambios += 1
        else:
            o["_estado"] = "vigente"
    eliminadas = sum(1 for oid in prev if oid not in cur_ids)
    escaneos = state.get("escaneos", 0) + 1
    return {"activas": len(offers), "nuevas": nuevas, "eliminadas": eliminadas, "cambios": cambios, "escaneos": escaneos}

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    src = Path(args[0]) if args and not args[0].startswith("--") else Path("reportes_ghl/_ejemplo_bil.json")
    save_state = "--save-state" in args
    out_name = "ghl_dashboard_capital_ejemplo.html"
    if "--out" in args:
        out_name = args[args.index("--out") + 1]

    offers = json.loads(src.read_text(encoding="utf-8"))
    state_file = Path("reportes_ghl/estado_ofertas.json")
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    out_dir = Path("reportes_ghl")

    if save_state:
        # ESCANEO: recalcula diff, marca estado/fecha de alta y persiste el estado
        kpis = compute_kpis(offers, state)
        run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        prev_date = state.get("last_run", "—")
        prev = state.get("offers", {})
        cur_ids = {str(o["id"]) for o in offers}
        for o in offers:
            oid = str(o["id"])
            o["_fecha_alta"] = run_date if o["_estado"] == "nueva" else (prev.get(oid, {}).get("fecha_alta") or prev_date)
            if o["_estado"] == "cambio":
                o["_cambios"] = change_summary(o, prev.get(oid, {}))
                o["_fecha_cambio"] = run_date
        # Archivo acumulativo de eliminadas
        archive = list(state.get("removed", []))
        arch_ids = {r.get("id") for r in archive}
        for oid in prev:
            if oid not in cur_ids and oid not in arch_ids:
                archive.append({**prev[oid], "id": oid, "fecha_baja": run_date})
        archive = [r for r in archive if r.get("id") not in cur_ids]

        html_out = build_html(offers, kpis, run_date, prev_date, removed=archive)
        (out_dir / out_name).write_text(html_out, encoding="utf-8")
        (out_dir / "ghl_dashboard_latest.html").write_text(html_out, encoding="utf-8")
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        (out_dir / f"ghl_dashboard_{ts}.html").write_text(html_out, encoding="utf-8")
        new_state = {"hash_version": HASH_VERSION, "escaneos": kpis["escaneos"],
                     "last_run": run_date, "prev_run": prev_date, "last_kpis": kpis,
                     "offers": {str(o["id"]): {**offer_snapshot(o), "estado": o["_estado"], "fecha_alta": o["_fecha_alta"],
                                               "cambios": o.get("_cambios", []), "fecha_cambio": o.get("_fecha_cambio", "")} for o in offers},
                     "removed": archive}
        state_file.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        # RE-RENDER (cambios de diseño): reutiliza el estado guardado, no recalcula ni avanza escaneos
        snaps = state.get("offers", {})
        for o in offers:
            s = snaps.get(str(o["id"]), {})
            o["_estado"] = s.get("estado", "vigente")
            o["_fecha_alta"] = s.get("fecha_alta", "—")
            o["_cambios"] = s.get("cambios", [])
            o["_fecha_cambio"] = s.get("fecha_cambio", "—")
        kpis = state.get("last_kpis") or compute_kpis(offers, {})
        run_date = state.get("last_run", "—")
        prev_date = state.get("prev_run", "—")
        archive = state.get("removed", [])
        html_out = build_html(offers, kpis, run_date, prev_date, removed=archive)
        (out_dir / out_name).write_text(html_out, encoding="utf-8")

    print(f"Dashboard generado: reportes_ghl/{out_name}. KPIs: {kpis} | eliminadas: {len(archive)}")
