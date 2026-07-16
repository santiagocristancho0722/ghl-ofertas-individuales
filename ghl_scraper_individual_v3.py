# -*- coding: utf-8 -*-
"""Scraper de ofertas de las webs INDIVIDUALES de cada hotel GHL (no el índice corporativo),
renderizado con el mismo diseño v3 (dashboard_v3.py) que usa el pipeline del índice corporativo.

Reutiliza sin modificar:
  - ghl_scraper_v2.HOTELS         (lista de 43 hoteles y sus URLs /ofertas por idioma)
  - scraper_full.classify/extract_param (categorización y detección de parámetro numérico)
  - dashboard_v3.build_html/compute_kpis/offer_snapshot/change_summary/geo_of/... (render + KPIs)

Archivos propios (nunca toca los del pipeline corporativo _full_bil.json / estado_ofertas.json /
ghl_dashboard_latest.html):
  - reportes_ghl/_individual_bil.json
  - reportes_ghl/estado_ofertas_individual.json
  - reportes_ghl/ghl_dashboard_individual_latest.html (+ copia con timestamp)
"""
import asyncio, json, re, hashlib, sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

from ghl_scraper_v2 import HOTELS, JS_EXTRACT as JS_EXTRACT_FALLBACK
from scraper_full import classify, extract_param
import dashboard_v3 as dv3

OUT_DIR = Path("reportes_ghl")

# ---------- Extracción DOM ----------

JS_EXTRACT_PRIMARY = """
(() => {
  const offers = [];
  document.querySelectorAll('.titular-title').forEach(h => {
    const title = h.innerText.trim();
    if (!title || title.length < 3 || title.length > 200) return;
    const GENERIC = ['ofertas','offers','promociones','promotions'];
    if (GENERIC.includes(title.toLowerCase())) return;
    let card = h.closest('.heading-block');
    card = card ? card.parentElement : h.parentElement;
    if (!card) return;
    if (card.querySelectorAll('.titular-title').length > 1) return;
    let paraEls = Array.from(card.querySelectorAll('markdown p'));
    if (paraEls.length === 0) paraEls = Array.from(card.querySelectorAll('p'));
    const paras = paraEls.map(p => p.innerText.trim()).filter(t => t && t !== title);
    const descripcion = paras.join(' ').trim();
    const link = card.querySelector('a.btn') || card.querySelector('a[href*="availability"]') || card.querySelector('a');
    const href = link ? link.href : '';
    offers.push({titulo: title, descripcion, href});
  });
  return JSON.stringify(offers);
})()
"""

GENERIC_TITLES = {"ofertas", "offers", "promociones", "promotions"}

async def extract_offers_from_page(page, url):
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3500)
    raw = await page.evaluate(JS_EXTRACT_PRIMARY)
    offers = json.loads(raw)
    if not offers:
        raw2 = await page.evaluate(JS_EXTRACT_FALLBACK)
        parsed = json.loads(raw2)
        offers = [{"titulo": o["titulo"], "descripcion": o.get("descripcion", ""), "href": ""} for o in parsed]
    return [o for o in offers if o["titulo"].strip().lower() not in GENERIC_TITLES]

def parse_booking_link(href):
    if not href:
        return None, None
    m_code = re.search(r'/availability/([^/]+)/', href)
    m_co = re.search(r'[?&]co=([^&]+)', href)
    return (m_code.group(1) if m_code else None), (m_co.group(1) if m_co else None)

def slugify(name):
    return re.sub(r'[^a-z0-9]+', '', (name or "").lower()) or "hotel"

# ---------- Categorización, descuento, vigencia ----------

CO_PREFIX_CATEGORY = [
    ("ebk", "early_booking", "Compra Anticipada"),
    ("lasm", "last_minute", "Ultimo Minuto"),
    ("lons", "min_stay", "Minima Estadia"),
    ("lon", "min_stay", "Minima Estadia"),
    ("minst", "min_stay", "Minima Estadia"),
    ("barrate", "bar_rate", "Descuento Directo"),
    ("weeknd", "weekend", "Fin de Semana"),
]

def classify_individual(co, title, desc):
    co_l = (co or "").lower()
    for prefix, canonical, cat in CO_PREFIX_CATEGORY:
        if co_l.startswith(prefix):
            return canonical, cat
    return classify(co or "", title, desc)

def extract_descuento(text):
    m = re.search(r'(\d{1,3})\s*%', text or "")
    return f"{m.group(1)}%" if m else None

def extract_vigencia(text):
    t = text or ""
    m = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})\D+?(\d{1,2}/\d{1,2}/\d{2,4})', t)
    if m:
        return f"{m.group(1)} - {m.group(2)}"
    m2 = re.search(r'hasta\s+el\s+(\d{1,2}\s+de\s+\w+(?:\s+de)?\s+\d{4})', t, re.IGNORECASE)
    if m2:
        return f"Hasta el {m2.group(1)}"
    m3 = re.search(r'valid\s+until\s+([A-Za-z]+\s+\d{1,2},?\s*\d{4})', t, re.IGNORECASE)
    if m3:
        return f"Valid until {m3.group(1)}"
    return None

# ---------- Construcción del esquema unificado (compatible con dashboard_v3) ----------

def build_lang_offer(hotel_display, url_page, lang, raw, fallback_hotel_code):
    href = raw.get("href", "")
    hotel_code, co = parse_booking_link(href)
    hotel_code = hotel_code or fallback_hotel_code
    titulo = raw["titulo"]
    descripcion = (raw.get("descripcion") or "")[:600]
    descuento = extract_descuento(descripcion + " " + titulo)
    vigencia = extract_vigencia(descripcion)
    canonical, cat_disp = classify_individual(co, titulo, descripcion)
    param = extract_param(f"{co or ''} {descripcion} {titulo}")
    match_key = co or f"{canonical}|{param}"
    return {
        "lang": lang, "url": url_page, "slug": co or "", "es_id": None,
        "hotel": hotel_display, "hotel_code": hotel_code,
        "titulo": titulo, "nombre_corto": titulo, "titular": "",
        "descripcion": descripcion, "categoria": cat_disp,
        "canonical": canonical, "param": param, "descuento": descuento,
        "precio_desde": None, "vigencia": vigencia, "match_key": match_key,
    }

def pair_es_en(es_list, en_list):
    en_pool = list(en_list)
    rows = []
    for es in es_list:
        es_co = es.get("slug") or ""
        match = next((e for e in en_pool if es_co and (e.get("slug") or "") == es_co), None)
        rows.append({"es": es, "en": match})
        if match:
            en_pool.remove(match)
    unmatched = [r for r in rows if r["en"] is None]
    for r in unmatched:
        if not en_pool:
            break
        cand = next((e for e in en_pool if e.get("param") is not None and e["param"] == r["es"].get("param")), None)
        if cand:
            r["en"] = cand
            en_pool.remove(cand)
    unmatched = [r for r in rows if r["en"] is None]
    if unmatched and en_pool and len(unmatched) == len(en_pool):
        for r, e in zip(unmatched, en_pool):
            r["en"] = e
        en_pool = []
    for en in en_pool:
        rows.append({"es": None, "en": en})
    return rows

def offer_hash_individual(o):
    payload = [o.get("titulo"), o.get("descripcion"), o.get("descuento"), o.get("vigencia")]
    return hashlib.md5(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()

def build_unified(hotel_display, rows, hotel_code_hint):
    unified = []
    for r in rows:
        es, en = r["es"], r["en"]
        base = es or en
        hotel_code = base.get("hotel_code") or hotel_code_hint
        co = base.get("slug") or ""
        oid_suffix = co or hashlib.md5((base.get("titulo") or "").encode()).hexdigest()[:6]
        unified.append({
            "hotel": hotel_display, "hotel_code": hotel_code,
            "match_key": base.get("match_key"), "categoria": base.get("categoria"),
            "id": f"{hotel_code}_{oid_suffix}",
            "es": es, "en": en,
            "hash": offer_hash_individual(base),
        })
    return unified

# ---------- Scraping por hotel ----------

async def scrape_hotel(page, hotel_entry):
    name = hotel_entry["hotel"]
    fallback_code = slugify(name)
    per_lang = {}
    for lang, url in hotel_entry["urls"].items():
        if lang not in ("es", "en"):
            continue
        print(f"  [{lang.upper()}] {url}", end=" ... ", flush=True)
        try:
            offers_raw = await extract_offers_from_page(page, url)
        except Exception as e:
            print(f"ERROR {str(e)[:120]}")
            per_lang[lang] = []
            continue
        built = [build_lang_offer(name, url, lang, o, fallback_code) for o in offers_raw]
        per_lang[lang] = built
        print(f"OK {len(built)} oferta(s)")
    es_list = per_lang.get("es", [])
    en_list = per_lang.get("en", [])
    if not es_list and not en_list:
        return []
    rows = pair_es_en(es_list, en_list)
    return build_unified(name, rows, fallback_code)

# ---------- Orquestación / dashboard ----------

FOOTER_OLD = "Dashboard generado automáticamente desde la web oficial GHL Hoteles · ghlhoteles.com/es/ofertas y /en/offers"
FOOTER_NEW = "Dashboard generado automáticamente desde las webs individuales de cada hotel GHL"

async def run(test=False):
    OUT_DIR.mkdir(exist_ok=True)
    hotels = HOTELS
    if test:
        hotels = [h for h in HOTELS if h["hotel"] == "Arsenal"]
        print("\nModo test -- solo Arsenal\n")

    all_unified = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-CO", viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()
        for i, hotel in enumerate(hotels, 1):
            print(f"[{i:02d}/{len(hotels)}] {hotel['hotel']}")
            try:
                unified = await scrape_hotel(page, hotel)
            except Exception as e:
                print(f"  ERROR general: {str(e)[:150]}")
                unified = []
            if not unified:
                print("  -> sin ofertas detectadas")
            all_unified.extend(unified)
            if i < len(hotels):
                await asyncio.sleep(0.5)
        await browser.close()

    suffix = "_test" if test else ""
    json_path = OUT_DIR / f"_individual_bil{suffix}.json"
    json_path.write_text(json.dumps(all_unified, ensure_ascii=False, indent=2), encoding="utf-8")

    state_path = OUT_DIR / f"estado_ofertas_individual{suffix}.json"
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

    n_hoteles = len(set(o["hotel"] for o in all_unified)) or dv3.TOTAL_PROPIEDADES
    prev_total = dv3.TOTAL_PROPIEDADES
    dv3.TOTAL_PROPIEDADES = n_hoteles
    try:
        html_out = dv3.build_html(all_unified, kpis, run_date, prev_date, removed=archive)
    finally:
        dv3.TOTAL_PROPIEDADES = prev_total
    html_out = html_out.replace(FOOTER_OLD, FOOTER_NEW)

    out_latest = OUT_DIR / f"ghl_dashboard_individual_latest{suffix}.html"
    out_latest.write_text(html_out, encoding="utf-8")
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    (OUT_DIR / f"ghl_dashboard_individual_{ts}{suffix}.html").write_text(html_out, encoding="utf-8")

    new_state = {
        "hash_version": dv3.HASH_VERSION, "escaneos": kpis["escaneos"],
        "last_run": run_date, "prev_run": prev_date, "last_kpis": kpis,
        "offers": {str(o["id"]): {**dv3.offer_snapshot(o), "estado": o["_estado"], "fecha_alta": o["_fecha_alta"],
                                   "cambios": o.get("_cambios", []), "fecha_cambio": o.get("_fecha_cambio", "")}
                   for o in all_unified},
        "removed": archive,
    }
    state_path.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== LISTO: {len(all_unified)} ofertas de {n_hoteles} hoteles ===")
    print(f"Dashboard: {out_latest}")

if __name__ == "__main__":
    asyncio.run(run(test="--test" in sys.argv))
