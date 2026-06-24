"""
test_backtest.py — pruebas de los helpers puros del backtest (sin reentrenar el modelo).
Ejecutar:  pytest test_backtest.py
"""
import pytest
import backtest as bt
import fit_dc


def test_wc_test_rows_filters():
    rows = [
        ("2018-06-14", "A", "B", 1, 0, True, "FIFA World Cup"),
        ("2018-03-01", "A", "B", 1, 0, False, "Friendly"),
        ("2018-06-20", "C", "D", 2, 2, True, "FIFA World Cup qualification"),  # no es el Mundial
        ("2014-06-15", "A", "B", 0, 0, True, "FIFA World Cup"),                # otro año
    ]
    out = bt._wc_test_rows(rows, 2018, "2018-06-14")
    assert len(out) == 1 and out[0][0] == "2018-06-14"

def test_metrics_values():
    P = [[0.5, 0.3, 0.2], [0.2, 0.3, 0.5]]
    O = [0, 2]   # ambos aciertan el favorito
    m = bt._metrics(P, O)
    assert m["n"] == 2
    assert m["rps"] == pytest.approx(fit_dc.rps([0.5, 0.3, 0.2], 0), abs=1e-9)  # ambos iguales por simetría
    assert m["logloss"] > 0 and m["brier"] > 0

def test_metrics_perfect_prediction():
    m = bt._metrics([[1.0, 0.0, 0.0]], [0])
    assert m["rps"] == pytest.approx(0.0, abs=1e-9)
    assert m["brier"] == pytest.approx(0.0, abs=1e-9)

def test_wc_goal_level_applied_in_prediction():
    # el nivel de goles mundialista multiplica ambos λ en predict_match.one_x_two
    import math
    import predict_match as pm
    import context_factors as cf
    atk = {"X": 0.2, "Y": 0.0}; dfn = {"X": 0.1, "Y": 0.0}
    _, _, _, lh, la, _ = pm.one_x_two("X", "Y", atk, dfn, 0.0, 0.2, -0.05)
    assert lh == pytest.approx(math.exp(0.2) * cf.WC_GOAL_LEVEL, abs=1e-9)
    assert la == pytest.approx(math.exp(-0.1) * cf.WC_GOAL_LEVEL, abs=1e-9)
    assert cf.WC_GOAL_LEVEL > 1.0   # sube el nivel de goles (el modelo los subestima)

def test_importance_weights():
    # eliminatorias/Mundial pesan más que amistosos
    assert fit_dc.importance("Friendly") == 1.0
    assert fit_dc.importance("FIFA World Cup") == 4.0
    assert fit_dc.importance("FIFA World Cup qualification") == 2.0
    assert fit_dc.importance("UEFA Nations League") == 2.5
    assert fit_dc.importance("Copa América") == 3.5
    assert fit_dc.importance("UEFA Euro qualification") == 2.0   # qualification manda sobre Euro
