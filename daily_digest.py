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
DISCLAIMER = ("Contenido informativo y de entretenimiento. No es consejo de apuestas ni "
              "garantía de resultados. +18. Juega con responsabilidad.")
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

def _get(url):
    try:
        return requests.get(url, headers=HEAD, timeout=20).json()
    except Exception:
        return requests.get(PROXY + urllib.parse.quote(url, safe=""), headers=HEAD, timeout=45).json()

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
        out.append({"a": a, "b": b, "utc": dt_utc, "label": label, "is_ko": is_ko})
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

    md = [f"# ⚽ {BRAND} · Mundial 2026", f"### Pronóstico del día · {fecha_h} _(horas en ET)_\n"]
    if not games:
        md.append("_Hoy no hay partidos del Mundial._ El torneo arranca el **11 de junio**.\n")
    else:
        # --- 1ª pasada: calcular todo y juntar candidatos a value (solo 1 y 2, no empate) ---
        data = []
        for m in sorted(games, key=lambda x: x["utc"]):
            a, b = m["a"], m["b"]
            if a not in pm.MAP or b not in pm.MAP:
                data.append({"m": m, "a": a, "b": b, "skip": True}); continue
            pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=True)
            mp = mkt.get(frozenset((a, b)))
            ma = mx = mb = None; vcands = []
            if mp:
                ma, mx, mb = mp.get(a), mp.get("Draw"), mp.get(b)
                if ma and pw >= VAL_FLOOR and pw > ma * VAL_MARGIN: vcands.append((a, pw, ma, pw/ma))
                if mb and pl >= VAL_FLOOR and pl > mb * VAL_MARGIN: vcands.append((b, pl, mb, pl/mb))
            data.append({"m": m, "a": a, "b": b, "pw": pw, "pdr": pdr, "pl": pl, "lh": lh, "la": la,
                         "sx": sx, "sy": sy, "ma": ma, "mx": mx, "mb": mb, "vcands": vcands,
                         "ba": bajas(a), "bb": bajas(b)})
        # --- Pick del día: el value de mayor "edge" (modelo/mercado) de toda la jornada ---
        allv = [(d, v) for d in data if not d.get("skip") for v in d["vcands"]]
        pick = max(allv, key=lambda x: x[1][3]) if allv else None
        md.append(f"**{len(games)} partidos hoy.**\n")
        if pick:
            d, (team, mpb, mkp, edge) = pick
            rival = d["b"] if team == d["a"] else d["a"]
            md.append("## 💎 PICK DEL DÍA")
            md.append(f"**{team}** vs {rival} ({d['m']['label']}, {hora_et(d['m']['utc'])}) — "
                      f"el modelo le da **{100*mpb:.0f}%** y el mercado solo **{100*mkp:.0f}%** "
                      f"(_edge +{(edge-1)*100:.0f}%_).")
            md.append("")
        md.append("Probabilidades del modelo (Dixon-Coles + 20.000 simulaciones):\n")
        # --- 2ª pasada: renderizar cada partido (título: partido · horario · grupo/ronda) ---
        for d in data:
            m = d["m"]; hora = hora_et(m["utc"])
            if d.get("skip"):
                md.append(f"### {m['label']} · {hora}")
                md.append(f"_{d['a']} vs {d['b']} — equipos por definir_\n"); continue
            a, b = d["a"], d["b"]
            md.append(f"### {a} vs {b} · {hora} · {m['label']}")
            md.append(f"- **1** {a}: **{100*d['pw']:.0f}%** · **X** Empate: **{100*d['pdr']:.0f}%** · **2** {b}: **{100*d['pl']:.0f}%**")
            md.append(f"- Goles esperados: {a} {d['lh']:.2f} – {d['la']:.2f} {b} · Marcador más probable: **{d['sx']}-{d['sy']}**")
            if d["ma"] is not None:
                linea = f"- 💰 Mercado: 1 {100*d['ma']:.0f}% · X {100*d['mx']:.0f}% · 2 {100*d['mb']:.0f}%"
                if d["vcands"]: linea += f"  → 💎 **VALUE** en {', '.join(v[0] for v in d['vcands'])}"
                md.append(linea)
            md.append(f"- 📝 {descripcion(a,b,d['pw'],d['pdr'],d['pl'],d['lh'],d['la'],m['is_ko'],d['ba'],d['bb'],m['label'])}")
            if d["ba"]: md.append(f"- ⚠️ Bajas {a}: {', '.join(d['ba'])}")
            if d["bb"]: md.append(f"- ⚠️ Bajas {b}: {', '.join(d['bb'])}")
            md.append("")
    top = champion_top()
    if top:
        md.append("## 🏆 Carrera por el título (hoy)")
        for t, v in top: md.append(f"- {t}: **{v:.1f}%**")
        md.append("")
    # historial de aciertos (transparencia) — lo genera track_record.py
    try:
        tr = json.load(open("track_record.json", encoding="utf-8"))
        if tr.get("n", 0) > 0:
            md.append("## 📈 Historial del modelo")
            md.append(f"- Aciertos 1X2: **{tr['aciertos_1x2']}/{tr['n']} ({tr['tasa_1x2']}%)** · "
                      f"marcador exacto {tr['tasa_exacta']}% · Brier {tr['brier']} _(más bajo = mejor)_")
            md.append("")
    except Exception:
        pass
    md.append(f"---\n**{BRAND}** · Mundial de fútbol 2026\n")
    md.append(f"_{DISCLAIMER}_")
    text = "\n".join(md)

    html_lines = []
    for ln in md:
        if ln.startswith("### "): html_lines.append(f"<h3 style='margin:14px 0 2px'>{ln[4:]}</h3>")
        elif ln.startswith("## "): html_lines.append(f"<h2>{ln[3:]}</h2>")
        elif ln.startswith("# "): html_lines.append(f"<h1>{ln[2:]}</h1>")
        elif ln.startswith("- "): html_lines.append(f"<p style='margin:2px 0'>{ln[2:]}</p>")
        elif ln.strip() == "---": html_lines.append("<hr>")
        elif ln.strip(): html_lines.append(f"<p>{ln}</p>")
    html = ("<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#0b1437'>"
            + "".join(html_lines).replace("**","") + "</div>")
    return text, html, len(games)

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
    text, html, ngames = build_digest(target)
    open("digest.md", "w", encoding="utf-8").write(text)
    open("digest.html", "w", encoding="utf-8").write(html)
    print(text)
    print(f"\n→ digest.md y digest.html guardados ({ngames} partido(s))")
    if "--send" in sys.argv:
        send_email(f"{BRAND} · Mundial 2026 — Pronóstico del {target[6:8]}/{target[4:6]}", html)
