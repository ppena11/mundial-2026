"""
build_context.py — convierte la salida de investigación verificada (wc2026_data.json) al
formato que consume context_factors.py (wc2026_context.json), y audita la cobertura.

No inventa: solo reordena datos ya verificados con fuente. Si falta una sede o equipo, lo avisa.

Uso:  python build_context.py [ruta_wc2026_data.json]
"""
import json, os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IN = "/private/tmp/claude-501/-Users-pedropena-mundial-2026/a93a5458-f07a-4b0d-b705-4b0cab29ef90/scratchpad/wc2026_data.json"
OUT_CONTEXT = os.path.join(_HERE, "wc2026_context.json")

# las 16 sedes (claves `ground` del calendario openfootball) y las 48 selecciones
GROUNDS = ["Mexico City", "Guadalajara (Zapopan)", "Monterrey (Guadalupe)", "Dallas (Arlington)",
           "Atlanta", "Los Angeles (Inglewood)", "New York/New Jersey (East Rutherford)",
           "Vancouver", "Boston (Foxborough)", "Miami (Miami Gardens)", "Houston", "Toronto",
           "San Francisco Bay Area (Santa Clara)", "Seattle", "Philadelphia", "Kansas City"]


def build(in_path):
    data = json.load(open(in_path, encoding="utf-8"))
    venues = {}
    for v in data.get("venues", []):
        venues[v["ground_key"]] = {
            "stadium": v.get("stadium"),
            "city": v.get("city"),
            "lat": v.get("lat"),
            "lon": v.get("lon"),
            "elevation_m": v.get("elevation_m"),
            "roof": v.get("roof"),
            "effective_ac_during_play": v.get("effective_ac_during_play", False),
            "summer_afternoon_heat_risk": v.get("summer_afternoon_heat_risk", "low"),
            "utc_offset": v.get("utc_offset_june"),
            "hot_humid": v.get("hot_humid_in_summer", False),
            "sources": v.get("sources", []),
        }
    teams = {}
    for t in data.get("teams", []):
        teams[t["team_es"]] = {
            "proxy_location": t.get("proxy_location"),
            "lat": t.get("lat"),
            "lon": t.get("lon"),
            "base_elevation_m": t.get("base_elevation_m"),
            "utc_offset": t.get("utc_offset"),
            "sources": t.get("sources", []),
        }
    return {"venues": venues, "teams": teams,
            "rules": data.get("rules"), "lit": data.get("lit"),
            "verification": data.get("verification")}


def audit(ctx):
    problems = []
    vk = set(ctx["venues"])
    for g in GROUNDS:
        if g not in vk:
            problems.append(f"FALTA sede: {g!r}")
        else:
            v = ctx["venues"][g]
            for f in ("elevation_m", "roof", "lat", "lon"):
                if v.get(f) is None:
                    problems.append(f"sede {g!r} sin {f}")
    extra = vk - set(GROUNDS)
    if extra:
        problems.append(f"sedes inesperadas (clave no coincide con el calendario): {sorted(extra)}")
    nm = json.load(open(os.path.join(_HERE, "namemap.json"), encoding="utf-8"))
    for t in nm:
        if t not in ctx["teams"]:
            problems.append(f"FALTA equipo: {t!r}")
        elif ctx["teams"][t].get("base_elevation_m") is None:
            problems.append(f"equipo {t!r} sin base_elevation_m")
    return problems


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    if not os.path.exists(in_path):
        print(f"No existe {in_path}. Corre primero la investigación."); sys.exit(1)
    ctx = build(in_path)
    json.dump(ctx, open(OUT_CONTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {OUT_CONTEXT} escrito: {len(ctx['venues'])} sedes, {len(ctx['teams'])} equipos")
    problems = audit(ctx)
    if problems:
        print(f"\n⚠️  AUDITORÍA: {len(problems)} problemas (revisar, no inventar):")
        for p in problems[:40]:
            print("   -", p)
    else:
        print("\n✓ AUDITORÍA: cobertura completa (16 sedes, 48 equipos, campos clave presentes)")
    # resumen de altura para ojo humano
    print("\nSedes por elevación (m):")
    for g, v in sorted(ctx["venues"].items(), key=lambda kv: -(kv[1].get("elevation_m") or 0)):
        print(f"   {v.get('elevation_m'):>6}  {g:<38} techo={v.get('roof'):<11} AC={v.get('effective_ac_during_play')} calor={v.get('summer_afternoon_heat_risk')}")
