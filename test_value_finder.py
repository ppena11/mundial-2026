"""test_value_finder.py — pruebas de la lógica de valor/stake. Ejecutar: pytest test_value_finder.py"""
import pytest
import value_finder as vf


def test_ev_sign():
    assert vf.ev(0.60, 1.80) == pytest.approx(0.08)      # 60% a 1.80 -> +8% EV (valor)
    assert vf.ev(0.50, 1.80) < 0                          # 50% a 1.80 -> sin valor

def test_implied_prob():
    assert vf.implied_prob(2.0) == pytest.approx(0.5)
    assert vf.implied_prob(1.5) == pytest.approx(0.6667, abs=1e-3)

def test_kelly_zero_without_edge():
    assert vf.kelly_fraction(0.50, 1.80) == 0.0          # sin ventaja -> 0
    assert vf.kelly_fraction(0.60, 1.80) > 0

def test_stake_zero_below_min_edge():
    # 60% a 1.80 = +8% EV, por debajo del umbral 10% -> no apostar
    assert vf.stake(1000, 0.60, 1.80, min_edge=0.10) == 0.0
    # 65% a 1.80 = +17% EV -> sí, con stake > 0
    assert vf.stake(1000, 0.65, 1.80, min_edge=0.10) > 0

def test_stake_capped():
    # ventaja enorme -> el stake se limita al tope (2% de 1000 = 20)
    assert vf.stake(1000, 0.95, 3.0, cap=0.02) == pytest.approx(20.0)

def test_stake_fractional_kelly():
    # 65% a 1.80: Kelly completo = (0.65*1.80-1)/0.80 = 0.2125 ; ×0.25 = 0.0531 ; ×1000 = 53.13
    assert vf.stake(1000, 0.65, 1.80, frac=0.25, cap=1.0, min_edge=0.0) == pytest.approx(53.12, abs=0.1)

def test_analyze_flags_value_and_sorts():
    lines = [{"market": "1X2", "sel": "A", "p_model": 0.50, "odds": 1.80},   # sin valor
             {"market": "O/U", "sel": "Over", "p_model": 0.70, "odds": 1.90}]  # valor
    res = vf.analyze(1000, lines)
    assert res[0]["sel"] == "Over" and res[0]["value"] is True     # el de más EV primero
    assert res[1]["value"] is False
