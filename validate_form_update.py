"""
validate_form_update.py — ¿actualizar los ratings con los partidos del Mundial ya jugados mejora
la predicción de las rondas siguientes? (disciplina: solo se activa si mejora fuera de muestra).

Para cada Mundial pasado: predice las ELIMINATORIAS (R16→Final, equipos y resultados reales) con
  (A) ratings CONGELADOS de antes del torneo, y
  (B) ratings ACTUALIZADOS incluyendo la fase de grupos de ese Mundial (con peso de forma y, opc.,
      corrección de goleadas margin-shrink).
Mide el RPS de las eliminatorias (menor = mejor). Barre FORM_BOOST y margin-shrink on/off.

Uso:  python validate_form_update.py
"""
import json, urllib.request
import fit_dc, wc_form
from backtest_tournament import ALIAS, WC_START

KO_ROUNDS = {"Round of 16", "Quarter-final", "Quarter-finals", "Semi-final", "Semi-finals",
             "Final", "Match for third place", "Third place play-off"}


def load(year):
    d = json.load(urllib.request.urlopen(
        f"https://raw.githubusercontent.com/openfootball/worldcup.json/master/{year}/worldcup.json", timeout=30))["matches"]
    def nm(t): return ALIAS.get(t, t)
    group, ko = [], []
    for m in d:
        ft = (m.get("score") or {}).get("ft")
        if not ft:
            continue
        if str(m.get("group", "")).startswith("Group"):
            group.append((m["date"], nm(m["team1"]), nm(m["team2"]), ft[0], ft[1]))
        elif m.get("round") in KO_ROUNDS:
            ko.append((nm(m["team1"]), nm(m["team2"]), ft[0], ft[1]))
    return group, ko


def evaluate(year, form_boost, use_margin):
    start = WC_START[year]
    group, ko = load(year)
    if not ko:
        return None
    group_end = max(g[0] for g in group)
    pre = [r for r in fit_dc.load("1990-01-01", f"{year}-12-31", with_tournament=True) if r[0] < start]
    group_rows = [(d, h, a, gh, ga, True, "FIFA World Cup") for (d, h, a, gh, ga) in group]

    base_M = fit_dc.fit(fit_dc.build(pre, group_end, importance_fn=fit_dc.importance))

    def wfn(row):
        tour = row[6] if len(row) > 6 else None
        if tour == "FIFA World Cup" and start <= row[0] <= group_end:   # partido de grupo de ESTE Mundial
            return form_boost * (wc_form.margin_reliability(row[3], row[4]) if use_margin else 1.0)
        return 1.0

    upd_M = fit_dc.fit(fit_dc.build(pre + group_rows, group_end,
                                    importance_fn=fit_dc.importance, row_weight_fn=wfn))

    rb = ru = 0.0
    for a, b, gh, ga in ko:
        o = 0 if gh > ga else (1 if gh == ga else 2)
        rb += fit_dc.rps(fit_dc.dc_probs(base_M, a, b, True), o)
        ru += fit_dc.rps(fit_dc.dc_probs(upd_M, a, b, True), o)
    return rb / len(ko), ru / len(ko), len(ko)


def scan(years=(2010, 2014, 2018, 2022)):
    print("RPS de ELIMINATORIAS (menor=mejor) — congelado vs actualizado con la fase de grupos\n")
    # base (congelado) es el mismo para todos los boosts; lo calculo una vez por año
    base_by_year = {}
    print(f"{'FORM_BOOST':>11}{'margin':>8}{'RPS congelado':>15}{'RPS actualizado':>17}{'Δ':>9}")
    print("-" * 60)
    for use_margin in (False, True):
        for boost in (1.0, 2.0, 3.0, 5.0, 8.0):
            tot_b = tot_u = n = 0
            for y in years:
                r = evaluate(y, boost, use_margin)
                if r:
                    tot_b += r[0] * r[2]; tot_u += r[1] * r[2]; n += r[2]
            rb, ru = tot_b / n, tot_u / n
            print(f"{boost:>11.1f}{('sí' if use_margin else 'no'):>8}{rb:>15.4f}{ru:>17.4f}{rb - ru:>+9.4f}")


if __name__ == "__main__":
    scan()
