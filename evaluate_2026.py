"""
evaluate_2026.py — compara las predicciones del modelo (held-out, entrenado con datos previos
al 2026-06-01) contra los RESULTADOS REALES del Mundial 2026 jugados hasta hoy.

Para cada partido jugado: predice 1X2 + goles esperados + marcador más probable usando la sede,
hora y viaje reales (sin ver el resultado), y lo contrasta con lo ocurrido. Evalúa el modelo
CON y SIN las capas de contexto para ver si ayudaron de verdad en el torneo real.

Métricas: RPS, log-loss, Brier, acierto 1X2, acierto de marcador exacto, calibración de goles y
empates, y desgloses (anfitriones, sedes de altura, favoritos vs sorpresas).

Uso:  python evaluate_2026.py
"""
import json, math, os, urllib.request
import fit_dc, predict_match as pm
import context_factors as cf
import schedule_2026 as sch
import calibration as cal

HOSTS = {"Mexico", "Estados Unidos", "Canada"}
GROUND_HOST = {"Mexico City": "Mexico", "Guadalajara (Zapopan)": "Mexico",
               "Monterrey (Guadalupe)": "Mexico", "Toronto": "Canada", "Vancouver": "Canada"}
OPENFOOTBALL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"


def played_matches():
    """Partidos de FASE DE GRUPOS ya jugados (de openfootball), con sede/hora/marcador reales."""
    try:
        data = json.load(urllib.request.urlopen(OPENFOOTBALL, timeout=30))
    except Exception:
        data = {"matches": json.load(open("schedule_2026.json", encoding="utf-8"))}
    en2es = sch._en2es()
    out = []
    for m in data["matches"]:
        if not str(m.get("round", "")).lower().startswith("matchday"):
            continue
        sc = m.get("score") or {}
        if not sc.get("ft"):
            continue
        hour, _ = sch.parse_kickoff(m.get("time"))
        out.append({"a": en2es.get(m["team1"], m["team1"]), "b": en2es.get(m["team2"], m["team2"]),
                    "ga": sc["ft"][0], "gb": sc["ft"][1], "ground": m.get("ground"),
                    "hour": hour, "date": m.get("date")})
    return out


def host_bonus(team, ground, g):
    return g if (team in HOSTS and GROUND_HOST.get(ground, "Estados Unidos") == team) else 0.0


def predict(a, b, ground, hour, atk, dfn, c, g, rho, schedule, use_context):
    """Devuelve (p1,pX,p2, lh,la, top_score) con o sin capas de contexto."""
    lh = math.exp(c + atk[a] - dfn[b] + host_bonus(a, ground, g)) * cf.WC_GOAL_LEVEL
    la = math.exp(c + atk[b] - dfn[a] + host_bonus(b, ground, g)) * cf.WC_GOAL_LEVEL
    if use_context:
        ta, tb = schedule.travel_for_pair(a, b)
        fh, fa = cf.match_factors(a, b, ground, hour, home_travel=ta, away_travel=tb,
                                  enable_alt=cf.USE_ALTITUDE, enable_heat=cf.USE_HEAT, enable_travel=cf.USE_TRAVEL)
        lh *= fh; la *= fa
    pw, pd, pl, grid = pm._grid_probs(lh, la, rho)
    top = max(grid, key=grid.get)
    return pw, pd, pl, lh, la, top


def outcome(ga, gb):
    return 0 if ga > gb else (1 if ga == gb else 2)


def evaluate(use_context):
    # fit LIMPIO pre-torneo (held-out honesto): estrictamente < 2026-06-01, SIN forma del Mundial,
    # para no entrenar sobre los partidos que se evalúan (pm.fit_model sí usa forma en producción).
    M = fit_dc.fit(fit_dc.build(fit_dc.load("2019-01-01", "2026-06-01"), "2026-06-01"), separate=True)
    ti = {t: i for i, t in enumerate(M["teams"])}
    atk = {es: M["atk"][ti[dn]] for es, dn in pm.MAP.items()}
    dfn = {es: M["dfn"][ti[dn]] for es, dn in pm.MAP.items()}
    c, g, rho = M["c"], M["g"], M["rho"]
    schedule = sch.load()
    matches = played_matches()
    rows = []
    for m in matches:
        if m["a"] not in atk or m["b"] not in atk:
            continue
        p1, pX, p2, lh, la, top = predict(m["a"], m["b"], m["ground"], m["hour"],
                                          atk, dfn, c, g, rho, schedule, use_context)
        o = outcome(m["ga"], m["gb"])
        probs = [p1, pX, p2]
        pick = max(range(3), key=lambda k: probs[k])
        rows.append({**m, "p1": p1, "pX": pX, "p2": p2, "lh": lh, "la": la,
                     "pred_score": top, "outcome": o, "pick": pick,
                     "rps": fit_dc.rps(probs, o), "logloss": cal.log_loss(probs, o),
                     "brier": cal.brier(probs, o),
                     "hit_1x2": pick == o, "hit_exact": top == (m["ga"], m["gb"])})
    return rows


def agg(rows):
    n = len(rows) or 1
    return {"n": len(rows),
            "rps": sum(r["rps"] for r in rows) / n, "logloss": sum(r["logloss"] for r in rows) / n,
            "brier": sum(r["brier"] for r in rows) / n,
            "acc_1x2": sum(r["hit_1x2"] for r in rows) / n,
            "acc_exact": sum(r["hit_exact"] for r in rows) / n,
            "pred_goals": sum(r["lh"] + r["la"] for r in rows) / n,
            "real_goals": sum(r["ga"] + r["gb"] for r in rows) / n,
            "pred_draws": sum(r["pX"] for r in rows) / n,
            "real_draws": sum(1 for r in rows if r["outcome"] == 1) / n}


if __name__ == "__main__":
    ctx = evaluate(use_context=True)
    base = evaluate(use_context=False)
    A, B = agg(ctx), agg(base)
    print(f"\n=== MUNDIAL 2026 — predicciones vs realidad ({A['n']} partidos de grupo jugados) ===\n")
    print(f"{'métrica':<26}{'CON contexto':>14}{'SIN contexto':>14}")
    print("-" * 54)
    for k, lab in [("rps", "RPS (↓)"), ("logloss", "log-loss (↓)"), ("brier", "Brier (↓)"),
                   ("acc_1x2", "acierto 1X2 (↑)"), ("acc_exact", "marcador exacto (↑)")]:
        print(f"{lab:<26}{A[k]:>14.4f}{B[k]:>14.4f}")
    print(f"\n{'goles/partido previstos':<26}{A['pred_goals']:>14.2f}{B['pred_goals']:>14.2f}")
    print(f"{'goles/partido reales':<26}{A['real_goals']:>14.2f}")
    print(f"{'prob. empate media prev.':<26}{A['pred_draws']:>14.2%}{B['pred_draws']:>14.2%}")
    print(f"{'empates reales':<26}{A['real_draws']:>14.2%}")

    # desgloses
    alt = [r for r in ctx if (cf.venue(r["ground"]) or {}).get("elevation_m", 0) > cf.ALT_THRESHOLD]
    host = [r for r in ctx if GROUND_HOST.get(r["ground"], "Estados Unidos") in (r["a"], r["b"])]
    print(f"\nDesgloses (CON contexto):")
    print(f"  sedes de altura  ({len(alt):>2}): acierto 1X2 {agg(alt)['acc_1x2']:.0%}  RPS {agg(alt)['rps']:.3f}" if alt else "  (sin partidos de altura)")
    print(f"  con anfitrión    ({len(host):>2}): acierto 1X2 {agg(host)['acc_1x2']:.0%}  RPS {agg(host)['rps']:.3f}" if host else "")

    # sorpresas: donde el modelo dio baja prob al resultado real
    surprises = sorted(ctx, key=lambda r: [r["p1"], r["pX"], r["p2"]][r["outcome"]])[:8]
    print(f"\nMayores sorpresas (el modelo dio baja prob. al resultado real):")
    lab = {0: "1", 1: "X", 2: "2"}
    for r in surprises:
        pr = [r["p1"], r["pX"], r["p2"]][r["outcome"]]
        print(f"  {r['a']:>14} {r['ga']}-{r['gb']} {r['b']:<14}  real={lab[r['outcome']]} p={pr:.0%}  (1X2 {r['p1']:.0%}/{r['pX']:.0%}/{r['p2']:.0%})")

    json.dump({"con_contexto": A, "sin_contexto": B, "n": A["n"]},
              open("eval_2026.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n→ eval_2026.json guardado")
