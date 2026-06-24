"""
validate_layers.py — valida cada capa de contexto contra el modelo BASE por RPS fuera de muestra.

DISCIPLINA (del diseño): cada capa debe MEJORAR el RPS out-of-sample. Si no mejora, se apaga.

La ALTURA es la única capa con un laboratorio natural en los datos históricos: las eliminatorias
CONMEBOL en La Paz (~3600 m), Quito (~2850 m) y Bogotá (~2640 m). results.csv trae columnas
`city`/`country`, así que se puede medir el efecto de verdad.

Uso:
  python validate_layers.py                  # valida altura (train<corte, test>=corte)
  python validate_layers.py --cut 2024-01-01

Necesita altitude_validation.json = {"cities": {ciudad: elev_m}, "team_base": {pais_o_equipo: elev_m}}.
(Se genera con datos verificados; si falta, el script lo dice y no inventa.)

Funciones puras reutilizables (probs_from_lambdas, rps_delta) con pruebas en test_validate_layers.py.
"""
import csv, json, math, os, sys, unicodedata
from datetime import date

import fit_dc
import context_factors as cf

_HERE = os.path.dirname(os.path.abspath(__file__))
ALT_MAP_FILE = os.path.join(_HERE, "altitude_validation.json")


# ============================================================
# Probabilidades 1X2 a partir de λ (con Dixon-Coles)
# ============================================================
def probs_from_lambdas(lh, la, rho, K=11):
    """1X2 (pw, pd, pl) a partir de goles esperados λ con corrección Dixon-Coles."""
    ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(K)]
    pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(K)]
    pw = pd = pl = 0.0
    for x in range(K):
        for y in range(K):
            p = ph[x] * pa[y]
            if x <= 1 and y <= 1:
                if   x == 0 and y == 0: p *= (1 - lh * la * rho)
                elif x == 0 and y == 1: p *= (1 + lh * rho)
                elif x == 1 and y == 0: p *= (1 + la * rho)
                else:                   p *= (1 - rho)
            if p < 0: p = 0.0
            if x > y: pw += p
            elif x == y: pd += p
            else: pl += p
    s = pw + pd + pl or 1.0
    return pw / s, pd / s, pl / s

# rps reutiliza la implementación canónica del modelo
rps = fit_dc.rps

def rps_delta(probs_base, probs_adj, outcome):
    """RPS_base - RPS_adj. Positivo = la capa ajustada MEJORA (RPS más bajo es mejor)."""
    return rps(probs_base, outcome) - rps(probs_adj, outcome)


# ============================================================
# Datos de validación (verificados; no se inventan)
# ============================================================
def load_alt_map(path=ALT_MAP_FILE):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return d.get("cities", {}), d.get("team_base", {})
    except FileNotFoundError:
        return None, None

def _norm(s):
    """Normaliza ciudad: sin acentos, minúsculas (para casar con la tabla de elevaciones)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).strip().lower()


# ============================================================
# Validación de ALTURA
# ============================================================
def validate_altitude(cut="2024-06-01", window_start="2010-01-01", end="2026-06-01",
                      threshold=cf.ALT_THRESHOLD):
    """Compara RPS base vs RPS con f_alt en partidos fuera de muestra.

    Devuelve un dict con métricas globales y, sobre todo, en el SUBCONJUNTO de altura
    (sede > umbral), que es donde la capa puede mover algo.
    """
    cities, team_base = load_alt_map()
    if cities is None:
        return {"error": f"falta {ALT_MAP_FILE} (datos verificados de ciudades/bases). No se inventa."}

    rows = fit_dc.load(window_start, end)              # (date, home, away, gh, ga, neutral)
    train = [r for r in rows if r[0] < cut]
    test = [r for r in rows if r[0] >= cut]
    if not test:
        return {"error": "no hay partidos de prueba en el rango"}

    M = fit_dc.fit(fit_dc.build(train, cut), separate=True)
    ti = {t: i for i, t in enumerate(M["teams"])}
    OTH = M["OTH"]; rho = M["rho"]; c = M["c"]; g = M["g"]
    atk, dfn = M["atk"], M["dfn"]

    def base_elev(team):
        # base de aclimatación: del mapa verificado; si no está, nivel del mar (0)
        return team_base.get(team, 0.0)

    # necesito el mapa fila->city del dataset crudo (fit_dc.load no trae city); recargo con city
    raw = []
    for r in csv.DictReader(open(os.path.join(_HERE, "results.csv"), encoding="utf-8")):
        if r["home_score"] in ("NA", ""): continue
        if not (window_start <= r["date"] <= end): continue
        raw.append(r)
    city_by_key = {}
    for r in raw:
        city_by_key[(r["date"], r["home_team"], r["away_team"])] = r["city"]

    base_all = []; adj_all = []
    base_alt = []; adj_alt = []; n_alt = 0
    for d, h, a, gh, ga, neu in test:
        city = _norm(city_by_key.get((d, h, a)))
        elev = cities.get(city, 0.0)
        hi = ti.get(h, OTH); ai = ti.get(a, OTH)
        lh = math.exp(c + atk[hi] - dfn[ai] + g * (0 if neu else 1))
        la = math.exp(c + atk[ai] - dfn[hi])
        pb = probs_from_lambdas(lh, la, rho)
        # ajuste de altura
        mh, ma = cf.f_altitude_pair(elev, base_elev(h), base_elev(a))
        pa = probs_from_lambdas(lh * mh, la * ma, rho)
        outcome = 0 if gh > ga else (1 if gh == ga else 2)
        base_all.append(rps(pb, outcome)); adj_all.append(rps(pa, outcome))
        if elev > threshold:
            n_alt += 1
            base_alt.append(rps(pb, outcome)); adj_alt.append(rps(pa, outcome))

    def mean(xs): return sum(xs) / len(xs) if xs else float("nan")
    res = {
        "n_test": len(test), "n_altitude": n_alt, "cut": cut,
        "rps_base_all": mean(base_all), "rps_adj_all": mean(adj_all),
        "rps_base_altitude": mean(base_alt), "rps_adj_altitude": mean(adj_alt),
        "improves_all": mean(adj_all) < mean(base_all),
        "improves_altitude": (mean(adj_alt) < mean(base_alt)) if base_alt else None,
    }
    return res


# ============================================================
# Validación de SOBREDISPERSIÓN (binomial negativa vs Poisson)
# ============================================================
def validate_dispersion(cut="2024-06-01", window_start="2010-01-01", end="2026-06-01"):
    """Ajusta el modelo en train y mide, fuera de muestra, si los goles están sobredispersos.

    Devuelve {r_best, loglik_nb, loglik_pois, mejora, recomendacion}. Si NB mejora la
    log-verosimilitud de los goles, conviene activar context_factors.DISPERSION_R = r_best.
    """
    import format_engine as fe
    rows = fit_dc.load(window_start, end)
    train = [r for r in rows if r[0] < cut]
    test = [r for r in rows if r[0] >= cut]
    if not test:
        return {"error": "sin partidos de prueba"}
    M = fit_dc.fit(fit_dc.build(train, cut), separate=True)
    ti = {t: i for i, t in enumerate(M["teams"])}
    OTH = M["OTH"]; c = M["c"]; g = M["g"]
    lams = []; goals = []
    for d, h, a, gh, ga, neu in test:
        hi = ti.get(h, OTH); ai = ti.get(a, OTH)
        lams.append(math.exp(c + M["atk"][hi] - M["dfn"][ai] + g * (0 if neu else 1))); goals.append(gh)
        lams.append(math.exp(c + M["atk"][ai] - M["dfn"][hi])); goals.append(ga)
    r_best, ll_nb, ll_pois = fe.fit_dispersion(lams, goals)
    return {"r_best": r_best, "loglik_nb": ll_nb, "loglik_pois": ll_pois,
            "mejora": ll_nb > ll_pois + 2,
            "recomendacion": (f"DISPERSION_R = {r_best}" if ll_nb > ll_pois + 2 else "DISPERSION_R = None (Poisson)")}


if __name__ == "__main__":
    cut = "2024-06-01"
    if "--cut" in sys.argv:
        cut = sys.argv[sys.argv.index("--cut") + 1]
    print("=== SOBREDISPERSIÓN (binomial negativa vs Poisson) ===")
    rd = validate_dispersion(cut=cut)
    if "error" not in rd:
        print(f"r óptimo={rd['r_best']}  logLik NB={rd['loglik_nb']:.1f}  Poisson={rd['loglik_pois']:.1f}  "
              f"→ {rd['recomendacion']}")
    r = validate_altitude(cut=cut)
    if "error" in r:
        print("No se pudo validar:", r["error"]); sys.exit(0)
    print(f"\n=== VALIDACIÓN ALTURA (corte {r['cut']}) ===")
    print(f"Partidos de prueba: {r['n_test']}  |  en sedes de altura (>{int(cf.ALT_THRESHOLD)} m): {r['n_altitude']}")
    print(f"RPS global   base={r['rps_base_all']:.5f}  con altura={r['rps_adj_all']:.5f}  "
          f"({'MEJORA' if r['improves_all'] else 'no mejora'})")
    if r["improves_altitude"] is not None:
        d = r["rps_base_altitude"] - r["rps_adj_altitude"]
        print(f"RPS ALTURA   base={r['rps_base_altitude']:.5f}  con altura={r['rps_adj_altitude']:.5f}  "
              f"(Δ={d:+.5f}, {'MEJORA' if r['improves_altitude'] else 'NO mejora → apagar'})")
    else:
        print("RPS ALTURA   (sin partidos de altura en el rango de prueba)")
