"""
format_engine.py — motor del formato nuevo (48 equipos) + colas y desempates.

Tres piezas, todas puras y testeables:

1) MUESTREO SOBREDISPERSO  — el Poisson puro subestima las goleadas (5-0, 6-0) que aparecen
   con 48 equipos (más mismatches). Se ofrece binomial negativa (Gamma-Poisson) parametrizada
   por media μ y dispersión r: Var = μ + μ²/r. Con r→∞ recupera Poisson. Mantiene la
   corrección Dixon-Coles para marcadores bajos.

2) DESEMPATES FIFA  — cascada oficial dentro de grupo:
   puntos → dif. de gol → goles a favor → (entre empatados) puntos/dif/gf head-to-head →
   fair play → sorteo. Incluye la resolución recursiva del subgrupo empatado (donde fallan
   la mayoría de los simuladores).

3) MEJORES TERCEROS  — ranking de los 12 terceros (puntos → dif → gf → fair play → sorteo)
   y asignación oficial de los 8 mejores a las casillas de la ronda de 32 (tabla candidatos).
"""
import math, random

# ============================================================
# 1) MUESTREO DE GOLES (Poisson / Binomial Negativa + Dixon-Coles)
# ============================================================
def poisson(lam, rng=random):
    """Muestrea Poisson(lam) por el método multiplicativo de Knuth."""
    if lam <= 0:
        return 0
    L = math.exp(-lam); k = 0; p = 1.0
    while True:
        k += 1; p *= rng.random()
        if p <= L:
            return k - 1

def negbin(mean, r, rng=random):
    """Muestrea Binomial Negativa con media `mean` y dispersión `r` (mezcla Gamma-Poisson).

    Var = mean + mean²/r. Con r grande → Poisson(mean). r debe ser > 0.
    """
    if mean <= 0:
        return 0
    if r is None or r == float("inf"):
        return poisson(mean, rng)
    if r <= 0:
        raise ValueError("r (dispersión) debe ser > 0")
    lam = rng.gammavariate(r, mean / r)   # λ' ~ Gamma(forma=r, escala=mean/r) → E[λ']=mean
    return poisson(lam, rng)

def poisson_pmf(k, lam):
    """P(X=k) para X~Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)

def negbin_pmf(k, mean, r):
    """P(X=k) para X~BinNeg con media `mean` y dispersión `r`."""
    if r is None or r == float("inf"):
        return poisson_pmf(k, mean)
    if mean <= 0:
        return 1.0 if k == 0 else 0.0
    p = r / (r + mean)                 # prob. de "éxito" en la parametrización estándar
    log_c = math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
    return math.exp(log_c + r * math.log(p) + k * math.log(1.0 - p))

def _pmf(k, mean, r):
    return poisson_pmf(k, mean) if (r is None or r == float("inf")) else negbin_pmf(k, mean, r)

def _dc_tau(x, y, lh, la, rho):
    """Factor de corrección Dixon-Coles para las celdas bajas (0/1)."""
    if x == 0 and y == 0: return 1.0 - lh * la * rho
    if x == 0 and y == 1: return 1.0 + lh * rho
    if x == 1 and y == 0: return 1.0 + la * rho
    if x == 1 and y == 1: return 1.0 - rho
    return 1.0

def sample_score(lh, la, rho=0.0, dispersion_r=None, rng=random):
    """Muestrea (gh, ga) con Poisson o BinNeg + corrección Dixon-Coles en marcadores bajos.

    lh, la       : goles esperados (λ) de local y visitante (ya ajustados por contexto).
    rho          : parámetro Dixon-Coles (correlación en marcadores bajos).
    dispersion_r : None/inf → Poisson; valor finito > 0 → Binomial Negativa (colas más gordas).
    Réplica de la lógica de sim20k.gm para conservar la calibración del modelo.
    """
    gh = negbin(lh, dispersion_r, rng); ga = negbin(la, dispersion_r, rng)
    if rho and gh <= 1 and ga <= 1:
        w = {}
        for x in (0, 1):
            for y in (0, 1):
                w[(x, y)] = max(0.0, _pmf(x, lh, dispersion_r) * _pmf(y, la, dispersion_r) * _dc_tau(x, y, lh, la, rho))
        tot = sum(w.values())
        if tot > 0:
            target = rng.random() * tot; acc = 0.0
            for cell, val in w.items():
                acc += val
                if acc >= target:
                    return cell
    return gh, ga

def negbin_loglik(lams, goals, r):
    """Log-verosimilitud total de `goals` bajo BinNeg(media=lam_i, dispersión=r). Para calibrar r."""
    s = 0.0
    for lam, k in zip(lams, goals):
        p = negbin_pmf(int(k), lam, r)
        s += math.log(p) if p > 0 else -1e9
    return s

def fit_dispersion(lams, goals, grid=None):
    """Estima la dispersión r que maximiza la log-verosimilitud BinNeg sobre (lams, goals).

    Devuelve (r_mejor, loglik_NB, loglik_Poisson). r grande ⇒ los datos no están sobredispersos.
    """
    if grid is None:
        grid = [2, 3, 4, 5, 6, 8, 10, 13, 17, 22, 30, 45, 70, 120, 300]
    best_r, best_ll = grid[0], negbin_loglik(lams, goals, grid[0])
    for r in grid[1:]:
        ll = negbin_loglik(lams, goals, r)
        if ll > best_ll:
            best_ll, best_r = ll, r
    ll_pois = sum(math.log(poisson_pmf(int(k), lam)) if poisson_pmf(int(k), lam) > 0 else -1e9
                  for lam, k in zip(lams, goals))
    return best_r, best_ll, ll_pois

# ============================================================
# 2) DESEMPATES FIFA (dentro de grupo, con head-to-head)
# ============================================================
def group_table(teams, matches):
    """Tabla acumulada {team: {pts,gf,ga,gd}} a partir de matches=[(a,b,ga,gb), ...]."""
    tab = {t: {"pts": 0, "gf": 0, "ga": 0, "gd": 0} for t in teams}
    for a, b, ga, gb in matches:
        if a not in tab or b not in tab:
            continue
        tab[a]["gf"] += ga; tab[a]["ga"] += gb
        tab[b]["gf"] += gb; tab[b]["ga"] += ga
        if ga > gb:   tab[a]["pts"] += 3
        elif gb > ga: tab[b]["pts"] += 3
        else:         tab[a]["pts"] += 1; tab[b]["pts"] += 1
    for t in teams:
        tab[t]["gd"] = tab[t]["gf"] - tab[t]["ga"]
    return tab

def _h2h_keys(subset, matches):
    """Mini-tabla head-to-head SOLO con los partidos entre los equipos de `subset`."""
    sub = [(a, b, ga, gb) for a, b, ga, gb in matches if a in subset and b in subset]
    return group_table(list(subset), sub)

def rank_group(teams, matches, fair_play=None, rng=None, fifa_ranking=None, h2h_first=True):
    """Ordena un grupo con la cascada oficial FIFA 2026 y devuelve la lista de equipos (1º→4º).

    Orden VERIFICADO (reglamento 2026):
      1) puntos
      2-4) si 2+ empatan en puntos → HEAD-TO-HEAD entre los empatados (pts → dif → gf)
      5-6) si persiste → global: dif. de gol → goles a favor
      7) fair play (menos descuentos de disciplina = mejor)
      8) ranking mundial FIFA previo / sorteo
    El head-to-head se RECALCULA en cada nivel sobre el subconjunto aún empatado (clave que
    la mayoría de los sims hace mal). Con h2h_first=False se usa el orden histórico (global antes
    de head-to-head), por si se valida cuál predice mejor.

    matches      : [(a, b, ga, gb), ...]
    fair_play    : {team: puntos_disciplina} (menos = mejor); por defecto 0.
    fifa_ranking : {team: posición} (menor = mejor); por defecto, se va al sorteo.
    rng          : random.Random para el sorteo reproducible.
    """
    fair_play = fair_play or {}
    fifa_ranking = fifa_ranking or {}
    rng = rng or random
    overall = group_table(teams, matches)
    lots = {t: rng.random() for t in teams}

    # cada criterio: subset -> {team: valor} (mayor = mejor). Los head-to-head se recalculan.
    C_points = lambda s: {t: overall[t]["pts"] for t in s}
    C_ov_gd  = lambda s: {t: overall[t]["gd"] for t in s}
    C_ov_gf  = lambda s: {t: overall[t]["gf"] for t in s}
    def C_h2h_pts(s): m = _h2h_keys(set(s), matches); return {t: m[t]["pts"] for t in s}
    def C_h2h_gd(s):  m = _h2h_keys(set(s), matches); return {t: m[t]["gd"] for t in s}
    def C_h2h_gf(s):  m = _h2h_keys(set(s), matches); return {t: m[t]["gf"] for t in s}
    C_fair = lambda s: {t: -fair_play.get(t, 0) for t in s}
    C_fifa = lambda s: {t: -fifa_ranking.get(t, 9999) for t in s}   # menor posición = mejor
    C_lots = lambda s: {t: lots[t] for t in s}                       # siempre desempata

    if h2h_first:   # FIFA 2026 (verificado)
        criteria = [C_points, C_h2h_pts, C_h2h_gd, C_h2h_gf, C_ov_gd, C_ov_gf, C_fair, C_fifa, C_lots]
    else:           # orden histórico (global antes de head-to-head)
        criteria = [C_points, C_ov_gd, C_ov_gf, C_h2h_pts, C_h2h_gd, C_h2h_gf, C_fair, C_fifa, C_lots]

    def resolve(subset, idx):
        if len(subset) == 1 or idx >= len(criteria):
            return list(subset)
        key = criteria[idx](subset)
        order = sorted(subset, key=lambda t: key[t], reverse=True)
        out = []
        i = 0
        while i < len(order):
            j = i + 1
            while j < len(order) and key[order[j]] == key[order[i]]:
                j += 1
            block = order[i:j]
            out.extend(resolve(block, idx + 1) if len(block) > 1 else block)
            i = j
        return out

    return resolve(list(teams), 0)

# ============================================================
# 3) MEJORES TERCEROS + ASIGNACIÓN OFICIAL A LA RONDA DE 32
# ============================================================
def rank_thirds(thirds, fair_play=None, rng=None, fifa_ranking=None):
    """Ordena los terceros de cada grupo (mejor → peor).

    thirds    : [(team, pts, gd, gf), ...] (un tercero por grupo)
    Criterios VERIFICADOS (2026): puntos → dif. de gol → goles a favor → fair play →
    ranking mundial FIFA → sorteo. NO hay head-to-head (los terceros son de grupos distintos
    y no se enfrentaron). Los 8 primeros de los 12 clasifican a la ronda de 32.
    """
    fair_play = fair_play or {}
    fifa_ranking = fifa_ranking or {}
    rng = rng or random
    lots = {t[0]: rng.random() for t in thirds}
    ordered = sorted(
        thirds,
        key=lambda x: (x[1], x[2], x[3], -fair_play.get(x[0], 0),
                       -fifa_ranking.get(x[0], 9999), lots[x[0]]),
        reverse=True,
    )
    return [t[0] for t in ordered]

# Conjuntos oficiales de grupos candidatos por casilla de tercero en la ronda de 32 (2026).
# Transcritos del cuadro oficial (mismos que sim_live_ko.R32_SLOTS). El backtracking de
# assign_thirds asigna, dada la combinación concreta de 8 grupos clasificados, qué tercero
# va a cada casilla — esto es lo que la mayoría de los sims hace mal.
THIRD_PLACE_CANDIDATES = {
    3:  frozenset("ABCDF"),
    6:  frozenset("CDFGH"),
    7:  frozenset("CEFHI"),
    8:  frozenset("EHIJK"),
    9:  frozenset("AEHIJ"),
    10: frozenset("BEFIJ"),
    13: frozenset("EFGIJ"),
    16: frozenset("DEIJL"),
}

def assign_thirds(qualified_groups, candidates=None):
    """Asigna los 8 grupos de los mejores terceros a sus 8 casillas de la ronda de 32.

    qualified_groups : iterable con las 8 letras de grupo cuyos terceros clasificaron.
    candidates       : {idx_R32: frozenset(grupos_candidatos)} (por defecto, tabla oficial).
    Devuelve {idx_R32: letra_grupo}. Usa backtracking (matching perfecto: menos candidatos
    primero). Si no hay matching perfecto (combinación imposible), reparte lo que quede.
    """
    candidates = candidates or THIRD_PLACE_CANDIDATES
    qualified = set(qualified_groups)
    slots = sorted(candidates.items(), key=lambda x: len(x[1]))  # menos candidatos primero
    res = {}

    def bt(i, used):
        if i == len(slots):
            return True
        idx, cands = slots[i]
        for grp in cands:
            if grp in qualified and grp not in used:
                res[idx] = grp; used.add(grp)
                if bt(i + 1, used):
                    return True
                used.discard(grp); del res[idx]
        return False

    if bt(0, set()):
        return res
    rem = [g for g in qualified if g not in res.values()]
    for idx, _ in slots:
        if idx not in res and rem:
            res[idx] = rem.pop()
    return res
