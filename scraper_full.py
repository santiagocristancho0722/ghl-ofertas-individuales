# -*- coding: utf-8 -*-
"""Scraper bilingüe COMPLETO GHL — todos los hoteles del índice, ES + EN, emparejado y con nombre de hotel detectado."""
import asyncio, json, re, hashlib
from collections import Counter
from pathlib import Path
from playwright.async_api import async_playwright

ES_INDEX = "https://www.ghlhoteles.com/es/ofertas/"
EN_INDEX = "https://www.ghlhoteles.com/en/offers/"

def classify(slug, title, desc):
    t = (slug + " " + title + " " + desc).lower()
    if "compra-anticipada" in slug or "reserva-anticipada" in slug or "early-booking" in slug or slug.startswith("ebk") \
       or "early booking" in t or "advance purchase" in t or "anticipa" in t or "in advance" in t:
        return ("early_booking", "Compra Anticipada")
    if "minima-estadia" in slug or "minimum" in slug or "lonstn" in slug or "minst" in slug \
       or "minima estadia" in t or "mínima estadía" in t or "minimum stay" in t or "minimum" in t or "long stay" in t:
        return ("min_stay", "Minima Estadia")
    if "ultimo-minuto" in slug or "lasm" in slug or "last-minute" in slug \
       or "last minute" in t or "ultimo minuto" in t or "último minuto" in t:
        return ("last_minute", "Ultimo Minuto")
    if "fin-de-semana" in slug or "weeknd" in slug or "weekend" in t or "fin de semana" in t:
        return ("weekend", "Fin de Semana")
    if "con-descuento" in slug or "barrate" in slug or slug == "discount" or "bar rate" in t:
        return ("bar_rate", "Descuento Directo")
    if "romance" in t or "pareja" in t or "couple" in t or "luna de miel" in t or "honeymoon" in t:
        return ("romance", "Romance")
    if "momentos" in slug or "experiencia" in t or "experience" in t or "concert" in t \
       or "magia" in t or "magic" in t or "noche gratis" in t or "free night" in t or "season" in t or "escape" in t:
        return ("special", "Promo Especial")
    return ("general", "Oferta General")

def extract_param(text):
    m = re.search(r'(\d+)\s*(d[ií]as?|days?|noches?|nights?)', text or "", re.I)
    return int(m.group(1)) if m else None

async def scroll_all(page):
    prev = 0; stable = 0
    for _ in range(45):
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await page.wait_for_timeout(900)
        h = await page.evaluate("document.body.scrollHeight")
        if h == prev:
            stable += 1
            if stable >= 3: break
        else:
            stable = 0
        prev = h
    await page.evaluate("window.scrollTo(0,0)")
    await page.wait_for_timeout(400)

async def collect_all_urls(page, lang):
    seg = "promociones" if lang == "es" else "promotions"
    return await page.evaluate(f"""() => {{
        const g={{}};
        document.querySelectorAll('a').forEach(a=>{{
            const m=(a.href||'').match(new RegExp('/{seg}/([^/]+)/(.+)'));
            if(m && m[2] && m[2] !== ''){{ g[m[1]]=g[m[1]]||[]; if(!g[m[1]].includes(a.href)) g[m[1]].push(a.href); }}
        }});
        return g;
    }}""")

async def scrape_offer(page, url, code, lang):
    """Devuelve dict (oferta), '404' (eliminada) o 'skip' (desafío anti-bot/no resuelta)."""
    valid_marker = "Oferta v" if lang == "es" else "Offer valid"
    ready = False
    for attempt in range(4):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            await page.wait_for_timeout(3000); continue
        await page.wait_for_timeout(2000)
        flags = await page.evaluate("""() => {
            const t = document.body.innerText;
            return {
                challenge: /confirm you are human|are you human|verifying you are human|just a moment|enable javascript and cookies|captcha|confirma que eres/i.test(t),
                is404: t.includes('not available') || t.includes('no está disponible'),
                hasvalid: t.includes('%s')
            };
        }""" % valid_marker)
        if flags["is404"]:
            return "404"
        if flags["challenge"]:
            await page.wait_for_timeout(5000 + attempt * 3000)  # backoff ante anti-bot
            continue
        if flags["hasvalid"]:
            ready = True; break
        try:
            await page.wait_for_function(f"() => document.body.innerText.includes('{valid_marker}')", timeout=10000)
            ready = True; break
        except Exception:
            await page.wait_for_timeout(2500)
    if not ready:
        return "skip"
    data = await page.evaluate("""() => {
        const txt = document.body.innerText;
        const h1 = (document.querySelector('h1')||{}).innerText || '';
        let endIdx = txt.length;
        ['Otras ofertas','Other offers','Outras ofertas'].forEach(m=>{const i=txt.indexOf(m); if(i>0 && i<endIdx) endIdx=i;});
        if (endIdx === txt.length){
            ['BUENAS RAZONES','GOOD REASONS','BOAS RAZÕES','BUONE RAGIONI'].forEach(m=>{const i=txt.indexOf(m); if(i>0 && i<endIdx) endIdx=i;});
        }
        return {h1, region: txt.substring(0, endIdx)};
    }""")
    h1 = re.sub(r'\s+', ' ', data["h1"]).strip()
    region = data["region"]
    lines = [l.strip() for l in region.split("\n") if l.strip()]
    m = re.search(r'/(?:promociones|promotions)/[^/]+/(?:[^/]+/)?(.+?)(?:-(\d+))?/?$', url)
    slug = (m.group(1) if m else url)
    es_id = m.group(2) if (m and m.group(2)) else None
    markers_block = ("OFERTA", "PROMOCION", "PROMOCIONES") if lang == "es" else ("OFFER", "PROMOTION", "PROMOTIONS")
    start = 0
    for i, l in enumerate(lines):
        if l.upper() in markers_block: start = i + 1
    block = lines[start:]
    nombre_corto = block[0] if block else ""
    titular = ""; desc_start = 1
    for i in range(1, min(len(block), 4)):
        if re.search(r'\d+\s*%', block[i]) or (block[i].isupper() and len(block[i]) > 12):
            titular = block[i]; desc_start = i + 1; break
    # Detectar línea de nombre del hotel (entre el subtítulo y la descripción)
    hotel_detected = ""
    if desc_start < len(block):
        cand = block[desc_start].strip()
        low = cand.lower()
        if (len(cand) <= 48 and not cand.endswith('.') and '%' not in cand
                and not low.startswith(("oferta v", "offer valid", "desde", "from", "incluye", "includes"))):
            hotel_detected = cand
            desc_start += 1
    skip = {"RESERVA AHORA","MAS INFORMACION","RESERVA","AHORA","IMP. NO INCL.",
            "BOOK NOW","MORE INFORMATION","BOOK","TAX NOT INCL.","FROM"}
    desc_lines = []
    for l in block[desc_start:]:
        ll = l.lower()
        if ll.startswith("hotel "): continue
        if ll.startswith("oferta v") or ll.startswith("offer valid"): break
        if l.upper().startswith("DESDE") or l.upper().startswith("FROM:"): break
        if l.upper() in skip: continue
        desc_lines.append(l)
    descripcion = " ".join(desc_lines).strip()
    vig = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})\D+?(\d{1,2}/\d{1,2}/\d{2,4})', region)
    vigencia = f"{vig.group(1)} - {vig.group(2)}" if vig else None
    dm = re.search(r'(\d{1,3})\s*%', region)
    descuento = f"{dm.group(1)}%" if dm else None
    pm = re.search(r'(?:DESDE|FROM):\s*([\d.,]+)\s*([A-Z]{3})', region)
    precio = f"{pm.group(1)} {pm.group(2)}" if pm else None
    # Defensa final: si pese a todo capturamos una página de desafío, no la guardamos
    if re.search(r'confirm you are human|are you human|captcha|just a moment', (h1 + " " + nombre_corto).lower()):
        return "skip"
    canonical, cat_disp = classify(slug, h1, descripcion)
    param = extract_param(slug + " " + descripcion + " " + titular)
    return {
        "lang": lang, "url": url, "slug": slug, "es_id": es_id, "hotel_code": code,
        "hotel_detected": hotel_detected, "titulo": h1, "nombre_corto": nombre_corto, "titular": titular,
        "descripcion": descripcion[:600], "categoria": cat_disp, "canonical": canonical,
        "param": param, "descuento": descuento, "precio_desde": precio, "vigencia": vigencia,
        "match_key": f"{canonical}|{param}",
    }

def offer_hash(o):
    return hashlib.md5(json.dumps([o.get("titulo"), o.get("titular"), o.get("descripcion"),
                                   o.get("descuento"), o.get("vigencia"), o.get("precio_desde")],
                                  ensure_ascii=False).encode()).hexdigest()

def hotel_name_for(code, es_offers, en_offers):
    names = [o["hotel_detected"] for o in es_offers if o.get("hotel_detected")] or \
            [o["hotel_detected"] for o in en_offers if o.get("hotel_detected")]
    if names:
        return Counter(names).most_common(1)[0][0]
    return code  # fallback

REG_PATH = Path("reportes_ghl/known_offers.json")

def code_of(u):
    m = re.search(r'/(?:promociones|promotions)/([^/]+)/', u)
    return m.group(1) if m else "?"

def load_registry():
    """Registro persistente de URLs de oferta conocidas. Bootstrap desde el dashboard publicado."""
    if REG_PATH.exists():
        reg = json.loads(REG_PATH.read_text(encoding="utf-8"))
    else:
        reg = {"es": [], "en": []}
        pub = Path("ghl-ofertas-pages/index.html")
        if pub.exists():
            html = pub.read_text(encoding="utf-8")
            allu = set(re.findall(r'https://www\.ghlhoteles\.com/(?:es|en)/(?:promociones|promotions)/[^"\s]+', html))
            reg["es"] = sorted(u for u in allu if "/promociones/" in u)
            reg["en"] = sorted(u for u in allu if "/promotions/" in u)
            print(f"Registro sembrado desde dashboard publicado: ES={len(reg['es'])} EN={len(reg['en'])}", flush=True)
    reg.setdefault("es", []); reg.setdefault("en", [])
    return reg

async def main():
    Path("reportes_ghl").mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", viewport={"width":1400,"height":1000})
        page = await ctx.new_page()
        print("Cargando índice ES...", flush=True)
        await page.goto(ES_INDEX, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(5000); await scroll_all(page)
        es_map = await collect_all_urls(page, "es")
        print("Cargando índice EN...", flush=True)
        await page.goto(EN_INDEX, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(5000); await scroll_all(page)
        en_map = await collect_all_urls(page, "en")

        # Unir URLs descubiertas en el índice con el registro persistente de ofertas conocidas.
        # Así, aunque el índice cargue incompleto, re-scrapeamos todas las conocidas directo;
        # solo se descartan (eliminadas) las que devuelven 404 real.
        reg = load_registry()
        disc_es = [u for urls in es_map.values() for u in urls]
        disc_en = [u for urls in en_map.values() for u in urls]
        all_es = sorted(set(reg["es"]) | set(disc_es))
        all_en = sorted(set(reg["en"]) | set(disc_en))
        print(f"\nÍndice: ES={len(disc_es)} EN={len(disc_en)} | Registro: ES={len(reg['es'])} EN={len(reg['en'])} "
              f"| A scrapear (unión): ES={len(all_es)} EN={len(all_en)}\n", flush=True)

        es_by_code, en_by_code = {}, {}
        alive_es, alive_en, dead = [], [], 0
        from collections import OrderedDict
        es_codes = OrderedDict()
        for u in all_es: es_codes.setdefault(code_of(u), []).append(u)
        en_codes = {}
        for u in all_en: en_codes.setdefault(code_of(u), []).append(u)
        codes = list(es_codes.keys()) + [c for c in en_codes if c not in es_codes]

        for ci, code in enumerate(codes, 1):
            es_urls = es_codes.get(code, [])
            en_urls = en_codes.get(code, [])
            print(f"[{ci:02d}/{len(codes)}] {code}  (ES:{len(es_urls)} EN:{len(en_urls)})", flush=True)
            es_by_code[code], en_by_code[code] = [], []
            skipped = 0
            for u in es_urls:
                try:
                    o = await scrape_offer(page, u, code, "es")
                    if isinstance(o, dict):
                        es_by_code[code].append(o); alive_es.append(u)
                    elif o == "404":
                        dead += 1                 # eliminada real -> sale del registro
                    else:                          # 'skip': desafío anti-bot -> conservar y reintentar
                        alive_es.append(u); skipped += 1
                except Exception as e:
                    alive_es.append(u)             # ante error, conservar la URL
                    print(f"     ES ERROR {str(e)[:60]}", flush=True)
                await asyncio.sleep(0.6)           # cortesía: reduce el riesgo de anti-bot
            for u in en_urls:
                try:
                    o = await scrape_offer(page, u, code, "en")
                    if isinstance(o, dict):
                        en_by_code[code].append(o); alive_en.append(u)
                    elif o == "skip":
                        alive_en.append(u)
                except Exception:
                    pass
                await asyncio.sleep(0.4)
            sk = f" ({skipped} skip)" if skipped else ""
            print(f"     -> ES:{len(es_by_code[code])} EN:{len(en_by_code[code])} ok{sk}", flush=True)
        await browser.close()

    # Guardar registro = URLs que siguen vivas (las 404 se descartan = eliminadas reales)
    REG_PATH.write_text(json.dumps({"es": sorted(set(alive_es)), "en": sorted(set(alive_en))},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRegistro actualizado: ES={len(set(alive_es))} EN={len(set(alive_en))} vivas | {dead} ES descartadas (404)", flush=True)

    # Emparejar por código
    unified = []
    for code in codes:
        es_list = list(es_by_code.get(code, []))
        en_list = list(en_by_code.get(code, []))
        if not es_list and not en_list:
            continue
        hotel = hotel_name_for(code, es_list, en_list)
        rows = []
        for es in es_list:
            en_match = next((e for e in en_list if e["match_key"] == es["match_key"]), None)
            if en_match: en_list.remove(en_match)
            rows.append({"es": es, "en": en_match})
        for r in [r for r in rows if r["en"] is None]:
            if not en_list: break
            cand = next((e for e in en_list if e["param"] == r["es"]["param"]), None)
            if cand and cand["param"] == r["es"]["param"]:
                r["en"] = cand; en_list.remove(cand)
        for r in rows:
            es = r["es"]
            unified.append({
                "hotel": hotel, "hotel_code": code, "match_key": es["match_key"], "categoria": es["categoria"],
                "id": (code + "_" + (es.get("es_id") or hashlib.md5(es["url"].encode()).hexdigest()[:6])),
                "es": es, "en": r["en"], "hash": offer_hash(es),
            })
        for en in en_list:
            unified.append({
                "hotel": hotel, "hotel_code": code, "match_key": en["match_key"], "categoria": en["categoria"],
                "id": (code + "_en_" + hashlib.md5(en["url"].encode()).hexdigest()[:6]),
                "es": None, "en": en, "hash": offer_hash(en),
            })

    Path("reportes_ghl/_full_bil.json").write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")
    hoteles = len(set(u["hotel"] for u in unified))
    paired = sum(1 for u in unified if u["es"] and u["en"])
    print(f"\n=== LISTO: {len(unified)} ofertas de {hoteles} hoteles ({paired} con ES+EN) ===", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
