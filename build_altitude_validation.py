"""
build_altitude_validation.py — arma altitude_validation.json para validar la capa de altura.

NO inventa:
  * cities    = elevaciones VERIFICADAS por web (altitude_cities.json), con clave normalizada
                (minúsculas, sin acentos) para casar con los nombres de results.csv.
  * team_base = base de aclimatación de cada selección DERIVADA de los datos: la elevación de su
                ciudad-sede de local MÁS FRECUENTE en results.csv (home_team==t, neutral==FALSE).
                Así Bolivia→La Paz, Ecuador→Quito, México→Ciudad de México, Colombia→Barranquilla
                (nivel del mar, ¡no Bogotá!), sin asignar nada a mano.

Uso:  python build_altitude_validation.py [altitude_cities.json]
"""
import csv, json, os, sys, unicodedata
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IN = "/private/tmp/claude-501/-Users-pedropena-mundial-2026/a93a5458-f07a-4b0d-b705-4b0cab29ef90/scratchpad/altitude_cities.json"
OUT = os.path.join(_HERE, "altitude_validation.json")


def norm_city(s):
    """Normaliza un nombre de ciudad: sin acentos, minúsculas, sin espacios extremos."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.strip().lower()


def build(in_path, window_start="2010-01-01"):
    raw = json.load(open(in_path, encoding="utf-8"))["cities"]
    cities = {}
    for c in raw:
        cities[norm_city(c["city"])] = c["elevation_m"]

    # base de cada selección = ciudad-sede de local más frecuente en la MISMA ventana que la
    # validación (la base de aclimatación moderna; ej. Colombia juega en Barranquilla, no Bogotá).
    home_cities = {}   # team -> Counter(city)
    for r in csv.DictReader(open(os.path.join(_HERE, "results.csv"), encoding="utf-8")):
        if r["home_score"] in ("NA", ""):
            continue
        if r["neutral"] == "TRUE":
            continue
        if r["date"] < window_start:
            continue
        home_cities.setdefault(r["home_team"], Counter())[norm_city(r["city"])] += 1

    team_base = {}
    for t, cnt in home_cities.items():
        modal_city, _ = cnt.most_common(1)[0]
        team_base[t] = cities.get(modal_city, 0.0)
    return {"cities": cities, "team_base": team_base,
            "_note": "cities con clave normalizada (sin acentos); team_base derivado de la sede local modal"}


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    if not os.path.exists(in_path):
        print(f"No existe {in_path}. Corre primero la investigación de ciudades."); sys.exit(1)
    d = build(in_path)
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {OUT}: {len(d['cities'])} ciudades, {len(d['team_base'])} selecciones con base derivada")
    print("\nCiudades de altura (>1500 m) verificadas:")
    for c, e in sorted(d["cities"].items(), key=lambda kv: -kv[1]):
        if e > 1500:
            print(f"   {e:>6.0f}  {c}")
    print("\nBases de altura (>1500 m) derivadas de datos:")
    for t, e in sorted(d["team_base"].items(), key=lambda kv: -kv[1]):
        if e > 1500:
            print(f"   {e:>6.0f}  {t}")
