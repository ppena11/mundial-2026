"""
test_context_factors.py — pruebas de las capas de contexto (altura, calor, viaje).
Deterministas, sin red ni fit del modelo.  Ejecutar:  pytest test_context_factors.py
"""
import math
import pytest
import context_factors as cf


# ---------------- clamp ----------------
def test_clamp_bounds():
    assert cf.clamp(0.5) == cf.CLAMP_LO == 0.90
    assert cf.clamp(2.0) == cf.CLAMP_HI == 1.08
    assert cf.clamp(1.0) == 1.0


# ---------------- haversine ----------------
def test_haversine_zero():
    assert cf.haversine(19.43, -99.13, 19.43, -99.13) == pytest.approx(0.0, abs=1e-6)

def test_haversine_half_circumference():
    # de (0,0) a (0,180) = media circunferencia = π·R
    assert cf.haversine(0, 0, 0, 180) == pytest.approx(math.pi * cf._EARTH_KM, rel=1e-6)

def test_haversine_quarter():
    assert cf.haversine(0, 0, 0, 90) == pytest.approx(math.pi * cf._EARTH_KM / 2, rel=1e-6)

def test_haversine_symmetric():
    d1 = cf.haversine(19.43, -99.13, 40.42, -3.70)
    d2 = cf.haversine(40.42, -3.70, 19.43, -99.13)
    assert d1 == pytest.approx(d2, rel=1e-9)

def test_haversine_cdmx_madrid_known():
    # Ciudad de México ↔ Madrid ≈ 9070 km (referencia geográfica)
    d = cf.haversine(19.4326, -99.1332, 40.4168, -3.7038)
    assert 8800 < d < 9300


# ---------------- f_altitude ----------------
def test_alt_below_threshold_no_effect():
    assert cf.f_altitude(500, 0) == 1.0
    assert cf.f_altitude(1500, 0) == 1.0   # justo en el umbral, sin efecto

def test_alt_sealevel_at_azteca():
    # 1 - 0.04·(2240-0)/1000 = 0.9104  (≈0.91, como en el diseño)
    assert cf.f_altitude(2240, 0) == pytest.approx(0.9104, abs=1e-4)

def test_alt_native_no_penalty():
    assert cf.f_altitude(2240, 2240) == 1.0          # gap 0 → sin castigo
    assert cf.f_altitude(2240, 3000) == 1.0          # base aún más alta → sin castigo

def test_alt_floor():
    # sede extrema vs base nivel del mar → cae al piso 0.90, nunca menos
    assert cf.f_altitude(5000, 0) == cf.ALT_FLOOR == 0.90

def test_alt_monotonic_in_venue():
    base = 0
    vals = [cf.f_altitude(e, base) for e in (1600, 1800, 2000, 2240)]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))

def test_alt_monotonic_in_base():
    venue = 2240
    vals = [cf.f_altitude(venue, b) for b in (0, 500, 1000, 1500, 2240)]
    assert all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))


# ---------------- f_altitude_pair ----------------
def test_alt_pair_below_threshold():
    assert cf.f_altitude_pair(800, 0, 2000) == (1.0, 1.0)

def test_alt_pair_native_boost():
    # local con base por encima de la sede recibe un pequeño plus; visitante nivel del mar, castigo
    mh, ma = cf.f_altitude_pair(2240, 2500, 0)
    assert mh == pytest.approx(1.05, abs=1e-6)         # 1·(1+0.02·2.5)
    assert ma == pytest.approx(0.9104, abs=1e-4)

def test_alt_pair_always_within_bounds():
    for ev in (0, 1600, 2240, 5000):
        for eh in (0, 1000, 2500, 4000):
            for ea in (0, 1000, 2500, 4000):
                mh, ma = cf.f_altitude_pair(ev, eh, ea)
                assert cf.CLAMP_LO <= mh <= cf.CLAMP_HI
                assert cf.CLAMP_LO <= ma <= cf.CLAMP_HI


# ---------------- f_heat ----------------
def test_heat_ac_off():
    # clima controlado apaga el factor SIEMPRE
    assert cf.f_heat("extreme", "retractable", True, 14) == 1.0

def test_heat_low_risk_no_effect():
    assert cf.f_heat("low", "open", False, 14) == 1.0

def test_heat_extreme_midday_compresses():
    f = cf.f_heat("extreme", "open", False, 14)
    assert f < 1.0
    assert f == pytest.approx(1 - cf.HEAT_MAX_COMPRESSION, abs=1e-9)  # severidad 1·hora 1

def test_heat_night_small():
    f_day = cf.f_heat("high", "open", False, 14)
    f_night = cf.f_heat("high", "open", False, 22)
    assert f_night > f_day            # de noche pega menos
    assert f_night > 0.99

def test_heat_monotonic_in_severity():
    vals = [cf.f_heat(r, "open", False, 14) for r in ("low", "moderate", "high", "extreme")]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))

def test_heat_within_bounds():
    for r in ("low", "moderate", "high", "extreme"):
        for h in range(24):
            assert cf.CLAMP_LO <= cf.f_heat(r, "open", False, h) <= cf.CLAMP_HI

def test_hour_weight():
    assert cf._hour_heat_weight(14) == 1.0
    assert cf._hour_heat_weight(3) < cf._hour_heat_weight(14)
    assert cf._hour_heat_weight(None) == 0.6


# ---------------- f_travel ----------------
def test_travel_no_data_no_effect():
    assert cf.f_travel(None, 0, 0) == 1.0
    assert cf.f_travel(cf.REST_REF, 0, 0) == 1.0   # descanso normal, sin viaje

def test_travel_less_rest_penalizes():
    assert cf.f_travel(2, 0, 0) < 1.0
    assert cf.f_travel(2, 0, 0) < cf.f_travel(3, 0, 0)

def test_travel_more_km_penalizes():
    assert cf.f_travel(cf.REST_REF, 4000, 0) < cf.f_travel(cf.REST_REF, 1000, 0)

def test_travel_east_worse_than_west():
    east = cf.f_travel(cf.REST_REF, 0, +3)
    west = cf.f_travel(cf.REST_REF, 0, -3)
    assert east < west            # viajar al este es peor (factor más bajo)

def test_travel_floor():
    f = cf.f_travel(0, 50000, 12)   # caso absurdo: cae al piso, nunca menos
    assert f == cf.FATIGUE_FLOOR == 0.90

def test_travel_within_bounds():
    for rest in (None, 0, 2, 4, 7):
        for km in (0, 1000, 5000):
            for tz in (-6, -3, 0, 3, 6):
                assert cf.FATIGUE_FLOOR <= cf.f_travel(rest, km, tz) <= 1.0


# ---------------- match_factors (con datos sintéticos inyectados) ----------------
@pytest.fixture
def synthetic_ctx(monkeypatch):
    ctx = {
        "venues": {
            "Mexico City": {"elevation_m": 2240, "roof": "open",
                            "effective_ac_during_play": False,
                            "summer_afternoon_heat_risk": "low"},
            "Miami (Miami Gardens)": {"elevation_m": 3, "roof": "open",
                                      "effective_ac_during_play": False,
                                      "summer_afternoon_heat_risk": "extreme"},
            "Houston": {"elevation_m": 15, "roof": "retractable",
                        "effective_ac_during_play": True,
                        "summer_afternoon_heat_risk": "extreme"},
        },
        "teams": {
            "Mexico": {"base_elevation_m": 2240},
            "Brasil": {"base_elevation_m": 1150},
            "Alemania": {"base_elevation_m": 100},
        },
    }
    monkeypatch.setattr(cf, "_CTX", ctx)
    yield ctx
    monkeypatch.setattr(cf, "_CTX", None)

def test_match_factors_missing_data_graceful():
    # sin contexto cargado y sin viaje → neutral (no inventa)
    cf._CTX = {}
    try:
        assert cf.match_factors("X", "Y", "SedeInexistente") == (1.0, 1.0)
    finally:
        cf._CTX = None

def test_match_factors_altitude(synthetic_ctx):
    # Alemania (nivel del mar) visita en CDMX: su λ se castiga; México (nativo) no
    fh, fa = cf.match_factors("Mexico", "Alemania", "Mexico City", kickoff_hour=12)
    assert fh == pytest.approx(1.0, abs=1e-6) or fh > fa   # local no castigado
    assert fa < 1.0                                        # visitante castigado
    assert cf.CLAMP_LO <= fa <= cf.CLAMP_HI

def test_match_factors_heat_symmetric(synthetic_ctx):
    fh, fa = cf.match_factors("Brasil", "Alemania", "Miami (Miami Gardens)", kickoff_hour=14)
    assert fh == pytest.approx(fa, abs=1e-9)   # calor simétrico, sin altura (3 m)
    assert fh < 1.0

def test_match_factors_heat_off_with_ac(synthetic_ctx):
    fh, fa = cf.match_factors("Brasil", "Alemania", "Houston", kickoff_hour=14)
    assert (fh, fa) == (1.0, 1.0)              # techo+aire apaga el calor; sin altura

def test_match_factors_travel_applies_without_venue(synthetic_ctx):
    fh, fa = cf.match_factors("Brasil", "Alemania", "SedeInexistente",
                              home_travel={"rest_days": 2, "km_travel": 4000, "tz_change": 3},
                              away_travel=None)
    assert fh < 1.0          # el local viajó y descansó poco
    assert fa == 1.0         # el visitante sin datos de viaje → neutral

def test_match_factors_toggles(synthetic_ctx):
    base = cf.match_factors("Mexico", "Alemania", "Mexico City", kickoff_hour=14)
    off = cf.match_factors("Mexico", "Alemania", "Mexico City", kickoff_hour=14,
                           enable_alt=False)
    assert off[1] >= base[1]   # apagar altura no castiga al visitante
