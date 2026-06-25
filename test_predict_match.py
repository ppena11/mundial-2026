"""
test_predict_match.py — pruebas del marcador publicado (coherente con el favorito) y outcome_de.
Ejecutar:  pytest test_predict_match.py
"""
import pytest
import predict_match as pm


def test_outcome_de():
    assert pm.outcome_de(2, 0) == "1"
    assert pm.outcome_de(1, 1) == "X"
    assert pm.outcome_de(0, 2) == "2"


def test_likely_scoreline_follows_home_favorite():
    # 1-1 es la CELDA más probable (0.18), pero el modelo favorece la victoria local
    # (P(local)=0.16+0.15+0.12=0.43 > P(empate)=0.10+0.18=0.28). Debe publicar victoria local.
    grid = {(0, 0): 0.10, (1, 1): 0.18, (1, 0): 0.16, (2, 1): 0.15, (2, 0): 0.12,
            (0, 1): 0.05, (1, 2): 0.05}
    sx, sy = pm.likely_scoreline(grid, 0.43, 0.28, 0.10)
    assert sx > sy                       # publica una victoria local, no el 1-1
    assert (sx, sy) == (1, 0)            # la victoria local MÁS probable (0.16)


def test_likely_scoreline_keeps_draw_when_draw_favored():
    grid = {(1, 1): 0.30, (0, 0): 0.20, (1, 0): 0.10, (0, 1): 0.10, (2, 2): 0.05}
    sx, sy = pm.likely_scoreline(grid, 0.10, 0.55, 0.10)
    assert sx == sy and (sx, sy) == (1, 1)   # favorito empate -> empate más probable


def test_likely_scoreline_away_favorite():
    grid = {(0, 0): 0.10, (1, 1): 0.20, (0, 1): 0.18, (0, 2): 0.16, (1, 2): 0.12}
    # P(visita)=0.18+0.16+0.12=0.46 > empate 0.30 -> publica victoria visitante
    sx, sy = pm.likely_scoreline(grid, 0.10, 0.30, 0.46)
    assert sx < sy and (sx, sy) == (0, 1)


def test_one_x_two_published_score_matches_favorite():
    # un local claramente superior: el marcador publicado debe implicar victoria local (no empate)
    atk = {"Fuerte": 0.6, "Debil": -0.4}; dfn = {"Fuerte": 0.5, "Debil": -0.3}
    pw, pd, pl, lh, la, (sx, sy) = pm.one_x_two("Fuerte", "Debil", atk, dfn, 0.1, 0.2, -0.05)
    assert pw > pd and pw > pl           # el modelo favorece al local
    assert pm.outcome_de(sx, sy) == "1"  # y el marcador publicado lo refleja
