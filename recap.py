"""
recap.py — MOTOR DEL "CIERRE DEL DÍA": confronta el pronóstico de la mañana con el resultado real.
Segundo contenido diario de @aiwithpedro (credibilidad: mostramos aciertos Y fallos).

Usa lo que ya registra track_record.py (pick, p1/pX/p2, marcador previsto) + el resultado real ya
calificado. Genera recap_today.json (cacheado por fecha), recap_voiceover.txt y recap_caption.txt;
en __main__ también recap_digest.md/html. La voz/tarjeta/caption cuentan exactamente lo mismo.

Regla de oro (igual que el resto): los NÚMEROS salen del log calificado (exactos); Claude solo
redacta el gancho. NUNCA inventar resultados ni cifras.

USO:  python recap.py [--date YYYYMMDD]   (por defecto: AYER en hora del Este)
"""
import sys, os, json, re
from datetime import datetime, timedelta, date
import daily_digest as dd
import predict_match as pm
import track_record as tr
try:
    import requests
except ImportError:
    requests = None
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

BRAND = "aiwithpedro"
BRAND_VOZ = "éi ái uíz Pédro"   # cómo se pronuncia @aiwithpedro en la voz (ElevenLabs)
KICKOFF = date(2026, 6, 11)     # día inaugural del Mundial 2026
RECAP_FILE = "recap_today.json"
DISCLAIMER = "Contenido informativo y de entretenimiento. Predicciones de un modelo, no certezas."

def yesterday_et():
    now_utc = datetime.utcnow()
    et_today = (now_utc + dd.ET_OFFSET).date()
    return (et_today - timedelta(days=1)).strftime("%Y%m%d")

def _iso(yyyymmdd): return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"

# ---------- Claude (gancho viral) ----------
AI_RECAP_SYS = (
    "Eres el guionista y editor de @aiwithpedro, un creador que enseña inteligencia artificial. "
    "DATO FIJO: el Mundial 2026 arrancó el 11 de junio de 2026; respeta esa cronología. "
    "DÍA DE LA SEMANA: el día correcto está en los datos ('Anoche fue …'); si nombras el día, usa EXACTAMENTE ese, NUNCA lo deduzcas. "
    "Es el CIERRE DEL DÍA "
    "del Mundial 2026: confrontamos el pronóstico de la mañana con lo que de verdad pasó. Te doy los datos EXACTOS "
    "(aciertos, fallos, marcadores, récord). Devuelve EXCLUSIVAMENTE un objeto JSON (sin ``` ni texto extra) con "
    "EXACTAMENTE estas claves:\n"
    '"titulo": título viral para el post (máx ~70 caracteres, con gancho, máximo 1 emoji).\n'
    '"gancho": 1 o 2 frases para el digest; engancha con cómo nos fue (acierto destacado o sorpresa).\n'
    '"voz": guion HABLADO que REPASA TODOS los partidos de anoche, uno por uno, ágil y con ritmo (UNA frase corta '
    "por partido: el marcador real + si ACERTAMOS o FALLAMOS; NO te alargues en ninguno). NO metas resultados de "
    "OTROS días. Tono de narrador con PERSONALIDAD. Estructura: "
    "(1) GANCHO de UNA frase con el récord de anoche ('acertamos X de Y'), directo, sin frases vagas tipo 'noche de "
    "luces y sombras'; (2) RECORRE CADA partido con su marcador real y si acertamos o fallamos —VARIANDO cómo lo "
    "dices, con HUMILDAD en los fallos y una pizca de orgullo en los aciertos—, sin omitir ninguno; (3) récord "
    "acumulado NATURAL ('vamos 18 de 32 aciertos', SIN palabras inventadas como 'predecidos'); (4) teaser BREVE de mañana; (5) una "
    "frase MEMORABLE y FLUIDA con chispa de tu marca de IA (COMPLETA, sin contrastes cortados/elípticos que suenen "
    "a pausa forzada; original, no copies ejemplos). CIERRE OBLIGATORIO (NUNCA lo omitas, aunque tengas que recortar lo demás): "
    "invita a SUSCRIBIRSE a mi canal de YouTube y a ver el cierre en el link de mi bio (NO nombres 'Substack' en la "
    "voz) y firma la voz diciendo EXACTAMENTE: "
    "Soy éi ái uíz Pédro (así se pronuncia @aiwithpedro). La despedida ('nos vemos mañana') y la firma van como "
    "FRASES SEPARADAS con PUNTO, NUNCA pegadas con coma (mal: 'Pédro, nos vemos mañana'; bien: 'Nos vemos mañana. "
    "Soy éi ái uíz Pédro.'). SIN emojis ni símbolos "
    "(lo lee un sintetizador de voz); números con dígitos y marcadores como '3 a 0' (NUNCA '3-0').\n"
    '"caption": 1 o 2 líneas para YouTube Shorts, con gancho; puede llevar 1 o 2 emojis; NO incluyas hashtags aquí.\n'
    '"hashtags": lista de EXACTAMENTE 5 hashtags virales; incluye #Mundial2026, #IA y #parati.\n'
    + dd.VIRAL_TITULO + dd.VIRAL_DESC +
    '"youtube_hashtags": lista de EXACTAMENTE 5 hashtags buscables para YouTube; incluye #Mundial2026 y #Shorts.\n'
    "Tono honesto y cercano (mostrar fallos suma credibilidad), apto para todo público, nada de apuestas. "
    "NO metas resultados de contexto (otros días) en la VOZ: la brevedad manda; ese contexto va en el digest/caption, no en la voz. "
    "Usa SOLO los datos dados; NUNCA inventes números ni marcadores. "
    "CUIDA LA GRAMÁTICA y la CONCORDANCIA sujeto-verbo (revisa cada frase); frases bien construidas, sin errores. "
    "ESCRIBE EN ESPAÑOL CON TODAS LAS TILDES Y SIGNOS CORRECTOS (á, é, í, ó, ú, ñ, ¿, ¡): la voz la lee un "
    "sintetizador y la acentuación es OBLIGATORIA.")

def ai_recap(summary):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return {}
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")  # texto corto: Haiku = barato
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 700, "system": AI_RECAP_SYS,
                  "messages": [{"role": "user", "content": "Datos del día:\n" + summary}]}, timeout=45)
        if r.status_code != 200:
            print(f"(IA recap no disponible: {r.status_code})"); return {}
        txt = r.json()["content"][0]["text"]
        return json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    except Exception as e:
        print(f"(IA recap falló: {e})"); return {}

def _five(tags, teams):
    base = ["#Mundial2026"] + ["#" + t.replace(" ", "").replace(".", "") for t in teams[:2]] + ["#IA", "#parati"]
    out = []
    for t in [str(x) for x in tags] + base:
        t = t if t.startswith("#") else "#" + t
        if t not in out:
            out.append(t)
    return out[:5]

def proximo_partido(after_iso, atk, dfn, c, g, rho):
    """Partido clave del primer día con partidos posterior a `after_iso`."""
    try:
        champ = {t for t, _ in list(dd.campeon_probs().items())[:8]}   # ENSEMBLE modelo+mercado
    except Exception:
        champ = set()
    fut = [m for m in dd.fetch_all()
           if dd.et_date(m["utc"]) > after_iso and m["a"] in pm.MAP and m["b"] in pm.MAP]
    if not fut:
        return None
    fut.sort(key=lambda m: m["utc"])
    ed0 = dd.et_date(fut[0]["utc"])
    dia = [m for m in fut if dd.et_date(m["utc"]) == ed0]
    cands = []
    for m in dia:
        pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(m["a"], m["b"], atk, dfn, c, g, rho, local_anfitrion=True)
        fav, fp = (m["a"], pw) if pw >= pl else (m["b"], pl)
        key = (m["a"] in champ or m["b"] in champ) or m["is_ko"]
        cands.append({"a": m["a"], "b": m["b"], "hora": dd.hora_et(m["utc"]),
                      "fecha_h": f"{ed0[8:10]}/{ed0[5:7]}", "fav": fav, "fp": round(fp, 3), "key": key})
    clave = [c for c in cands if c["key"]] or cands
    clave.sort(key=lambda c: c["fp"], reverse=True)
    return clave[0]

def _sep_firma(voz):
    """La despedida y la firma van como FRASES APARTE (punto), no pegadas con coma: pausas.normalizar_pausas pone
    el silencio en los límites de frase (puntos), así que 'Pédro, nos vemos mañana' queda pegado; '...Pédro. Nos
    vemos mañana.' sí respira."""
    voz = re.sub(r",\s*nos vemos", ". Nos vemos", voz, flags=re.IGNORECASE)
    voz = re.sub(r"(Soy éi ái uíz [Pp]édro)\s*,\s*(\S)", lambda m: f"{m.group(1)}. {m.group(2).upper()}", voz)
    return voz

def build(target):
    target_iso = _iso(target)
    tr.grade()                                   # asegura calificados los partidos ya jugados
    logbykey = {r["key"]: r for r in tr.load_log()}
    atk, dfn, c, g, rho = pm.fit_model(); pm.apply_adjustments(atk, dfn)

    matches = []
    for m in sorted(dd.matches_on(target), key=lambda x: x["utc"]):
        a, b = m["a"], m["b"]
        if a not in pm.MAP or b not in pm.MAP:
            continue
        r = logbykey.get(tr._key(a, b, dd.et_date(m["utc"])))
        if not r or r.get("actual") is None:
            continue
        pick_code = r["pick"]
        pick_team = a if pick_code == "1" else (b if pick_code == "2" else "Empate")
        ppick = {"1": r["p1"], "X": r["pX"], "2": r["p2"]}[pick_code]
        matches.append({"a": a, "b": b, "hora": dd.hora_et(m["utc"]), "label": m["label"],
                        "pick_code": pick_code, "pick_team": pick_team, "ppick": round(ppick, 3),
                        "marcador_pred": r.get("marcador_pred", ""), "marcador_real": r.get("marcador_real", ""),
                        "ok1x2": bool(r.get("acierto_1x2")), "okexact": bool(r.get("acierto_exacto"))})

    if not matches:
        out = {"date": target, "empty": True}
        json.dump(out, open(RECAP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return out

    n = len(matches); hits = sum(1 for x in matches if x["ok1x2"])
    record = tr.summary()
    prox = proximo_partido(target_iso, atk, dfn, c, g, rho)
    fecha_h = f"{target[6:8]}/{target[4:6]}/{target[0:4]}"

    # --- resumen exacto para Claude ---
    best = max((x for x in matches if x["ok1x2"]), key=lambda x: x["ppick"], default=None)
    miss = next((x for x in matches if not x["ok1x2"]), None)
    surprise = min((x for x in matches if x["ok1x2"]), key=lambda x: x["ppick"], default=None)
    # export para la INFOGRAFÍA VIRAL del recap (Remotion): TODOS los partidos (tabla + tarjetas)
    try:
        def _sc(s):
            mm = re.match(r"\s*(\d+)\s*-\s*(\d+)", s or "")
            return (int(mm.group(1)), int(mm.group(2))) if mm else (None, None)
        vr = {"fecha": fecha_h, "aciertos": hits, "n": n,
              "partidos": [{"a": dd.acc(x["a"]), "b": dd.acc(x["b"]),
                            "real_sx": _sc(x["marcador_real"])[0], "real_sy": _sc(x["marcador_real"])[1],
                            "pred_sx": _sc(x["marcador_pred"])[0], "pred_sy": _sc(x["marcador_pred"])[1],
                            "acierto": bool(x["ok1x2"]), "pred": x.get("marcador_pred", "")} for x in matches]}
        json.dump(vr, open("viral_recap.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"(viral_recap.json no exportado: {e})")
    dia = dd.weekday_es(target)   # día calculado en Python (Claude no lo deduce)
    sm = [f"Anoche fue {dia}, {fecha_h}. El modelo acertó {hits} de {n} partidos." if dia
          else f"Cierre del {fecha_h}. El modelo acertó {hits} de {n} partidos."]
    for x in matches:
        sm.append(f"- {dd.acc(x['a'])} {x['marcador_real']} {dd.acc(x['b'])}: dijimos {dd.acc(x['pick_team'])} "
                  f"({round(100*x['ppick'])} por ciento), {'ACERTAMOS' if x['ok1x2'] else 'FALLAMOS'}.")
    if surprise and surprise["ppick"] < 0.55:
        sm.append(f"Sorpresa bien clavada: {dd.acc(surprise['pick_team'])} (le daban {round(100*surprise['ppick'])} por ciento).")
    if record.get("n", 0) > 0:
        sm.append(f"Récord acumulado: {record['aciertos_1x2']} de {record['n']} ({record['tasa_1x2']} por ciento).")
    if prox:
        sm.append(f"Lo que viene: {dd.acc(prox['a'])} contra {dd.acc(prox['b'])}, favorito {dd.acc(prox['fav'])} {round(100*prox['fp'])} por ciento.")
    # La VOZ repasa TODOS los partidos (resultado + si acertamos), con ritmo ágil.
    sm.append("PARA LA VOZ: repasa TODOS los partidos de la lista de arriba, uno por uno, con su marcador real y "
              "si ACERTAMOS o FALLAMOS. NO te saltes ninguno; una frase corta por partido, variando cómo lo dices.")
    # marco temporal (sin resultados de otros días, para no alargar la voz)
    try:
        td = date.fromisoformat(target_iso)
        if td > KICKOFF:
            sm.insert(1, "El Mundial 2026 ya está en marcha (arrancó el 11 de junio). NO menciones 'el día N del torneo'.")
    except Exception:
        pass
    try:
        import contexto
        dc = contexto.dato_curioso(target)
        if dc: sm.append("DATO CURIOSO (OPCIONAL, solo para el título/caption; NO lo metas en la voz): " + dc)
    except Exception:
        pass
    ai = ai_recap("\n".join(sm))

    # --- textos (Claude redacta; datos exactos) ---
    rec_txt = (f"{record['aciertos_1x2']} de {record['n']} ({record['tasa_1x2']} por ciento)"
               if record.get("n", 0) > 0 else "arrancando el historial")
    prox_txt = (f" Mañana ojo con {dd.acc(prox['a'])} contra {dd.acc(prox['b'])}." if prox else "")
    titulo = (ai.get("titulo") or "").strip() or f"Le atinamos {hits} de {n} anoche en el Mundial"
    gancho = (ai.get("gancho") or "").strip() or (
        f"Cerramos la jornada: el modelo acertó {hits} de {n}." + (f" Bien clavado: {dd.acc(best['a'])} vs {dd.acc(best['b'])}." if best else ""))
    voz = (ai.get("voz") or "").strip() or (
        f"Veamos cómo nos fue anoche en el Mundial. Mi inteligencia artificial acertó {hits} de {n} partidos. "
        + " ".join(f"{dd.acc(x['a'])} {x['marcador_real'].replace('-', ' a ')} {dd.acc(x['b'])}, "
                   f"{'acertamos' if x['ok1x2'] else 'fallamos'}." for x in matches)
        + f" En total llevamos {rec_txt}.{prox_txt} El análisis completo está en el link de mi bio. "
          f"Suscríbete a mi canal de YouTube. Nos vemos mañana. Soy {BRAND_VOZ}.")
    voz = _sep_firma(voz)   # despedida/firma como frases APARTE (punto), no pegadas con coma
    caption = re.sub(r"\s*#\S+", "", (ai.get("caption") or "").strip()).strip() or (
        f"Así nos fue anoche: {hits}/{n} aciertos 🎯 Mostramos aciertos y fallos. Análisis gratis en mi Substack (link en bio).")
    tags = _five(ai.get("hashtags") or [], [matches[0]["a"], matches[0]["b"]])

    out = {"date": target, "empty": False, "fecha_h": fecha_h, "matches": matches,
           "n": n, "hits": hits, "record": record, "proximo": prox,
           "titulo": titulo, "gancho": gancho, "voz": voz, "caption": caption, "hashtags": tags}
    json.dump(out, open(RECAP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open("recap_voiceover.txt", "w", encoding="utf-8").write(voz)
    open("recap_caption.txt", "w", encoding="utf-8").write(caption.rstrip() + " " + " ".join(tags[:5]))
    # YouTube: título VIRAL + descripción + 5 hashtags
    yt_t = (ai.get("youtube_titulo") or "").strip() or f"🎯 Acerté {hits} de {n} anoche en el Mundial 2026 ⚽"
    yt_d = (ai.get("youtube_descripcion") or "").strip() or (
        f"El Mundial 2026 en 60 segundos al día ⚽ Anoche mi IA acertó {hits} de {n}: comparo el pronóstico con los "
        f"resultados reales, con aciertos y fallos y total transparencia. Suscríbete para el detalle diario, link en la bio.")
    yt_h = [(t if str(t).startswith("#") else "#"+str(t)) for t in (ai.get("youtube_hashtags") or [])]
    for extra in ["#Mundial2026", "#" + matches[0]["a"].replace(" ", "").replace(".", ""), "#Shorts", "#Resultados", "#WorldCup2026"]:
        if len(yt_h) >= 5: break
        if extra not in yt_h: yt_h.append(extra)
    open("recap_youtube.txt", "w", encoding="utf-8").write(f"{yt_t[:95]}\n\n{yt_d}\n\n{' '.join(yt_h[:5])}")
    return out

def ensure(target):
    try:
        c = json.load(open(RECAP_FILE, encoding="utf-8"))
        if c.get("date") == target:
            return c
    except Exception:
        pass
    return build(target)

# ---------- digest del cierre ----------
def build_digest(cu):
    md = [f"# ⚽ {BRAND} · Mundial 2026 — Cierre del día", f"#### Cómo nos fue el {cu['fecha_h']} · horas del Este (ET)\n"]
    if cu.get("gancho"):
        md.append(cu["gancho"].strip()); md.append("")
    md.append(f"## 🎯 Acertamos **{cu['hits']} de {cu['n']}** hoy")
    for x in cu["matches"]:
        mark = "✅" if x["ok1x2"] else "❌"
        ex = " · 🎯 marcador exacto" if x["okexact"] else ""
        md.append(f"- {mark} **{x['a']} {x['marcador_real']} {x['b']}** ({x['label']}) — dijimos **{x['pick_team']}** "
                  f"({x['ppick']:.0%}); previsto {x['marcador_pred']}{ex}")
    md.append("")
    rec = cu.get("record", {})
    if rec.get("n", 0) > 0:
        md.append("## 📈 Récord del modelo")
        md.append(f"Acumulado: **{rec['aciertos_1x2']} de {rec['n']}** ({rec['tasa_1x2']:.0f}%) · "
                  f"marcador exacto {rec.get('tasa_exacta',0):.0f}% · _Brier {rec['brier']}_.")
        md.append("")
    if cu.get("proximo"):
        p = cu["proximo"]
        md.append("## 🔮 Lo que viene")
        md.append(f"- **{p['fecha_h']} · {p['hora']}** · {p['a']} vs {p['b']} — favorita **{p['fav']} ({p['fp']:.0%})**")
        md.append("")
    md.append("---")
    md.append(f"🎬 Mira el cierre en video en mi **canal de YouTube @{BRAND}**  ·  🙌 Compártelo.")
    md.append(f"_{DISCLAIMER}_")
    text = "\n".join(md)
    def b(s): return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s).replace("_", "")
    html = []
    for ln in md:
        if ln.startswith("#### "): html.append(f"<p style='color:#5566aa;margin:0 0 10px;font-size:14px'>{b(ln[5:])}</p>")
        elif ln.startswith("## "): html.append(f"<h2 style='color:#1f3b8b;margin:18px 0 6px'>{b(ln[3:])}</h2>")
        elif ln.startswith("# "): html.append(f"<h1 style='margin:0'>{b(ln[2:])}</h1>")
        elif ln.startswith("- "): html.append(f"<p style='margin:4px 0;line-height:1.45'>{b(ln[2:])}</p>")
        elif ln.strip() == "---": html.append("<hr style='border:none;border-top:1px solid #d9deec;margin:14px 0'>")
        elif ln.strip(): html.append(f"<p style='margin:4px 0'>{b(ln)}</p>")
    html_doc = ("<div style='font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;"
                "color:#0b1437;padding:8px 14px'>" + "".join(html) + "</div>")
    return text, html_doc

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else yesterday_et()
    cu = build(target)
    if cu.get("empty"):
        print(f"Sin partidos para recapitular el {_iso(target)} (no se genera cierre)."); sys.exit(0)
    text, html = build_digest(cu)
    open("recap_digest.md", "w", encoding="utf-8").write(text)
    open("recap_digest.html", "w", encoding="utf-8").write(html)
    print(text)
    print(f"\n📌 Título sugerido: {cu['titulo']}")
    print(f"\n→ recap_today.json, recap_voiceover.txt, recap_caption.txt, recap_digest.* ({cu['hits']}/{cu['n']} aciertos)")
