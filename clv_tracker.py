"""
clv_tracker.py — mide AUTOMÁTICAMENTE el CLV (closing line value) y el ROI de tus apuestas.

Cruza tres fuentes (dos automáticas, una tuya):
  • bets_log.jsonl          -> TUS apuestas (las registra bet_today; el único input manual)
  • odds_h2h_history.jsonl  -> snapshots de cuotas 1X2 del mercado (los guarda el cron)  [AUTOMÁTICO]
  • openfootball            -> resultados reales para liquidar las apuestas               [AUTOMÁTICO]

CLV = ¿conseguiste mejor precio que el CIERRE del mercado? Es la mejor señal de edge REAL.
  CLV% = mi_cuota × prob_cierre_devigueada − 1   (>0 = le ganaste a la línea de cierre)

Uso:  python clv_tracker.py        (corre cada día; idempotente)
Funciones puras (clv_pct, grade_bet) con pruebas en test_clv_tracker.py.
"""
import json, os, urllib.request
import predict_match as pm

BETS = "bets_log.jsonl"; SNAPS = "odds_h2h_history.jsonl"
OF = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
_EN = {es: en for es, en in pm.MAP.items()}   # ES -> EN (para casar con el mercado)


def _load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []


def clv_pct(my_odds, closing_prob):
    """CLV vs el cierre justo (de-vigueado): mi_cuota × prob_cierre − 1. >0 = batiste la línea."""
    return my_odds * closing_prob - 1.0 if closing_prob else None


def closing_prob(snaps, a, b, sel):
    """Prob. de cierre (de-vigueada) del mercado para la selección, del ÚLTIMO snapshot con ese partido."""
    aen, ben = _EN.get(a, a), _EN.get(b, b)
    best = None
    for snap in snaps:                       # snaps en orden cronológico -> el último gana
        for mt in snap.get("matches", []):
            teams = {mt.get("home"), mt.get("away")}
            if aen in teams and ben in teams:
                cp = mt.get("clean_probs", {})
                key = aen if sel == "1" else (ben if sel == "2" else "Draw")
                if key in cp:
                    best = cp[key]
    return best


def grade_bet(bet, result):
    """Liquida una apuesta (1X2 u Over/Under 2.5) dado el resultado (gh,ga) en la orientación (a,b).
    Devuelve 'pending'|'won'|'lost' y la ganancia neta (stake×(cuota−1) si gana, −stake si pierde)."""
    if result is None:
        return "pending", 0.0
    gh, ga = result; sel = bet["sel"]
    if sel in ("1", "X", "2"):
        won = sel == pm.outcome_de(gh, ga)
    elif sel == "O2.5":
        won = (gh + ga) >= 3
    elif sel == "U2.5":
        won = (gh + ga) <= 2
    else:
        return "pending", 0.0                # outright: liquidación aparte
    return ("won", bet["stake"] * (bet["my_odds"] - 1)) if won else ("lost", -bet["stake"])


def results():
    """Resultados reales {frozenset({a_es,b_es}): (gh,ga)} de openfootball (orientación del feed)."""
    try:
        data = json.load(urllib.request.urlopen(OF, timeout=30))
    except Exception:
        return {}
    import schedule_2026 as sch
    en2es = sch._en2es(); out = {}
    for m in data.get("matches", []):
        ft = (m.get("score") or {}).get("ft")
        if ft:
            out[frozenset((en2es.get(m["team1"], m["team1"]), en2es.get(m["team2"], m["team2"])))] = \
                (en2es.get(m["team1"], m["team1"]), ft[0], ft[1])
    return out


def report():
    bets = _load(BETS); snaps = _load(SNAPS); res = results()
    if not bets:
        print(f"Sin apuestas en {BETS}. Regístralas con bet_today (te pregunta si guardar)."); return
    clvs = []; settled = 0; pnl = 0.0; staked = 0.0; beat = 0
    print(f"{'fecha':<11}{'apuesta':<26}{'mi_cuota':>9}{'cierre%':>9}{'CLV%':>8}{'result':>9}")
    print("-" * 73)
    for bt in bets:
        cp = closing_prob(snaps, bt["a"], bt["b"], bt["sel"]) if bt["sel"] in ("1", "X", "2") else None
        c = clv_pct(bt["my_odds"], cp)
        # resultado en la orientación de la apuesta (a,b)
        r = res.get(frozenset((bt["a"], bt["b"])))
        result = None
        if r:
            home_es, gh, ga = r
            result = (gh, ga) if home_es == bt["a"] else (ga, gh)   # reorienta a (a,b)
        status, profit = grade_bet(bt, result)
        if c is not None:
            clvs.append(c); beat += (c > 0)
        if status in ("won", "lost"):
            settled += 1; pnl += profit; staked += bt["stake"]
        sel_lbl = {"1": bt["a"], "X": "Empate", "2": bt["b"]}.get(bt["sel"], bt["sel"])
        print(f"{bt.get('date',''):<11}{(sel_lbl)[:25]:<26}{bt['my_odds']:>9.2f}"
              f"{(100*cp if cp else 0):>8.0f}%{(100*c if c is not None else 0):>7.1f}%{status:>9}")
    print("\n=== RESUMEN ===")
    if clvs:
        print(f"CLV medio: {100*sum(clvs)/len(clvs):+.1f}%  |  apuestas que batieron el cierre: {beat}/{len(clvs)} "
              f"({100*beat/len(clvs):.0f}%)   <- la señal de edge REAL")
    if settled:
        print(f"Liquidadas: {settled}  |  apostado ${staked:.2f}  |  ganancia ${pnl:+.2f}  |  ROI {100*pnl/staked:+.1f}%")
    else:
        print("Aún no hay apuestas liquidadas (resultados pendientes).")
    print("\nNota: CLV+ sostenido = tienes edge real. ROI con pocas apuestas es ruido; el CLV es la señal honesta.")


if __name__ == "__main__":
    report()
