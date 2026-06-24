"""
backtest.py — backtesting sobre Mundiales pasados (held-out) para demostrar calibración.

Para cada Mundial (2010, 2014, 2018, 2022): entrena SOLO con partidos previos y evalúa sobre
los 64 partidos de ESE Mundial (fuera de muestra real). Compara variantes del modelo:

  base   : Dixon-Coles con decaimiento temporal
  +comp  : + peso por importancia de competición (eliminatorias/Mundial > amistosos)
  +cal   : +comp + calibración (vector scaling, ajustada en datos PREVIOS, sin fuga)

Métricas estándar de forecasting de fútbol: RPS, log-loss y Brier (menor = mejor).

Uso:  python backtest.py
Funciones reutilizables (evaluate_wc) con prueba ligera en test_backtest.py.
"""
import sys
from datetime import date

import fit_dc
import calibration as cal

WC_START = {2010: "2010-06-11", 2014: "2014-06-12", 2018: "2018-06-14", 2022: "2022-11-20"}


def _wc_test_rows(rows, year, start):
    return [r for r in rows if r[6] == "FIFA World Cup" and r[0][:4] == str(year) and r[0] >= start]

def _probs_outcomes(M, rows):
    P = []; O = []
    for r in rows:
        d, h, a, gh, ga, neu = r[:6]
        P.append(list(fit_dc.dc_probs(M, h, a, neu)))
        O.append(0 if gh > ga else (1 if gh == ga else 2))
    return P, O

def _metrics(P, O):
    n = len(O) or 1
    rps = sum(fit_dc.rps(p, o) for p, o in zip(P, O)) / n
    ll = sum(cal.log_loss(p, o) for p, o in zip(P, O)) / n
    br = sum(cal.brier(p, o) for p, o in zip(P, O)) / n
    return {"rps": rps, "logloss": ll, "brier": br, "n": len(O)}


def evaluate_wc(year, calib_years=4):
    """Backtest de un Mundial. Devuelve {variant: metrics} para base / +comp / +cal."""
    start = WC_START[year]
    rows = fit_dc.load("1990-01-01", f"{year}-12-31", with_tournament=True)
    train = [r for r in rows if r[0] < start]
    test = _wc_test_rows(rows, year, start)
    if not test:
        return None

    Mb = fit_dc.fit(fit_dc.build(train, start))                                   # base
    Mw = fit_dc.fit(fit_dc.build(train, start, importance_fn=fit_dc.importance))  # +competición

    # calibrador: se AJUSTA con partidos previos (sin tocar el test) → sin fuga
    cut = f"{int(year) - calib_years}-01-01"
    calib_rows = [r for r in train if r[0] >= cut]
    Pc, Oc = _probs_outcomes(Mw, calib_rows)
    calibrator = cal.fit_vector_scaling(Pc, Oc) if Pc else None

    Pb, Ob = _probs_outcomes(Mb, test)
    Pw, Ow = _probs_outcomes(Mw, test)
    Pcal = [cal.apply_calibrator(calibrator, p) for p in Pw] if calibrator else Pw

    return {"base": _metrics(Pb, Ob), "+comp": _metrics(Pw, Ow), "+cal": _metrics(Pcal, Ow),
            "calibrator": calibrator}


def run_all(years=(2010, 2014, 2018, 2022)):
    rows = {}
    agg = {"base": [], "+comp": [], "+cal": []}
    for y in years:
        r = evaluate_wc(y)
        if r:
            rows[y] = r
            for v in agg:
                agg[v].append(r[v])
    return rows, agg


if __name__ == "__main__":
    rows, agg = run_all()
    print(f"{'Mundial':<10}{'variante':<8}{'RPS':>9}{'logloss':>10}{'Brier':>9}{'n':>5}")
    print("-" * 51)
    for y in sorted(rows):
        for v in ("base", "+comp", "+cal"):
            m = rows[y][v]
            print(f"{y:<10}{v:<8}{m['rps']:>9.4f}{m['logloss']:>10.4f}{m['brier']:>9.4f}{m['n']:>5}")
        print()
    print("PROMEDIO sobre los 4 Mundiales (menor = mejor):")
    for v in ("base", "+comp", "+cal"):
        ms = agg[v]
        rps = sum(m["rps"] for m in ms) / len(ms)
        ll = sum(m["logloss"] for m in ms) / len(ms)
        br = sum(m["brier"] for m in ms) / len(ms)
        print(f"   {v:<8} RPS={rps:.4f}  logloss={ll:.4f}  Brier={br:.4f}")
    # recomendación de calibración final (ajustada sobre todo el histórico reciente)
    print("\nAjustando calibrador final sobre histórico reciente (2014→2026) para producción...")
    allrows = fit_dc.load("1990-01-01", "2026-06-01", with_tournament=True)
    Mw = fit_dc.fit(fit_dc.build(allrows, "2026-06-01", importance_fn=fit_dc.importance))
    cr = [r for r in allrows if r[0] >= "2014-01-01"]
    P, O = _probs_outcomes(Mw, cr)
    final = cal.fit_vector_scaling(P, O)
    cal.save(final)
    print(f"→ calibration.json guardado: a={[round(x,3) for x in final['a']]} b={[round(x,3) for x in final['b']]}")
