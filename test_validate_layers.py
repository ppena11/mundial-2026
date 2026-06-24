"""
test_validate_layers.py — pruebas de la lógica de validación (puras, sin datos del torneo).
Ejecutar:  pytest test_validate_layers.py
"""
import pytest
import validate_layers as vl


def test_probs_sum_to_one():
    pw, pd, pl = vl.probs_from_lambdas(1.4, 1.1, -0.05)
    assert pw + pd + pl == pytest.approx(1.0, abs=1e-9)
    assert all(0 <= x <= 1 for x in (pw, pd, pl))

def test_probs_symmetric():
    pw, pd, pl = vl.probs_from_lambdas(1.3, 1.3, -0.05)
    assert pw == pytest.approx(pl, abs=1e-6)     # λ iguales → local y visitante simétricos

def test_probs_higher_home_lambda_more_home_win():
    pw_lo, _, _ = vl.probs_from_lambdas(1.2, 1.2, -0.05)
    pw_hi, _, _ = vl.probs_from_lambdas(1.8, 1.2, -0.05)
    assert pw_hi > pw_lo

def test_altitude_adjustment_reduces_home_win():
    # penalizar el λ del local (f_alt<1) baja su prob. de victoria
    lh, la, rho = 1.6, 1.0, -0.05
    pw_base, _, _ = vl.probs_from_lambdas(lh, la, rho)
    pw_adj, _, _ = vl.probs_from_lambdas(lh * 0.92, la, rho)
    assert pw_adj < pw_base

def test_rps_delta_sign():
    # outcome 0 = gana local. La capa que sube pw debe MEJORAR (delta > 0) cuando local gana.
    base = vl.probs_from_lambdas(1.2, 1.2, -0.05)
    adj = vl.probs_from_lambdas(1.8, 1.0, -0.05)   # más favorable al local
    assert vl.rps_delta(base, adj, outcome=0) > 0

def test_rps_matches_fit_dc():
    import fit_dc
    p = (0.5, 0.3, 0.2)
    assert vl.rps(p, 0) == fit_dc.rps(p, 0)

def test_load_alt_map_missing_returns_none(tmp_path):
    cities, base = vl.load_alt_map(str(tmp_path / "no_existe.json"))
    assert cities is None and base is None
