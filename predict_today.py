"""
predict_today.py — pronóstico de la jornada de HOY con TODAS las herramientas, entrenando
ESTRICTAMENTE con lo jugado antes de hoy (held-out honesto), y comparación con los resultados.

Uso:  python predict_today.py [YYYY-MM-DD]   (def. hoy)
"""
import json, math, os, sys, urllib.request
from datetime import date, timedelta
import fit_dc, predict_match as pm, context_factors as cf, schedule_2026 as sch, wc_form

HOSTS = {"Mexico", "Estados Unidos", "Canada"}
GROUND_HOST = {"Mexico City": "Mexico", "Guadalajara (Zapopan)": "Mexico", "Monterrey (Guadalupe)": "Mexico",
               "Toronto": "Canada", "Vancouver": "Canada"}
OF = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"


def fit_through(cutoff):
    """Fit con TODAS las herramientas usando solo partidos con fecha < cutoff (sin fuga)."""
    rows = [r for r in fit_dc.load("2019-01-01", cutoff, with_tournament=True) if r[0] < cutoff]
    inv = {v: k for k, v in pm.MAP.items()}
    redcards = {}
    try:
        redcards = wc_form.load_red_cards()
    except Exception:
        pass
    wc_count = {}
    for r in rows:
        if r[0] >= "2026-06-11" and len(r) > 6 and r[6] == "FIFA World Cup":
            wc_count[r[1]] = wc_count.get(r[1], 0) + 1; wc_count[r[2]] = wc_count.get(r[2], 0) + 1
    def wfn(r):
        if r[0] >= "2026-06-11" and len(r) > 6 and r[6] == "FIFA World Cup":
            rm = redcards.get(frozenset((inv.get(r[1]), inv.get(r[2]))))
            w = wc_form.reliability(r[3], r[4], rm)
            if wc_count.get(r[1], 0) >= cf.WC_FORM_MIN and wc_count.get(r[2], 0) >= cf.WC_FORM_MIN:
                w *= cf.WC_FORM_BOOST
            return w
        return 1.0
    M = fit_dc.fit(fit_dc.build(rows, cutoff, row_weight_fn=wfn), separate=True)
    ti = {t: i for i, t in enumerate(M["teams"])}
    atk = {es: M["atk"][ti[dn]] for es, dn in pm.MAP.items()}
    dfn = {es: M["dfn"][ti[dn]] for es, dn in pm.MAP.items()}
    return atk, dfn, M["c"], M["g"], M["rho"], len(wc_count) > 0


def host_bonus(team, ground, g):
    return g if (team in HOSTS and GROUND_HOST.get(ground, "Estados Unidos") == team) else 0.0


if __name__ == "__main__":
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    data = json.load(urllib.request.urlopen(OF, timeout=30))
    en2es = sch._en2es()
    today = [m for m in data["matches"] if m.get("date") == day and str(m.get("round", "")).lower().startswith("matchday")]

    atk, dfn, c, g, rho, has_form = fit_through(day)          # entrenado < hoy
    sq = pm.apply_adjustments(atk, dfn)                       # lesiones / XI
    schedule = sch.load()

    print(f"\n=== PRONÓSTICO JORNADA {day} (entrenado solo con lo jugado antes de hoy) ===\n")
    rows = []
    for m in today:
        a, b = en2es.get(m["team1"], m["team1"]), en2es.get(m["team2"], m["team2"])
        ground = m.get("ground"); hour, _ = sch.parse_kickoff(m.get("time"))
        if a not in atk or b not in atk:
            continue
        lh = math.exp(c + atk[a] - dfn[b] + host_bonus(a, ground, g)) * cf.WC_GOAL_LEVEL
        la = math.exp(c + atk[b] - dfn[a] + host_bonus(b, ground, g)) * cf.WC_GOAL_LEVEL
        ta, tb = schedule.travel_for_pair(a, b)
        fh, fa = cf.match_factors(a, b, ground, hour, home_travel=ta, away_travel=tb,
                                  enable_alt=cf.USE_ALTITUDE, enable_heat=cf.USE_HEAT, enable_travel=cf.USE_TRAVEL)
        lh *= fh; la *= fa
        pw, pd, pl, grid = pm._grid_probs(lh, la, rho)
        sx, sy = pm.likely_scoreline(grid, pw, pd, pl)
        ft = (m.get("score") or {}).get("ft")
        rows.append({"a": a, "b": b, "ground": ground, "hour": hour, "p1": pw, "pX": pd, "p2": pl,
                     "lh": lh, "la": la, "sx": sx, "sy": sy, "fh": fh, "fa": fa, "ft": ft})
        v = cf.venue(ground) or {}
        tags = []
        if v.get("elevation_m", 0) > cf.ALT_THRESHOLD: tags.append(f"ALTURA {v['elevation_m']:.0f}m")
        if abs(fh - fa) < 1e-9 and fh < 0.999: tags.append("CALOR")
        if (ta or tb): tags.append("VIAJE")
        if host_bonus(a, ground, g) or host_bonus(b, ground, g): tags.append("ANFITRIÓN")
        print(f"{a} vs {b}  @ {ground} {hour}h")
        print(f"   1X2:  {a} {100*pw:.0f}%  |  empate {100*pd:.0f}%  |  {b} {100*pl:.0f}%")
        print(f"   goles esperados: {lh:.2f}-{la:.2f}   marcador más probable: {sx}-{sy}"
              f"{'   factores: ' + ', '.join(tags) if tags else ''}")
        print()

    # comparación con los resultados que ya hay
    played = [r for r in rows if r["ft"]]
    if played:
        print("=== COMPARACIÓN CON RESULTADOS REALES ===\n")
        lab = {0: "1", 1: "X", 2: "2"}; hits = 0; rps_sum = 0.0
        for r in played:
            gh, ga = r["ft"]; o = 0 if gh > ga else (1 if gh == ga else 2)
            pick = max(range(3), key=lambda k: [r["p1"], r["pX"], r["p2"]][k])
            ok = pick == o; hits += ok
            rps = fit_dc.rps([r["p1"], r["pX"], r["p2"]], o); rps_sum += rps
            mark = "✓" if ok else "✗"
            print(f" {mark} {r['a']} {gh}-{ga} {r['b']}   real={lab[o]}  | pronóstico 1X2 "
                  f"{100*r['p1']:.0f}/{100*r['pX']:.0f}/{100*r['p2']:.0f}  marcador prev. {r['sx']}-{r['sy']}  (RPS {rps:.3f})")
        print(f"\n Acierto 1X2: {hits}/{len(played)}   RPS medio: {rps_sum/len(played):.3f}")
    pend = [r for r in rows if not r["ft"]]
    if pend:
        print("\n(pendientes de jugarse hoy: " + ", ".join(f"{r['a']} vs {r['b']}" for r in pend) + ")")
