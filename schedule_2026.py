"""
schedule_2026.py — calendario real del Mundial 2026 (sede + hora local) y derivación
de viaje/descanso/jet lag por equipo, para alimentar context_factors en el Monte Carlo.

FUENTE (no se inventa nada): openfootball/worldcup.json — dominio público; da fecha, hora
local (con offset UTC), grupo, sede (`ground`) y equipos de los 104 partidos. Se cachea en
schedule_2026.json para que el pipeline diario sea offline/determinista.

Lo que expone:
  * parse_kickoff("13:00 UTC-6") -> (13, -6.0)           [puro]
  * normalize(raw_matches, en2es) -> lista normalizada    [puro]
  * Schedule(matches): índice por par de equipos + cronología por equipo
       .factors_for(a, b)  -> (ground, kickoff_hour)      del partido de grupo a-b
       .travel_for(team, ground, date, utc_offset) -> {rest_days, km_travel, tz_change}
  * load(): carga (cache local -> red) y devuelve un Schedule listo.

El viaje se deriva del partido ANTERIOR de cada equipo en el calendario:
  km_travel  = great-circle entre la sede anterior y la actual (coords de context_factors)
  rest_days  = días entre ambos partidos
  tz_change  = offset_actual - offset_anterior  (positivo = hacia el ESTE = peor)
"""
import json, os, re, urllib.request
from datetime import date

import context_factors as cf

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = os.path.join(_HERE, "schedule_2026.json")
OPENFOOTBALL_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

# Alias de nombres de la fuente (inglés) -> español del modelo. Se completa con namemap.json.
_EXTRA_ALIASES = {
    "Bosnia & Herzegovina": "Bosnia", "Bosnia and Herzegovina": "Bosnia",
    "United States": "Estados Unidos", "USA": "Estados Unidos",
    "South Korea": "Corea del Sur", "Korea Republic": "Corea del Sur",
    "Czech Republic": "Chequia", "Czechia": "Chequia",
    "IR Iran": "Iran", "Türkiye": "Turquia", "Turkey": "Turquia",
    "Côte d'Ivoire": "Costa de Marfil", "Ivory Coast": "Costa de Marfil",
    "Cape Verde": "Cabo Verde", "DR Congo": "R.D. Congo",
}

def _en2es():
    try:
        nm = json.load(open(os.path.join(_HERE, "namemap.json"), encoding="utf-8"))
        m = {en: es for es, en in nm.items()}
    except Exception:
        m = {}
    m.update(_EXTRA_ALIASES)
    return m

# ============================================================
# Parsing puro
# ============================================================
_TIME_RE = re.compile(r"\s*(\d{1,2}):(\d{2})\s*UTC\s*([+-]\d{1,2})(?::?(\d{2}))?", re.I)

def parse_kickoff(time_str):
    """'13:00 UTC-6' -> (hora_local=13, offset_utc=-6.0). Devuelve (None,None) si no parsea."""
    if not time_str:
        return None, None
    m = _TIME_RE.match(time_str)
    if not m:
        m2 = re.match(r"\s*(\d{1,2}):(\d{2})", time_str)
        return (int(m2.group(1)), None) if m2 else (None, None)
    hour = int(m.group(1))
    off = float(int(m.group(3)))
    if m.group(4):
        off += (1 if off >= 0 else -1) * int(m.group(4)) / 60.0
    return hour, off

def is_group_round(round_str):
    """True si el `round` del feed es de fase de grupos (Matchday N)."""
    return bool(round_str) and str(round_str).lower().startswith("matchday")

def normalize(raw_matches, en2es=None):
    """Normaliza la lista cruda del feed a dicts con nombres en español y hora/offset parseados."""
    en2es = en2es if en2es is not None else _en2es()
    out = []
    for m in raw_matches:
        hour, off = parse_kickoff(m.get("time"))
        out.append({
            "date": m.get("date"),
            "hour": hour,
            "utc_offset": off,
            "round": m.get("round"),
            "group": m.get("group"),
            "ground": m.get("ground"),
            "team1": en2es.get(m.get("team1"), m.get("team1")),
            "team2": en2es.get(m.get("team2"), m.get("team2")),
            "is_group": is_group_round(m.get("round")),
        })
    return out

# ============================================================
# Índice consultable
# ============================================================
class Schedule:
    """Índice del calendario: par de equipos (grupo) y cronología por equipo."""

    def __init__(self, matches):
        self.matches = matches
        self.pair = {}        # frozenset({a,b}) -> match (solo fase de grupos)
        self.by_team = {}     # team -> [matches ordenados por fecha]
        for m in matches:
            a, b = m["team1"], m["team2"]
            if m["is_group"] and a and b:
                self.pair[frozenset((a, b))] = m
            for t in (a, b):
                if t:
                    self.by_team.setdefault(t, []).append(m)
        for t in self.by_team:
            self.by_team[t].sort(key=lambda x: (x["date"] or "", x["hour"] or 0))

    def factors_for(self, a, b):
        """(ground, kickoff_hour) del partido de grupo entre a y b, o (None, None)."""
        m = self.pair.get(frozenset((a, b)))
        if not m:
            return None, None
        return m["ground"], m["hour"]

    def _prev_match(self, team, before_date):
        prev = None
        for m in self.by_team.get(team, []):
            if m["date"] and before_date and m["date"] < before_date:
                prev = m
            else:
                break
        return prev

    def travel_for(self, team, ground, match_date, utc_offset):
        """Deriva {rest_days, km_travel, tz_change} para `team` que juega en `ground` en `match_date`.

        Usa el partido ANTERIOR del equipo. Si no hay anterior o faltan coords, devuelve None
        en los campos sin dato (no inventa). tz_change positivo = hacia el este.
        """
        prev = self._prev_match(team, match_date)
        if not prev:
            return None
        out = {"rest_days": None, "km_travel": 0.0, "tz_change": 0}
        # descanso
        try:
            if prev["date"] and match_date:
                out["rest_days"] = (date.fromisoformat(match_date) - date.fromisoformat(prev["date"])).days
        except Exception:
            pass
        # km entre sedes (coords de context_factors)
        v_now = cf.venue(ground); v_prev = cf.venue(prev["ground"])
        if v_now and v_prev and None not in (v_now.get("lat"), v_now.get("lon"), v_prev.get("lat"), v_prev.get("lon")):
            out["km_travel"] = cf.haversine(v_prev["lat"], v_prev["lon"], v_now["lat"], v_now["lon"])
        # husos (del propio feed): positivo = este
        if utc_offset is not None and prev["utc_offset"] is not None:
            out["tz_change"] = utc_offset - prev["utc_offset"]
        return out

    def travel_for_pair(self, a, b):
        """Devuelve (travel_a, travel_b) para el partido de grupo entre a y b (o (None,None))."""
        m = self.pair.get(frozenset((a, b)))
        if not m:
            return None, None
        ta = self.travel_for(a, m["ground"], m["date"], m["utc_offset"])
        tb = self.travel_for(b, m["ground"], m["date"], m["utc_offset"])
        return ta, tb

# ============================================================
# Carga (cache local -> red)
# ============================================================
def _fetch_raw():
    with urllib.request.urlopen(OPENFOOTBALL_URL, timeout=30) as fh:
        return json.load(fh).get("matches", [])

def load(prefer_cache=True, save_cache=True):
    """Devuelve un Schedule listo. Usa schedule_2026.json si existe; si no, baja y cachea.

    Si no hay red ni cache, devuelve un Schedule vacío (el modelo sigue sin factores de viaje).
    """
    raw = None
    if prefer_cache and os.path.exists(_CACHE):
        try:
            raw = json.load(open(_CACHE, encoding="utf-8"))
        except Exception:
            raw = None
    if raw is None:
        try:
            raw = _fetch_raw()
            if save_cache:
                try:
                    json.dump(raw, open(_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                except Exception:
                    pass
        except Exception:
            raw = []
    return Schedule(normalize(raw))


if __name__ == "__main__":
    s = load()
    g = sum(1 for m in s.matches if m["is_group"])
    print(f"Calendario cargado: {len(s.matches)} partidos ({g} de grupo, {len(s.pair)} pares indexados)")
    # muestra los partidos en sedes de altura (México)
    for m in s.matches:
        if m["is_group"] and m["ground"] in ("Mexico City", "Guadalajara (Zapopan)"):
            print(f"  {m['date']} {str(m['hour']):>4}h  {m['team1']} vs {m['team2']}  @ {m['ground']}")
