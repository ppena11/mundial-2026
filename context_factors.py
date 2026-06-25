"""
context_factors.py — capas de contexto físico del Mundial 2026 sobre el λ del modelo.

Implementa los multiplicadores que se enchufan al Monte Carlo:

    λ_ajustado = λ_base × f_alt × f_calor × f_viaje

1) ALTURA  (f_alt)   — caída aeróbica del equipo NO aclimatado por encima de ~1500 m.
2) CALOR   (f_calor) — carga térmica (proxy WBGT) que comprime ambos λ; se apaga con techo+aire.
3) VIAJE   (f_viaje) — fatiga por días de descanso, km recorridos y husos cruzados (este peor).

DISCIPLINA (del diseño del modelo):
  * Todos los multiplicadores están ACOTADOS a [0.90, 1.08]. Nunca más.
  * Cada capa se VALIDA con RPS fuera de muestra (validate_layers.py). Si no mejora, se apaga
    poniendo su flag en CONFIG (context_config.json) o pasando enabled=False.
  * Los DATOS del mundo real (elevaciones, techos, coordenadas, husos, bases de aclimatación)
    viven en wc2026_context.json, cada valor con su fuente. Aquí solo va la LÓGICA.

Las funciones núcleo (f_altitude, f_heat, f_travel, haversine) son puras y deterministas:
no leen archivos ni dependen de los datos, así se prueban con entradas sintéticas.
"""
import json, math, os

_HERE = os.path.dirname(os.path.abspath(__file__))

# Overrides por entorno SOLO para auditoría/ablación (ablation.py). Si la variable no está,
# se usa el default de producción IDÉNTICO — no cambia nada en el pipeline normal.
def _env_flag(name, default):
    v = os.environ.get(name)
    return default if v is None else (v not in ("0", "false", "False", ""))

def _env_float(name, default):
    v = os.environ.get(name)
    if v is None:
        return default
    if v.lower() == "none":
        return None
    return float(v)

# ============================================================
# Cotas globales (la disciplina del diseño: nunca castigar/premiar de más)
# ============================================================
CLAMP_LO = 0.90
CLAMP_HI = 1.08

def clamp(x, lo=CLAMP_LO, hi=CLAMP_HI):
    """Acota un multiplicador al rango permitido [0.90, 1.08]."""
    return lo if x < lo else (hi if x > hi else x)

# ============================================================
# CONFIG de capas: qué se aplica en el Monte Carlo (sim_live / predict_match).
# Se ajusta tras validar con validate_layers.py. Disciplina: si una capa no mejora
# el RPS fuera de muestra, se apaga aquí (sin piedad).
# ============================================================
USE_ALTITUDE = _env_flag("CF_ALT", True)     # altura: validada contra RPS histórico (CONMEBOL)
USE_HEAT = _env_flag("CF_HEAT", True)        # calor: efecto ~neutro en goles; compresión simétrica
USE_TRAVEL = _env_flag("CF_TRAVEL", True)    # viaje/jet lag: calibrado por literatura (este peor)
DISPERSION_R = _env_float("CF_DISP", 17)     # binomial negativa (colas): r=17 validado OOS.
                                             # None/Poisson si CF_DISP=none.

# Nivel de goles mundialista: el modelo entrena con amistosos/eliminatorias (más defensivos) y
# SUBESTIMA los goles del Mundial. Multiplicador simétrico sobre ambos λ, VALIDADO en el held-out
# de 5 Mundiales (2010-2022 + 2026 hasta hoy): calibra los goles (previstos→reales) y mejora el RPS.
# mu=1.15 iguala goles previstos≈reales (2.57) sin sobreinflar. 1.0 = desactivado.
WC_GOAL_LEVEL = _env_float("CF_GOAL", 1.15)

# ============================================================
# Geografía
# ============================================================
_EARTH_KM = 6371.0088  # radio medio terrestre (IUGG)

def haversine(lat1, lon1, lat2, lon2):
    """Distancia great-circle en km entre dos puntos (grados decimales)."""
    p1 = math.radians(lat1); p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_KM * math.asin(min(1.0, math.sqrt(a)))

# ============================================================
# 1) ALTURA
# ============================================================
# f_alt = 1 - k · max(0, (elev_sede - elev_base)/1000)   solo si la sede está sobre ~1500 m.
# Equipo de nivel del mar en el Azteca (~2240 m): 1 - 0.04·2.24 ≈ 0.910 (piso 0.90).
# Equipo nativo de altura: gap≈0 → ≈1.0 (no sufre), y opcionalmente un pequeño plus ofensivo.
ALT_K = 0.04            # caída fraccional por cada 1000 m de desventaja de aclimatación
ALT_THRESHOLD = 1500.0  # la altura solo pesa por encima de este umbral (m)
ALT_FLOOR = 0.90        # piso del multiplicador de altura
ALT_BOOST_K = 0.02      # "un pelín" al equipo más aclimatado (≤ +0.08 por la cota global)

def f_altitude(elev_venue, elev_base, k=ALT_K, threshold=ALT_THRESHOLD, floor=ALT_FLOOR):
    """Multiplicador de altura sobre el λ OFENSIVO de UN equipo, según SU base de aclimatación.

    elev_venue : elevación de la sede (m)
    elev_base  : elevación de la base de aclimatación del equipo (m)
    Devuelve 1.0 si la sede no está por encima del umbral (no hay efecto de altura).
    """
    if elev_venue <= threshold:
        return 1.0
    gap_km = max(0.0, (elev_venue - elev_base) / 1000.0)
    return max(floor, 1.0 - k * gap_km)

def f_altitude_pair(elev_venue, elev_home_base, elev_away_base,
                    k=ALT_K, threshold=ALT_THRESHOLD, floor=ALT_FLOOR,
                    boost_k=ALT_BOOST_K, boost=True):
    """Devuelve (mult_home, mult_away) de altura para un partido en una sede.

    Cada equipo recibe su penalización según su propia base. Si boost=True, al equipo MÁS
    aclimatado se le suma un pequeño plus proporcional a la diferencia de aclimatación
    (acotado por la cota global), tal como pide el diseño ("le subes un pelín al nativo").
    """
    mh = f_altitude(elev_venue, elev_home_base, k, threshold, floor)
    ma = f_altitude(elev_venue, elev_away_base, k, threshold, floor)
    if boost and elev_venue > threshold and boost_k > 0:
        # diferencia de aclimatación: base más alta = más aclimatado
        diff_km = (elev_home_base - elev_away_base) / 1000.0
        if diff_km > 0:    # local más aclimatado
            mh = clamp(mh * (1.0 + boost_k * diff_km))
        elif diff_km < 0:  # visitante más aclimatado
            ma = clamp(ma * (1.0 - boost_k * diff_km))
    return clamp(mh), clamp(ma)

# ============================================================
# 2) CALOR (carga térmica, proxy WBGT)
# ============================================================
# La dirección del efecto del calor sobre los goles es ambigua. El movimiento limpio:
# comprimir AMBOS λ un poco (menos ritmo del favorito → menos goles totales → más empates
# y más varianza relativa). Se APAGA con techo cerrado + aire (clima controlado).
HEAT_SEVERITY = {"low": 0.0, "moderate": 0.4, "high": 0.7, "extreme": 1.0}
HEAT_MAX_COMPRESSION = 0.06   # compresión máxima de λ (→ multiplicador 0.94) en lo más duro

def _hour_heat_weight(kickoff_hour):
    """Peso del horario: el golpe real es mediodía/tarde (12:00–17:00); de noche ~0."""
    if kickoff_hour is None:
        return 0.6   # desconocido: peso moderado
    h = kickoff_hour
    if 12 <= h < 16:   return 1.0    # lo más caliente del día
    if 16 <= h < 18:   return 0.8
    if 10 <= h < 12:   return 0.6
    if 18 <= h < 20:   return 0.4
    return 0.1                        # mañana temprano / noche

def f_heat(heat_risk, roof, effective_ac, kickoff_hour,
           max_compression=HEAT_MAX_COMPRESSION):
    """Multiplicador SIMÉTRICO de calor (se aplica a AMBOS λ).

    heat_risk    : 'low' | 'moderate' | 'high' | 'extreme'  (riesgo WBGT de la sede en verano)
    roof         : 'open' | 'retractable' | 'fixed'
    effective_ac : True si en verano se juega con techo cerrado + aire (clima controlado)
    kickoff_hour : hora local de inicio (0–23) o None
    Devuelve un multiplicador en [1-max_compression, 1.0]. 1.0 = sin efecto.
    """
    if effective_ac:
        return 1.0                       # clima controlado: el factor se apaga
    sev = HEAT_SEVERITY.get(heat_risk, 0.0)
    if sev <= 0:
        return 1.0
    w = _hour_heat_weight(kickoff_hour)
    return clamp(1.0 - max_compression * sev * w)

# ============================================================
# 3) VIAJE, DESCANSO Y JET LAG
# ============================================================
# Tres features por equipo y partido (derivables del calendario):
#   rest_days  : días de descanso desde su partido anterior
#   km_travel  : distancia great-circle desde su sede anterior
#   tz_change  : husos cruzados desde el último partido (positivo = hacia el ESTE = peor)
# Se mapean a una penalización de fatiga sobre el λ del equipo (cada equipo el suyo).
REST_REF = 4.0          # días de descanso "normales" en fase de grupos
TRAVEL_PIVOT_KM = 1000.0
FATIGUE_K_REST = 0.010  # penalización por día de descanso por debajo de REST_REF
FATIGUE_K_KM = 0.010    # penalización por cada 1000 km recorridos
FATIGUE_K_TZ_EAST = 0.008  # penalización por huso cruzado hacia el este
FATIGUE_K_TZ_WEST = 0.004  # hacia el oeste (la mitad: está documentado que es menos duro)
FATIGUE_FLOOR = 0.90

def f_travel(rest_days, km_travel, tz_change,
             rest_ref=REST_REF, floor=FATIGUE_FLOOR):
    """Multiplicador de fatiga sobre el λ ofensivo de UN equipo.

    rest_days : días de descanso desde el partido anterior (None = sin dato → sin efecto)
    km_travel : km recorridos desde la sede anterior (0 si no se movió)
    tz_change : husos cruzados con signo (+este peor, -oeste menos malo)
    Devuelve un multiplicador en [floor, 1.0].
    """
    pen = 0.0
    if rest_days is not None:
        pen += FATIGUE_K_REST * max(0.0, rest_ref - rest_days)
    if km_travel:
        pen += FATIGUE_K_KM * (max(0.0, km_travel) / TRAVEL_PIVOT_KM)
    if tz_change:
        if tz_change > 0:   pen += FATIGUE_K_TZ_EAST * tz_change
        else:               pen += FATIGUE_K_TZ_WEST * (-tz_change)
    return max(floor, 1.0 - pen)

# ============================================================
# DATOS VERIFICADOS (sedes + bases de aclimatación) — cargados de wc2026_context.json
# ============================================================
_CONTEXT_FILE = os.path.join(_HERE, "wc2026_context.json")

def load_context(path=_CONTEXT_FILE):
    """Carga el JSON de datos verificados {venues:{ground:{...}}, teams:{team_es:{...}}}.

    Devuelve {} si no existe (el modelo sigue funcionando sin factores de contexto).
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}

# Caché perezosa
_CTX = None
def ctx():
    global _CTX
    if _CTX is None:
        _CTX = load_context()
    return _CTX

def venue(ground):
    """Propiedades de una sede por su clave 'ground' del calendario (o None)."""
    return ctx().get("venues", {}).get(ground)

def team_base(team_es):
    """Base de aclimatación de una selección por su nombre en español (o None)."""
    return ctx().get("teams", {}).get(team_es)

# ============================================================
# COMBINADOR: factores de UN partido
# ============================================================
def match_factors(home, away, ground, kickoff_hour=None,
                  home_travel=None, away_travel=None,
                  enable_alt=True, enable_heat=True, enable_travel=True):
    """Devuelve (fh, fa): multiplicadores totales sobre (λ_home, λ_away) de un partido.

        fh = f_alt_home × f_calor × f_viaje_home
        fa = f_alt_away × f_calor × f_viaje_away    (f_calor es simétrico)

    home, away : nombres en español (claves de namemap / wc2026_context.teams)
    ground     : clave de sede del calendario (claves de wc2026_context.venues)
    kickoff_hour : hora local de inicio (0–23) o None
    home_travel / away_travel : dict {rest_days, km_travel, tz_change} o None
    Si faltan datos de una capa, esa capa devuelve 1.0 (no inventa).
    """
    fh = fa = 1.0
    v = venue(ground)

    # --- altura ---
    if enable_alt and v is not None and v.get("elevation_m") is not None:
        bh = team_base(home); ba = team_base(away)
        eh = bh.get("base_elevation_m") if bh else None
        ea = ba.get("base_elevation_m") if ba else None
        if eh is not None and ea is not None:
            mh, ma = f_altitude_pair(v["elevation_m"], eh, ea)
            fh *= mh; fa *= ma

    # --- calor (simétrico) ---
    if enable_heat and v is not None:
        fc = f_heat(v.get("summer_afternoon_heat_risk", "low"),
                    v.get("roof", "open"),
                    v.get("effective_ac_during_play", False),
                    kickoff_hour)
        fh *= fc; fa *= fc

    # --- viaje (cada equipo el suyo) ---
    if enable_travel:
        if home_travel:
            fh *= f_travel(home_travel.get("rest_days"),
                           home_travel.get("km_travel", 0.0),
                           home_travel.get("tz_change", 0))
        if away_travel:
            fa *= f_travel(away_travel.get("rest_days"),
                           away_travel.get("km_travel", 0.0),
                           away_travel.get("tz_change", 0))

    return clamp(fh), clamp(fa)
