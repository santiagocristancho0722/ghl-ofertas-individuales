import asyncio, json, re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

HOTELS = [
    {"hotel":"Arsenal","urls":{"es":"https://www.arsenalhotel.com/ofertas","en":"https://en.arsenalhotel.com/offers"}},
    {"hotel":"Biohotel","urls":{"es":"https://www.biohotelcolombia.com/ofertas","en":"https://en.biohotelcolombia.com/offers"}},
    {"hotel":"Bioxury","urls":{"es":"https://www.bioxury.com/ofertas","en":"https://en.bioxury.com/offers"}},
    {"hotel":"Geotel Antofagasta","urls":{"es":"https://www.geotelantofagasta.com/ofertas","en":"https://en.geotelantofagasta.com/offers"}},
    {"hotel":"Geotel Calama","urls":{"es":"https://www.geotelcalama.com/ofertas","en":"https://en.geotelcalama.com/offers"}},
    {"hotel":"GHL Collection 93","urls":{"es":"https://www.hotelghl93.com/ofertas","en":"https://en.hotelghl93.com/offers"}},
    {"hotel":"Armeria Real","urls":{"es":"https://www.armeriarealhotel.com/ofertas","en":"https://en.armeriarealhotel.com/offers"}},
    {"hotel":"GHL Collection Hamilton","urls":{"es":"https://www.ghlcollectionhamilton.com/ofertas"}},
    {"hotel":"GHL Grand Villavicencio","urls":{"es":"https://www.ghlvillavicencio.com/ofertas"}},
    {"hotel":"GHL Hotel Capital","urls":{"es":"https://www.hotelcapital.com.co/ofertas","en":"https://en.hotelcapital.com.co/offers"}},
    {"hotel":"GHL Lago Titicaca","urls":{"es":"https://www.ghllagotiticaca.com/ofertas","en":"https://en.ghllagotiticaca.com/offers"}},
    {"hotel":"GHL Monteria","urls":{"es":"https://www.ghlhotelmonteria.com/ofertas"}},
    {"hotel":"GHL Porton Medellin","urls":{"es":"https://www.hotelportonmedellin.com/ofertas","en":"https://en.hotelportonmedellin.com/offers"}},
    {"hotel":"GHL Relax Club el Puente","urls":{"es":"https://www.ghlclubelpuente.com/ofertas"}},
    {"hotel":"GHL Relax Corales de Indias","urls":{"es":"https://www.coralesdeindias.com/ofertas","en":"https://en.coralesdeindias.com/offers"}},
    {"hotel":"GHL Relax Costa Azul","urls":{"es":"https://www.ghlhotelcostaazul.com/ofertas","en":"https://en.ghlhotelcostaazul.com/offers"}},
    {"hotel":"GHL Relax Sunrise","urls":{"es":"https://www.ghlhotelsunrise.com/ofertas","en":"https://en.ghlhotelsunrise.com/offers","pt":"https://pt.ghlhotelsunrise.com/ofertas"}},
    {"hotel":"GHL Style Barrancabermeja","urls":{"es":"https://www.ghlstylebarrancabermeja.com/ofertas"}},
    {"hotel":"GHL Style Bogota Occidente","urls":{"es":"https://www.ghlbogotaoccidente.com/ofertas","en":"https://en.ghlbogotaoccidente.com/offers"}},
    {"hotel":"GHL Style Neiva","urls":{"es":"https://www.ghlhotelneiva.com/ofertas","en":"https://en.ghlhotelneiva.com/offers"}},
    {"hotel":"GHL Style Yopal","urls":{"es":"https://www.ghlhotelyopal.com/ofertas","en":"https://en.ghlhotelyopal.com/offers"}},
    {"hotel":"Hotel Tequendama Bogota","urls":{"es":"https://www.tequendamahotel.com/ofertas","en":"https://en.tequendamahotel.com/offers"}},
    {"hotel":"GHL Hotel Abadia Plaza","urls":{"es":"https://www.hotelabadiaplaza.com/ofertas"}},
    {"hotel":"GHL Grand Barranquilla","urls":{"es":"https://www.ghlgrandbarranquilla.com/ofertas","en":"https://en.ghlgrandbarranquilla.com/offers"}},
    {"hotel":"LATAM XELA","urls":{"es":"https://www.latamhotelxela.com/ofertas","en":"https://en.latamhotelxela.com/offers"}},
    {"hotel":"Makani Luxury Wanderlust","urls":{"es":"https://www.makaniluxury.com/ofertas","en":"https://en.makaniluxury.com/offers"}},
    {"hotel":"Park Lake Luxury","urls":{"es":"https://www.parklakeluxury.com/ofertas","en":"https://en.parklakeluxury.com/offers","pt":"https://pt.parklakeluxury.com/ofertas"}},
    {"hotel":"San Lazaro Art","urls":{"es":"https://www.sanlazaroarthotel.com/ofertas","en":"https://en.sanlazaroarthotel.com/offers"}},
    {"hotel":"Sonesta Bucaramanga","urls":{"es":"https://www.sonestabucaramanga.com/ofertas","en":"https://www.sonestabucaramanga.com/offers"}},
    {"hotel":"Sonesta Cali","urls":{"es":"https://www.sonestacali.com/ofertas","en":"https://en.sonestacali.com/offers"}},
    {"hotel":"Sonesta Cartagena","urls":{"es":"https://www.sonestacartagena.com/ofertas","en":"https://en.sonestacartagena.com/offers","pt":"https://pt.sonestacartagena.com/ofertas"}},
    {"hotel":"Sonesta Cusco","urls":{"es":"https://www.sonestacusco.com/ofertas","en":"https://en.sonestacusco.com/offers"}},
    {"hotel":"Sonesta El Olivar","urls":{"es":"https://www.sonestaelolivar.com/ofertas","en":"https://en.sonestaelolivar.com/offers"}},
    {"hotel":"Sonesta Arequipa","urls":{"es":"https://www.sonestaarequipa.com/ofertas","en":"https://en.sonestaarequipa.com/offers"}},
    {"hotel":"Sonesta Bogota","urls":{"es":"https://www.sonestabogota.com/ofertas","en":"https://en.sonestabogota.com/offers"}},
    {"hotel":"Sonesta Ibague","urls":{"es":"https://www.sonestaibague.com/ofertas","en":"https://en.sonestaibague.com/offers"}},
    {"hotel":"Sonesta Loja","urls":{"es":"https://www.sonestaloja.com/ofertas","en":"https://en.sonestaloja.com/offers"}},
    {"hotel":"Sonesta Osorno","urls":{"es":"https://www.sonestaosorno.com/ofertas","en":"https://en.sonestaosorno.com/offers","pt":"https://pt.sonestaosorno.com/ofertas"}},
    {"hotel":"Sonesta Pereira","urls":{"es":"https://www.sonestapereira.com/ofertas","en":"https://en.sonestapereira.com/offers"}},
    {"hotel":"Sonesta Puno","urls":{"es":"https://www.sonestapipuno.com/ofertas","en":"https://en.sonestapipuno.com/offers"}},
    {"hotel":"Sonesta Yucay","urls":{"es":"https://www.sonestapiyucay.com/ofertas","en":"https://en.sonestapiyucay.com/offers"}},
    {"hotel":"Sonesta Valledupar","urls":{"es":"https://www.sonestavalledupar.com/ofertas","en":"https://en.sonestavalledupar.com/offers"}},
    {"hotel":"Sonesta Miraflores","urls":{"es":"https://www.sonestamiraflores.com/ofertas","en":"https://en.sonestamiraflores.com/offers"}},
    # Irotama Resort (Santa Marta): un complejo con 6 torres, todas comparten la misma
    # pagina de ofertas; se filtran por el codigo de torre embebido en el link de reserva.
    {"hotel":"Irotama del Mar","urls":{"es":"https://www.irotama.com/ofertas"},"hotel_code_filter":"irodmr"},
    {"hotel":"Irotama del Sol","urls":{"es":"https://www.irotama.com/ofertas"},"hotel_code_filter":"irodsl"},
    {"hotel":"Irotama Bungalows y Bohios","urls":{"es":"https://www.irotama.com/ofertas"},"hotel_code_filter":"irohbb"},
    {"hotel":"Irotama Lago","urls":{"es":"https://www.irotama.com/ofertas"},"hotel_code_filter":"irolago"},
    {"hotel":"Irotama Reservado","urls":{"es":"https://www.irotama.com/ofertas"},"hotel_code_filter":"irorvd"},
    {"hotel":"Irotama XXI","urls":{"es":"https://www.irotama.com/ofertas"},"hotel_code_filter":"iroxxl"},
    # Bastion Luxury Hotel (Cartagena): web en otra plataforma (reservhotel), solo espanol,
    # sin la estructura .titular-title ni links con ?co=. Usa un extractor propio ("bastion",
    # ver ghl_scraper_individual_v3.py) y code_hint fija el hotel_code para que geo_of resuelva.
    {"hotel":"Bastión Luxury Hotel","urls":{"es":"https://www.bastionluxuryhotel.com/ofertas-en-hoteles-cartagena"},"extractor":"bastion","code_hint":"bastionlux"},
]

CATEGORIES = {
    "Early Booking":["anticipad","early booking","early bird","advance"],
    "Long Stay":["estadía mínima","mínima estadía","minimum stay","noches","nights"],
    "Promo Especial":["promo","especial","special","experiencia","experience","noche gratis","free night"],
    "Corporativo":["corporativ","corporate","empresa","business","ejecutiv","executive"],
    "Romance":["romance","romántic","romantic","pareja","couple","luna de miel","honeymoon"],
    "Temporada":["temporada","season","navidad","christmas","año nuevo","new year"],
}

JS_EXTRACT = """
(async () => {
  await new Promise(r => setTimeout(r, 2000));
  const offers = [];
  const skip = ['cookie','footer','header','menu','nav','login','newsletter','conoce','ya conoces','know our','best offer'];
  document.querySelectorAll('h2,h3,h4').forEach(h => {
    const title = h.innerText.trim();
    if (title.length < 5 || title.length > 200) return;
    if (skip.some(s => title.toLowerCase().includes(s))) return;
    let card = h.parentElement;
    for (let i = 0; i < 8; i++) {
      if (!card) break;
      if (card.innerText.trim().length > title.length + 20) break;
      card = card.parentElement;
    }
    const full = card ? card.innerText.trim() : '';
    if (full.length <= title.length + 5) return;
    const innerHeadings = card ? card.querySelectorAll('h2,h3,h4').length : 1;
    if (innerHeadings > 1) return;
    const desc = full.replace(title,'').replace(/\\bRESERVAR\\b|\\bBOOK\\b|\\bBOOK NOW\\b|\\bReservar\\b/g,'').trim();
    const discounts = full.match(/(\\d+)\\s*%/g) || [];
    const promoCode = (full.match(/[Cc]digo[:\\s]+([A-Z0-9]+)|[Cc]ode[:\\s]+([A-Z0-9]+)/)||[])[1]||'';
    const hasArtifact = desc.startsWith('"') || desc.startsWith('\\u201c');
    offers.push({titulo:title,descripcion:desc.substring(0,400),descuentos:discounts,codigo_promo:promoCode,tiene_artifact:hasArtifact,texto_completo:full.substring(0,600)});
  });
  return JSON.stringify(offers);
})()
"""

def detect_category(title, desc):
    text = (title+" "+desc).lower()
    for cat,kws in CATEGORIES.items():
        if any(k in text for k in kws): return cat
    return "Oferta General"

def detect_dates(text):
    for p in [r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',r'hasta\s+el\s+\d{1,2}',r'valido\s+hasta',r'valid\s+until']:
        m = re.search(p,text,re.IGNORECASE)
        if m: return m.group(0)
    return ""

def check_bp(offer):
    notes=[]
    full=offer.get("texto_completo","")
    if offer.get("tiene_artifact"): notes.append({"tipo":"error","texto":"Artefacto CRS visible en web"})
    if not offer.get("fechas"): notes.append({"tipo":"warn","texto":"Fechas de vigencia no especificadas"})
    if "t&c" not in full.lower() and "terminos" not in full.lower() and "terms" not in full.lower():
        notes.append({"tipo":"warn","texto":"T&C no incluido"})
    if len(offer.get("titulo",""))>60: notes.append({"tipo":"warn","texto":"Titulo demasiado largo"})
    if not offer.get("descuentos") and "gratis" not in full.lower() and "free" not in full.lower():
        notes.append({"tipo":"warn","texto":"Beneficio no especificado claramente"})
    return notes

async def scrape_hotel(page, hotel):
    result={"hotel":hotel["hotel"],"idiomas":{}}
    for lang,url in hotel["urls"].items():
        print(f"  [{lang.upper()}] {url}",end=" ... ",flush=True)
        ld={"url":url,"offers":[],"error":None}
        try:
            await page.goto(url,wait_until="domcontentloaded",timeout=30000)
            await page.wait_for_timeout(3500)
            raw=await page.evaluate(JS_EXTRACT)
            parsed=json.loads(raw)
            for o in parsed:
                cat=detect_category(o["titulo"],o["descripcion"])
                dates=detect_dates(o["texto_completo"])
                o["fechas"]=dates or None
                o["categoria"]=cat
                o["bp_notes"]=check_bp({**o,"fechas":dates})
                ld["offers"].append(o)
            print(f"OK {len(ld['offers'])} oferta(s)")
        except Exception as e:
            ld["error"]=str(e)[:120]
            print(f"ERROR {ld['error']}")
        result["idiomas"][lang]=ld
    return result

CAT_CLASS={"Early Booking":"cat-early","Long Stay":"cat-long","Promo Especial":"cat-promo","Corporativo":"cat-corp","Romance":"cat-romance","Temporada":"cat-temporada","Oferta General":"cat-general"}

def safe_id(n): return re.sub(r'[^a-z0-9]','_',n.lower())

CSS="""<style>
:root{--navy:#023859;--mid:#2A5E95;--blue:#6399BA;--gray:#808080;--lgray:#D1D1D1;--bg:#f0f4f8;--white:#fff;--ok:#1a7a4a;--ok-bg:#e6f4ea;--warn:#8a5c00;--warn-bg:#fff8e1;--err:#b0281a;--err-bg:#fce8e6;--neu:#f4f7fb}
*{box-sizing:border-box;margin:0;padding:0}body{font-family:sans-serif;background:var(--bg);color:#1a2533;font-size:13px}
.hdr{background:var(--navy);padding:32px 48px 24px}.hdr h1{color:#fff;font-size:26px;font-weight:400}.hdr .meta{color:var(--blue);font-size:12px;margin-top:4px}
.stats{background:var(--mid);display:flex;padding:0 48px;flex-wrap:wrap}
.stat{padding:12px 28px 12px 0;margin-right:28px;border-right:1px solid rgba(255,255,255,.1)}.stat:last-child{border:none}
.stat .v{color:#fff;font-size:22px;font-weight:600}.stat .l{color:var(--blue);font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.hotel-bar{background:#fff;border-bottom:2px solid var(--lgray);padding:0 48px;display:flex;gap:2px;position:sticky;top:0;z-index:200;overflow-x:auto}
.hotel-tab{padding:12px 16px;font-size:12px;font-weight:500;color:var(--gray);border:none;background:none;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;white-space:nowrap}
.hotel-tab.active{color:var(--navy);border-bottom-color:var(--navy);font-weight:700}
.hotel-panel{display:none;padding:24px 48px 48px}.hotel-panel.active{display:block}
.sub-bar{display:flex;gap:2px;margin-bottom:24px;border-bottom:1px solid var(--lgray)}
.sub-tab{padding:8px 18px;font-size:12px;font-weight:500;color:var(--gray);border:none;background:none;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
.sub-tab.active{color:var(--navy);border-bottom-color:var(--blue);font-weight:600}
.sub-panel{display:none}.sub-panel.active{display:block}
.lang-row{display:flex;align-items:center;gap:8px;margin-bottom:18px}
.lang-btn{padding:4px 14px;border-radius:20px;font-size:11px;font-weight:500;cursor:pointer;border:1.5px solid var(--lgray);background:#fff;color:var(--gray)}
.lang-btn.active{background:var(--navy);color:#fff;border-color:var(--navy)}
.lv{display:none}.lv.active{display:block}
.hs-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:24px}
.hs-card{background:#fff;border-radius:8px;border:1px solid var(--lgray);padding:14px 16px}
.hs-card .hv{font-size:26px;font-weight:700;color:var(--navy)}.hs-card .hl{font-size:10px;color:var(--gray);text-transform:uppercase;letter-spacing:.4px;margin-top:2px}
.hs-card.accent{background:var(--navy)}.hs-card.accent .hv{color:#fff}.hs-card.accent .hl{color:var(--blue)}
.slabel{font-size:10px;font-weight:700;text-transform:uppercase;color:var(--mid);margin:0 0 12px;padding-bottom:4px;border-bottom:1px solid var(--lgray)}
.ogrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;margin-bottom:8px}
.ocard{background:#fff;border-radius:8px;border:1px solid var(--lgray);overflow:hidden}
.ocard-hdr{padding:11px 14px 9px;border-bottom:1px solid var(--lgray);display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.otitle{font-weight:600;font-size:13px;color:var(--navy);line-height:1.4;margin-bottom:3px}
.cat-tag{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px;text-transform:uppercase}
.cat-early{background:#e8f1fb;color:#1a4a9a}.cat-long{background:#e8f5ee;color:#0f6e56}
.cat-promo{background:#faeeda;color:#854f0b}.cat-corp{background:#f0eafb;color:#5a2d9a}
.cat-romance{background:#fce8f3;color:#8a1a5a}.cat-temporada{background:#fff3e0;color:#8a4a00}
.cat-general{background:var(--neu);color:var(--mid)}
.sbadge{font-size:10px;font-weight:700;padding:2px 9px;border-radius:20px;background:var(--ok-bg);color:var(--ok);flex:none}
.ocard-body{padding:11px 14px}
.fl{display:flex;gap:8px;margin-bottom:7px;align-items:flex-start}
.fl-lbl{font-size:10px;font-weight:600;text-transform:uppercase;color:var(--blue);min-width:72px;flex:none;padding-top:1px}
.fl-val{font-size:12px;color:#2a3a4a;line-height:1.5;flex:1}
.miss{color:var(--lgray);font-style:italic}
.dtag{display:inline-block;background:var(--navy);color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;margin-right:3px}
.bp-notes{margin-top:8px;padding-top:8px;border-top:1px dashed var(--lgray)}
.bp-note{font-size:11px;line-height:1.4;color:#4a6a85;margin-bottom:4px}
.empty-state{padding:32px;text-align:center;color:var(--gray);font-size:13px;background:#fff;border-radius:8px;border:1px solid var(--lgray)}
.error-state{padding:20px;background:var(--err-bg);border-radius:8px;color:var(--err);font-size:12px}
.ctbl{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;border:1px solid var(--lgray);margin-bottom:16px;font-size:12px}
.ctbl th{padding:9px 14px;font-size:10px;font-weight:600;text-transform:uppercase;color:#fff;background:var(--navy);text-align:left}
.ctbl th:first-child{background:var(--mid);width:130px}
.ctbl td{padding:9px 14px;border-bottom:1px solid var(--lgray);vertical-align:top;line-height:1.4}
.ctbl tr:last-child td{border-bottom:none}.ctbl td:first-child{font-weight:600;color:var(--navy);background:#f8fafc}
.ctbl .sec td{background:var(--navy)!important;color:#fff!important;font-size:10px!important;font-weight:600!important;padding:6px 14px!important}
.mok{color:var(--ok);font-weight:500}.mdiff{color:var(--warn);font-weight:500}.mmiss{color:var(--err);font-weight:500}
.atbl{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;border:1px solid var(--lgray);font-size:12px}
.atbl th{padding:8px 12px;font-size:10px;font-weight:600;text-transform:uppercase;color:#fff;background:var(--mid);text-align:left}
.atbl td{padding:8px 12px;border-bottom:1px solid var(--lgray);vertical-align:top;line-height:1.4}
.atbl tr:last-child td{border-bottom:none}
.p-alta{color:var(--err);font-weight:600}.p-media{color:var(--warn);font-weight:600}.p-baja{color:var(--gray)}
</style>"""

def render_lang(hid,lang,ld):
    if ld.get("error"): return f'<div class="error-state">Error al cargar: {ld["error"]}</div>'
    offers=ld.get("offers",[])
    if not offers: return '<div class="empty-state">Sin ofertas detectadas en esta pagina</div>'
    lname={"es":"Espanol","en":"English","pt":"Portugues"}.get(lang,lang.upper())
    html=f'<div class="slabel">{len(offers)} oferta(s) - {lname}</div><div class="ogrid">'
    for o in offers:
        cc=CAT_CLASS.get(o["categoria"],"cat-general")
        discs="".join(f'<span class="dtag">{d}</span>' for d in o["descuentos"]) if o["descuentos"] else '<span class="miss">No especificado</span>'
        fechas=o.get("fechas") or '<span class="miss">No especificadas</span>'
        notes="".join(f'<div class="bp-note">{n["texto"]}</div>' for n in o.get("bp_notes",[]))
        bp=f'<div class="bp-notes">{notes}</div>' if notes else ""
        t=o["titulo"].replace("<","&lt;").replace(">","&gt;")
        d=(o.get("descripcion") or "").replace("<","&lt;").replace(">","&gt;")[:300]
        html+=f'<div class="ocard"><div class="ocard-hdr"><div><div class="otitle">{t}</div><span class="cat-tag {cc}">{o["categoria"]}</span></div><span class="sbadge">Activa</span></div><div class="ocard-body"><div class="fl"><span class="fl-lbl">Descripcion</span><span class="fl-val">{d or "<span class=miss>Sin descripcion</span>"}</span></div><div class="fl"><span class="fl-lbl">Descuento</span><span class="fl-val">{discs}</span></div><div class="fl"><span class="fl-lbl">Fechas</span><span class="fl-val">{fechas}</span></div>{bp}</div></div>'
    return html+"</div>"

def render_compare(hd):
    idiomas=hd["idiomas"]; langs=list(idiomas.keys())
    if len(langs)<2: return '<div class="empty-state">Solo un idioma configurado</div>'
    all_o={l:idiomas[l].get("offers",[]) for l in langs}
    max_o=max(len(v) for v in all_o.values())
    if not max_o: return '<div class="empty-state">Sin ofertas para comparar</div>'
    headers="".join(f'<th>{l.upper()}</th>' for l in langs)
    html=f'<table class="ctbl"><thead><tr><th>Campo</th>{headers}<th>Estado</th></tr></thead><tbody>'
    for i in range(max_o):
        obl={l:all_o[l][i] if i<len(all_o[l]) else None for l in langs}
        base=next((o for o in obl.values() if o),None)
        if not base: continue
        titles=[obl[l]["titulo"] for l in langs if obl[l]]
        ts='<span class="mok">Consistente</span>' if len(set(t.lower()[:20] for t in titles))==1 else '<span class="mdiff">Distintos</span>'
        discs=[tuple(obl[l]["descuentos"]) for l in langs if obl[l]]
        ds='<span class="mok">Identico</span>' if len(set(discs))==1 else '<span class="mdiff">Diferente</span>'
        fechas=[obl[l].get("fechas") for l in langs if obl[l]]
        fs='<span class="mmiss">Sin fechas</span>' if not any(fechas) else '<span class="mok">Presente</span>'
        errors=[l for l in langs if obl[l] and any(n["tipo"]=="error" for n in obl[l].get("bp_notes",[]))]
        es=f'<span class="mmiss">Error en {",".join(errors)}</span>' if errors else '<span class="mok">Sin errores</span>'
        tr="".join(f'<td>{obl[l]["titulo"].replace("<","&lt;") if obl[l] else "-"}</td>' for l in langs)
        dr="".join(f'<td>{",".join(obl[l]["descuentos"]) if obl[l] and obl[l]["descuentos"] else "-"}</td>' for l in langs)
        fr="".join(f'<td>{obl[l].get("fechas") or "-" if obl[l] else "-"}</td>' for l in langs)
        er="".join(f'<td>{"Si" if l in errors else "-"}</td>' for l in langs)
        bt=base["titulo"].replace("<","&lt;").upper()
        html+=f'<tr class="sec"><td colspan="{len(langs)+2}">{bt}</td></tr><tr><td>Titulo</td>{tr}<td>{ts}</td></tr><tr><td>Descuento</td>{dr}<td>{ds}</td></tr><tr><td>Fechas</td>{fr}<td>{fs}</td></tr><tr><td>Error CRS</td>{er}<td>{es}</td></tr>'
    return html+"</tbody></table>"

def render_bp(hd):
    rows=""
    for lang,ld in hd["idiomas"].items():
        for o in ld.get("offers",[]):
            for n in o.get("bp_notes",[]):
                pc={"error":"p-alta","warn":"p-media","info":"p-baja"}.get(n["tipo"],"p-baja")
                pl={"error":"Alta","warn":"Media","info":"Baja"}.get(n["tipo"],"Baja")
                t=o["titulo"][:40].replace("<","&lt;")
                rows+=f'<tr><td>{t}</td><td>{lang.upper()}</td><td>{n["texto"]}</td><td class="{pc}">{pl}</td></tr>'
    if not rows: return '<div class="empty-state">Sin observaciones registradas</div>'
    return f'<table class="atbl"><thead><tr><th>Oferta</th><th>Idioma</th><th>Observacion</th><th>Prioridad</th></tr></thead><tbody>{rows}</tbody></table>'

def render_resumen(hd):
    all_o=[o for ld in hd["idiomas"].values() for o in ld.get("offers",[])]
    if not all_o: return '<div class="empty-state">Sin datos</div>'
    total=len(set(o["titulo"] for o in all_o))
    cats={}
    for o in all_o: cats[o["categoria"]]=cats.get(o["categoria"],0)+1
    wd=sum(1 for o in all_o if o.get("fechas"))
    we=sum(1 for o in all_o if any(n["tipo"]=="error" for n in o.get("bp_notes",[])))
    pd_v=int(wd/len(all_o)*100) if all_o else 0
    cats_html="".join(f'<div style="padding:6px 0;border-bottom:1px solid var(--lgray);display:flex;justify-content:space-between;font-size:12px"><span>{c} (x{n})</span><span style="color:var(--ok);font-weight:600">Activa(s)</span></div>' for c,n in sorted(cats.items(),key=lambda x:-x[1]))
    err_note=f'<div style="margin-top:12px;padding:10px 14px;background:var(--err-bg);border-radius:6px;color:var(--err);font-size:12px">{we} oferta(s) con errores de formato CRS</div>' if we else ""
    return f'<div class="hs-grid"><div class="hs-card accent"><div class="hv">{total}</div><div class="hl">Ofertas unicas</div></div><div class="hs-card"><div class="hv">{len(hd["idiomas"])}</div><div class="hl">Idiomas</div></div><div class="hs-card"><div class="hv">{pd_v}%</div><div class="hl">Con fechas</div></div><div class="hs-card"><div class="hv">{we}</div><div class="hl">Errores CRS</div></div></div><div style="background:#fff;border-radius:8px;border:1px solid var(--lgray);padding:16px"><div class="slabel">Por categoria</div>{cats_html}</div>{err_note}'

def build_html(all_data,run_date):
    total_o=sum(len(ld.get("offers",[])) for hd in all_data for ld in hd["idiomas"].values())
    total_l=len(set(l for hd in all_data for l in hd["idiomas"]))
    total_e=sum(1 for hd in all_data for ld in hd["idiomas"].values() if ld.get("error") or any(any(n["tipo"]=="error" for n in o.get("bp_notes",[])) for o in ld.get("offers",[])))
    tabs=""; panels=""
    for hd in all_data:
        hid=safe_id(hd["hotel"]); langs=list(hd["idiomas"].keys())
        tabs+=f'<button class="hotel-tab" onclick="switchHotel(\'{hid}\',this)">{hd["hotel"]}</button>\n'
        lbtns="".join(f'<button class="lang-btn {"active" if i==0 else ""}" onclick="switchLang(\'{hid}-ofertas\',\'{l}\',this)">{l.upper()}</button>' for i,l in enumerate(langs))
        lviews="".join(f'<div class="lv {"active" if i==0 else ""}" id="{hid}-ofertas-{l}">{render_lang(hid,l,hd["idiomas"][l])}</div>' for i,l in enumerate(langs))
        total_h=sum(len(hd["idiomas"][l].get("offers",[])) for l in langs)
        cats_h={}
        for l in langs:
            for o in hd["idiomas"][l].get("offers",[]): cats_h[o["categoria"]]=cats_h.get(o["categoria"],0)+1
        cc="".join(f'<div class="hs-card"><div class="hv">{n}</div><div class="hl">{c}</div></div>' for c,n in sorted(cats_h.items(),key=lambda x:-x[1])[:3])
        while cc.count("hs-card")<3: cc+='<div class="hs-card"><div class="hv">-</div><div class="hl">&nbsp;</div></div>'
        panels+=f'<div class="hotel-panel" id="hp-{hid}"><div class="sub-bar"><button class="sub-tab active" onclick="switchSub(\'{hid}\',\'ofertas\',this)">Ofertas</button><button class="sub-tab" onclick="switchSub(\'{hid}\',\'comparativo\',this)">Comparativo ES/EN</button><button class="sub-tab" onclick="switchSub(\'{hid}\',\'auditoria\',this)">Observaciones BP</button><button class="sub-tab" onclick="switchSub(\'{hid}\',\'resumen\',this)">Resumen</button></div><div class="sub-panel active" id="{hid}-ofertas"><div class="hs-grid"><div class="hs-card accent"><div class="hv">{total_h}</div><div class="hl">Ofertas activas</div></div>{cc}</div><div class="lang-row"><span style="font-size:11px;color:var(--gray)">Idioma:</span>{lbtns}</div>{lviews}</div><div class="sub-panel" id="{hid}-comparativo">{render_compare(hd)}</div><div class="sub-panel" id="{hid}-auditoria">{render_bp(hd)}</div><div class="sub-panel" id="{hid}-resumen">{render_resumen(hd)}</div></div>'
    tabs=tabs.replace('class="hotel-tab"','class="hotel-tab active"',1)
    panels=panels.replace('class="hotel-panel"','class="hotel-panel active"',1)
    return f'<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Dashboard Ofertas GHL</title>{CSS}</head><body><div class="hdr"><h1>Dashboard de Ofertas - GHL Hotels</h1><div class="meta">Extraccion: {run_date} - {len(all_data)} hoteles - {total_l} idiomas</div></div><div class="stats"><div class="stat"><div class="v">{len(all_data)}</div><div class="l">Hoteles</div></div><div class="stat"><div class="v">{total_o}</div><div class="l">Ofertas</div></div><div class="stat"><div class="v">{total_l}</div><div class="l">Idiomas</div></div><div class="stat"><div class="v">{total_e}</div><div class="l">Errores CRS</div></div></div><div class="hotel-bar">{tabs}</div>{panels}<script>function switchHotel(id,btn){{document.querySelectorAll(".hotel-panel").forEach(p=>p.classList.remove("active"));document.querySelectorAll(".hotel-tab").forEach(b=>b.classList.remove("active"));document.getElementById("hp-"+id).classList.add("active");btn.classList.add("active");}}function switchSub(hotel,sub,btn){{const hp=document.getElementById("hp-"+hotel);hp.querySelectorAll(".sub-panel").forEach(p=>p.classList.remove("active"));hp.querySelectorAll(".sub-tab").forEach(b=>b.classList.remove("active"));document.getElementById(hotel+"-"+sub).classList.add("active");btn.classList.add("active");}}function switchLang(scope,lang,btn){{const c=document.getElementById(scope);c.querySelectorAll(".lv").forEach(v=>v.classList.remove("active"));c.querySelectorAll(".lang-btn").forEach(b=>b.classList.remove("active"));document.getElementById(scope+"-"+lang).classList.add("active");btn.classList.add("active");}}</script></body></html>'

async def main():
    run_date=datetime.now().strftime("%d/%m/%Y %H:%M")
    timestamp=datetime.now().strftime("%Y-%m-%d_%H-%M")
    out=Path("reportes_ghl"); out.mkdir(exist_ok=True)
    print(f"\n{'='*60}\n  GHL Dashboard -- {run_date}\n  {len(HOTELS)} hoteles\n{'='*60}\n")
    all_data=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",locale="es-CO",viewport={"width":1280,"height":800})
        page=await ctx.new_page()
        for i,hotel in enumerate(HOTELS,1):
            print(f"[{i:02d}/{len(HOTELS)}] {hotel['hotel']}")
            all_data.append(await scrape_hotel(page,hotel))
            if i<len(HOTELS): await asyncio.sleep(0.5)
        await browser.close()
    html=build_html(all_data,run_date)
    (out/f"ghl_dashboard_{timestamp}.html").write_text(html,encoding="utf-8")
    (out/"ghl_dashboard_latest.html").write_text(html,encoding="utf-8")
    (out/f"ghl_ofertas_{timestamp}.json").write_text(json.dumps(all_data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"\nDashboard generado: reportes_ghl/ghl_dashboard_latest.html\n")

if __name__=="__main__":
    import sys
    if "--test" in sys.argv:
        HOTELS[:]=[h for h in HOTELS if h["hotel"] in ("Arsenal","Bioxury")]
        print("\nModo test -- solo Arsenal y Bioxury\n")
    asyncio.run(main())