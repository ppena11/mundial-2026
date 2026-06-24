"""
test_calibration.py — pruebas de calibración (vector scaling) y métricas.
Ejecutar:  pytest test_calibration.py
"""
import math
import pytest
import calibration as cal


def test_apply_none_is_identity():
    p = [0.5, 0.3, 0.2]
    assert cal.apply_calibrator(None, p) == p

def test_apply_normalizes_to_one():
    out = cal.apply_calibrator({"a": [1, 1, 1], "b": [0, 0, 0]}, [0.5, 0.3, 0.2])
    assert sum(out) == pytest.approx(1.0, abs=1e-9)

def test_identity_params_preserve_probs():
    p = [0.5, 0.3, 0.2]
    out = cal.apply_calibrator({"a": [1.0, 1.0, 1.0], "b": [0.0, 0.0, 0.0]}, p)
    assert out == pytest.approx(p, abs=1e-9)   # softmax(log p) = p

def test_fit_empty_returns_identity():
    c = cal.fit_vector_scaling([], [])
    assert c["a"] == [1.0, 1.0, 1.0] and c["b"] == [0.0, 0.0, 0.0]

def test_fit_reduces_logloss_in_sample():
    # probas crudas SOBRECONFIADAS [0.8,0.15,0.05] pero la frecuencia real es 0.5/0.3/0.2
    probs = [[0.8, 0.15, 0.05]] * 500
    outcomes = [0] * 250 + [1] * 150 + [2] * 100
    raw_ll = sum(cal.log_loss(p, o) for p, o in zip(probs, outcomes)) / 500
    c = cal.fit_vector_scaling(probs, outcomes, l2=0.0)
    calp = [cal.apply_calibrator(c, p) for p in probs]
    cal_ll = sum(cal.log_loss(p, o) for p, o in zip(calp, outcomes)) / 500
    assert cal_ll < raw_ll - 0.05            # la calibración acerca a la frecuencia real

def test_log_loss_known():
    assert cal.log_loss([0.5, 0.3, 0.2], 0) == pytest.approx(-math.log(0.5))

def test_brier_known():
    # outcome local: (0.5-1)^2 + 0.3^2 + 0.2^2 = 0.25+0.09+0.04 = 0.38
    assert cal.brier([0.5, 0.3, 0.2], 0) == pytest.approx(0.38, abs=1e-9)

def test_save_load_roundtrip(tmp_path):
    p = str(tmp_path / "cal.json")
    c = {"a": [0.9, 1.0, 1.1], "b": [0.1, 0.0, -0.1]}
    cal.save(c, p)
    assert cal.load(p) == c

def test_load_missing_returns_none(tmp_path):
    assert cal.load(str(tmp_path / "no.json")) is None
