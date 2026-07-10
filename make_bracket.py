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
    """'2026-07-09T19:00Z' -> '9 JUL' en día ET (todo el pipeline habla en ET; un juego a las 9 PM ET del 11
    es 12-jul en UTC y mostraba el día equivocado)."""
    try:
        d = dd.et_date(iso) or iso[:10]
        return f"{int(d[8:10])} {_MES.get(d[5:7], '')}".strip()
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
            ganador = None; marcador = None
            if comp.get("status", {}).get("type", {}).get("state") == "post":
                w = next((c for c in cs if c.get("winner") or c.get("advance")), None)
                if w is not None:
                    ganador = _team(w.get("team", {}).get("displayName", ""))
                try:
                    ga, gb = int(cs[0].get("score", 0)), int(cs[1].get("score", 0))
                    marcador = f"{ga}-{gb}" + (" (pen.)" if ga == gb else "")   # empate reglamentario = penales
                except Exception:
                    pass
            out.append({"slug": slug, "date": e.get("date", ""),
                        "venue": comp.get("venue", {}).get("fullName", ""),
                        "a": nm[0], "b": nm[1], "ganador": ganador, "marcador": marcador})
    return out


def _acierto_de(a, b, iso):
    """(acierto_1x2, acierto_exacto) del pronóstico REGISTRADO para ese cruce (predictions_log.jsonl),
    o (None, None) si no se registró. a/b SIN acentos (nombres del modelo); iso 'YYYY-MM-DD'."""
    try:
        key = f"{iso}|" + "|".join(sorted([a, b]))
        for l in open("predictions_log.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if r.get("key") == key and r.get("actual") is not None:
                return bool(r.get("acierto_1x2")), bool(r.get("acierto_exacto"))
    except Exception:
        pass
    return None, None


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
        c = {"a": dd.acc(e["a"]) if e["a"] else None, "b": dd.acc(e["b"]) if e["b"] else None,
             "fecha": _fecha_corta(e["date"]), "ganador": dd.acc(e["ganador"]) if e["ganador"] else None,
             "marcador": e.get("marcador")}
        if e.get("ganador") and e.get("a") and e.get("b"):     # cruce JUGADO: ¿la IA lo acertó?
            iso = dd.et_date(e.get("date", "")) or e.get("date", "")[:10]
            c["acierto"], c["exacto"] = _acierto_de(e["a"], e["b"], iso)
        return c

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
    out = {"estado": estado, "ronda": ronda, "final_fecha": final_fecha,
           "final_sede": (fin[0]["venue"] if fin and fin[0]["venue"] else FINAL_SEDE_DEF),
           "qf": QF, "sf": SF, "final": FIN}
    out["probs"] = _probs_vivos(out)   # P(semis/final/campeón) por equipo VIVO — la CARRERA AL TÍTULO del bracket
    return out


def _probs_vivos(br):
    """{equipo_acentuado: {semis, final, campeon}} para los equipos AÚN VIVOS del cuadro, desde champ_today.json
    (100.000 simulaciones condicionadas al torneo real). {} si el simulador aún no exporta las rondas."""
    try:
        ch = json.load(open("champ_today.json", encoding="utf-8"))
    except Exception:
        return {}
    semis, final, camp = ch.get("semis") or {}, ch.get("final") or {}, ch.get("campeon") or {}
    if not camp or not semis or not final:
        return {}   # simulador viejo sin rondas (o export corrupto): sin probs no hay carrera (mejor que 0%)
    if str(ch.get("fase", "")).startswith("PRE-TORNEO"):
        return {}   # estado regresado a PRE-TORNEO con el torneo andando = datos NO condicionados: no publicar
    vivos = set()
    for c in br["qf"] + br["sf"] + [br["final"]]:
        for k in ("a", "b"):
            if c.get(k): vivos.add(c[k])
    eliminados = {c[k] for c in br["qf"] + br["sf"] for k in ("a", "b")
                  if c.get(k) and c.get("ganador") and c["ganador"] != c[k]}
    vivos -= eliminados
    out = {}
    for t, cp in camp.items():
        ta = dd.acc(t)
        if ta in vivos:
            out[ta] = {"semis": round(float(semis.get(t, 0)), 1), "final": round(float(final.get(t, 0)), 1),
                       "campeon": round(float(cp), 1)}
    return out


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


def frase_carrera(br):
    """UNA línea con la CARRERA AL TÍTULO simulada (datos del modelo, nada inventado): favorito de cada llave
    pendiente + campeón más probable con su %. Contiene la palabra 'carrera' (ancla de la escena en Remotion)."""
    if not br or not br.get("probs") or br.get("estado") == "CAMPEON":
        return ""
    P = br["probs"]
    def fav(c):
        if not (c.get("a") and c.get("b")) or c.get("ganador"): return None
        pa, pb = P.get(c["a"], {}).get("semis", 0), P.get(c["b"], {}).get("semis", 0)
        if br["estado"] not in ("QF_PENDIENTES", "QF_EN_CURSO"):   # en semis la P relevante es llegar a la final
            pa, pb = P.get(c["a"], {}).get("final", 0), P.get(c["b"], {}).get("final", 0)
        return (c["a"], pa) if pa >= pb else (c["b"], pb)
    cruces = br["qf"] if br["estado"].startswith("QF") else br["sf"]
    favs = [f for f in (fav(c) for c in cruces) if f]
    champ = max(P.items(), key=lambda kv: kv[1].get("campeon", 0)) if P else None
    partes = []
    if favs:
        partes.append("mi modelo ve avanzando a " + ", ".join(f"{t} ({round(p)} por ciento)" for t, p in favs))
    if champ:
        partes.append(("y " if partes else "") + f"el campeón más probable hoy es {champ[0]} con "
                      f"{round(champ[1]['campeon'])} por ciento")   # sin favs (final lista) la frase abre limpia
    return ("En la carrera al título, " + "; ".join(partes) + ".") if partes else ""


if __name__ == "__main__":
    br = build()
    if br is None:
        print("(cuadro no disponible aún o feed inconsistente: viral_bracket.json queda como estaba)")
        sys.exit(0)
    json.dump(br, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"→ {OUT} guardado — estado {br['estado']} ({br['ronda']})")
    for c in br["qf"]:
        print(f"   QF {c['a']} vs {c['b']} [{c['fecha']}]" + (f"  -> avanza {c['ganador']}" if c["ganador"] else ""))
