"""
test_schedule_2026.py — pruebas del calendario y la derivación de viaje (puro, sin red).
Ejecutar:  pytest test_schedule_2026.py
"""
import pytest
import context_factors as cf
import schedule_2026 as sch


# ---------------- parse_kickoff ----------------
def test_parse_kickoff_basic():
    assert sch.parse_kickoff("13:00 UTC-6") == (13, -6.0)
    assert sch.parse_kickoff("20:00 UTC-6") == (20, -6.0)
    assert sch.parse_kickoff("12:00 UTC-4") == (12, -4.0)
    assert sch.parse_kickoff("09:00 UTC+9") == (9, 9.0)

def test_parse_kickoff_empty_and_garbage():
    assert sch.parse_kickoff("") == (None, None)
    assert sch.parse_kickoff(None) == (None, None)
    assert sch.parse_kickoff("sin hora") == (None, None)

def test_parse_kickoff_no_offset():
    assert sch.parse_kickoff("15:30") == (15, None)


# ---------------- is_group_round ----------------
def test_is_group_round():
    assert sch.is_group_round("Matchday 1")
    assert sch.is_group_round("Matchday 13")
    assert not sch.is_group_round("Round of 32")
    assert not sch.is_group_round("Final")
    assert not sch.is_group_round(None)


# ---------------- normalize ----------------
def test_normalize_maps_and_parses():
    raw = [{"date": "2026-06-11", "time": "13:00 UTC-6", "round": "Matchday 1",
            "group": "Group A", "ground": "Mexico City",
            "team1": "Mexico", "team2": "South Africa"}]
    out = sch.normalize(raw)   # usa namemap real
    m = out[0]
    assert m["team2"] == "Sudafrica"     # mapeo EN->ES
    assert m["hour"] == 13 and m["utc_offset"] == -6.0
    assert m["is_group"] is True


# ---------------- Schedule ----------------
@pytest.fixture
def synth_schedule(monkeypatch):
    # coords sintéticas: VenueA ~LA (UTC-8), VenueB ~NY (UTC-5)
    monkeypatch.setattr(cf, "_CTX", {
        "venues": {
            "VenueA": {"lat": 34.0, "lon": -118.0},
            "VenueB": {"lat": 40.0, "lon": -74.0},
        }
    })
    raw = [
        {"date": "2026-06-11", "time": "13:00 UTC-8", "round": "Matchday 1",
         "group": "Group A", "ground": "VenueA", "team1": "X", "team2": "Z"},
        {"date": "2026-06-12", "time": "12:00 UTC-5", "round": "Matchday 1",
         "group": "Group A", "ground": "VenueB", "team1": "Y", "team2": "W"},
        {"date": "2026-06-15", "time": "18:00 UTC-5", "round": "Matchday 2",
         "group": "Group A", "ground": "VenueB", "team1": "X", "team2": "Y"},
    ]
    s = sch.Schedule(sch.normalize(raw, en2es={}))
    yield s
    monkeypatch.setattr(cf, "_CTX", None)

def test_factors_for(synth_schedule):
    assert synth_schedule.factors_for("X", "Y") == ("VenueB", 18)
    assert synth_schedule.factors_for("Y", "X") == ("VenueB", 18)   # par sin orden
    assert synth_schedule.factors_for("X", "Nadie") == (None, None)

def test_travel_for_eastward(synth_schedule):
    # X: VenueA(06-11, UTC-8) -> VenueB(06-15, UTC-5): 4 días, ~LA->NY, +3 husos (este)
    t = synth_schedule.travel_for("X", "VenueB", "2026-06-15", -5.0)
    assert t["rest_days"] == 4
    assert t["km_travel"] > 3000
    assert t["tz_change"] == pytest.approx(3.0)   # este = positivo

def test_travel_for_no_move(synth_schedule):
    # Y: VenueB(06-12) -> VenueB(06-15): 3 días, 0 km, 0 husos
    t = synth_schedule.travel_for("Y", "VenueB", "2026-06-15", -5.0)
    assert t["rest_days"] == 3
    assert t["km_travel"] == pytest.approx(0.0, abs=1e-6)
    assert t["tz_change"] == pytest.approx(0.0)

def test_travel_for_first_match_none(synth_schedule):
    # primer partido de X (no hay anterior) -> None
    assert synth_schedule.travel_for("X", "VenueA", "2026-06-11", -8.0) is None

def test_travel_for_pair(synth_schedule):
    ta, tb = synth_schedule.travel_for_pair("X", "Y")
    assert ta["tz_change"] == pytest.approx(3.0)   # X viajó al este
    assert tb["km_travel"] == pytest.approx(0.0)   # Y no se movió
