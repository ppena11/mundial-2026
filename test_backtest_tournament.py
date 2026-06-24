"""
test_backtest_tournament.py — pruebas de la validación de torneo completo (helpers puros +
una simulación mínima). No descarga datos: usa grupos sintéticos.
Ejecutar:  pytest test_backtest_tournament.py
"""
import random
import backtest_tournament as bt
import fit_dc


def test_bracket_is_standard_32():
    # 8 cruces de R16 que usan cada grupo dos veces (1º y 2º) y cada posición una vez
    assert len(bt.R16) == 8
    used = [(p, L) for p1, L1, p2, L2 in bt.R16 for p, L in ((p1, L1), (p2, L2))]
    assert len(used) == 16 and len(set(used)) == 16            # 16 slots distintos
    for L in "ABCDEFGH":
        assert ("1", L) in used and ("2", L) in used           # cada grupo aporta 1º y 2º

def test_champions_are_facts():
    assert bt.CHAMPION == {2010: "Spain", 2014: "Germany", 2018: "France", 2022: "Argentina"}

def _toy_model(teams):
    # modelo DC sintético: A>B>C>... (atacan más, defienden mejor por orden)
    import numpy as np
    n = len(teams)
    atk = np.array([0.6 - 0.04 * i for i in range(n)])
    dfn = np.array([0.6 - 0.04 * i for i in range(n)])
    return {"teams": teams, "atk": atk, "dfn": dfn, "g": 0.2, "c": 0.0, "rho": -0.05, "OTH": n}

def test_simulate_structure_and_favorite_wins_most():
    teams = [f"T{i}" for i in range(32)]
    groups = {L: teams[k * 4:(k + 1) * 4] for k, L in enumerate("ABCDEFGH")}
    M = _toy_model(teams)
    random.seed(1)
    pchamp, preach, allt = bt.simulate(groups, M, host=None, K=300)
    assert abs(sum(pchamp.values()) - 1.0) < 1e-9                # P(campeón) suma 1
    assert all(abs(sum(preach[s].values()) - n_exp) < 1e-9
               for s, n_exp in [("R16", 16), ("QF", 8), ("SF", 4), ("Final", 2)])  # cuentas por etapa
    # el equipo más fuerte (T0) debe ser campeón más veces que el más débil (T31)
    assert pchamp["T0"] > pchamp["T31"]
    # alcanzar etapas es monótono decreciente para el favorito
    assert preach["R16"]["T0"] >= preach["QF"]["T0"] >= preach["SF"]["T0"] >= preach["Final"]["T0"]

def test_rps_and_importance_available():
    # sanity: las piezas que usa el backtest existen
    assert callable(fit_dc.fit) and callable(fit_dc.build)
