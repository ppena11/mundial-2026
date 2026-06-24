"""
test_format_engine.py — pruebas del motor de formato (sobredispersión, desempates FIFA,
mejores terceros, asignación a ronda de 32).  Ejecutar:  pytest test_format_engine.py
"""
import math
import random
from itertools import combinations
import pytest
import format_engine as fe


# ================= MUESTREO DE GOLES =================
def test_poisson_nonneg_int():
    rng = random.Random(1)
    xs = [fe.poisson(1.5, rng) for _ in range(2000)]
    assert all(isinstance(x, int) and x >= 0 for x in xs)

def test_poisson_zero_lambda():
    assert fe.poisson(0) == 0
    assert fe.poisson(-1) == 0

def test_poisson_mean():
    rng = random.Random(2)
    xs = [fe.poisson(2.0, rng) for _ in range(50000)]
    assert abs(sum(xs) / len(xs) - 2.0) < 0.05

def test_negbin_inf_is_poisson():
    assert fe.negbin(1.3, float("inf")) >= 0   # no falla
    rng = random.Random(3)
    xs = [fe.negbin(2.0, float("inf"), rng) for _ in range(20000)]
    assert abs(sum(xs) / len(xs) - 2.0) < 0.08

def test_negbin_mean_and_overdispersion():
    rng = random.Random(4)
    mean, r = 1.6, 4.0
    xs = [fe.negbin(mean, r, rng) for _ in range(60000)]
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / len(xs)
    assert abs(m - mean) < 0.05                 # media correcta
    assert var > m + 0.1                         # sobredispersión: Var > media (Poisson tendría Var=media)
    assert abs(var - (mean + mean ** 2 / r)) < 0.4   # cerca de mean + mean²/r

def test_negbin_bad_r():
    with pytest.raises(ValueError):
        fe.negbin(1.0, -2.0)

def test_poisson_pmf_sums_to_one():
    s = sum(fe.poisson_pmf(k, 2.3) for k in range(40))
    assert abs(s - 1.0) < 1e-9

def test_poisson_pmf_known():
    assert fe.poisson_pmf(0, 1.0) == pytest.approx(math.exp(-1.0))

def test_negbin_pmf_sums_and_mean():
    mean, r = 2.0, 5.0
    s = sum(fe.negbin_pmf(k, mean, r) for k in range(200))
    em = sum(k * fe.negbin_pmf(k, mean, r) for k in range(200))
    assert abs(s - 1.0) < 1e-6
    assert abs(em - mean) < 1e-3                 # la media de la pmf es `mean`

def test_negbin_pmf_large_r_approx_poisson():
    for k in range(6):
        assert fe.negbin_pmf(k, 1.5, 1e6) == pytest.approx(fe.poisson_pmf(k, 1.5), abs=1e-3)

def test_dc_tau_values():
    lh, la, rho = 1.2, 0.9, -0.05
    assert fe._dc_tau(0, 0, lh, la, rho) == pytest.approx(1 - lh * la * rho)
    assert fe._dc_tau(0, 1, lh, la, rho) == pytest.approx(1 + lh * rho)
    assert fe._dc_tau(1, 0, lh, la, rho) == pytest.approx(1 + la * rho)
    assert fe._dc_tau(1, 1, lh, la, rho) == pytest.approx(1 - rho)
    assert fe._dc_tau(2, 3, lh, la, rho) == 1.0

def test_sample_score_returns_pair():
    rng = random.Random(7)
    gh, ga = fe.sample_score(1.4, 1.1, rho=-0.05, rng=rng)
    assert isinstance(gh, int) and isinstance(ga, int) and gh >= 0 and ga >= 0

def test_sample_score_nb_tail_heavier():
    # con sobredispersión deben aparecer más goleadas (margen >= 4) que con Poisson
    rng1 = random.Random(11); rng2 = random.Random(11)
    big_pois = 0
    for _ in range(40000):
        gh, ga = fe.sample_score(2.2, 0.6, rho=0.0, rng=rng1)
        if gh - ga >= 4:
            big_pois += 1
    big_nb = 0
    for _ in range(40000):
        gh, ga = fe.sample_score(2.2, 0.6, rho=0.0, dispersion_r=3.0, rng=rng2)
        if gh - ga >= 4:
            big_nb += 1
    assert big_nb > big_pois

def test_fit_dispersion_detects_overdispersion():
    rng = random.Random(21)
    lams = [random.Random(i).uniform(0.6, 2.4) for i in range(4000)]
    goals = [fe.negbin(l, 4.0, rng) for l in lams]      # datos sobredispersos (r=4)
    r_best, ll_nb, ll_pois = fe.fit_dispersion(lams, goals)
    assert ll_nb >= ll_pois                              # NB ajusta al menos igual de bien
    assert r_best < 100                                  # detecta dispersión finita

def test_fit_dispersion_poisson_data_prefers_large_r():
    rng = random.Random(22)
    lams = [random.Random(i + 5).uniform(0.6, 2.4) for i in range(4000)]
    goals = [fe.poisson(l, rng) for l in lams]           # datos Poisson (sin sobredispersión)
    r_best, ll_nb, ll_pois = fe.fit_dispersion(lams, goals)
    assert r_best >= 30                                  # prefiere r grande (≈ Poisson)


# ================= DESEMPATES FIFA =================
def test_group_table_basic():
    teams = ["A", "B", "C", "D"]
    matches = [("A", "B", 2, 0), ("A", "C", 1, 1), ("A", "D", 3, 0),
               ("B", "C", 0, 0), ("B", "D", 1, 1), ("C", "D", 2, 1)]
    tab = fe.group_table(teams, matches)
    assert tab["A"]["pts"] == 7                          # 2 victorias + 1 empate
    assert tab["A"]["gf"] == 6 and tab["A"]["ga"] == 1 and tab["A"]["gd"] == 5

def test_rank_group_no_tie():
    teams = ["A", "B", "C", "D"]
    matches = [("A", "B", 2, 0), ("A", "C", 2, 0), ("A", "D", 2, 0),
               ("B", "C", 2, 0), ("B", "D", 2, 0), ("C", "D", 2, 0)]
    order = fe.rank_group(teams, matches, rng=random.Random(0))
    assert order == ["A", "B", "C", "D"]

def test_rank_group_head_to_head():
    # A y B empatan en pts/dif/gf globales, pero A le ganó a B → A por delante (head-to-head)
    teams = ["A", "B", "C", "D"]
    matches = [
        ("A", "B", 1, 0),   # A vence a B (head-to-head decisivo)
        ("A", "C", 1, 1),
        ("A", "D", 0, 1),
        ("B", "C", 1, 0),
        ("B", "D", 1, 1),
        ("C", "D", 2, 2),
    ]
    tab = fe.group_table(teams, matches)
    # A y B: ambos 4 pts, dif 0, gf 2 → empate total salvo head-to-head
    assert (tab["A"]["pts"], tab["A"]["gd"], tab["A"]["gf"]) == (4, 0, 2)
    assert (tab["B"]["pts"], tab["B"]["gd"], tab["B"]["gf"]) == (4, 0, 2)
    order = fe.rank_group(teams, matches, rng=random.Random(0))
    assert order.index("A") < order.index("B")          # A por delante por el head-to-head

def test_rank_group_fair_play_breaks_when_h2h_tied():
    # dos equipos empatados global y en head-to-head (empate entre ellos) → decide fair play
    teams = ["A", "B", "C", "D"]
    matches = [
        ("A", "B", 1, 1),   # empate head-to-head
        ("A", "C", 2, 0), ("A", "D", 0, 1),
        ("B", "C", 2, 0), ("B", "D", 0, 1),
        ("C", "D", 0, 0),
    ]
    # A y B idénticos en todo y en head-to-head → fair play decide (menos tarjetas mejor)
    order = fe.rank_group(teams, matches, fair_play={"A": 1, "B": 5}, rng=random.Random(0))
    assert order.index("A") < order.index("B")

def test_rank_group_h2h_before_overall_gd():
    # A vence a B en head-to-head, pero B tiene mejor diferencia GLOBAL.
    # FIFA 2026 (h2h_first=True): manda el head-to-head → A por delante.
    # Orden histórico (h2h_first=False): manda la diferencia global → B por delante.
    teams = ["A", "B", "C", "D"]
    matches = [("A", "B", 1, 0), ("A", "C", 0, 5), ("A", "D", 1, 0),
               ("B", "C", 3, 0), ("B", "D", 3, 0), ("C", "D", 1, 1)]
    tab = fe.group_table(teams, matches)
    assert tab["A"]["pts"] == tab["B"]["pts"] == 6        # empatados en puntos
    assert tab["B"]["gd"] > tab["A"]["gd"]                # B mejor diferencia global
    o_2026 = fe.rank_group(teams, matches, rng=random.Random(0), h2h_first=True)
    o_hist = fe.rank_group(teams, matches, rng=random.Random(0), h2h_first=False)
    assert o_2026.index("A") < o_2026.index("B")          # 2026: head-to-head manda
    assert o_hist.index("B") < o_hist.index("A")          # histórico: diferencia global manda

def test_rank_group_fifa_ranking_breaks_total_tie():
    teams = ["A", "B", "C", "D"]
    matches = [("A", "B", 0, 0), ("A", "C", 0, 0), ("A", "D", 0, 0),
               ("B", "C", 0, 0), ("B", "D", 0, 0), ("C", "D", 0, 0)]   # todo empate total
    order = fe.rank_group(teams, matches, rng=random.Random(0),
                          fifa_ranking={"A": 10, "B": 5, "C": 20, "D": 1})
    assert order == ["D", "B", "A", "C"]                  # menor ranking FIFA = mejor

def test_rank_group_deterministic_with_seed():
    teams = ["A", "B", "C", "D"]
    matches = [("A", "B", 0, 0), ("A", "C", 0, 0), ("A", "D", 0, 0),
               ("B", "C", 0, 0), ("B", "D", 0, 0), ("C", "D", 0, 0)]   # todo empate → sorteo
    o1 = fe.rank_group(teams, matches, rng=random.Random(42))
    o2 = fe.rank_group(teams, matches, rng=random.Random(42))
    assert o1 == o2
    assert sorted(o1) == sorted(teams)


# ================= MEJORES TERCEROS =================
def test_rank_thirds_order():
    thirds = [("G1", 4, 1, 3), ("G2", 6, 2, 5), ("G3", 4, 2, 2), ("G4", 3, -2, 1)]
    order = fe.rank_thirds(thirds, rng=random.Random(0))
    assert order[0] == "G2"                              # más puntos
    assert order.index("G3") < order.index("G1")        # mismo pts, mejor dif
    assert order[-1] == "G4"

def test_rank_thirds_top8_count():
    thirds = [(f"G{i}", i, 0, 0) for i in range(12)]     # 12 terceros
    top8 = fe.rank_thirds(thirds, rng=random.Random(0))[:8]
    assert len(top8) == 8
    assert "G11" in top8 and "G0" not in top8            # mejores por puntos


# ================= ASIGNACIÓN OFICIAL DE TERCEROS =================
def test_assign_thirds_perfect_matching_all_combos():
    """En las 495 combinaciones de 8 grupos de 12, debe existir matching perfecto."""
    groups = list("ABCDEFGHIJKL")
    fails = 0
    for combo in combinations(groups, 8):
        res = fe.assign_thirds(set(combo))
        if len(res) != 8:
            fails += 1; continue
        # cada casilla recibe un grupo distinto y candidato válido
        if len(set(res.values())) != 8:
            fails += 1; continue
        for idx, grp in res.items():
            if grp not in fe.THIRD_PLACE_CANDIDATES[idx] or grp not in combo:
                fails += 1; break
    assert fails == 0, f"{fails} combinaciones sin matching perfecto"

def test_assign_thirds_eight_slots():
    res = fe.assign_thirds(set("ABCDEFGH"))
    assert set(res.keys()) == set(fe.THIRD_PLACE_CANDIDATES.keys())
