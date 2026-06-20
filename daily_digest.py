"""
daily_digest.py — arma el DIGEST DIARIO premium (producto de pago) y, opcionalmente,
lo envía por email. Reutiliza el modelo y los datos que ya genera el pipeline.

QUÉ INCLUYE por partido:
  - Hora de inicio en ET (hora del Este, UTC-4 durante el Mundial).
  - Etiqueta: "Grupo X" (fase de grupos) o "Semifinal 1" / "Dieciseisavos 3" / "Final" (eliminatorias).
  - 1X2 del modelo, goles esperados, marcador más probable, bajas.
  - Descripción automática del partido (favorito, parejo, goles, eliminación, bajas).
Más: seguimiento del campeón y disclaimer legal.

SALIDA: digest.md + digest.html.  ENVÍO EMAIL opcional: RESEND_API_KEY/DIGEST_FROM/DIGEST_TO.
USO: python daily_digest.py [--date YYYYMMDD] [--send]
"""
import sys, os, json, urllib.parse
from datetime import date, datetime, timedelta
try:
    import requests
except ImportError:
    requests = None
try:
    from env_loader import load_env; load_env()
except Exception:
    pass
import predict_match as pm   # fit_model, apply_adjustments, one_x_two, MAP, HOSTS

BRAND = "aiwithpedro"
DISCLAIMER = ("Contenido informativo y de entretenimiento. Son predicciones de un modelo "
              "estadístico, no certezas.")
ET_OFFSET = timedelta(hours=-4)   # America/Toronto = EDT (UTC-4) durante jun–jul 2026

GROUPS = {"A":["Mexico","Sudafrica","Corea del Sur","Chequia"],"B":["Canada","Bosnia","Catar","Suiza"],
 "C":["Brasil","Marruecos","Haiti","Escocia"],"D":["Estados Unidos","Paraguay","Australia","Turquia"],
 "E":["Alemania","Curazao","Costa de Marfil","Ecuador"],"F":["Paises Bajos","Japon","Suecia","Tunez"],
 "G":["Belgica","Egipto","Iran","Nueva Zelanda"],"H":["Espana","Cabo Verde","Arabia Saudi","Uruguay"],
 "I":["Francia","Senegal","Irak","Noruega"],"J":["Argentina","Argelia","Austria","Jordania"],
 "K":["Portugal","R.D. Congo","Uzbekistan","Colombia"],"L":["Inglaterra","Croacia","Ghana","Panama"]}
TEAM2GROUP = {t: gN for gN, T in GROUPS.items() for t in T}
ROUND_ES = {"round-of-32":"Dieciseisavos","round-of-16":"Octavos","quarterfinals":"Cuartos",
            "semifinals":"Semifinal","final":"Final","3rd-place":"Tercer puesto"}
NO_NUMBER = {"final", "3rd-place"}

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PROXY = "https://api.codetabs.com/v1/proxy/?quest="
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
EN2ES = {en: es for es, en in pm.MAP.items()}
EN2ES.update({"Czechia":"Chequia","Czech Republic":"Chequia","USA":"Estados Unidos",
              "United States":"Estados Unidos","South Korea":"Corea del Sur","IR Iran":"Iran",
              "Türkiye":"Turquia","Bosnia & Herzegovina":"Bosnia","Bosnia-Herzegovina":"Bosnia",
              "Bosnia and Herzegovina":"Bosnia","Côte d'Ivoire":"Costa de Marfil",
              "Congo DR":"R.D. Congo","DR Congo":"R.D. Congo","Cape Verde":"Cabo Verde",
              "Cape Verde Islands":"Cabo Verde","Curaçao":"Curazao"})

# nombres del modelo (ASCII) -> con acentos, para MOSTRAR y para la VOZ (ElevenLabs los pronuncia bien)
ACENTOS = {"Mexico":"México","Sudafrica":"Sudáfrica","Canada":"Canadá","Haiti":"Haití","Turquia":"Turquía",
           "Paises Bajos":"Países Bajos","Japon":"Japón","Tunez":"Túnez","Belgica":"Bélgica","Iran":"Irán",
           "Espana":"España","Arabia Saudi":"Arabia Saudí","Uzbekistan":"Uzbekistán","Panama":"Panamá",
           "R.D. Congo":"República Democrática del Congo"}
def acc(t): return ACENTOS.get(t, t)

def _get(url):
    try:
        return requests.get(url, headers=HEAD, timeout=20).json()
    except Exception:
        return requests.get(PROXY + urllib.parse.quote(url, safe=""), headers=HEAD, timeout=45).json()

_PAIS_SEDE = {"USA": "Estados Unidos", "United States": "Estados Unidos",
              "Canada": "Canadá", "Mexico": "México"}

def fetch_all():
    """Todos los eventos del torneo con número de ronda asignado por orden de fecha."""
    # la API limita ~100 eventos por respuesta; el Mundial tiene 104 -> bajamos en 2 tramos
    evs, seen = [], set()
    for rng in ("20260611-20260704", "20260705-20260720"):
        try:
            for e in _get(f"{ESPN}/scoreboard?dates={rng}").get("events", []):
                if e.get("id") not in seen:
                    seen.add(e.get("id")); evs.append(e)
        except Exception as e:
            print(f"(no pude leer un tramo del calendario: {e})")
    # numerar partidos dentro de cada ronda KO (por fecha)
    ko = {}
    for e in evs:
        slug = e.get("season", {}).get("slug", "")
        if slug in ROUND_ES:
            ko.setdefault(slug, []).append(e)
    numbering = {}
    for slug, lst in ko.items():
        for i, e in enumerate(sorted(lst, key=lambda x: (x.get("date",""), str(x.get("id")))), 1):
            numbering[str(e.get("id"))] = i
    out = []
    for e in evs:
        comp = (e.get("competitions") or [{}])[0]
        cs = comp.get("competitors", [])
        if len(cs) != 2: continue
        home = next((c for c in cs if c.get("homeAway") == "home"), cs[0])
        away = next((c for c in cs if c.get("homeAway") == "away"), cs[1])
        a = EN2ES.get(home["team"]["displayName"], home["team"]["displayName"])
        b = EN2ES.get(away["team"]["displayName"], away["team"]["displayName"])
        dt_utc = e.get("date", "")
        slug = e.get("season", {}).get("slug", "")
        # etiqueta: grupo si ambos del mismo grupo; si no, ronda KO
        if TEAM2GROUP.get(a) and TEAM2GROUP.get(a) == TEAM2GROUP.get(b):
            label, is_ko = f"Grupo {TEAM2GROUP[a]}", False
        elif slug in ROUND_ES:
            rn = ROUND_ES[slug]
            label = rn if slug in NO_NUMBER else f"{rn} {numbering.get(str(e.get('id')),'')}".strip()
            is_ko = True
        else:
            label, is_ko = "Partido", (slug in ROUND_ES)
        v = comp.get("venue", {}) or {}
        addr = v.get("address", {}) or {}
        estadio = (v.get("fullName") or "").strip()
        if " at " in estadio:                 # "GEHA Field at Arrowhead Stadium" -> "Arrowhead Stadium" (TTS limpio)
            estadio = estadio.split(" at ", 1)[1].strip()
        ciudad = (addr.get("city") or "").strip()
        pais = (addr.get("country") or "").strip()
        pais = _PAIS_SEDE.get(pais, pais)
        out.append({"a": a, "b": b, "utc": dt_utc, "label": label, "is_ko": is_ko,
                    "estadio": estadio, "ciudad": ciudad, "pais": pais})
    return out

def _et(dt_utc):
    return datetime.strptime(dt_utc[:16], "%Y-%m-%dT%H:%M") + ET_OFFSET

def hora_et(dt_utc):
    try:
        return _et(dt_utc).strftime("%H:%M") + " ET"
    except Exception:
        return "—"

def et_date(dt_utc):
    """Fecha del partido en hora del Este (ET), como 'YYYY-MM-DD'."""
    try:
        return _et(dt_utc).strftime("%Y-%m-%d")
    except Exception:
        return dt_utc[:10]

_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
def weekday_es(target):
    """Nombre del día de la semana en español para un 'YYYYMMDD'. Lo calcula Python (no Claude,
    que se equivoca al deducir qué día cae una fecha)."""
    try:
        return _DIAS_ES[date(int(target[:4]), int(target[4:6]), int(target[6:8])).weekday()]
    except Exception:
        return ""

def fecha_larga(target):
    """Fecha hablada: 'jueves 18 de junio' a partir de 'YYYYMMDD' (calculada en Python, no por Claude)."""
    try:
        d = date(int(target[:4]), int(target[4:6]), int(target[6:8]))
        return f"{_DIAS_ES[d.weekday()]} {d.day} de {_MESES_ES[d.month-1]}"
    except Exception:
        return ""

def matches_on(yyyymmdd):
    iso = f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
    return [m for m in fetch_all() if et_date(m["utc"]) == iso]   # día en ET, no UTC

def champion_top(n=5):
    try:
        d = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
        return list(d.items())[:n]
    except Exception:
        return []

def descripcion(a, b, pw, pdr, pl, lh, la, is_ko, bajas_a, bajas_b, label):
    fav, fp = (a, pw) if pw >= pl else (b, pl)
    diff = abs(pw - pl); total = lh + la
    cl = []
    if fp >= 0.62: cl.append(f"{fav} parte como amplio favorito")
    elif fp >= 0.46 and diff < 0.10: cl.append("duelo muy parejo, puede caer para cualquiera")
    elif pdr >= 0.30 and diff < 0.14: cl.append("partido cerrado, con aroma a empate")
    else: cl.append(f"ligera ventaja para {fav}")
    if total >= 2.9: cl.append("se esperan goles")
    elif total <= 1.9: cl.append("pinta a pocos goles")
    bf = bajas_a if fav == a else bajas_b
    if bf: cl.append(f"ojo: {fav} llega con bajas ({', '.join(bf[:2])})")
    cuerpo = "; ".join(cl)
    if is_ko:
        pre = "La gran final. " if label.startswith("Final") else "Eliminación directa. "
        return pre + cuerpo[0].upper() + cuerpo[1:] + ". El que pierde queda fuera."
    return cuerpo[0].upper() + cuerpo[1:] + "."

AI_DIGEST_SYS = (
    "Eres el editor de @aiwithpedro, un creador que enseña inteligencia artificial. Con los datos del día del "
    "Mundial 2026, devuelve EXCLUSIVAMENTE un objeto JSON (sin ``` ni texto extra) con estas claves:\n"
    '"titulo": título viral para el post (máx ~70 caracteres, con gancho, máximo 1 emoji).\n'
    '"intro": 1 o 2 frases de apertura que enganchen, destacando el ángulo más jugoso del día.\n'
    '"jugada": 1 o 2 frases sobre la jugada de valor del día, explicada simple y atractiva.\n'
    "DÍA DE LA SEMANA: el día correcto está en los datos ('Hoy es …'); si lo nombras, usa EXACTAMENTE ese, NUNCA lo deduzcas. "
    "Español, cercano y enérgico, apto para todo público, nada de apuestas. Usa SOLO los datos dados; NO inventes números. "
    "ESCRIBE EN ESPAÑOL CON TODAS LAS TILDES Y SIGNOS CORRECTOS (á, é, í, ó, ú, ñ, ¿, ¡).")

def _digest_summary(fecha_h, data, pick, top, tr):
    dia = weekday_es(f"{fecha_h[6:10]}{fecha_h[3:5]}{fecha_h[0:2]}")   # día calculado en Python (Claude no lo deduce)
    L = [f"Hoy es {dia}, {fecha_h}." if dia else f"Fecha: {fecha_h}."]
    played = [d for d in data if not d.get("skip")]
    if not played:
        L.append("Hoy no hay partidos del Mundial."); return "\n".join(L)
    L.append("Partidos de hoy:")
    for d in played:
        fv, fp = (d["a"], d["pw"]) if d["pw"] >= d["pl"] else (d["b"], d["pl"])
        L.append(f"- {d['a']} contra {d['b']}: favorito {fv} {round(100*fp)} por ciento; empate "
                 f"{round(100*d['pdr'])}; marcador probable {d['sx']}-{d['sy']}.")
    if pick:
        t, mpb, mkp, edge = pick[1]
        L.append(f"Jugada de valor: {t} (modelo {round(100*mpb)} por ciento, mercado {round(100*mkp)} por ciento; infravalorada).")
    if top:
        L.append("Campeón: " + ", ".join(f"{t} {v} por ciento" for t, v in top[:3]) + ".")
    if tr.get("n", 0) > 0:
        L.append(f"Historial del modelo: {tr['aciertos_1x2']} de {tr['n']} aciertos.")
    return "\n".join(L)

def ai_digest(summary):
    """Claude redacta titulo + intro + jugada virales (los datos siguen siendo exactos). {} si no hay key."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return {}
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")  # texto corto: Haiku = barato
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 500, "system": AI_DIGEST_SYS,
                  "messages": [{"role": "user", "content": "Datos:\n" + summary}]}, timeout=45)
        if r.status_code != 200:
            print(f"(IA digest no disponible: {r.status_code})"); return {}
        txt = r.json()["content"][0]["text"]
        return json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    except Exception as e:
        print(f"(IA digest falló: {e})"); return {}

def build_digest(target):
    fecha_h = f"{target[6:8]}/{target[4:6]}/{target[0:4]}"
    games = matches_on(target)
    atk, dfn, c, g, rho = pm.fit_model()
    sq = pm.apply_adjustments(atk, dfn)
    def bajas(t): return [n for n,w,av in sq.get(t,{}).get("key_players",[]) if not av]

    # cuotas 1X2 del mercado (de-vigueadas) por partido, para detectar VALUE (1 sola llamada)
    mkt = {}
    try:
        import fetch_odds
        for ev in fetch_odds.h2h():
            probs_es = {EN2ES.get(k, k): v for k, v in ev["clean_probs"].items()}
            teams = [t for t in probs_es if t != "Draw"]
            if len(teams) == 2:
                mkt[frozenset(teams)] = probs_es
    except Exception as e:
        print(f"(sin cuotas de partido para value: {e})")

    VAL_MARGIN = 1.20   # el modelo debe superar al mercado por 20%+ para marcar value
    VAL_FLOOR = 0.20    # y la prob del modelo debe ser >= 20% (evita longshots ruidosos)

    # --- calcular todo (probabilidades + candidatos a "valor") ---
    data = []
    for m in sorted(games, key=lambda x: x["utc"]):
        a, b = m["a"], m["b"]
        if a not in pm.MAP or b not in pm.MAP:
            data.append({"m": m, "a": a, "b": b, "skip": True}); continue
        pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=True)
        mp = mkt.get(frozenset((a, b))); vcands = []
        if mp:
            ma, mb = mp.get(a), mp.get(b)
            if ma and pw >= VAL_FLOOR and pw > ma * VAL_MARGIN: vcands.append((a, pw, ma, pw/ma))
            if mb and pl >= VAL_FLOOR and pl > mb * VAL_MARGIN: vcands.append((b, pl, mb, pl/mb))
        data.append({"m": m, "a": a, "b": b, "pw": pw, "pdr": pdr, "pl": pl, "sx": sx, "sy": sy,
                     "vcands": vcands, "ba": bajas(a), "bb": bajas(b)})
    played = [d for d in data if not d.get("skip")]
    allv = [(d, v) for d in played for v in d["vcands"]]
    pick = max(allv, key=lambda x: x[1][3]) if allv else None
    def fav(d): return (d["a"], d["pw"]) if d["pw"] >= d["pl"] else (d["b"], d["pl"])
    clearest = max(played, key=lambda d: max(d["pw"], d["pl"]), default=None)
    evenest  = min(played, key=lambda d: max(d["pw"], d["pl"]), default=None)
    top = champion_top()
    try:
        tr = json.load(open("track_record.json", encoding="utf-8"))
    except Exception:
        tr = {"n": 0}

    # Claude redacta lo viral (título, gancho, jugada); los datos siguen exactos
    adig = ai_digest(_digest_summary(fecha_h, data, pick, top, tr)) if games else {}
    titulo_sug = (adig.get("titulo") or "").strip()

    # ====== ARMADO DEL EMAIL (estilo newsletter) ======
    md = [f"# ⚽ {BRAND} · Mundial 2026", f"#### Tu pronóstico del {fecha_h} · horas del Este (ET)\n"]

    if not games:
        import curio
        cu = curio.ensure(target)
        titulo_sug = cu.get("titulo") or titulo_sug
        if cu.get("gancho"):
            md.append(cu["gancho"].strip()); md.append("")
        cd = f"Faltan **{cu['days']} días** para el inicio (11 de junio)." if cu.get("days", 0) > 0 else "Hoy es **día de descanso** del torneo."
        md.append(f"📅 Hoy **no hay partidos** del Mundial. {cd}")
        if cu.get("is_news") and cu.get("link"):
            md.append(f"📰 **Dato del día:** {cu.get('card','')} — fuente: [{cu.get('source','')}]({cu['link']}).")
        elif cu.get("card"):
            md.append(f"🤖 **Dato del día (mi modelo):** {cu['card']}")
        md.append("")
    else:
        # --- gancho viral de apertura (Claude) ---
        if adig.get("intro"):
            md.append(adig["intro"].strip()); md.append("")
        # --- TL;DR de 10 segundos ---
        md.append("👋 Esto es lo que dice el modelo para hoy, en **10 segundos**:")
        md.append(f"- 📅 **{len(played) or len(games)} partido(s)** en juego")
        if pick:
            dp, (pteam, *_ ) = pick
            md.append(f"- 💎 **La jugada del día:** {pteam} (el mercado la está subestimando)")
        if clearest:
            ft, fp = fav(clearest)
            md.append(f"- 🔥 **El resultado más claro:** {ft} ({fp:.0%}) en {clearest['a']} vs {clearest['b']}")
        if evenest and evenest is not clearest:
            md.append(f"- ⚖️ **El más impredecible:** {evenest['a']} vs {evenest['b']}")
        md.append("")

        # --- jugada del día (explicada en simple) ---
        if pick:
            d, (team, mpb, mkp, edge) = pick
            rival = d["b"] if team == d["a"] else d["a"]
            md.append("## 💎 La jugada del día")
            if adig.get("jugada"):
                md.append(adig["jugada"].strip())
            else:
                md.append(f"**{team}** (vs {rival} · {d['m']['label']} · {hora_et(d['m']['utc'])}). "
                          f"Nuestro modelo le da **{mpb:.0%}** de ganar, pero las casas la pagan como si tuviera solo "
                          f"**{mkp:.0%}**. Traducción: está **infravalorada**. 👀")
            md.append("")

        # --- partidos del día (una línea humana cada uno) ---
        md.append("## ⚽ Los partidos de hoy")
        md.append("_El % es la probabilidad de ganar según el modelo. 🎯 = marcador más probable._\n")
        for d in data:
            m = d["m"]; hora = hora_et(m["utc"])
            if d.get("skip"):
                md.append(f"- ⏳ **{hora} · {m['label']}** — {d['a']} vs {d['b']} _(rivales por definir)_"); continue
            a, b = d["a"], d["b"]; pdr = d["pdr"]
            ft, fp = fav(d)
            if fp >= 0.62:   tag, frase = "🔥", f"**{ft}** gran favorito (**{fp:.0%}**)"
            elif fp >= 0.45: tag, frase = "🟢", f"favorita **{ft}** (**{fp:.0%}**)"
            else:            tag, frase = "⚖️", f"muy parejo — leve ventaja **{ft}** (**{fp:.0%}**)"
            val = f" · 💎 **valor en {d['vcands'][0][0]}**" if d["vcands"] else ""
            inj = " · ⚠️ con bajas" if (d["ba"] or d["bb"]) else ""
            md.append(f"- {tag} **{hora} · {a} vs {b}** — {frase} · empate {pdr:.0%} · 🎯 {d['sx']}-{d['sy']}{val}{inj}")
        md.append("")

    # --- campeón (storytelling) ---
    if top:
        medals = ["🥇", "🥈", "🥉"]
        parts = [f"{medals[i] if i < 3 else '•'} {t} {v:.1f}%" for i, (t, v) in enumerate(top)]
        md.append("## 🏆 ¿Quién va ganando el Mundial?")
        md.append("Probabilidad de salir campeón (20.000 simulaciones de hoy):")
        md.append("- " + "  ".join(parts))
        md.append("")

    # --- historial (transparencia, en simple) ---
    if tr.get("n", 0) > 0:
        md.append("## 📈 ¿Le venimos atinando?")
        md.append(f"De los últimos **{tr['n']} partidos**, acertamos quién ganó en **{tr['aciertos_1x2']} "
                  f"(≈{tr['tasa_1x2']:.0f}%)**. Te mostramos los aciertos **y** los fallos — transparencia total. "
                  f"_(Calibración Brier {tr['brier']}; más bajo = mejor.)_")
        md.append("")

    # --- cierre / CTA ---
    md.append("---")
    md.append(f"🎬 Mira el **video del análisis de hoy** en mi **canal de YouTube @{BRAND}**  ·  🙌 Compártelo con un amigo futbolero.")
    md.append("📩 Cada semana mando un resumen por correo — suscríbete para no perdértelo.")
    md.append(f"_{DISCLAIMER}_")
    text = "\n".join(md)

    import re
    def b(s): return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s).replace("_", "")
    html_lines = []
    for ln in md:
        if ln.startswith("#### "): html_lines.append(f"<p style='color:#5566aa;margin:0 0 10px;font-size:14px'>{b(ln[5:])}</p>")
        elif ln.startswith("### "): html_lines.append(f"<h3 style='margin:14px 0 2px'>{b(ln[4:])}</h3>")
        elif ln.startswith("## "): html_lines.append(f"<h2 style='color:#1f3b8b;margin:18px 0 6px'>{b(ln[3:])}</h2>")
        elif ln.startswith("# "): html_lines.append(f"<h1 style='margin:0'>{b(ln[2:])}</h1>")
        elif ln.startswith("- "): html_lines.append(f"<p style='margin:4px 0;line-height:1.45'>{b(ln[2:])}</p>")
        elif ln.strip() == "---": html_lines.append("<hr style='border:none;border-top:1px solid #d9deec;margin:14px 0'>")
        elif ln.strip(): html_lines.append(f"<p style='margin:4px 0'>{b(ln)}</p>")
    html = ("<div style='font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;"
            "color:#0b1437;padding:8px 14px'>" + "".join(html_lines) + "</div>")
    return text, html, len(games), titulo_sug

def send_email(subject, html):
    key = os.environ.get("RESEND_API_KEY", "").strip()
    frm = os.environ.get("DIGEST_FROM", "").strip()
    to = [x.strip() for x in os.environ.get("DIGEST_TO", "").split(",") if x.strip()]
    if not (key and frm and to):
        print("(envío omitido: faltan RESEND_API_KEY / DIGEST_FROM / DIGEST_TO)"); return False
    r = requests.post("https://api.resend.com/emails",
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"from": frm, "to": to, "subject": subject, "html": html}, timeout=30)
    ok = r.status_code in (200, 201)
    print("→ email enviado" if ok else f"(fallo email: {r.status_code} {r.text[:200]})")
    return ok

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    text, html, ngames, titulo = build_digest(target)
    open("digest.md", "w", encoding="utf-8").write(text)
    open("digest.html", "w", encoding="utf-8").write(html)
    print(text)
    if titulo:
        print(f"\n📌 Título sugerido para Substack: {titulo}")
    print(f"\n→ digest.md y digest.html guardados ({ngames} partido(s))")
    if "--send" in sys.argv:
        send_email(f"{BRAND} · Mundial 2026 — Pronóstico del {target[6:8]}/{target[4:6]}", html)
