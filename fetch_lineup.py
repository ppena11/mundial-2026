"""
fetch_lineup.py — XI confirmado GRATIS desde la API interna de ESPN (sin clave, sin pago).
Disponible ~1h antes del saque. Devuelve los 11 titulares por equipo y, además,
escribe lineups.json con las ESTRELLAS (STAR_WEIGHTS) que NO salen de titulares,
listo para que player_layer / predict_match lo usen.

USO:
  python fetch_lineup.py --list                      # próximos partidos del Mundial con su ID de ESPN
  python fetch_lineup.py --event 760415              # XI de ese partido (por ID)
  python fetch_lineup.py "Mexico" "Sudafrica"        # busca el partido por equipos y trae el XI
  python fetch_lineup.py --event 760415 --no-write   # solo muestra, no toca lineups.json

NOTA: si el XI aún no está publicado (faltan >1-2h), ESPN devuelve 0 titulares y se avisa.
"""
import sys, json
try:
    import requests
except ImportError:
    print("Falta requests:  pip install requests"); sys.exit(1)

LEAGUE = "fifa.world"
BASE = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}"
HEAD = {"User-Agent": "Mozilla/5.0"}

# ESPN (inglés) -> español del modelo. Partimos de namemap y añadimos alias de ESPN.
def _en2es():
    nm = json.load(open("namemap.json", encoding="utf-8"))
    m = {en: es for es, en in nm.items()}
    m.update({"Czechia":"Chequia", "Czech Republic":"Chequia", "USA":"Estados Unidos",
              "United States":"Estados Unidos", "Korea Republic":"Corea del Sur",
              "South Korea":"Corea del Sur", "IR Iran":"Iran", "Türkiye":"Turquia",
              "Bosnia & Herzegovina":"Bosnia", "Bosnia and Herzegovina":"Bosnia",
              "Côte d'Ivoire":"Costa de Marfil", "Cape Verde Islands":"Cabo Verde"})
    return m

def get(path, **params):
    return requests.get(f"{BASE}/{path}", headers=HEAD, params=params, timeout=25).json()

def fixtures(dates=None):
    """Próximos partidos del Mundial con su ID de ESPN."""
    d = get("scoreboard", **({"dates": dates} if dates else {}))
    out = []
    for e in d.get("events", []):
        out.append((e.get("id"), e.get("date"), e.get("name")))
    return out

def lineup(event_id):
    """Devuelve {equipo_es: {'xi':[...], 'bench':[...]}} si el XI está publicado."""
    d = get("summary", event=event_id)
    en2es = _en2es()
    res = {}
    for r in d.get("rosters", []):
        team_en = r.get("team", {}).get("displayName", "")
        team_es = en2es.get(team_en, team_en)
        xi, bench = [], []
        for p in r.get("roster", []):
            name = p.get("athlete", {}).get("displayName", "")
            (xi if p.get("starter") else bench).append(name)
        res[team_es] = {"xi": xi, "bench": bench}
    return res

def stars_not_starting(lineups_dict):
    """Por equipo, estrellas (STAR_WEIGHTS) que están en el banquillo (no titulares)."""
    try:
        from player_layer import STAR_WEIGHTS
    except Exception:
        STAR_WEIGHTS = {}
    out = {}
    for team, d in lineups_dict.items():
        squad = set(d["xi"]) | set(d["bench"])
        benched_stars = [n for n in d["bench"] if n in STAR_WEIGHTS]
        if benched_stars:
            out[team] = benched_stars
    return out

if __name__ == "__main__":
    if "--list" in sys.argv:
        for fid, date, name in fixtures():
            print(f"{fid}  {date}  {name}")
        sys.exit(0)

    # resolver el evento: por --event o por nombres de equipo
    event_id = None
    if "--event" in sys.argv:
        event_id = sys.argv[sys.argv.index("--event")+1]
    else:
        teams = [a for a in sys.argv[1:] if not a.startswith("--")]
        if len(teams) >= 2:
            want = {teams[0].lower(), teams[1].lower()}
            en2es = _en2es()
            for fid, date, name in fixtures():
                # name viene en inglés ("South Africa at Mexico"); traducimos a español
                parts = [en2es.get(x.strip(), x.strip()).lower()
                         for x in name.replace(" at ", " vs ").split(" vs ")]
                if want.issubset(set(parts)) or want.issubset({p for p in parts}):
                    event_id = fid; break
    if not event_id:
        print("No encontré el partido. Usa --list para ver IDs, o pásalo con --event <id>."); sys.exit(1)

    lu = lineup(event_id)
    total = sum(len(d["xi"]) for d in lu.values())
    if total == 0:
        print(f"⚠️  El XI del evento {event_id} aún no está publicado (ESPN lo pone ~1h antes). Reintenta más cerca del saque.")
        sys.exit(0)

    for team, d in lu.items():
        print(f"\n=== {team} (XI confirmado) ===")
        for n in d["xi"]:
            print(f"   {n}")

    benched = stars_not_starting(lu)
    if "--no-write" not in sys.argv:
        out = {"_fuente": f"ESPN evento {event_id} (XI confirmado)", **benched}
        json.dump(out, open("lineups.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n→ lineups.json actualizado. Estrellas en el banquillo: "
              f"{benched if benched else 'ninguna (XI de gala)'}")
        print("   Ahora corre:  python predict_match.py \"Local\" \"Visitante\"")
