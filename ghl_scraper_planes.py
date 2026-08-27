# -*- coding: utf-8 -*-
"""Scraper de PLANES de las webs individuales de cada hotel GHL, con el MISMO pipeline y
diseno que el de ofertas (ghl_scraper_individual_v3.py + dashboard_v3.py), pero apuntando
a /planes (ES) y /plans (EN):

  - extractor .titular-title (reutilizado de ghl_scraper_individual_v3)
  - dato estrella = PRECIO (COP $ ...); tambien captura descuento % si aparece
  - categorias propias de planes (Romantico, Aniversario, Cumpleanos, ...)
  - link DIRECTO a cada plan (el href del boton/tarjeta del plan)
  - emparejado ES/EN por categoria (el orden ES/EN difiere entre webs)
  - seguimiento de estado semanal (nuevos / con cambios / eliminados) y KPIs
  - render con dashboard_planes.py (identico look al dashboard de ofertas)

hotel_code (para geografia/filtros): se reutilizan los codigos ya resueltos por el
pipeline de ofertas (_individual_bil.json) + overrides para hoteles sin ofertas activas.

Salidas (reportes_ghl/, no toca nada del pipeline de ofertas):
  - _planes_bil.json
  - estado_planes.json
  - planes_dashboard_latest.html (+ copia con timestamp)
"""
import asyncio, json, re, hashlib, sys, unicodedata
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

from ghl_scraper_v2 import HOTELS
from ghl_scraper_individual_v3 import JS_EXTRACT_BASTION, slugify, extract_vigencia
import dashboard_planes as dp
import dashboard_v3 as dv3

# Extractor de PLANES: como el .titular-title de ofertas, pero devuelve tambien el texto
# COMPLETO de la tarjeta (`full`), porque el PRECIO del plan vive en un heading aparte
# (ej. "COP $ 640,000"), no dentro de los <p> de la descripcion.
JS_EXTRACT_PLANES = """
(() => {
  const plans = [];
  const GENERIC = ['planes','plans','plan','ofertas','offers','promociones','promotions'];
  document.querySelectorAll('.titular-title').forEach(h => {
    const title = h.innerText.trim();
    if (!title || title.length < 3 || title.length > 200) return;
    if (GENERIC.includes(title.toLowerCase())) return;
    let card = h.closest('.heading-block');
    card = card ? card.parentElement : h.parentElement;
    if (!card) return;
    if (card.querySelectorAll('.titular-title').length > 1) return;
    let paraEls = Array.from(card.querySelectorAll('markdown p'));
    if (paraEls.length === 0) paraEls = Array.from(card.querySelectorAll('p'));
    const paras = paraEls.map(p => p.innerText.trim()).filter(t => t && t !== title);
    const descripcion = paras.join(' ').trim();
    const full = card.innerText.trim();
    const link = card.querySelector('a.btn') || card.querySelector('a[href*="availability"]') || card.querySelector('a');
    const href = link ? link.href : '';
    plans.push({titulo:title, descripcion:descripcion.substring(0,600), full:full.substring(0,800), href:href});
  });
  return JSON.stringify(plans);
})()
"""

OUT_DIR = Path("reportes_ghl")
ERROR_RATE_THRESHOLD = 0.15

# Codigos de hotel para hoteles sin ofertas activas (no aparecen en _individual_bil.json).
# Todos existen en dashboard_v3.GEO -> geografia y filtros correctos.
CODE_OVERRIDES = {
    "GHL Collection 93": "ghlstyle93",
    "GHL Relax Club el Puente": "ghlclubelpuente",
    "GHL Style Barrancabermeja": "ghlstylebarrancabermeja",
    "GHL Style Neiva": "ghlhotelneiva",
    "Sonesta Valledupar": "ghlsonvalledupar",
}

# Irotama: 6 torres comparten la pagina /planes, que lista 6 planes "IROTAMA FULL X"
# (uno por torre). Se asigna a cada torre solo su plan, via palabra clave en el slug del
# link (analogo al hotel_code_filter de ofertas).
IROTAMA_PLAN_SLUG = {
    "irodmr": "full-mar", "irodsl": "full-sol", "irohbb": "bungalow",
    "irolago": "full-lago", "irorvd": "reservado", "iroxxl": "xxi",
}

def build_code_map():
    m = {}
    p = OUT_DIR / "_individual_bil.json"
    if p.exists():
        for o in json.loads(p.read_text(encoding="utf-8")):
            m.setdefault(o["hotel"], o.get("hotel_code"))
    for k, v in CODE_OVERRIDES.items():
        m.setdefault(k, v)
    return m

# ---------------------------------------------------------------------------
def plan_urls(hotel):
    out = {}
    for lang, url in hotel["urls"].items():
        if lang not in ("es", "en"):
            continue
        pu = url.replace("/ofertas-en-hoteles-cartagena", "/planes")
        pu = pu.replace("/ofertas", "/planes").replace("/offers", "/plans")
        out[lang] = pu
    return out

# ---------- Categorias a medida (matching sin acentos, el titulo manda) ----------
def _norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()

PLAN_CATEGORIES = {
    "Noche de bodas": ["noche de boda", "wedding night", "luna de miel", "honeymoon", "boda"],
    "Aniversario": ["aniversario", "anniversary"],
    "Cumpleaños": ["cumplea", "birthday"],
    "Concierto/Evento": ["concierto", "concert", "evento", "event", "festival", "espectaculo"],
    "Fin de semana": ["fin de semana", "weekend", "escapada", "getaway"],
    "Familiar": ["familiar", "family", "ninos", "kids", "children"],
    "Gastronómico": ["gastronom", "cena", "dinner", "almuerzo", "lunch", "culinari"],
    "Bienestar/Spa": ["spa", "wellness", "bienestar", "masaje", "massage", "relax"],
    "Romántico": ["romantic", "romance", "pareja", "couple", "amor"],
}

def detect_category(title, desc):
    ntitle, ndesc = _norm(title), _norm(desc)
    for cat, kws in PLAN_CATEGORIES.items():
        if any(k in ntitle for k in kws):
            return cat
    for cat, kws in PLAN_CATEGORIES.items():
        if any(k in ndesc for k in kws):
            return cat
    return "Plan General"

# ---------- Precio / descuento ----------
PRICE_RE = re.compile(r'(?:COP|USD)\s*\$?\s*[\d][\d.,]*|\$\s*[\d][\d.,]*', re.IGNORECASE)

def extract_price(text):
    out = []
    for p in PRICE_RE.findall(text or ""):
        p = re.sub(r'\s+', ' ', p).strip()
        digits = re.sub(r'\D', '', p)
        is_usd = "usd" in p.lower()
        if not is_usd and len(digits) < 5:   # COP/$ de <5 digitos = ruido (ej. $4.200)
            continue
        if p not in out:
            out.append(p)
    return out[0] if out else None   # precio principal (el primero valido)

def extract_descuento(text):
    for d in re.findall(r'(\d+)\s*%', text or ""):
        if 0 < int(d) < 100:
            return f"{d}%"
    return None

def url_slug(href):
    m = re.search(r'/(?:planes|plans)/([^/?#]+)', href or "")
    return m.group(1).lower() if m else ""

GENERIC_TITLES = {"planes", "plans", "plan", "ofertas", "offers", "promociones", "promotions"}

async def extract_plans_from_page(page, url, extractor=None):
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3500)
    if extractor == "bastion":
        raw = json.loads(await page.evaluate(JS_EXTRACT_BASTION))
    else:
        raw = json.loads(await page.evaluate(JS_EXTRACT_PLANES))
    return [o for o in raw if o["titulo"].strip().lower() not in GENERIC_TITLES]

def build_lang_plan(hotel_display, page_url, lang, raw, hotel_code):
    href = raw.get("href", "") or ""
    titulo = raw["titulo"]
    descripcion = (raw.get("descripcion") or "")[:600]
    # el precio suele estar en un heading aparte de la tarjeta -> se busca en `full`
    full = (raw.get("full") or "") + " " + titulo + " " + descripcion
    return {
        "lang": lang, "url": href or page_url, "page_url": page_url,
        "slug": url_slug(href), "hotel": hotel_display, "hotel_code": hotel_code,
        "titulo": titulo, "nombre_corto": titulo, "titular": "",
        "descripcion": descripcion, "categoria": detect_category(titulo, descripcion),
        "descuento": extract_descuento(full), "precio_desde": extract_price(full),
        "vigencia": extract_vigencia(descripcion),
    }

def norm_price(p):
    """Normaliza precio para comparar ES/EN (formato difiere: 'COP $ 688,700' vs 'COP 688,700').
    Devuelve (moneda, digitos) o None."""
    if not p:
        return None
    cur = "usd" if "usd" in p.lower() else "cop"
    digits = re.sub(r'\D', '', p)
    return (cur, digits) if digits else None

def pair_es_en(es_list, en_list):
    """Empareja ES<->EN dentro del hotel. El orden, los slugs y hasta la categoria pueden
    diferir entre idiomas, pero el PRECIO casi siempre coincide -> es la senal mas fuerte.

    Se hace por PASADAS GLOBALES (no plan por plan): primero se resuelven TODOS los cruces
    precio+categoria, luego precio, luego categoria, luego slug, y al final posicional. Asi,
    cuando varios planes comparten el mismo precio, cada uno encuentra primero su mejor cruce
    (evita que uno se lleve por precio el EN que le corresponde a otro por categoria)."""
    matches = {}          # id(es) -> en
    remaining_es = list(es_list)
    en_pool = list(en_list)

    def run_pass(pred):
        still = []
        for es in remaining_es:
            m = next((e for e in en_pool if pred(es, e)), None)
            if m:
                matches[id(es)] = m
                en_pool.remove(m)
            else:
                still.append(es)
        remaining_es[:] = still

    pe = lambda o: norm_price(o.get("precio_desde"))
    run_pass(lambda es, e: pe(es) and pe(e) == pe(es) and e["categoria"] == es["categoria"])
    run_pass(lambda es, e: pe(es) and pe(e) == pe(es))
    run_pass(lambda es, e: es["categoria"] != "Plan General" and e["categoria"] == es["categoria"])
    run_pass(lambda es, e: es.get("slug") and e.get("slug") == es["slug"])

    rows = []
    for es in es_list:
        m = matches.get(id(es))
        if m is None and remaining_es and en_pool:   # posicional para los restantes
            if es in remaining_es:
                m = en_pool.pop(0)
                remaining_es.remove(es)
        rows.append({"es": es, "en": m})
    for en in en_pool:
        rows.append({"es": None, "en": en})
    return rows

def plan_hash(o):
    payload = [o.get("titulo"), o.get("descripcion"), o.get("precio_desde"), o.get("descuento"), o.get("vigencia")]
    return hashlib.md5(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()

def build_unified(hotel_display, rows, hotel_code):
    unified = []
    for r in rows:
        es, en = r["es"], r["en"]
        base = es or en
        co = base.get("slug") or ""
        oid_suffix = co or hashlib.md5((base.get("titulo") or "").encode()).hexdigest()[:6]
        unified.append({
            "hotel": hotel_display, "hotel_code": hotel_code,
            "categoria": base.get("categoria"),
            "id": f"plan_{hotel_code}_{oid_suffix}",
            "es": es, "en": en,
            "hash": plan_hash(base),
        })
    return unified

async def scrape_hotel(page, hotel_entry, code_map):
    name = hotel_entry["hotel"]
    extractor = hotel_entry.get("extractor")
    hotel_code = code_map.get(name) or slugify(name)
    if extractor == "bastion":
        print("  [SKIP] Bastion: plataforma sin ruta de planes mapeada")
        return [], True
    per_lang = {}
    lang_ok = {}
    for lang, url in plan_urls(hotel_entry).items():
        print(f"  [{lang.upper()}] {url}", end=" ... ", flush=True)
        try:
            raw = await extract_plans_from_page(page, url, extractor)
        except Exception as e:
            print(f"ERROR {str(e)[:120]}")
            per_lang[lang] = []; lang_ok[lang] = False
            continue
        built = [build_lang_plan(name, url, lang, o, hotel_code) for o in raw]
        # Irotama: pagina compartida -> cada torre se queda solo con su plan "FULL X"
        slug_kw = IROTAMA_PLAN_SLUG.get(hotel_entry.get("hotel_code_filter"))
        if slug_kw:
            built = [b for b in built if slug_kw in (b.get("slug") or "")]
        per_lang[lang] = built
        lang_ok[lang] = True
        print(f"OK {len(built)} plan(es)")
    es_list, en_list = per_lang.get("es", []), per_lang.get("en", [])
    verified = any(lang_ok.values())
    if not es_list and not en_list:
        return [], verified
    return build_unified(name, pair_es_en(es_list, en_list), hotel_code), verified

# ---------- sin planes ----------
def render_sin_planes(sin_planes):
    if not sin_planes:
        return ""
    rows = ""
    for h in sin_planes:
        url = (h["urls"].get("es") or next(iter(h["urls"].values()), "")).replace("/ofertas", "/planes").replace("/offers", "/plans")
        rows += (f'<tr><td><div class="m-offer">{dv3.esc(h["hotel"])}</div></td>'
                 f'<td><a class="ver-link" href="{dv3.esc(url)}" target="_blank">Ver web &rarr;</a></td></tr>')
    return (f'<div class="sec-title" style="margin-top:28px">Hoteles sin planes activos actualmente '
            f'<span class="tag">{len(sin_planes)}</span></div>'
            f'<div class="tbl-card"><table class="master"><thead><tr>'
            f'<th>Hotel</th><th>Web</th></tr></thead><tbody>{rows}</tbody></table></div>')

CONS_NORESULTS = '<div class="no-results" id="cons-noresults">Sin resultados para los filtros seleccionados.</div>'

async def run(test=False):
    OUT_DIR.mkdir(exist_ok=True)
    code_map = build_code_map()
    hotels = HOTELS
    if test:
        TEST = ("Sonesta Cali", "Sonesta Bogota", "GHL Style Neiva", "Arsenal")
        hotels = [h for h in HOTELS if h["hotel"] in TEST]
        print(f"\nModo test -- {', '.join(TEST)}\n")

    all_unified = []
    hoteles_error = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-CO", viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()
        for i, hotel in enumerate(hotels, 1):
            print(f"[{i:02d}/{len(hotels)}] {hotel['hotel']}")
            try:
                unified, verified = await scrape_hotel(page, hotel, code_map)
            except Exception as e:
                print(f"  ERROR general: {str(e)[:150]}")
                unified, verified = [], False
            if not unified:
                if verified:
                    print("  -> sin planes detectados (confirmado)")
                else:
                    print("  -> ERROR: no se pudo verificar (fallo tecnico/red)")
                    hoteles_error.append(hotel["hotel"])
            all_unified.extend(unified)
            if i < len(hotels):
                await asyncio.sleep(0.5)
        await browser.close()

    error_rate = len(hoteles_error) / len(hotels) if hotels else 0
    suffix = "_test" if test else ""

    if error_rate > ERROR_RATE_THRESHOLD:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        fail_path = OUT_DIR / f"_planes_bil_FAILED_{ts}{suffix}.json"
        fail_path.write_text(json.dumps(all_unified, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n⚠ ADVERTENCIA: {len(hoteles_error)}/{len(hotels)} hoteles fallaron ({error_rate:.0%}): "
              f"{', '.join(hoteles_error)}")
        print(f"No se actualiza estado ni dashboard (guardado para inspeccion en {fail_path}).")
        return 3

    json_path = OUT_DIR / f"_planes_bil{suffix}.json"
    json_path.write_text(json.dumps(all_unified, ensure_ascii=False, indent=2), encoding="utf-8")

    state_path = OUT_DIR / f"estado_planes{suffix}.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    kpis = dv3.compute_kpis(all_unified, state)
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    prev_date = state.get("last_run", "—")
    prev = state.get("offers", {})
    cur_ids = {str(o["id"]) for o in all_unified}
    for o in all_unified:
        oid = str(o["id"])
        o["_fecha_alta"] = run_date if o["_estado"] == "nueva" else (prev.get(oid, {}).get("fecha_alta") or prev_date)
        if o["_estado"] == "cambio":
            o["_cambios"] = dv3.change_summary(o, prev.get(oid, {}))
            o["_fecha_cambio"] = run_date
    archive = list(state.get("removed", []))
    arch_ids = {r.get("id") for r in archive}
    for oid in prev:
        if oid not in cur_ids and oid not in arch_ids:
            archive.append({**prev[oid], "id": oid, "fecha_baja": run_date})
    archive = [r for r in archive if r.get("id") not in cur_ids]

    con_planes = set(o["hotel"] for o in all_unified)
    error_set = set(hoteles_error)
    sin_planes = [h for h in hotels if h["hotel"] not in con_planes and h["hotel"] not in error_set]

    prev_total = dp.TOTAL_PROPIEDADES
    dp.TOTAL_PROPIEDADES = len(hotels)
    try:
        html_out = dp.build_html(all_unified, kpis, run_date, prev_date, removed=archive)
    finally:
        dp.TOTAL_PROPIEDADES = prev_total
    html_out = html_out.replace(CONS_NORESULTS, CONS_NORESULTS + render_sin_planes(sin_planes))

    out_latest = OUT_DIR / f"planes_dashboard_latest{suffix}.html"
    out_latest.write_text(html_out, encoding="utf-8")
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    (OUT_DIR / f"planes_dashboard_{ts}{suffix}.html").write_text(html_out, encoding="utf-8")

    new_state = {
        "hash_version": dv3.HASH_VERSION, "escaneos": kpis["escaneos"],
        "last_run": run_date, "prev_run": prev_date, "last_kpis": kpis,
        "offers": {str(o["id"]): {**dv3.offer_snapshot(o), "estado": o["_estado"], "fecha_alta": o["_fecha_alta"],
                                   "cambios": o.get("_cambios", []), "fecha_cambio": o.get("_fecha_cambio", "")}
                   for o in all_unified},
        "removed": archive,
    }
    state_path.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== LISTO: {len(all_unified)} planes de {len(con_planes)}/{len(hotels)} hoteles con planes activos ===")
    if sin_planes:
        print(f"Sin planes activos ({len(sin_planes)}): " + ", ".join(h["hotel"] for h in sin_planes))
    if hoteles_error:
        print(f"No verificados por error tecnico ({len(hoteles_error)}): " + ", ".join(hoteles_error))
    print(f"Dashboard: {out_latest}")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run(test="--test" in sys.argv)))
