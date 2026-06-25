"""
test_wc_form.py — pruebas de la fiabilidad por contexto (actualización en torneo).
Ejecutar:  pytest test_wc_form.py
"""
import pytest
import wc_form
import fit_dc


def test_margin_reliability_decreasing():
    # un resultado ajustado vale pleno; las goleadas valen cada vez menos
    assert wc_form.margin_reliability(2, 0) == 1.0
    assert wc_form.margin_reliability(1, 1) == 1.0
    vals = [wc_form.margin_reliability(m, 0) for m in (2, 3, 4, 5, 6)]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))
    assert wc_form.margin_reliability(6, 0) < 0.6        # 6-0 (caso Canadá) muy descontado

def test_margin_symmetric():
    assert wc_form.margin_reliability(0, 4) == wc_form.margin_reliability(4, 0)

def test_red_card_reliability():
    assert wc_form.red_card_reliability(None) == 1.0     # sin roja, pleno
    assert wc_form.red_card_reliability(20) < wc_form.red_card_reliability(70)  # roja temprana descuenta más
    assert wc_form.red_card_reliability(90) == 1.0       # roja en el descuento no distorsiona

def test_reliability_takes_worst():
    # un 6-0 CON roja temprana se descuenta por lo que más pese (el mínimo)
    r = wc_form.reliability(6, 0, red_minute=20)
    assert r == min(wc_form.margin_reliability(6, 0), wc_form.red_card_reliability(20))
    assert r <= 0.6

def test_reliability_clean_result_full():
    assert wc_form.reliability(2, 1, None) == 1.0

def test_load_red_cards_off_by_default(monkeypatch):
    monkeypatch.delenv("CF_REDCARDS", raising=False)        # OFF por defecto -> sin API, vacío
    assert wc_form.load_red_cards() == {}

def test_load_red_cards_on_without_key_returns_empty(monkeypatch):
    monkeypatch.setenv("CF_REDCARDS", "1")
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)   # activa pero sin key -> vacío, no rompe
    assert wc_form.load_red_cards() == {}


# --- row_weight_fn en fit_dc.build (mecanismo de la actualización en torneo) ---
def test_build_row_weight_fn_applies():
    import numpy as np
    rows = [("2025-01-01", "A", "B", 1, 0, True, "Friendly"),
            ("2026-06-15", "A", "B", 6, 0, True, "FIFA World Cup")]
    # sin peso especial
    d0 = fit_dc.build(rows, "2026-06-20", min_matches=1)
    # con peso de forma (×2) y fiabilidad de goleada para el partido del Mundial
    def wfn(r):
        return 2.0 * wc_form.margin_reliability(r[3], r[4]) if r[6] == "FIFA World Cup" else 1.0
    d1 = fit_dc.build(rows, "2026-06-20", min_matches=1, row_weight_fn=wfn)
    W0, W1 = d0[4], d1[4]
    # el partido del Mundial (índice 1) cambia de peso; el amistoso no
    assert W1[0] == pytest.approx(W0[0])
    assert W1[1] == pytest.approx(W0[1] * 2.0 * wc_form.margin_reliability(6, 0))
