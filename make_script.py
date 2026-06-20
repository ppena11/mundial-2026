"""
make_script.py — GUION HABLADO del día para ElevenLabs (tu voz) + caption para YouTube Shorts.
Texto natural en español (sin símbolos ni emojis, para que ElevenLabs lo lea limpio):
  hook + lo más importante de la infografía + CTA.

USO: python make_script.py [--date YYYYMMDD]
Genera: voiceover.txt (para pegar en ElevenLabs) y caption.txt (descripción + hashtags YouTube Shorts).
Flujo: voiceover.txt -> ElevenLabs (tu voz) -> voice.mp3 -> make_reel.py -> matchday.mp4
"""
import sys, os, json
from datetime import date
import daily_digest as dd
import predict_match as pm
try:
    import requests
except ImportError:
    requests = None

BRAND = "aiwithpedro"
BRAND_VOZ = "éi ái uíz Pédro"   # cómo se pronuncia @aiwithpedro en la voz (ElevenLabs)
KICKOFF = date(2026, 6, 11)     # día inaugural del Mundial 2026 (anclaje temporal para Claude)
VAL_MARGIN, VAL_FLOOR = 1.20, 0.20

def pct(x): return f"{round(100*x)} por ciento"

# nombres con espacios/acentos -> hashtag limpio
_TAG = {"Estados Unidos":"USA","Corea del Sur":"Corea","Arabia Saudi":"ArabiaSaudita",
        "Paises Bajos":"PaisesBajos","Nueva Zelanda":"NuevaZelanda","Cabo Verde":"CaboVerde",
        "Costa de Marfil":"CostaDeMarfil","R.D. Congo":"Congo","Sudafrica":"Sudafrica"}
def _tag(team): return "#" + _TAG.get(team, team.replace(" ", ""))

def _summary(fh, played, pick, clearest, tr):
    """Resumen de datos del día que se le pasa a Claude para que redacte el guion."""
    flarga = dd.fecha_larga(f"{fh[6:10]}{fh[3:5]}{fh[0:2]}")   # 'jueves 18 de junio', calculada en Python
    L = [f"Hoy es {flarga} de 2026." if flarga else f"Fecha: {fh}."]
    # anclaje temporal: evita que Claude diga "el Mundial comienza/comenzó hoy" en día equivocado
    try:
        td = date(int(fh[6:10]), int(fh[3:5]), int(fh[0:2]))
        if td < KICKOFF:
            L.append("El Mundial aún no empieza (arranca el 11 de junio de 2026).")
        elif td == KICKOFF:
            L.append("HOY, 11 de junio, ARRANCA el Mundial 2026 (día inaugural).")
        else:
            L.append("El Mundial 2026 YA ESTÁ EN MARCHA (arrancó el 11 de junio). NO digas que el Mundial "
                     "'comienza' ni 'comenzó hoy', y NO menciones 'el día N del torneo'.")
    except Exception:
        pass
    # contexto de lo que ha pasado en el torneo (resultados, sorpresas, récord, titular) — datos reales
    try:
        import contexto
        ctx = contexto.resumen_torneo(f"{fh[6:10]}{fh[3:5]}{fh[0:2]}")
        if ctx: L.append(ctx)
    except Exception:
        pass
    if not played:
        L.append("Hoy no hay partidos del Mundial (el torneo arranca el 11 de junio).")
        return "\n".join(L)
    L.append(f"Partidos de hoy ({len(played)}). Di EL PRONÓSTICO (marcador) de TODOS:")
    target = f"{fh[6:10]}{fh[3:5]}{fh[0:2]}"
    try:
        import contexto
    except Exception:
        contexto = None
    # partido MÁS IMPORTANTE del día = el del equipo con mayor probabilidad de ser campeón
    champ = {}
    try:
        champ = dict(json.load(open("champ_today.json", encoding="utf-8"))["campeon"])
    except Exception:
        pass
    feat = max(range(len(played)), key=lambda i: max(champ.get(played[i]["a"], 0), champ.get(played[i]["b"], 0)))
    for i, d in enumerate(played):
        hora = dd.hora_hablada(d["utc"]) if d.get("utc") else ""
        base = (f"PRONÓSTICO {dd.acc(d['a'])} contra {dd.acc(d['b'])}: favorito {dd.acc(d['fav'])} con "
                f"{round(100*d['fp'])} por ciento; marcador previsto {dd.acc(d['a'])} {d['sx']} - {d['sy']} {dd.acc(d['b'])}.")
        if i == feat:
            sede = ", ".join(x for x in (d.get("estadio"), d.get("ciudad"), d.get("pais")) if x)
            det = (f" Hora: {hora}." if hora else "") + (f" Sede: {sede}." if sede else "")
            L.append("- [PARTIDO DESTACADO DEL DÍA] " + base + det)
            n = contexto.noticia_partido(dd.acc(d['a']), dd.acc(d['b']), target) if contexto else None
            if n:
                L.append(f"  Ángulo noticioso del día para el partido destacado (intégralo con naturalidad, "
                         f"SIN citar el medio ni decir 'según'): {n['title']}")
        else:
            L.append(f"- {base}" + (f" Hora: {hora}." if hora else ""))
    if pick:
        t, mpb, mkp, edge = pick[1]
        L.append(f"Jugada de valor del día: {dd.acc(t)} (el modelo le da {round(100*mpb)} por ciento y el mercado solo {round(100*mkp)} por ciento; está infravalorada).")
    if clearest:
        L.append(f"Resultado más claro: {dd.acc(clearest['fav'])} con {round(100*clearest['fp'])} por ciento en {dd.acc(clearest['a'])} contra {dd.acc(clearest['b'])}.")
    if tr.get("n", 0) > 0:
        L.append(f"Historial del modelo: {tr['aciertos_1x2']} aciertos de {tr['n']} ({tr['tasa_1x2']} por ciento).")
    try:
        champ = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
        playing = {d["a"] for d in played} | {d["b"] for d in played}
        stars = [dd.acc(t) for t in champ if t in playing][:2]
        if stars:
            L.append("Equipos más buscados que juegan hoy (úsalos en los hashtags): " + ", ".join(stars) + ".")
    except Exception:
        pass
    return "\n".join(L)

AI_SYSTEM = (
    "Eres el guionista y community manager de @aiwithpedro, un creador que enseña inteligencia artificial. "
    "DATO FIJO: el Mundial 2026 ARRANCÓ el 11 de junio de 2026; NO afirmes que 'comienza' ni 'comenzó hoy' salvo "
    "que la fecha del día sea exactamente el 11 de junio (mírala en los datos). "
    "DÍA DE LA SEMANA: el día correcto está en los datos ('Hoy es …'). Si nombras el día (hoy, mañana, 'el sábado'), "
    "usa EXACTAMENTE ese; NUNCA lo deduzcas tú de la fecha. "
    "Con los datos del día del Mundial 2026, genera el contenido de un video de YouTube Shorts y devuelve EXCLUSIVAMENTE "
    "un objeto JSON válido (sin ``` ni texto extra) con EXACTAMENTE estas claves:\n"
    '"voiceover": el guion HABLADO, con TONO DE NARRADOR DEPORTIVO PROFESIONAL: claro, enérgico y con autoridad, '
    "frases limpias y bien armadas, sin relleno ni muletillas. "
    'ABRE diciendo la fecha de hoy con ESTE formato: "Aquí está el pronóstico de hoy, <día de la semana> <número> '
    'de <mes>" (usa EXACTAMENTE el día y la fecha de los datos, p. ej. "Aquí está el pronóstico de hoy, jueves 18 '
    'de junio"); NO digas "el día N del torneo". '
    "Presenta CADA partido como 'el pronóstico de A contra B' con su MARCADOR PREVISTO, sin omitir ninguno. "
    "El partido marcado como [PARTIDO DESTACADO DEL DÍA] es el MÁS IMPORTANTE: dale el trato de narrador COMPLETO "
    "—además del pronóstico, di DÓNDE se juega EN DETALLE (estadio, ciudad y país) y la hora, e integra con "
    "naturalidad LA NOTICIA del día como parte del comentario (SIN citar el medio ni decir 'según'). "
    "Para LOS DEMÁS partidos di SOLO el pronóstico (marcador y favorito) y la HORA; NO menciones su sede ni noticia. "
    "Usa SOLO los datos dados; NUNCA inventes nada —ni la hora, ni la sede, ni noticias, ni lesiones—: si un dato "
    "no está, NO lo menciones. "
    "Ritmo de narrador: ágil y limpio, ~40 a 60 segundos en total. "
    "Cierra invitando a SUSCRIBIRSE a mi canal de YouTube y a ver el análisis completo en el link "
    "de mi bio (NO nombres 'Substack' en la voz) "
    "y firma la voz diciendo EXACTAMENTE: Soy éi ái uíz Pédro (así se pronuncia @aiwithpedro). SIN otros emojis ni "
    "símbolos (lo lee un sintetizador de voz); números con dígitos y "
    "'por ciento'; 'contra' en vez de 'vs'; varía el arranque para no repetir. Si en los datos hay CONTEXTO del "
    "torneo (resultados recientes, una sorpresa, el récord o un titular), téjelo en 1 frase para que suene al día.\n"
    '"caption": 1 o 2 líneas cortas para la descripción de YouTube Shorts, con gancho; puede llevar 1 o 2 emojis; menciona '
    "que el análisis completo está gratis en el Substack (link en bio). NO incluyas hashtags aquí.\n"
    '"hashtags": lista de EXACTAMENTE 5 hashtags, los más virales; incluye #Mundial2026, los 2 equipos más buscados '
    "que juegan hoy, y #IA y #parati.\n"
    '"youtube_descripcion": 2 o 3 frases para la descripción de YouTube, RICAS EN PALABRAS CLAVE (los equipos del día, '
    "Mundial 2026, predicción con inteligencia artificial, marcador, probabilidades), con un CTA al análisis completo "
    "(link en la bio). NO incluyas hashtags aquí.\n"
    '"youtube_hashtags": lista de EXACTAMENTE 5 hashtags buscables para YouTube; incluye #Mundial2026, los equipos clave '
    "del día y #Shorts.\n"
    "Español neutro, cercano y enérgico. Apto para todo público, nada de apuestas. "
    "ESCRIBE EN ESPAÑOL CON TODAS LAS TILDES Y SIGNOS CORRECTOS (á, é, í, ó, ú, ñ, ¿, ¡): el guion lo lee un "
    "sintetizador de voz y la acentuación es OBLIGATORIA.")

def ai_content(summary):
    """Claude redacta guion + caption + 5 hashtags. Devuelve (voiceover, caption, hashtags) o None."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return None
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")  # texto corto: Haiku = barato
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 800, "system": AI_SYSTEM,
                  "messages": [{"role": "user", "content": "Datos de hoy:\n" + summary}]}, timeout=45)
        if r.status_code != 200:
            print(f"(IA no disponible: {r.status_code} {r.text[:150]})"); return None
        txt = r.json()["content"][0]["text"]
        data = json.loads(txt[txt.find("{"):txt.rfind("}")+1])   # extrae el JSON
        vo = (data.get("voiceover") or "").strip()
        cap = (data.get("caption") or "").strip()
        tags = [str(t).strip() for t in data.get("hashtags", []) if str(t).strip()]
        yt = ((data.get("youtube_titulo") or "").strip(), (data.get("youtube_descripcion") or "").strip(),
              [str(t).strip() for t in data.get("youtube_hashtags", []) if str(t).strip()])
        return vo, cap, tags, yt
    except Exception as e:
        print(f"(IA falló: {e})"); return None

def day_hashtags(played):
    """Exactamente 5 hashtags virales, 2 según los equipos estrella del día."""
    teams = []
    try:
        champ = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]  # ordenado por prob desc
        playing = {d["a"] for d in played} | {d["b"] for d in played}
        teams = [t for t in champ if t in playing][:2]   # los 2 más "buscados" que juegan hoy
    except Exception:
        pass
    tags = ["#Mundial2026"] + [_tag(t) for t in teams] + ["#IA", "#parati"]
    for fill in ("#futbol", "#WorldCup2026"):            # relleno si hoy no hay equipos (raro)
        if len(tags) >= 5: break
        if fill not in tags: tags.append(fill)
    out = []
    for t in tags:
        if t not in out: out.append(t)
    return " ".join(out[:5])

def _yt_tags(tags, played):
    """5 hashtags buscables para YouTube (#Mundial2026 + equipos del día + #Shorts/#Pronosticos)."""
    teams = []
    try:
        champ = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
        playing = {d["a"] for d in played} | {d["b"] for d in played}
        teams = [t for t in champ if t in playing][:2]
    except Exception:
        pass
    base = ["#Mundial2026"] + [_tag(t) for t in teams] + ["#Shorts", "#Pronosticos", "#WorldCup2026"]
    out = []
    for t in [(x if str(x).startswith("#") else "#"+str(x)) for x in tags] + base:
        if t not in out: out.append(t)
    return out[:5]

def write_youtube(path, played, fh, yt_ai):
    """Escribe título + descripción + 5 hashtags optimizados para SEO de YouTube. yt_ai=(t,d,h) de Claude o None."""
    yt_t, yt_d, yt_h = (yt_ai or ("", "", []))
    nombres = " · ".join(f"{dd.acc(d['a'])} vs {dd.acc(d['b'])}" for d in played[:2]) if played else ""
    yt_t = f"{fh} - Pronósticos Mundial 2026 @aiwithpedro"   # formato fijo de marca (no el de Claude)
    if not yt_d:
        yt_d = (f"Predicción del Mundial 2026 con inteligencia artificial para hoy ({fh}): marcadores y probabilidades "
                f"de cada partido según el modelo. {nombres}. Análisis completo gratis, link en la bio.")
    yt_h = _yt_tags(yt_h, played)
    open(path, "w", encoding="utf-8").write(f"{yt_t}\n\n{yt_d}\n\n{' '.join(yt_h[:5])}")

def build(target):
    games = dd.matches_on(target)
    atk,dfn,c,g,rho = pm.fit_model(); pm.apply_adjustments(atk,dfn)
    mkt={}
    try:
        import fetch_odds
        for ev in fetch_odds.h2h():
            pe={dd.EN2ES.get(k,k):v for k,v in ev["clean_probs"].items()}
            ts=[t for t in pe if t!="Draw"]
            if len(ts)==2: mkt[frozenset(ts)]=pe
    except Exception: pass
    played=[]
    for m in sorted(games,key=lambda x:x["utc"]):
        a,b=m["a"],m["b"]
        if a not in pm.MAP or b not in pm.MAP: continue
        pw,pdr,pl,lh,la,(sx,sy)=pm.one_x_two(a,b,atk,dfn,c,g,rho,local_anfitrion=True)
        mp=mkt.get(frozenset((a,b))); vc=[]
        if mp:
            ma,mb=mp.get(a),mp.get(b)
            if ma and pw>=VAL_FLOOR and pw>ma*VAL_MARGIN: vc.append((a,pw,ma,pw/ma))
            if mb and pl>=VAL_FLOOR and pl>mb*VAL_MARGIN: vc.append((b,pl,mb,pl/mb))
        fav,fp=(a,pw) if pw>=pl else (b,pl)
        played.append({"a":a,"b":b,"fav":fav,"fp":fp,"vc":vc,"sx":sx,"sy":sy,"pdr":pdr,
                       "utc":m.get("utc",""),"estadio":m.get("estadio",""),
                       "ciudad":m.get("ciudad",""),"pais":m.get("pais","")})
    if not played:                                   # día sin partidos -> dato curioso (voz + caption)
        import curio
        cu = curio.ensure(target)
        caption = cu["caption"].rstrip() + " " + " ".join(cu["hashtags"][:5])
        open("youtube.txt", "w", encoding="utf-8").write(
            f"{cu.get('youtube_titulo','')}\n\n{cu.get('youtube_descripcion','')}\n\n"
            f"{' '.join(cu.get('youtube_hashtags', [])[:5])}")
        return cu["voz"], caption, 0
    pickall=[(d,v) for d in played for v in d["vc"]]
    pick=max(pickall,key=lambda x:x[1][3]) if pickall else None
    clearest=max(played,key=lambda d:d["fp"],default=None)
    try: tr=json.load(open("track_record.json",encoding="utf-8"))
    except Exception: tr={"n":0}

    # ---------- GUION (hablado, sin símbolos) ----------
    S=[]
    if not played:
        S.append("Hoy no hay partidos del Mundial, pero mi inteligencia artificial ya está lista para cuando ruede el balón.")
    else:
        S.append(f"Aquí está el pronóstico de hoy, {dd.fecha_larga(target)}. Mi inteligencia artificial corrió veinte mil simulaciones, y estos son los marcadores que proyecta.")
        S.append(". ".join(f"{dd.acc(d['a'])} {d['sx']} a {d['sy']} {dd.acc(d['b'])}" for d in played) + ".")
        if pick:
            d,(team,mpb,mkp,edge)=pick; riv=d["b"] if team==d["a"] else d["a"]
            S.append(f"La jugada del día es {dd.acc(team)}, contra {dd.acc(riv)}. Mi modelo le da {pct(mpb)} de ganar, "
                     f"pero las casas la pagan como si fuera mucho más difícil. Para mí, está infravalorada.")
        if clearest:
            S.append(f"El resultado más claro del día: en {dd.acc(clearest['a'])} contra {dd.acc(clearest['b'])}, "
                     f"el favorito es {dd.acc(clearest['fav'])}, con {pct(clearest['fp'])}.")
        if tr.get("n",0)>0:
            S.append(f"Y para que confíes en el modelo: llevamos {tr['aciertos_1x2']} aciertos de {tr['n']} partidos.")
    S.append(f"El análisis completo de todos los partidos lo tienes en el link de mi bio. "
             f"Suscríbete a mi canal de YouTube. "
             f"Soy {BRAND_VOZ}, esto es inteligencia artificial aplicada al fútbol. Nos vemos mañana.")
    voiceover=" ".join(S)   # guion de respaldo (plantilla)
    # caption de respaldo (plantilla)
    cap_pick = f" Pick del día: {pick[1][0]}." if pick else ""
    caption = (f"Mi IA predice el Mundial 2026 ⚽🤖{cap_pick} Análisis completo gratis en mi Substack (link en bio). "
               + day_hashtags(played))

    # ---- Claude redacta guion + caption + 5 hashtags (si hay ANTHROPIC_API_KEY) ----
    fh = target[6:8]+"/"+target[4:6]+"/"+target[0:4]
    res = ai_content(_summary(fh, played, pick, clearest, tr))
    yt_ai = None
    if res:
        vo_ai, cap_ai, tags_ai, yt_ai = res
        if vo_ai:
            voiceover = vo_ai
        if cap_ai:
            import re
            cap_ai = re.sub(r"\s*#\S+", "", cap_ai).strip()   # Claude a veces mete hashtags en el caption: quitarlos
            tags = [(t if t.startswith("#") else "#"+t) for t in tags_ai]
            for t in day_hashtags(played).split():     # completa a 5 si Claude devolvió menos
                if len(tags) >= 5: break
                if t not in tags: tags.append(t)
            caption = cap_ai.rstrip() + " " + " ".join(tags[:5])
    write_youtube("youtube.txt", played, fh, yt_ai)     # título + descripción + 5 hashtags SEO de YouTube
    return voiceover, caption, len(played)

if __name__=="__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    vo, cap, n = build(target)
    open("voiceover.txt","w",encoding="utf-8").write(vo)
    open("caption.txt","w",encoding="utf-8").write(cap)
    print("===== VOICEOVER (pégalo en ElevenLabs) =====\n")
    print(vo)
    print("\n===== CAPTION YouTube Shorts =====\n")
    print(cap)
    print("\n===== YOUTUBE (título · descripción · 5 hashtags) =====\n")
    try: print(open("youtube.txt", encoding="utf-8").read())
    except Exception: pass
    print(f"\n→ voiceover.txt, caption.txt y youtube.txt guardados ({n} partidos)")
