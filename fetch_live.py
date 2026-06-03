"""
fetch_live.py — conexión a API-Football para el Mundial 2026 (league=1, season=2026).
EJECUTAR EN TU MÁQUINA con Claude Code (NO en el entorno de Claude.ai, que no tiene red abierta).

PASOS:
  1) Crea cuenta gratis en https://www.api-football.com  -> copia tu API key
  2) pip install requests
  3) export API_FOOTBALL_KEY="tu_key_aqui"   (o ponla abajo)
  4) python3 fetch_live.py --injuries        # lesiones actuales de todas las selecciones
     python3 fetch_live.py --lineup FIXTURE_ID  # XI confirmado (1h antes del partido)

Claude Code puede ejecutar, depurar y ampliar esto contigo en vivo.
"""
import os, sys, json
try:
    import requests
except ImportError:
    print("Falta 'requests'. Corre:  pip install requests"); sys.exit(1)
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

KEY = os.environ.get("API_FOOTBALL_KEY", "PEGA_TU_KEY_AQUI")
BASE = "https://v3.football.api-sports.io"
HEAD = {"x-apisports-key": KEY}
WC = {"league": 1, "season": 2026}   # FIFA World Cup 2026

def get(path, **params):
    r = requests.get(f"{BASE}/{path}", headers=HEAD, params=params, timeout=20)
    r.raise_for_status()
    body = r.json()
    errs = body.get("errors")
    if errs:  # API-Football devuelve HTTP 200 con errores dentro del cuerpo
        print(f"⚠️  API-Football: {errs}", file=sys.stderr)
    return body.get("response", [])

def injuries():
    """Lesionados/no disponibles de la competición."""
    data = get("injuries", **WC)
    out = {}
    for it in data:
        team = it["team"]["name"]; pl = it["player"]["name"]; reason = it["player"].get("reason","")
        out.setdefault(team, []).append({"player": pl, "reason": reason})
    return out

def lineup(fixture_id):
    """XI confirmado de un partido (disponible ~1h antes del saque)."""
    data = get("fixtures/lineups", fixture=fixture_id)
    res = {}
    for side in data:
        team = side["team"]["name"]
        xi = [p["player"]["name"] for p in side.get("startXI", [])]
        formation = side.get("formation","")
        res[team] = {"formation": formation, "startXI": xi}
    return res

def fixtures_today():
    """IDs de los partidos del Mundial de hoy (para pasar a lineup())."""
    return [(f["fixture"]["id"], f["teams"]["home"]["name"], f["teams"]["away"]["name"],
             f["fixture"]["date"]) for f in get("fixtures", **WC, next=20)]

# ---- FUENTE GRATIS (sin API key): calendario completo del Mundial 2026 ----
# openfootball/worldcup.json — dominio público, no requiere clave. Da fecha, hora,
# equipos, grupo y sede de los 104 partidos. NO da lesiones ni XI confirmado.
OPENFOOTBALL_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

def schedule_free():
    """Calendario del Mundial 2026 desde datos abiertos (gratis, sin clave)."""
    import urllib.request
    data = json.load(urllib.request.urlopen(OPENFOOTBALL_URL, timeout=20))
    # traducir nombres en inglés -> español del modelo usando namemap.json
    try:
        nm = json.load(open("namemap.json", encoding="utf-8"))
        en2es = {en: es for es, en in nm.items()}
        # alias de fuentes externas que escriben distinto al namemap
        en2es["Bosnia & Herzegovina"] = "Bosnia"
        en2es["United States"] = "Estados Unidos"
        en2es["USA"] = "Estados Unidos"
    except Exception:
        en2es = {}
    out = []
    for m in data.get("matches", []):
        t1 = en2es.get(m.get("team1"), m.get("team1"))
        t2 = en2es.get(m.get("team2"), m.get("team2"))
        out.append({"date": m.get("date"), "time": m.get("time"), "round": m.get("round"),
                    "group": m.get("group"), "ground": m.get("ground"), "team1": t1, "team2": t2})
    return out

if __name__ == "__main__":
    # --schedule es GRATIS (datos abiertos), no necesita API key:
    if "--schedule" in sys.argv:
        for m in schedule_free():
            print(f"{m['date']} {m['time']:<10} {m['team1']} vs {m['team2']}  ({m['group']}, {m['ground']})")
        sys.exit(0)
    # El resto necesita la API key de pago (API-Football):
    if KEY == "PEGA_TU_KEY_AQUI":
        print("⚠️  Primero pon tu API key (paso 3 del encabezado)."); sys.exit(1)
    if "--injuries" in sys.argv:
        print(json.dumps(injuries(), ensure_ascii=False, indent=2))
    elif "--lineup" in sys.argv:
        fid = sys.argv[sys.argv.index("--lineup")+1]
        print(json.dumps(lineup(fid), ensure_ascii=False, indent=2))
    elif "--today" in sys.argv:
        try:
            rows = fixtures_today()
        except Exception:
            rows = []
        if rows:
            for fid, h, a, d in rows:
                print(f"{fid}  {h} vs {a}  ({d})")
        else:
            print("(API de pago sin datos para 2026; mostrando calendario gratis abierto:)")
            for m in schedule_free():
                print(f"{m['date']} {m['time']:<10} {m['team1']} vs {m['team2']}  ({m['group']}, {m['ground']})")
    else:
        print(__doc__)
