"""
validate_walkforward.py — valida la actualización en torneo PARTIDO A PARTIDO (no solo eliminatorias).

Walk-forward (online) sobre los 4 Mundiales pasados: recorriendo el torneo por fecha, reentrena el
modelo con TODO lo jugado ANTES de esa fecha y predice los partidos de esa fecha, comparando:
  (A) ratings CONGELADOS pre-torneo   vs   (B) ratings ACTUALIZADOS con los partidos previos del Mundial.
Mide el RPS por fase (grupos jornada 2/3 y eliminatorias) para demostrar que CADA partido jugado
mejora la predicción de los siguientes, en todas las fases —no solo en la ronda de 32.

Ambos modelos se reentrenan con la MISMA fecha de referencia: la única diferencia es la forma del
Mundial incorporada (B). No hay fuga: para predecir la fecha D solo se usan partidos con fecha < D.

Uso:  python validate_walkforward.py
"""
import json, urllib.request
import fit_dc, wc_form, context_factors as cf
from backtest_tournament import ALIAS, WC_START

KO_ROUNDS = {"Round of 16", "Quarter-final", "Quarter-finals", "Semi-final", "Semi-finals",
             "Final", "Match for third place", "Third place play-off"}


def load(year):
    d = json.load(urllib.request.urlopen(
        f"https://raw.githubusercontent.com/openfootball/worldcup.json/master/{year}/worldcup.json", timeout=30))["matches"]
    def nm(t): return ALIAS.get(t, t)
    out = []
    for m in d:
        ft = (m.get("score") or {}).get("ft")
        if not ft:
            continue
        if str(m.get("group", "")).startswith("Group"):
            phase = "Grupos"
        elif m.get("round") in KO_ROUNDS:
            phase = "Eliminatorias"
        else:
            continue
        out.append((m["date"], nm(m["team1"]), nm(m["team2"]), ft[0], ft[1], phase))
    return sorted(out, key=lambda x: x[0])


def _wc_weight_fn(prior, gate):
    """row_weight_fn que replica EXACTAMENTE producción: fiabilidad (margen/roja) siempre; el boost
    de forma solo si gate=False (sin shrinkage) o si ambos equipos ya tienen ≥ WC_FORM_MIN partidos."""
    keyset = {(m[0], m[1], m[2]) for m in prior}
    cnt = {}
    for m in prior:
        cnt[m[1]] = cnt.get(m[1], 0) + 1; cnt[m[2]] = cnt.get(m[2], 0) + 1
    def wfn(row):
        if (row[0], row[1], row[2]) not in keyset:
            return 1.0
        w = wc_form.reliability(row[3], row[4])
        if (not gate) or (cnt.get(row[1], 0) >= cf.WC_FORM_MIN and cnt.get(row[2], 0) >= cf.WC_FORM_MIN):
            w *= cf.WC_FORM_BOOST
        return w
    return wfn


def collect(year):
    """Por partido (con info previa): RPS congelado vs actualizado SIN shrinkage vs CON shrinkage
    (la lógica EXACTA de producción). Fitea cada modelo una vez por fecha."""
    start = WC_START[year]
    matches = load(year)
    pre = [r for r in fit_dc.load("1990-01-01", f"{year}-12-31", with_tournament=True) if r[0] < start]
    out = []
    for D in sorted(set(m[0] for m in matches)):
        prior = [m for m in matches if m[0] < D]
        frozen_M = fit_dc.fit(fit_dc.build(pre, D))                 # base = producción (sin importance)
        if prior:
            gr = [(m[0], m[1], m[2], m[3], m[4], True, "FIFA World Cup") for m in prior]
            nogate_M = fit_dc.fit(fit_dc.build(pre + gr, D, row_weight_fn=_wc_weight_fn(prior, gate=False)))
            prod_M = fit_dc.fit(fit_dc.build(pre + gr, D, row_weight_fn=_wc_weight_fn(prior, gate=True)))
        else:
            nogate_M = prod_M = frozen_M
        for m in (x for x in matches if x[0] == D):
            o = 0 if m[3] > m[4] else (1 if m[3] == m[4] else 2)
            out.append({"phase": m[5], "prior": bool(prior),
                        "rb": fit_dc.rps(fit_dc.dc_probs(frozen_M, m[1], m[2], True), o),
                        "rn": fit_dc.rps(fit_dc.dc_probs(nogate_M, m[1], m[2], True), o),
                        "rp": fit_dc.rps(fit_dc.dc_probs(prod_M, m[1], m[2], True), o)})
    return out


def report(years=(2010, 2014, 2018, 2022)):
    data = [r for y in years for r in collect(y)]
    upd = [r for r in data if r["prior"]]
    def agg(rows, key):
        n = len(rows)
        return (n, sum(r["rb"] for r in rows) / n, sum(r[key] for r in rows) / n,
                (sum(r["rb"] for r in rows) - sum(r[key] for r in rows)) / n,
                sum(1 for r in rows if r[key] < r["rb"]) / n) if n else None
    print(f"Walk-forward partido a partido sobre 4 Mundiales (FORM_BOOST={cf.WC_FORM_BOOST}, "
          f"WC_FORM_MIN={cf.WC_FORM_MIN}) — RPS congelado vs actualizado\n")
    for key, lab in (("rn", "actualizado SIN shrinkage"), ("rp", "actualizado PRODUCCIÓN (con shrinkage)")):
        print(f"### {lab}")
        print(f"{'fase':<26}{'n':>5}{'RPS cong.':>11}{'RPS act.':>11}{'Δ':>9}{'%mej':>7}")
        for name, rows in [("TODOS (con info previa)", upd),
                           ("  Grupos (J2/J3)", [r for r in upd if r["phase"] == "Grupos"]),
                           ("  Eliminatorias", [r for r in upd if r["phase"] == "Eliminatorias"])]:
            a = agg(rows, key)
            if a:
                print(f"{name:<26}{a[0]:>5}{a[1]:>11.4f}{a[2]:>11.4f}{a[3]:>+9.4f}{a[4]:>7.0%}")
        print()


if __name__ == "__main__":
    report()


if __name__ == "__main__":
    report()
