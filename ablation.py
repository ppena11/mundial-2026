"""
ablation.py — AUDITORÍA empírica: confirma que el pronóstico diario usa CADA herramienta y mide,
una por una, cuánto la mueve. Corre el sim de producción REAL (sim_live.py) apagando cada capa vía
variables de entorno y compara el pronóstico resultante con el modelo completo.

Condiciona a los resultados REALES ya jugados (estado actual del pronóstico). Reporta, por capa, la
distancia de variación total (TVD, en puntos %) sobre la distribución de CAMPEÓN y de FINALISTA, y
el mayor desplazamiento de un equipo. Una capa "se está usando para modificar el pronóstico" si su
TVD > 0. Al final valida el MERCADO (make_ensemble) y confirma qué archivo consume el contenido.

Uso:  python ablation.py [K]      (K = simulaciones por corrida, def. 8000)
"""
import json, os, subprocess, sys, urllib.request
import schedule_2026 as sch

K = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else "8000"
PY = sys.executable
CHAMP = "champ_today.json"; ENS = "champ_ensemble.json"; MOCK = "wc_results_mock.json"

# Cada herramienta con la variable que la APAGA (lo demás queda en producción)
TOOLS = [
    ("Lesiones / disponibilidad",        {"SL_INJ": "0"}),
    ("Ventaja de anfitrión",             {"SL_HOST": "0"}),
    ("Altura",                           {"CF_ALT": "0"}),
    ("Calor (WBGT)",                     {"CF_HEAT": "0"}),
    ("Viaje / jet lag",                  {"CF_TRAVEL": "0"}),
    ("Sobredispersión (binomial neg.)",  {"CF_DISP": "none"}),
    ("Nivel de goles mundialista",       {"CF_GOAL": "1.0"}),
    ("Bracket oficial + desempates FIFA", {"SL_BRACKET": "0"}),
    ("Forma del Mundial (en torneo)",    {"CF_FORM": "0"}),
]


def build_mock():
    """Condiciona a los partidos de grupo REALES ya jugados (openfootball)."""
    data = json.load(urllib.request.urlopen(
        "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json", timeout=30))
    en2es = sch._en2es()
    mock = []
    for m in data["matches"]:
        if not str(m.get("round", "")).lower().startswith("matchday"):
            continue
        sc = m.get("score") or {}
        if not sc.get("ft"):
            continue
        mock.append([en2es.get(m["team1"], m["team1"]), en2es.get(m["team2"], m["team2"]),
                     sc["ft"][0], sc["ft"][1]])
    json.dump(mock, open(MOCK, "w", encoding="utf-8"))
    return len(mock)


def run_sim(extra_env):
    env = dict(os.environ, SL_K=K, **extra_env)
    subprocess.run([PY, "sim_live.py"], env=env, capture_output=True, text=True, timeout=600)
    d = json.load(open(CHAMP, encoding="utf-8"))
    return d["campeon"], d.get("final", {})


def tvd(a, b):
    """Distancia de variación total (puntos %) entre dos distribuciones {equipo: %}."""
    keys = set(a) | set(b)
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


def max_shift(a, b):
    keys = set(a) | set(b)
    t = max(keys, key=lambda k: abs(a.get(k, 0.0) - b.get(k, 0.0)))
    return t, a.get(t, 0.0) - b.get(t, 0.0)


if __name__ == "__main__":
    bak = {f: f + ".ablbak" for f in (CHAMP, ENS)}
    for f, b in bak.items():
        if os.path.exists(f): os.replace(f, b)
    try:
        n = build_mock()
        print(f"Ablación condicionada a {n} partidos de grupo REALES · K={K} sims/corrida\n")
        print("Corriendo modelo COMPLETO (todas las herramientas)...")
        champ_full, final_full = run_sim({})
        top = sorted(champ_full, key=champ_full.get, reverse=True)[:5]
        print("Pronóstico completo (campeón):  " + ", ".join(f"{t} {champ_full[t]:.1f}%" for t in top))
        # piso de ruido Monte Carlo: mismo modelo COMPLETO con otro seed (referencia honesta)
        champ_seed2, final_seed2 = run_sim({"SL_SEED": "22"})
        noise = tvd(champ_full, champ_seed2)
        print(f"Piso de ruido MC (modelo completo, otro seed): {noise:.1f}pp campeón "
              f"→ efectos por debajo de esto son ruido, por encima son reales.")
        print(f"\n{'Herramienta':<36}{'Δ campeón (TVD)':>16}{'Δ final (TVD)':>15}{'mayor mov.':>22}")
        print("-" * 89)
        rows = []
        for name, env in TOOLS:
            champ_off, final_off = run_sim(env)
            tc = tvd(champ_full, champ_off); tf = tvd(final_full, final_off)
            mt, md = max_shift(champ_full, champ_off)
            rows.append((name, tc, tf, mt, md))
            print(f"{name:<36}{tc:>14.1f}pp{tf:>13.1f}pp   {mt} {md:+.1f}pp")
        # MERCADO: ensemble sobre el modelo completo
        print("\nCorriendo make_ensemble (combina modelo COMPLETO + MERCADO)...")
        r = subprocess.run([PY, "make_ensemble.py"], capture_output=True, text=True, timeout=120)
        market_tvd = None
        if os.path.exists(ENS):
            ens = json.load(open(ENS, encoding="utf-8"))
            market_tvd = tvd(champ_full, ens["ensemble"])
            etop = sorted(ens["ensemble"], key=ens["ensemble"].get, reverse=True)[:5]
            print(f"{'Mercado (ensemble modelo+cuotas)':<36}{market_tvd:>14.1f}pp{'—':>15}")
            print("Ensemble (lo que ve el contenido):  " + ", ".join(f"{t} {ens['ensemble'][t]:.1f}%" for t in etop))
        # veredicto
        print(f"\nVEREDICTO (una por una; piso de ruido MC = {noise:.1f}pp):")
        for name, tc, tf, mt, md in rows:
            real = tc > noise
            usa = "SÍ modifica el pronóstico (efecto > ruido)" if real else "efecto dentro del ruido MC"
            print(f"  {'✓' if real else '~'} {name:<36} {usa} (campeón TVD {tc:.1f}pp)")
        if market_tvd is not None:
            print(f"  ✓ {'Mercado (lo ve el contenido)':<36} SÍ modifica el pronóstico (TVD {market_tvd:.1f}pp)")
    finally:
        for f in (MOCK,):
            if os.path.exists(f): os.remove(f)
        for f, b in bak.items():
            if os.path.exists(b): os.replace(b, f)
        print("\n(estado restaurado: champ_today.json y champ_ensemble.json originales)")
