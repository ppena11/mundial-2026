"""
wc_form.py — actualización EN TORNEO: aprende de los partidos del Mundial ya jugados para mejorar
las predicciones de las rondas que faltan, leyendo el contexto como un experto ("ver el Mundial").

Idea: una goleada (6-0) suele estar DISTORSIONADA (expulsión del rival, garbage time) y dice menos
sobre la fuerza repetible que un 2-0 limpio. Así que al aprender de cada resultado:

  peso_partido = recencia × importancia(Mundial) × FIABILIDAD

donde FIABILIDAD baja con el margen (síntoma de distorsión, funciona SIEMPRE) y baja MÁS si hubo
una expulsión temprana (cuando hay datos de tarjetas). Esto evita sobre-reaccionar a un marcador
inflado —p. ej. Canadá 6-0 Catar— sin dejar de incorporar la información real del torneo.

Funciones puras (margin_reliability, reliability) con pruebas en test_wc_form.py.
"""
import json, os
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_REDCARD_CACHE = os.path.join(_HERE, "redcards_2026.json")

# Fiabilidad por margen de goles (robusta; no necesita datos de tarjetas).
# Margen ≤2: resultado plenamente informativo. Goleadas: cada vez menos (ruido/distorsión).
def margin_reliability(gh, ga):
    m = abs(int(gh) - int(ga))
    return {0: 1.0, 1: 1.0, 2: 1.0, 3: 0.90, 4: 0.78, 5: 0.66}.get(m, 0.55)


def red_card_reliability(red_minute):
    """Penalización extra si un equipo jugó con uno menos. Cuanto más temprana la roja, más
    distorsiona el marcador. red_minute = minuto de la primera expulsión (None si no hubo)."""
    if red_minute is None:
        return 1.0
    if red_minute <= 30:  return 0.55   # casi todo el partido con ventaja numérica
    if red_minute <= 60:  return 0.75
    if red_minute <= 80:  return 0.90
    return 1.0                          # roja en el descuento: no distorsiona el resultado


def reliability(gh, ga, red_minute=None):
    """Fiabilidad combinada de un resultado del Mundial para ACTUALIZAR ratings (0<r≤1).
    Toma el mínimo entre el efecto del margen y el de la roja (la distorsión que más pese)."""
    return min(margin_reliability(gh, ga), red_card_reliability(red_minute))


def _cache_read():
    """Lee la caché diaria de rojas: {frozenset({a,b}): minuto}. Vacío si no existe o es de otro día."""
    try:
        c = json.load(open(_REDCARD_CACHE, encoding="utf-8"))
        if c.get("date") == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            return {frozenset(k.split("|")): v for k, v in c.get("cards", {}).items()}
    except Exception:
        pass
    return None

def load_red_cards():
    """Minuto de la primera roja por partido: {frozenset({equipo_es,equipo_es}): minuto}.

    OFF por defecto (devuelve {}): la fiabilidad por MARGEN ya descuenta el marcador inflado (Canadá
    6-0 → 0.55) SIN gastar API. Activar con CF_REDCARDS=1 (refina el descuento con la roja real).
    Cuando está activa, CACHEA a redcards_2026.json y solo llama a API-Football UNA vez al día
    (la versión sin caché hacía ~100 llamadas por cada fit → reventaba la cuota en la nube)."""
    if os.environ.get("CF_REDCARDS", "0") not in ("1", "true", "True"):
        return {}
    cached = _cache_read()
    if cached is not None:
        return cached
    key = os.environ.get("API_FOOTBALL_KEY", "")
    if not key or key == "PEGA_TU_KEY_AQUI":
        return {}
    cards = {}
    try:
        import requests
        nm = json.load(open(os.path.join(_HERE, "namemap.json"), encoding="utf-8"))
        en2es = {en: es for es, en in nm.items()}
        fixtures = requests.get("https://v3.football.api-sports.io/fixtures",
                                headers={"x-apisports-key": key}, params={"league": 1, "season": 2026},
                                timeout=20).json().get("response", [])
        for fx in fixtures:
            if fx.get("fixture", {}).get("status", {}).get("short") not in ("FT", "AET", "PEN"):
                continue   # solo partidos terminados (acota las llamadas a eventos)
            ev = requests.get("https://v3.football.api-sports.io/fixtures/events",
                              headers={"x-apisports-key": key}, params={"fixture": fx["fixture"]["id"]},
                              timeout=20).json().get("response", [])
            home = en2es.get(fx["teams"]["home"]["name"], fx["teams"]["home"]["name"])
            away = en2es.get(fx["teams"]["away"]["name"], fx["teams"]["away"]["name"])
            mins = [e.get("time", {}).get("elapsed") for e in ev
                    if e.get("type") == "Card" and "Red" in str(e.get("detail", "")) and e.get("time", {}).get("elapsed") is not None]
            if mins:
                cards[frozenset((home, away))] = min(mins)
        # cachea (clave "a|b" porque JSON no admite frozenset)
        json.dump({"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                   "cards": {"|".join(sorted(k)): v for k, v in cards.items()}},
                  open(_REDCARD_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        return {}
    return cards
