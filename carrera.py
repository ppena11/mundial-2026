"""
carrera.py — GUION + textos del video CARRERA VIRAL (~45s): el explainer diario del bracket en la recta
final. Recorre las llaves EN ORDEN VISUAL (QF1→QF4 → semis → final) contando lo que YA PASÓ (resultado real
+ si la IA acertó, del predictions_log) y lo que VIENE (duelo con % del simulador), y cierra con el campeón
más probable. Las MENCIONES de equipos en ese orden son las ANCLAS de la cámara en Remotion (CarreraTour).

REGLAS: nada inventado (resultados de ESPN vía viral_bracket.json, aciertos del log, % del modelo);
Claude solo redacta. Sin partidos de cuadro definidos (pre-cuartos) sale limpio sin generar nada.

USO:  python carrera.py   ->  carrera_today.json, carrera_voiceover.txt, carrera_caption.txt, carrera_youtube.txt
      (la voz la genera después make_voice.py --in carrera_voiceover.txt --out carrera_voice.mp3)
"""
import os, sys, json
try:
    from env_loader import load_env; load_env()
except Exception:
    pass
try:
    import requests
except ImportError:
    requests = None
import daily_digest as dd

OUT_JSON = "carrera_today.json"

AI_CARRERA_SYS = (
    "Eres el guionista de @aiwithpedro, un creador que enseña inteligencia artificial. Es el video LA CARRERA "
    "AL TÍTULO del Mundial 2026: un tour por el cuadro de la recta final donde mi IA PRESUME su racha real y "
    "cuenta lo que YA PASÓ en cada llave y lo que ve para lo que viene. Te doy los datos EXACTOS. Devuelve "
    "EXCLUSIVAMENTE un objeto JSON (sin ``` ni texto extra) con EXACTAMENTE estas claves:\n"
    '"voz": guion HABLADO de 105 a 120 palabras (~45 segundos), tono narrador deportivo PRESUMIDO y con chispa '
    "— confiado, chulería simpática, jamás arrogancia pesada; que se sienta ÉPICO. ESTRUCTURA OBLIGATORIA: "
    "(1) GANCHO PRESUMIDO de 1-2 frases que ABRA con el DATO ESTRELLA de la racha tal cual te lo doy (p. ej. "
    "'cien por ciento de aciertos desde cuartos') e incluya la frase EXACTA 'la carrera al título' — presume "
    "que no es suerte, son cien mil simulaciones; "
    "(2) RECORRE LAS LLAVES EN EL MISMO ORDEN en que te las doy — una frase corta por llave y NOMBRA al menos "
    "un equipo de cada una (esas menciones sincronizan la cámara del video, NO cambies el orden ni te saltes "
    "ninguna); los números de LLAVE son etiquetas INTERNAS: JAMÁS digas la palabra 'llave' en la voz, nómbralas "
    "por sus equipos; en las jugadas presume el acierto (o admite el fallo con gracia); en las pendientes di el "
    "porcentaje del favorito como QUIEN YA SABE; "
    "(3) cierra con el CAMPEÓN más probable y su porcentaje, desafiante (p. ej. 'apúntenlo'); "
    "(4) CTA breve a suscribirse (canal de YouTube, link en bio) para ver si sigue la racha, y firma EXACTA: "
    "Soy éi ái uíz Pédro. Español con TODAS las tildes, sin emojis ni símbolos, números como cifras (el "
    "sistema los convierte). PROHIBIDO inventar números o resultados que no estén en los datos: presume SOLO "
    "con la RACHA REAL que te doy. PROHIBIDA la palabra 'campeonar' (no existe en español cuidado): di "
    "'quedar campeón', 'ser campeón' o 'levantar la copa'.\n"
    '"titulo": título viral (máx ~70 caracteres, máximo 1 emoji).\n'
    '"caption": caption corto para TikTok (1-2 líneas, 1-2 emojis, SIN hashtags).\n'
    '"hashtags": lista de EXACTAMENTE 5 hashtags virales (#Mundial2026 primero).\n'
    '"youtube_titulo": título para Shorts (~40-60 caracteres).\n'
    '"youtube_descripcion": 2 frases para Shorts.\n'
    '"youtube_hashtags": lista de 5 hashtags.\n'
    "DÍA y FASE: usa EXACTAMENTE los que vienen en los datos, NUNCA los deduzcas. Nada de apuestas."
)


def _racha():
    """Récord REAL en eliminatorias por ronda (predictions_log) — el material para PRESUMIR sin inventar.
    Devuelve {'por': {ronda:[h,n]}, 'total':[h,n], 'exactos':N, 'perfecta_desde':ronda, 'perfecta':[h,n]}."""
    import re as _re
    from collections import defaultdict
    try:
        rows = [json.loads(l) for l in open("predictions_log.jsonl", encoding="utf-8") if l.strip()]
    except Exception:
        return None
    ko = [r for r in rows if r.get("is_ko") and r.get("actual") is not None]
    if not ko:
        return None
    por = defaultdict(lambda: [0, 0])
    ORDEN = ["Dieciseisavos", "Octavos", "Cuartos", "Semifinal", "Final"]
    for r in ko:
        ron = _re.sub(r"\s*\d+$", "", r.get("label", "")) or "?"
        por[ron][1] += 1
        por[ron][0] += 1 if r.get("acierto_1x2") else 0
    tot = [sum(v[0] for v in por.values()), sum(v[1] for v in por.values())]
    exactos = sum(1 for r in ko if r.get("acierto_exacto"))
    perf, run = None, [0, 0]                      # racha 100% desde la ronda más temprana que se mantenga
    for ron in reversed([r for r in ORDEN if r in por]):
        h, n = por[ron]
        if h == n and n > 0:
            run = [run[0] + h, run[1] + n]; perf = ron
        else:
            break
    return {"por": dict(por), "total": tot, "exactos": exactos, "perfecta_desde": perf, "perfecta": run}


_RON_HABLADA = {"Dieciseisavos": "dieciseisavos", "Octavos": "octavos", "Cuartos": "cuartos de final",
                "Semifinal": "semifinales", "Final": "la final"}


def _linea_racha(rc):
    """Líneas de datos EXACTOS de la racha para el prompt (y el dato estrella para el gancho)."""
    if not rc:
        return [], ""
    L = ["RACHA REAL PARA PRESUMIR (calculada del historial; PROHIBIDO usar otros números):"]
    estrella = ""
    if rc["perfecta_desde"] and rc["perfecta"][1] >= 3:
        h, n = rc["perfecta"]
        estrella = (f"{h} de {n} aciertos desde {_RON_HABLADA.get(rc['perfecta_desde'], rc['perfecta_desde'])}: "
                    f"CIEN POR CIENTO")
        L.append(f"- DATO ESTRELLA (ábrelo con esto): {estrella}.")
    th, tn = rc["total"]
    L.append(f"- Eliminatorias completas: {th} de {tn} ({round(100 * th / tn)} por ciento).")
    for ron, (h, n) in rc["por"].items():
        L.append(f"  · {_RON_HABLADA.get(ron, ron)}: {h} de {n} ({round(100 * h / n)} por ciento).")
    if rc["exactos"]:
        L.append(f"- Marcadores EXACTOS clavados en eliminatorias: {rc['exactos']}.")
    return L, estrella


def _llaves(br):
    """Lista ordenada de llaves narrables: [(etiqueta, cruce, tipo)] tipo='jugada'|'pendiente'."""
    out = []
    for i, c in enumerate(br.get("qf") or [], 1):
        if c.get("a") and c.get("b"):
            out.append((f"CUARTOS {i}", c, "jugada" if c.get("ganador") else "pendiente"))
    for i, c in enumerate(br.get("sf") or [], 1):
        if c.get("a") and c.get("b"):
            out.append((f"SEMIFINAL {i}", c, "jugada" if c.get("ganador") else "pendiente"))
    f = br.get("final") or {}
    if f.get("a") and f.get("b"):
        out.append(("LA FINAL", f, "jugada" if f.get("ganador") else "pendiente"))
    return out


def _material(br, target):
    P = br.get("probs") or {}
    L = [f"Hoy es {dd.weekday_es(target)}, {target[6:8]}/{target[4:6]}/{target[0:4]}."]
    try:
        L.append(f"FASE ACTUAL DEL TORNEO: {dd.fase_actual(target)}.")
    except Exception:
        pass
    _rl, _ = _linea_racha(_racha())
    L.extend(_rl)
    L.append("LLAVES DEL CUADRO EN ORDEN (nárralas TODAS, numeradas, EXACTAMENTE en este orden — una frase "
             "cada una; los goles SIEMPRE en el orden en que te doy los equipos):")
    for _n, (et, c, tipo) in enumerate(_llaves(br), 1):
        lab = f"LLAVE {_n} · {et}"                 # etiqueta SOLO para ordenar; la lógica usa la ronda (et)
        if tipo == "jugada":
            ac = c.get("acierto")
            ac_txt = ("mi IA ACERTÓ el marcador EXACTO" if c.get("exacto")
                      else ("mi IA ACERTÓ el ganador" if ac else ("mi IA FALLÓ" if ac is False else "")))
            L.append(f"- {lab} (YA JUGADA): {c['a']} {c.get('marcador') or ''} {c['b']}; avanzó {c['ganador']}."
                     + (f" {ac_txt}." if ac_txt else ""))
        else:
            _k = "semis" if et.startswith("CUARTOS") else ("final" if et.startswith("SEMI") else "campeon")
            pa = P.get(c["a"], {}).get(_k, 0)
            pb = P.get(c["b"], {}).get(_k, 0)
            fav, fp = (c["a"], pa) if pa >= pb else (c["b"], pb)
            L.append(f"- {lab} (PENDIENTE, {c.get('fecha','')}): {c['a']} contra {c['b']}; "
                     f"mi modelo favorece a {fav} con {round(fp)} por ciento" +
                     (" de llegar a la final." if _k == "final" else " de avanzar."))
    if P and br.get("estado") != "CAMPEON":
        ch = max(P.items(), key=lambda kv: kv[1].get("campeon", 0))
        L.append(f"CAMPEÓN MÁS PROBABLE HOY: {ch[0]} con {round(ch[1]['campeon'])} por ciento.")
    if br.get("estado") == "CAMPEON" and (br.get("final") or {}).get("ganador"):
        L.append(f"CAMPEÓN DEL MUNDO: {br['final']['ganador']}. Es un tour retrospectivo de cómo se ganó.")
    try:
        tr = json.load(open("track_record.json", encoding="utf-8"))
        if tr.get("n"):
            L.append(f"Récord del modelo (credencial): {tr['aciertos_1x2']} de {tr['n']} aciertos.")
    except Exception:
        pass
    return "\n".join(L)


def _ai(material, extra=""):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return {}
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 800, "system": AI_CARRERA_SYS + extra,
                  "messages": [{"role": "user", "content": "Datos del cuadro:\n" + material}]}, timeout=45)
        if r.status_code != 200:
            print(f"(IA carrera no disponible: {r.status_code})"); return {}
        txt = r.json()["content"][0]["text"]
        return json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
    except Exception as e:
        print(f"(IA carrera falló: {e})"); return {}


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if c.isalnum() or c == " ")


def valida_voz(voz, br):
    """El guion DEBE recorrer TODAS las llaves EN ORDEN (cada una con la 1ª mención de alguno de sus equipos
    en posición creciente) — si no, la cámara del video se desincroniza. Devuelve lista de problemas ([] = ok)."""
    n = _norm(voz)
    problemas, pos = [], -1
    for i, (et, c, _t) in enumerate(_llaves(br), 1):
        cand = [x for x in (_norm(c.get("a")).split(" ")[0], _norm(c.get("b")).split(" ")[0]) if len(x) >= 3]
        hits = [n.find(w, pos + 1) for w in cand]
        hits = [h for h in hits if h >= 0]
        if not hits:
            problemas.append(f"la llave {i} ({c.get('a')} vs {c.get('b')}) no se menciona después de la anterior")
        else:
            pos = min(hits)
    if "llave" in n:
        problemas.append("dice 'llave' en la voz (etiqueta interna: nómbralo por los equipos)")
    return problemas


def _fallback_voz(br):
    """Respaldo SIN Claude: guion de plantilla con los mismos datos exactos (recorre las llaves en orden)."""
    _, estrella = _linea_racha(_racha())
    S = [(f"Mi inteligencia artificial lleva {estrella.lower().replace('CIEN POR CIENTO', 'cien por ciento')} "
          f"en la carrera al título del Mundial 2026." if estrella
          else "Así está la carrera al título del Mundial 2026 según mi inteligencia artificial.")]
    P = br.get("probs") or {}
    for et, c, tipo in _llaves(br):
        if tipo == "jugada":
            S.append(f"{c['a']} {(c.get('marcador') or '').replace('-', ' a ').replace('(pen.)', 'con penales')} "
                     f"{c['b']}, avanzó {c['ganador']}.")
        else:
            pa = P.get(c["a"], {}).get("semis", 0); pb = P.get(c["b"], {}).get("semis", 0)
            fav, fp = (c["a"], pa) if pa >= pb else (c["b"], pb)
            S.append(f"{c['a']} contra {c['b']}: mi modelo favorece a {fav} con {round(fp)} por ciento.")
    if P and br.get("estado") != "CAMPEON":
        ch = max(P.items(), key=lambda kv: kv[1].get("campeon", 0))
        S.append(f"Y el campeón más probable hoy es {ch[0]} con {round(ch[1]['campeon'])} por ciento.")
    S.append("Suscríbete a mi canal de YouTube y ve el análisis completo en el link de mi bio. Soy éi ái uíz Pédro.")
    return " ".join(S)


def build(target=None):
    from datetime import date
    target = target or date.today().strftime("%Y%m%d")
    try:
        br = json.load(open("viral_bracket.json", encoding="utf-8"))
    except Exception:
        print("(sin viral_bracket.json: no hay carrera que contar)"); return None
    if len(br.get("qf") or []) != 4:
        print("(cuadro sin cuartos definidos: la carrera arranca cuando haya llaves)"); return None
    mat = _material(br, target)
    ai = _ai(mat)
    voz = (ai.get("voz") or "").strip()
    probs_v = valida_voz(voz, br) if voz else ["sin voz"]
    if probs_v:                                     # el guion no recorre las llaves en orden -> UN reintento duro
        print(f"(guion inválido: {'; '.join(probs_v)}; reintento)")
        ai2 = _ai(mat, extra=" FALLASTE ANTES EN ESTO — CORRÍGELO SÍ O SÍ: narra LAS " +
                  f"{len(_llaves(br))} LLAVES numeradas, TODAS, UNA POR UNA y EN ESE ORDEN EXACTO, " +
                  "nombrando un equipo de cada una; nada de combinarlas ni adelantar rondas.")
        v2 = (ai2.get("voz") or "").strip()
        if v2 and not valida_voz(v2, br):
            ai, voz = ai2, v2
        else:
            print("(reintento inválido: uso el guion de PLANTILLA, que siempre recorre bien)")
            voz = ""
    voz = voz or _fallback_voz(br)
    try:
        from make_script import fix_team_hashtags as _fix, _limpiar_voz as _lv
        voz = _lv(voz) if callable(_lv) else voz
    except Exception:
        def _fix(x): return x
    if "Soy éi ái uíz Pédro" not in voz:            # firma de la marca GARANTIZADA (Claude a veces la omite)
        voz = voz.rstrip().rstrip(".") + ". Soy éi ái uíz Pédro."
    def _five(tags):
        base = ["#Mundial2026", "#IA", "#CarreraAlTitulo", "#futbol", "#parati"]
        seen, out = set(), []
        for t in _fix([str(x) for x in (tags or [])] + base):
            t = t if str(t).startswith("#") else "#" + str(t)
            if t not in seen:
                seen.add(t); out.append(t)
        return out[:5]
    tags = _five(ai.get("hashtags"))
    cap = ((ai.get("caption") or "La carrera al título del Mundial 2026, jugada por mi IA 🏆").strip()
           + " " + " ".join(tags))
    out = {"date": target, "titulo": ai.get("titulo") or "La carrera al título según mi IA 🏆",
           "voz": voz, "caption": cap, "hashtags": tags,
           "youtube_titulo": ai.get("youtube_titulo") or "La CARRERA AL TÍTULO del Mundial según la IA 🏆",
           "youtube_descripcion": ai.get("youtube_descripcion") or
               "Mi inteligencia artificial recorre el cuadro de la recta final: lo que pasó y lo que viene. "
               "Suscríbete para el análisis diario, link en la bio.",
           "youtube_hashtags": _five(ai.get("youtube_hashtags"))}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open("carrera_voiceover.txt", "w", encoding="utf-8").write(voz)
    open("carrera_caption.txt", "w", encoding="utf-8").write(cap)
    open("carrera_youtube.txt", "w", encoding="utf-8").write(
        out["youtube_titulo"] + "\n\n" + out["youtube_descripcion"] + "\n\n" + " ".join(out["youtube_hashtags"]))
    print(f"→ {OUT_JSON} + carrera_voiceover.txt + carrera_caption.txt + carrera_youtube.txt")
    return out


if __name__ == "__main__":
    r = build(sys.argv[1] if len(sys.argv) > 1 else None)
    sys.exit(0)
