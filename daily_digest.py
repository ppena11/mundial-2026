"""
daily_digest.py — arma el DIGEST DIARIO premium (producto de pago) y, opcionalmente,
lo envía por email. Reutiliza el modelo y los datos que ya genera el pipeline.

QUÉ INCLUYE:
  - Todos los partidos del día: 1X2 (modelo), goles esperados, marcador más probable, bajas.
  - Seguimiento del campeón (de champ_today.json, modelo consciente del torneo).
  - Disclaimer legal fijo (análisis/entretenimiento, +18).

SALIDA: digest.md + digest.html (listos para pegar en Beehiiv/Substack o enviar por email).

ENVÍO POR EMAIL (opcional, automático):
  Define en variables de entorno (o .env / GitHub Secrets):
    RESEND_API_KEY, DIGEST_FROM ("Nombre <correo@dominio>"), DIGEST_TO ("a@x.com,b@y.com")
  Si no están, solo guarda los archivos.

USO:
  python daily_digest.py                 # partidos de HOY
  python daily_digest.py --date 20260611 # una fecha concreta (para probar)
  python daily_digest.py --send          # además, intenta enviar por email
"""
import sys, os, json, urllib.parse
from datetime import date, datetime
try:
    import requests
except ImportError:
    requests = None
try:
    from env_loader import load_env; load_env()
except Exception:
    pass
import predict_match as pm   # reutiliza fit_model, apply_adjustments, one_x_two, MAP, HOSTS

BRAND = "aiwithpedro"
DISCLAIMER = ("Contenido informativo y de entretenimiento. No es consejo de apuestas ni "
              "garantía de resultados. +18. Juega con responsabilidad.")

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PROXY = "https://api.codetabs.com/v1/proxy/?quest="
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
EN2ES = {en: es for es, en in pm.MAP.items()}
EN2ES.update({"Czechia":"Chequia","Czech Republic":"Chequia","USA":"Estados Unidos",
              "United States":"Estados Unidos","South Korea":"Corea del Sur","IR Iran":"Iran",
              "Türkiye":"Turquia","Bosnia & Herzegovina":"Bosnia","Bosnia-Herzegovina":"Bosnia",
              "Bosnia and Herzegovina":"Bosnia","Côte d'Ivoire":"Costa de Marfil","Cabo Verde":"Cabo Verde"})

def _get(url):
    try:
        return requests.get(url, headers=HEAD, timeout=20).json()
    except Exception:
        return requests.get(PROXY + urllib.parse.quote(url, safe=""), headers=HEAD, timeout=45).json()

def matches_on(yyyymmdd):
    """Partidos del Mundial en esa fecha: [(local_es, visitante_es, hora_utc)]."""
    out = []
    try:
        data = _get(f"{ESPN}/scoreboard?dates={yyyymmdd}")
    except Exception as e:
        print(f"(no pude leer el calendario: {e})"); return out
    for e in data.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        cs = comp.get("competitors", [])
        if len(cs) != 2: continue
        home = next((c for c in cs if c.get("homeAway") == "home"), cs[0])
        away = next((c for c in cs if c.get("homeAway") == "away"), cs[1])
        a = EN2ES.get(home["team"]["displayName"], home["team"]["displayName"])
        b = EN2ES.get(away["team"]["displayName"], away["team"]["displayName"])
        out.append((a, b, e.get("date", "")))
    return out

def champion_top(n=5):
    try:
        d = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
        return list(d.items())[:n]
    except Exception:
        return []

def build_digest(target):
    fecha_h = f"{target[6:8]}/{target[4:6]}/{target[0:4]}"
    games = matches_on(target)
    atk, dfn, c, g, rho = pm.fit_model()
    sq = pm.apply_adjustments(atk, dfn)
    def bajas(t): return [n for n,w,av in sq.get(t,{}).get("key_players",[]) if not av]

    md = [f"# ⚽ {BRAND} · Mundial 2026", f"### Pronóstico del día · {fecha_h}\n"]
    if not games:
        md.append("_Hoy no hay partidos del Mundial._ El torneo arranca el **11 de junio**.\n")
    else:
        md.append(f"**{len(games)} partido(s) hoy.** Probabilidades del modelo (Dixon-Coles + 20.000 simulaciones):\n")
        for a, b, dt in games:
            if a not in pm.MAP or b not in pm.MAP:
                md.append(f"### {a} vs {b}\n_(equipo fuera del modelo, omito)_\n"); continue
            pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=True)
            md.append(f"### {a} vs {b}")
            md.append(f"- **1** {a}: **{100*pw:.0f}%** · **X** Empate: **{100*pdr:.0f}%** · **2** {b}: **{100*pl:.0f}%**")
            md.append(f"- Goles esperados: {a} {lh:.2f} – {la:.2f} {b} · Marcador más probable: **{sx}-{sy}**")
            if bajas(a): md.append(f"- Bajas {a}: {', '.join(bajas(a))}")
            if bajas(b): md.append(f"- Bajas {b}: {', '.join(bajas(b))}")
            md.append("")
    top = champion_top()
    if top:
        md.append("## 🏆 Carrera por el título (hoy)")
        for t, v in top: md.append(f"- {t}: **{v:.1f}%**")
        md.append("")
    md.append(f"---\n**{BRAND}** · Mundial de fútbol 2026\n")
    md.append(f"_{DISCLAIMER}_")
    text = "\n".join(md)

    # HTML simple a partir del markdown (suficiente para email/newsletter)
    html_lines = []
    for ln in md:
        if ln.startswith("### "): html_lines.append(f"<h3>{ln[4:]}</h3>")
        elif ln.startswith("## "): html_lines.append(f"<h2>{ln[3:]}</h2>")
        elif ln.startswith("# "): html_lines.append(f"<h1>{ln[2:]}</h1>")
        elif ln.startswith("- "): html_lines.append(f"<p style='margin:2px 0'>{ln[2:]}</p>")
        elif ln.strip() == "---": html_lines.append("<hr>")
        elif ln.strip(): html_lines.append(f"<p>{ln}</p>")
    html = ("<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#0b1437'>"
            + "".join(html_lines).replace("**","") + "</div>")
    return text, html, len(games)

def send_email(subject, html):
    """Envía por Resend (HTTP) si hay credenciales; si no, avisa."""
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
    if "--date" in sys.argv:
        target = sys.argv[sys.argv.index("--date")+1]
    else:
        target = date.today().strftime("%Y%m%d")
    text, html, ngames = build_digest(target)
    open("digest.md", "w", encoding="utf-8").write(text)
    open("digest.html", "w", encoding="utf-8").write(html)
    print(text)
    print(f"\n→ digest.md y digest.html guardados ({ngames} partido(s))")
    if "--send" in sys.argv:
        send_email(f"Mundial 2026 — Pronóstico del día ({target[6:8]}/{target[4:6]})", html)
