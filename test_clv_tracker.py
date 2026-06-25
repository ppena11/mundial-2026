"""test_clv_tracker.py — pruebas de CLV y liquidación. Ejecutar: pytest test_clv_tracker.py"""
import pytest
import clv_tracker as ct


def test_clv_pct():
    assert ct.clv_pct(2.5, 0.45) == pytest.approx(0.125)   # 2.5×0.45−1 = +12.5% (batió el cierre)
    assert ct.clv_pct(2.0, 0.45) == pytest.approx(-0.10)    # peor que el cierre
    assert ct.clv_pct(2.0, None) is None                    # sin cierre -> None

def test_grade_1x2():
    assert ct.grade_bet({"sel": "1", "stake": 10, "my_odds": 2.0}, (2, 0)) == ("won", 10.0)
    assert ct.grade_bet({"sel": "2", "stake": 10, "my_odds": 2.0}, (2, 0)) == ("lost", -10.0)
    assert ct.grade_bet({"sel": "X", "stake": 10, "my_odds": 3.0}, (1, 1)) == ("won", 20.0)
    assert ct.grade_bet({"sel": "1", "stake": 10, "my_odds": 2.0}, None) == ("pending", 0.0)

def test_grade_over_under():
    assert ct.grade_bet({"sel": "O2.5", "stake": 10, "my_odds": 1.9}, (2, 1))[0] == "won"   # total 3
    assert ct.grade_bet({"sel": "O2.5", "stake": 10, "my_odds": 1.9}, (1, 1))[0] == "lost"  # total 2
    assert ct.grade_bet({"sel": "U2.5", "stake": 10, "my_odds": 1.9}, (1, 1))[0] == "won"   # total 2
    assert ct.grade_bet({"sel": "U2.5", "stake": 10, "my_odds": 1.9}, (3, 0))[0] == "lost"  # total 3

def test_grade_outright_pending():
    assert ct.grade_bet({"sel": "Campeón", "stake": 10, "my_odds": 6.0}, (2, 0)) == ("pending", 0.0)

def test_closing_prob_latest_wins():
    snaps = [
        {"matches": [{"home": "Argentina", "away": "Brazil", "clean_probs": {"Argentina": 0.40, "Brazil": 0.35, "Draw": 0.25}}]},
        {"matches": [{"home": "Argentina", "away": "Brazil", "clean_probs": {"Argentina": 0.50, "Brazil": 0.30, "Draw": 0.20}}]},
    ]
    # a="Argentina", b="Brasil" (ES) -> mapea a EN; toma el ÚLTIMO snapshot
    assert ct.closing_prob(snaps, "Argentina", "Brasil", "1") == pytest.approx(0.50)
    assert ct.closing_prob(snaps, "Argentina", "Brasil", "2") == pytest.approx(0.30)
    assert ct.closing_prob(snaps, "Argentina", "Brasil", "X") == pytest.approx(0.20)

def test_closing_prob_missing():
    assert ct.closing_prob([], "Argentina", "Brasil", "1") is None
