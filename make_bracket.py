"""
make_bracket.py — exporta viral_bracket.json: el CUADRO REAL de la recta final del Mundial 2026
(cuartos → semis → final) leído EN VIVO de ESPN, para la infografía dinámica de Remotion (Bracket.tsx).

REGLAS:
  - Nada inventado: equipos, fechas, sedes y ganadores salen de la API de ESPN. El que AVANZA se toma
    del flag winner/advance (vale para partidos definidos en PENALES, donde el marcador queda empatado).
  - El árbol está VALIDADO contra ESPN (28-jun): SF1 = ganadores de QF1 y QF2; SF2 = QF3 y QF4;
    el orden nativo de los eventos de ESPN ES la numeración del cuadro.
  - El ESTADO se deriva solo de los datos (máquina de estados) — la corrida nocturna produce cada día
    el cuadro correcto sin tocar nada:
      QF_PENDIENTES → QF_EN_CURSO → SF_LISTAS → SF_EN_CURSO → FINAL_LISTA → CAMPEON
  - Si ESPN no responde o el estado es inconsistente, NO se sobrescribe el export anterior.

USO:  python make_bracket.py            ->  viral_bracket.json
"""
import sys, json
import daily_digest as dd

OUT = "viral_bracket.json"
_SLUGS = {"quarterfinals": "qf", "semifinals": "sf", "final": "final"}
_MES = {"06": "JUN", "07": "JUL"}
_PLACEHOLDER = ("Winner", "Loser", "Quarterfinal", "Semifinal", "Round", "TBD", "Place")
FINAL_SEDE_DEF = "MetLife Stadium"   # respaldo si el feed no trae la sede (final: 19-jul, Nueva York/NJ)


def _fecha_corta(iso):
    """'2026-07-09T19:00Z' -> '9 JUL' (solo datos del feed)."""
    try:
        return f"{int(iso[8:10])} {_MES.get(iso[5:7], '')}".strip()
    except Exception:
        return ""


def _team(nombre):
    """Nombre ES del modelo, o None si es placeholder ('Quarterfinal 1 Winner')."""
    if not nombre or any(p in nombre for p in _PLACEHOLDER):
        return None
    return dd.EN2ES.get(nombre, nombre)


def fetch_events():
    """Eventos QF/SF/Final de ESPN normalizados: [{slug, date, venue, a, b, ganador}] en ORDEN NATIVO
    (= numeración del cuadro). ganador = el que AVANZA (flag winner/advance), None si no se ha jugado."""
    out, seen = [], set()
    for rng in ("20260705-20260716", "20260714-20260725"):
        try:
            data = dd._get(f"{dd.ESPN}/scoreboard?dates={rng}")
        except Exception as e:
            print(f"(sin ESPN {rng}: {e})")
            continue
        for e in data.get("events", []):
            slug = e.get("season", {}).get("slug", "")
            if slug not in _SLUGS or e.get("id") in seen:
                continue
            seen.add(e.get("id"))
            comp = (e.get("competitions") or [{}])[0]
            cs = comp.get("competitors", [])
            if len(cs) != 2:
                continue
            nm = [_team(c.get("team", {}).get("displayName", "")) for c in cs]
            ganador = None
            if comp.get("status", {}).get("type", {}).get("state") == "post":
                w = next((c for c in cs if c.get("winner") or c.get("advance")), None)
                if w is not None:
                    ganador = _team(w.get("team", {}).get("displayName", ""))
            out.append({"slug": slug, "date": e.get("date", ""),
                        "venue": comp.get("venue", {}).get("fullName", ""),
                        "a": nm[0], "b": nm[1], "ganador": ganador})
    return out


def build(events=None):
    """Arma el dict del cuadro desde los eventos (o los baja de ESPN). None si el estado es inutilizable."""
    if events is None:
        events = fetch_events()
    qf = [e for e in events if e["slug"] == "quarterfinals"]
    sf = [e for e in events if e["slug"] == "semifinals"]
    fin = [e for e in events if e["slug"] == "final"]
    if len(qf) != 4 or sum(1 for e in qf if e["a"] and e["b"]) != 4:
        return None                      # cuartos aún sin definir del todo -> no hay cuadro que mostrar

    def _cruce(e):
        return {"a": dd.acc(e["a"]) if e["a"] else None, "b": dd.acc(e["b"]) if e["b"] else None,
                "fecha": _fecha_corta(e["date"]), "ganador": dd.acc(e["ganador"]) if e["ganador"] else None}

    QF = [_cruce(e) for e in qf]
    SF = [_cruce(e) for e in (sf + [{}] * 2)[:2] if e] or []
    while len(SF) < 2:
        SF.append({"a": None, "b": None, "fecha": "", "ganador": None})
    FIN = _cruce(fin[0]) if fin else {"a": None, "b": None, "fecha": "19 JUL", "ganador": None}

    # completar SF/Final con los GANADORES reales si el feed aún trae placeholders (árbol validado:
    # SF1 = W(QF1) vs W(QF2), SF2 = W(QF3) vs W(QF4), Final = W(SF1) vs W(SF2))
    for i, (x, y) in enumerate(((0, 1), (2, 3))):
        if not SF[i]["a"] and QF[x]["ganador"]: SF[i]["a"] = QF[x]["ganador"]
        if not SF[i]["b"] and QF[y]["ganador"]: SF[i]["b"] = QF[y]["ganador"]
    if not FIN["a"] and SF[0]["ganador"]: FIN["a"] = SF[0]["ganador"]
    if not FIN["b"] and SF[1]["ganador"]: FIN["b"] = SF[1]["ganador"]

    # máquina de estados (solo de los datos)
    nqf = sum(1 for c in QF if c["ganador"]); nsf = sum(1 for c in SF if c["ganador"])
    if FIN["ganador"]:   estado, ronda = "CAMPEON", "CAMPEÓN DEL MUNDO"
    elif nsf == 2:       estado, ronda = "FINAL_LISTA", "LA GRAN FINAL"
    elif nsf == 1:       estado, ronda = "SF_EN_CURSO", "SEMIFINALES"
    elif nqf == 4:       estado, ronda = "SF_LISTAS", "SEMIFINALES"
    elif nqf >= 1:       estado, ronda = "QF_EN_CURSO", "CUARTOS DE FINAL"
    else:                estado, ronda = "QF_PENDIENTES", "CUARTOS DE FINAL"

    f_iso = (fin[0]["date"] if fin else "")
    try:
        final_fecha = f"{int(f_iso[8:10])} DE {'JULIO' if f_iso[5:7] == '07' else 'JUNIO'}"
    except Exception:
        final_fecha = "19 DE JULIO"
    return {"estado": estado, "ronda": ronda, "final_fecha": final_fecha,
            "final_sede": (fin[0]["venue"] if fin and fin[0]["venue"] else FINAL_SEDE_DEF),
            "qf": QF, "sf": SF, "final": FIN}


def frase_cuadro(br):
    """Resumen de UNA línea del cuadro (dato para la voz de Claude — solo hechos)."""
    if not br: return ""
    if br["estado"] == "CAMPEON":
        return f"{br['final']['ganador']} es el campeón del mundo."
    if br["estado"] == "FINAL_LISTA":
        return f"La gran final: {br['final']['a']} contra {br['final']['b']}, el {br['final_fecha'].lower()}."
    pend = [c for c in br["qf"] if not c["ganador"]] if br["estado"].startswith("QF") else [c for c in br["sf"] if not c["ganador"] and c["a"] and c["b"]]
    cruces = "; ".join(f"{c['a']} contra {c['b']}" for c in pend if c["a"] and c["b"])
    ronda = "cuartos de final" if br["estado"].startswith("QF") else "semifinales"
    return f"Así está el cuadro rumbo a Nueva York — {ronda}: {cruces}."


if __name__ == "__main__":
    br = build()
    if br is None:
        print("(cuadro no disponible aún o feed inconsistente: viral_bracket.json queda como estaba)")
        sys.exit(0)
    json.dump(br, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"→ {OUT} guardado — estado {br['estado']} ({br['ronda']})")
    for c in br["qf"]:
        print(f"   QF {c['a']} vs {c['b']} [{c['fecha']}]" + (f"  -> avanza {c['ganador']}" if c["ganador"] else ""))
