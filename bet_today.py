"""
bet_today.py — conecta el MODELO con el detector de valor en un solo comando.

Tira las probabilidades del modelo (1X2 + Over/Under 2.5) de los partidos de una fecha —entrenando
estrictamente con lo jugado antes (sin fuga) y con TODAS las herramientas— y te deja pegar las cuotas
de Mise-o-jeu para que marque las apuestas de VALOR y su stake (cuarto de Kelly, tope 2%).

Uso:
  python bet_today.py 1500            # banca $; partidos de hoy
  python bet_today.py 1500 2026-06-28 # una fecha concreta

Por cada partido pegas:  cuota1, cuotaX, cuota2, cuotaOver2.5, cuotaUnder2.5
(deja en blanco las que no quieras; Enter vacío salta el partido).
"""
import math, sys
from datetime import date
import json, urllib.request
import fit_dc, predict_match as pm, context_factors as cf, schedule_2026 as sch, value_finder as vf
import predict_today as pt


def model_lines(day):
    """Devuelve, por partido del día, las probabilidades del modelo para 1X2 y Over/Under 2.5."""
    data = json.load(urllib.request.urlopen(pt.OF, timeout=30))
    en2es = sch._en2es()
    matches = [m for m in data["matches"] if m.get("date") == day]
    atk, dfn, c, g, rho, _ = pt.fit_through(day)      # entrenado < día, todas las herramientas
    pm.apply_adjustments(atk, dfn)                    # lesiones / XI
    schedule = sch.load()
    out = []
    for m in matches:
        a, b = en2es.get(m["team1"], m["team1"]), en2es.get(m["team2"], m["team2"])
        if a not in atk or b not in atk:
            continue
        ground = m.get("ground"); hour, _ = sch.parse_kickoff(m.get("time"))
        lh = math.exp(c + atk[a] - dfn[b] + pt.host_bonus(a, ground, g)) * cf.WC_GOAL_LEVEL
        la = math.exp(c + atk[b] - dfn[a] + pt.host_bonus(b, ground, g)) * cf.WC_GOAL_LEVEL
        ta, tb = schedule.travel_for_pair(a, b)
        fh, fa = cf.match_factors(a, b, ground, hour, home_travel=ta, away_travel=tb)
        lh *= fh; la *= fa
        pw, pd, pl, grid = pm._grid_probs(lh, la, rho)
        played = (m.get("score") or {}).get("ft")
        out.append({"a": a, "b": b, "ground": ground, "hour": hour, "played": played,
                    "p": {"1": pw, "X": pd, "2": pl,
                          "O2.5": vf.prob_over(grid, 2.5), "U2.5": vf.prob_under(grid, 2.5)}})
    return out


def _ask_odds(prompt):
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return raw


if __name__ == "__main__":
    bankroll = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].replace(".", "", 1).isdigit() else 1000.0
    day = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()
    print(f"\n=== APUESTAS DE VALOR {day} · banca ${bankroll:.0f} · Kelly×{vf.KELLY_FRACTION} · tope {vf.STAKE_CAP:.0%} · min EV {vf.MIN_EDGE:.0%} ===")
    games = model_lines(day)
    if not games:
        print("(sin partidos con equipos del modelo en esa fecha)"); sys.exit(0)
    SEL = [("1", "gana {a}"), ("X", "empate"), ("2", "gana {b}"), ("O2.5", "Over 2.5"), ("U2.5", "Under 2.5")]
    bets = []
    for gme in games:
        a, b, P = gme["a"], gme["b"], gme["p"]
        tag = "  [YA JUGADO]" if gme["played"] else ""
        print(f"\n▶ {a} vs {b}  @ {gme['ground']} {gme['hour']}h{tag}")
        print("  modelo:  " + "  ".join(f"{k} {100*P[k]:.0f}%" for k, _ in SEL))
        raw = _ask_odds("  cuotas Mise-o-jeu  1,X,2,Over,Under  (coma; vacío=saltar): ")
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(",")]
        for (k, lab), val in zip(SEL, parts):
            if not val:
                continue
            try:
                odds = float(val)
            except ValueError:
                continue
            bets.append({"market": f"{a[:3]}-{b[:3]}", "sel": lab.format(a=a, b=b), "p_model": P[k], "odds": odds})
    print(f"\n{'partido':<10}{'apuesta':<18}{'p_mod':>7}{'implic':>8}{'cuota':>7}{'EV%':>7}{'stake$':>9}")
    print("-" * 66)
    total = 0.0
    for r in vf.analyze(bankroll, bets):
        flag = "  ✅" if r["value"] else ""
        total += r["stake"]
        print(f"{r['market']:<10}{r['sel']:<18}{100*r['p_model']:>6.0f}%{r['implicita']:>7.0f}%{r['odds']:>7.2f}{r['EV%']:>7.1f}{r['stake']:>9.2f}{flag}")
    val = [r for r in vf.analyze(bankroll, bets) if r["value"]]
    print(f"\n{len(val)} apuesta(s) de VALOR · stake total ${total:.2f} ({100*total/bankroll:.1f}% de la banca)")
    print("Recuerda: registra tu cuota vs la de cierre (CLV) para saber si tienes edge real.")
