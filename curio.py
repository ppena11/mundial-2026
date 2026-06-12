"""
curio.py — MOTOR DE "DATO CURIOSO" para los días SIN partido del Mundial.
Mantiene la cadencia diaria (video + digest + caption) cuando no rueda el balón.

Regla de oro (credibilidad de @aiwithpedro):
  - Las NOTICIAS salen de un feed real (Google News RSS) y SIEMPRE se cita la fuente + link.
  - Claude solo reformula con gancho; NUNCA inventa números ni noticias.
  - Si no hay noticia relevante, cae a un DATO EXACTO de las 20.000 simulaciones del modelo.

Genera/lee curio_today.json (cacheado por fecha) para que el video, el digest y el caption
del día cuenten exactamente lo mismo. Una sola llamada a Claude y una sola al feed por día.

USO:  python curio.py [--date YYYYMMDD]
"""
import sys, os, json, urllib.parse
from datetime import datetime, date
try:
    import requests
except ImportError:
    requests = None
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

KICKOFF = date(2026, 6, 11)
CURIO_FILE = "curio_today.json"
BRAND = "aiwithpedro"
BRAND_VOZ = "éi ái uíz Pédro"   # cómo se pronuncia @aiwithpedro en la voz (ElevenLabs)
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PROXY = "https://api.codetabs.com/v1/proxy/?quest="
NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl=es-419&gl=US&ceid=US:es-419"
NEWS_QUERY = ('("Mundial 2026" OR "World Cup 2026") '
              '(IA OR "inteligencia artificial" OR tecnologia OR VAR OR FIFA OR balon)')

# ---------- material seguro ----------
def days_to_kickoff(target):
    td = datetime.strptime(target, "%Y%m%d").date()
    return (KICKOFF - td).days

def _champ():
    try:
        return list(json.load(open("champ_today.json", encoding="utf-8"))["campeon"].items())
    except Exception:
        return []

def model_fact(champ, days):
    """Un dato EXACTO derivado de las simulaciones; rota por día para no repetir."""
    if not champ:
        return "Mi inteligencia artificial corre 20.000 simulaciones del Mundial cada día."
    import daily_digest as dd
    f = []
    t1, v1 = champ[0]
    f.append(f"Según mis 20.000 simulaciones, quien más veces queda campeón es {dd.acc(t1)}, con {round(v1)} por ciento.")
    if len(champ) >= 2:
        t2, v2 = champ[1]
        f.append(f"La pelea por el primer puesto está cerrada: {dd.acc(t1)} con {round(v1)} por ciento contra {dd.acc(t2)} con {round(v2)} por ciento.")
    if len(champ) >= 3:
        t3, v3 = champ[2]
        f.append(f"Dato que sorprende: mi IA mete a {dd.acc(t3)} entre los tres primeros, con {round(v3)} por ciento de quedar campeón.")
    dh = [(t, v) for t, v in champ[5:11] if v >= 1.0]
    if dh:
        t, v = dh[0]
        f.append(f"El tapado del Mundial: {dd.acc(t)} queda campeón en {round(v)} de cada 100 simulaciones, y casi nadie habla de él.")
    return f[days % len(f)] if f else ""

def web_news():
    """Top noticia REAL (IA x Mundial) del feed de Google News. None si no hay nada relevante."""
    if requests is None:
        return None
    import xml.etree.ElementTree as ET
    url = NEWS_RSS.format(q=urllib.parse.quote(NEWS_QUERY))
    raw = None
    for u in (url, PROXY + urllib.parse.quote(url, safe="")):
        try:
            r = requests.get(u, headers=HEAD, timeout=20)
            if r.status_code == 200 and "<item" in r.text:
                raw = r.text; break
        except Exception:
            pass
    if not raw:
        return None
    try:
        root = ET.fromstring(raw)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            src_el = item.find("source")
            source = (src_el.text.strip() if src_el is not None and src_el.text else "")
            low = title.lower()
            if any(k in low for k in ("mundial", "world cup", "fifa", "2026")):
                if " - " in title and not source:        # Google News: "Título - Fuente"
                    title, source = title.rsplit(" - ", 1)
                return {"title": title.strip(), "source": (source or "Google News").strip(), "link": link}
    except Exception:
        pass
    return None

# ---------- Claude (gancho viral) ----------
CURIO_SYS = (
    "Eres el guionista y editor de @aiwithpedro, un creador que enseña inteligencia artificial. "
    "DATO FIJO: el Mundial 2026 arrancó el 11 de junio de 2026; respeta esa cronología (no digas que 'comienza hoy'). "
    "HOY NO HAY PARTIDOS del Mundial 2026: tu trabajo es mantener a la audiencia enganchada, dejando claro que hoy "
    "no rueda el balon. Te indico el ESTADO del torneo y te doy material REAL (una noticia con su fuente y/o un dato "
    "EXACTO de mis simulaciones). Devuelve EXCLUSIVAMENTE un objeto JSON (sin ``` ni texto extra) con EXACTAMENTE "
    "estas claves:\n"
    '"titulo": titulo viral para el post (max ~70 caracteres, gancho, max 1 emoji).\n'
    '"gancho": 1 o 2 frases para el digest; engancha y deja claro que hoy no hay partidos.\n'
    '"voz": guion HABLADO de 45 a 70 palabras (~20 s). Gancho fuerte al inicio; SIN emojis ni simbolos (lo lee un '
    "sintetizador de voz); numeros con digitos y 'por ciento'; invita a ver mas en el link de mi bio (NO nombres 'Substack' en la voz) y "
    "firma la voz diciendo EXACTAMENTE: Soy éi ái uíz Pédro (así se pronuncia @aiwithpedro).\n"
    '"card": resumen MUY corto y potente para una imagen (max 8 palabras, sin emojis, sin cortar a media palabra). '
    "Si hay noticia, es el titular resumido de forma viral.\n"
    '"caption": 1 o 2 lineas para TikTok, con gancho; puede llevar 1 o 2 emojis; NO incluyas hashtags aqui.\n'
    '"hashtags": lista de EXACTAMENTE 5 hashtags virales; incluye #Mundial2026, #IA y #parati.\n'
    '"youtube_titulo": título SEO para YouTube Shorts (al inicio "Mundial 2026" y el tema del día); máx ~90 caracteres.\n'
    '"youtube_descripcion": 2 o 3 frases con palabras clave (Mundial 2026, predicción con IA), con CTA (link en la bio). NO incluyas hashtags.\n'
    '"youtube_hashtags": lista de EXACTAMENTE 5 hashtags buscables; incluye #Mundial2026 y #Shorts.\n'
    "REGLAS DE ESTADO: si el torneo AUN NO empieza, puedes usar la cuenta regresiva (faltan N dias). "
    "Si el torneo YA EMPEZO (dia de descanso), NO menciones ninguna cuenta regresiva ni 'faltan dias'; "
    "manda al frente la NOTICIA mas viral del Mundial y cierra invitando a volver cuando haya partidos.\n"
    "Si el material trae una NOTICIA, MENCIONA la fuente en el gancho y en la voz, y NO agregues datos que no esten "
    "en el material. Español cercano y enérgico, apto para todo público, nada de apuestas. NUNCA inventes números. "
    "ESCRIBE EN ESPAÑOL CON TODAS LAS TILDES Y SIGNOS CORRECTOS (á, é, í, ó, ú, ñ, ¿, ¡): el texto lo lee un "
    "sintetizador de voz y la acentuación es OBLIGATORIA.")

def _material(p):
    import daily_digest as dd
    L = []
    if p["days"] > 0:
        dtxt = "Falta un día" if p["days"] == 1 else f"Faltan {p['days']} días"
        L.append(f"ESTADO: PRE-TORNEO. {dtxt} para el inicio del Mundial 2026 (11 de junio). "
                 "Puedes usar la cuenta regresiva (di 'un día' en singular, no 'uno día').")
    else:
        L.append("ESTADO: TORNEO EN CURSO, hoy es un día de descanso (sin partidos). NO uses cuenta regresiva; "
                 "lleva al frente la noticia más viral del Mundial.")
    if p["news"]:
        L.append(f"NOTICIA REAL (fuente {p['news']['source']}): {p['news']['title']}")
    L.append("DATO EXACTO DE MIS SIMULACIONES (úsalo, no inventes otros números): " + p["model_fact"])
    if p["champ"]:
        L.append("Top campeón hoy: " + ", ".join(f"{dd.acc(t)} {round(v)} por ciento" for t, v in p["champ"][:3]) + ".")
    try:
        import contexto
        ctx = contexto.resumen_torneo(p.get("target", ""), con_noticia=False)  # curio ya trae su propia noticia
        if ctx: L.append(ctx)
    except Exception:
        pass
    return "\n".join(L)

def ai_curio(material):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return {}
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")  # texto corto: Haiku = barato
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 700, "system": CURIO_SYS,
                  "messages": [{"role": "user", "content": "Material de hoy:\n" + material}]}, timeout=45)
        if r.status_code != 200:
            print(f"(IA curio no disponible: {r.status_code})"); return {}
        txt = r.json()["content"][0]["text"]
        return json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    except Exception as e:
        print(f"(IA curio falló: {e})"); return {}

# ---------- ensamblado + caché ----------
def _five(tags, champ):
    base = ["#Mundial2026"] + ["#" + t.replace(" ", "").replace(".", "") for t, _ in champ[:2]] + ["#IA", "#parati"]
    out = []
    for t in [str(x) for x in tags] + base:
        t = t if t.startswith("#") else "#" + t
        if t not in out:
            out.append(t)
    return out[:5]

def gather(target):
    days = days_to_kickoff(target)
    champ = _champ()
    return {"target": target, "days": days, "champ": champ, "model_fact": model_fact(champ, days), "news": web_news()}

def build(target):
    p = gather(target)
    ai = ai_curio(_material(p))
    days, news, mf, champ = p["days"], p["news"], p["model_fact"], p["champ"]
    pre = days > 0                                  # pre-torneo (cuenta regresiva) vs torneo en curso
    cd = (("Falta un día para el Mundial." if days == 1 else f"Faltan {days} días para el Mundial.")
          if pre else "El Mundial continúa cuando vuelvan los partidos.")
    via = f" (vía {news['source']})" if news else ""

    titulo = (ai.get("titulo") or "").strip() or (
        (news["title"][:64]) if news else (("Cuenta regresiva: falta 1 día" if days == 1 else f"Cuenta regresiva: faltan {days} días") if pre else "El Mundial, en pausa"))
    gancho = (ai.get("gancho") or "").strip() or (
        (f"Hoy no rueda el balón, pero hay novedades: {news['title']}{via}. {cd}") if news
        else f"Hoy no hay partidos, pero mi IA no descansa. {mf} {cd}")
    voz = (ai.get("voz") or "").strip() or (
        "Hoy no hay partidos del Mundial, pero te dejo algo. "
        + (f"{news['title']}, según {news['source']}. " if news else f"{mf} ")
        + f"{cd} El análisis completo está en el link de mi bio. "
          f"Soy {BRAND_VOZ}, nos vemos pronto.")
    card = (ai.get("card") or "").strip() or ((news["title"][:60]) if news else mf[:60])
    caption = (ai.get("caption") or "").strip() or (
        "Hoy sin partidos, pero el Mundial no para 👀 Analisis gratis en mi Substack (link en bio).")
    tags = _five(ai.get("hashtags") or [], champ)

    # YouTube (SEO) para el video de día sin partido
    yt_t = (ai.get("youtube_titulo") or "").strip() or (
        f"Mundial 2026: {('faltan ' + str(days) + ' días' if days > 0 else 'dato del día')} | predicción con IA")
    yt_d = (ai.get("youtube_descripcion") or "").strip() or (
        f"Mundial 2026 con inteligencia artificial. {(card or '')} Pronósticos diarios y análisis del modelo. "
        "Todo gratis, link en la bio.")
    yt_h = [(t if str(t).startswith("#") else "#"+str(t)) for t in (ai.get("youtube_hashtags") or [])]
    for extra in ["#Mundial2026", "#Shorts", "#IA", "#Pronosticos", "#WorldCup2026"]:
        if len(yt_h) >= 5: break
        if extra not in yt_h: yt_h.append(extra)

    out = {"date": target, "titulo": titulo, "gancho": gancho, "voz": voz, "card": card,
           "caption": caption, "hashtags": tags, "is_news": bool(news),
           "youtube_titulo": yt_t[:95], "youtube_descripcion": yt_d, "youtube_hashtags": yt_h[:5],
           "source": (news["source"] if news else ""), "link": (news["link"] if news else ""), "days": days}
    json.dump(out, open(CURIO_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return out

def ensure(target):
    """Devuelve el curio del día; lo genera una vez y lo cachea (mismo dato para video/digest/caption)."""
    try:
        c = json.load(open(CURIO_FILE, encoding="utf-8"))
        if c.get("date") == target:
            return c
    except Exception:
        pass
    return build(target)

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    c = build(target)
    print(json.dumps(c, ensure_ascii=False, indent=2))
    print(f"\n→ {CURIO_FILE} guardado ({'noticia: '+c['source'] if c['is_news'] else 'dato del modelo'})")
