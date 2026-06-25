"""
evaluate_wc_sofar.py — evalúa TODO el Mundial 2026 jugado hasta hoy bajo la REGLA DEL RECAP
(el 1/X/2 que implica el marcador publicado), en walk-forward (cada partido se predice entrenando
SOLO con lo jugado antes de su fecha — sin fuga), con TODAS las herramientas y correcciones actuales
(forma en torneo + shrinkage + nivel de goles + altura/calor/viaje + anfitrión).

Reporta: acierto por la regla del recap, marcador exacto (bonus), favorito por probabilidad 1X2
(referencia), RPS medio y calibración de goles. Desglose por jornada.

Uso:  python evaluate_wc_sofar.py
"""
import json, math, urllib.request
import fit_dc, predict_match as pm, context_factors as cf, schedule_2026 as sch
import predict_today as pt


def main():
    data = json.load(urllib.request.urlopen(pt.OF, timeout=30))
    en2es = sch._en2es()
    schedule = sch.load()
    played = []
    for m in data["matches"]:
        ft = (m.get("score") or {}).get("ft")
        if not ft or not str(m.get("round", "")).lower().startswith("matchday"):
            continue
        hh, _ = sch.parse_kickoff(m.get("time"))
        played.append({"date": m["date"], "a": en2es.get(m["team1"], m["team1"]), "b": en2es.get(m["team2"], m["team2"]),
                       "ground": m.get("ground"), "hour": hh, "gh": ft[0], "ga": ft[1], "round": m.get("round")})
    rows = []
    O = {"1": 0, "X": 1, "2": 2}
    for D in sorted(set(p["date"] for p in played)):
        atk, dfn, c, g, rho, _ = pt.fit_through(D)              # entrena < D, todas las herramientas
        for p in (x for x in played if x["date"] == D):
            a, b = p["a"], p["b"]
            if a not in atk or b not in atk:
                continue
            lh = math.exp(c + atk[a] - dfn[b] + pt.host_bonus(a, p["ground"], g)) * cf.WC_GOAL_LEVEL
            la = math.exp(c + atk[b] - dfn[a] + pt.host_bonus(b, p["ground"], g)) * cf.WC_GOAL_LEVEL
            ta, tb = schedule.travel_for_pair(a, b)
            fh, fa = cf.match_factors(a, b, p["ground"], p["hour"], home_travel=ta, away_travel=tb)
            lh *= fh; la *= fa
            pw, pd, pl, grid = pm._grid_probs(lh, la, rho); sx, sy = pm.likely_scoreline(grid, pw, pd, pl)
            o = pm.outcome_de(p["gh"], p["ga"])
            rows.append({"recap": pm.outcome_de(sx, sy) == o,
                         "exact": (sx == p["gh"] and sy == p["ga"]),
                         "argmax": ["1", "X", "2"][max(range(3), key=lambda k: [pw, pd, pl][k])] == o,
                         "rps": fit_dc.rps([pw, pd, pl], O[o]),
                         "pt": lh + la, "rt": p["gh"] + p["ga"]})
    n = len(rows)
    pct = lambda k: 100 * sum(r[k] for r in rows) / n
    print(f"\n=== MUNDIAL 2026 hasta hoy — {n} partidos (walk-forward, con todas las correcciones) ===\n")
    print(f"  ACIERTO regla del recap (1/X/2 del marcador publicado): {sum(r['recap'] for r in rows)}/{n} = {pct('recap'):.0f}%")
    print(f"  Marcador EXACTO (bonus):                                {sum(r['exact'] for r in rows)}/{n} = {pct('exact'):.0f}%")
    print(f"  (ref.) favorito por probabilidad 1X2:                   {sum(r['argmax'] for r in rows)}/{n} = {pct('argmax'):.0f}%")
    print(f"  RPS medio: {sum(r['rps'] for r in rows)/n:.3f}   (azar ≈ 0.33; menor = mejor)")
    print(f"  Goles/partido: previstos {sum(r['pt'] for r in rows)/n:.2f}  vs  reales {sum(r['rt'] for r in rows)/n:.2f}")


if __name__ == "__main__":
    main()
