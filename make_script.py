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
# variantes para NO repetir "veinte mil simulaciones" cada día (rota por fecha); honestas, el modelo es real
_INTRO_VARIANTS = ["mi inteligencia artificial ya jugó la jornada", "mi modelo lo tiene clarísimo",
                   "el algoritmo procesó todos los escenarios", "mi IA corrió veinte mil simulaciones",
                   "miles de escenarios, un solo veredicto", "mi modelo de IA ya tiene los marcadores"]

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
        champ = dict(dd.campeon_probs())   # ENSEMBLE modelo+mercado (cae al modelo si no hay)
    except Exception:
        pass
    feat = max(range(len(played)), key=lambda i: max(champ.get(played[i]["a"], 0), champ.get(played[i]["b"], 0)))
    # Desde el 28-jun-2026 (Dieciseisavos) la fase de grupos terminó: TODOS los partidos van en detalle.
    # En fase de grupos, solo el más importante (el destacado).
    eliminatorias = target >= "20260628"
    # nº de partido de cada equipo en el torneo (contado del calendario real, para que Claude NO lo invente)
    try:
        _todos = dd.fetch_all()
    except Exception:
        _todos = []
    _tgt = f"{target[:4]}-{target[4:6]}-{target[6:8]}"
    def _num_partido(team):
        fechas = sorted(m.get("utc", "")[:10] for m in _todos if team in (m.get("a"), m.get("b")))
        return sum(1 for f in fechas if f and f <= _tgt)
    for i, d in enumerate(played):
        hora = dd.hora_hablada(d["utc"]) if d.get("utc") else ""
        if d['fav'] == "Empate":
            base = (f"PRONÓSTICO {dd.acc(d['a'])} contra {dd.acc(d['b'])}: el modelo ve EMPATE a {d['sx']} "
                    f"({round(100*d['fp'])} por ciento de empate); marcador previsto {dd.acc(d['a'])} {d['sx']} - {d['sy']} {dd.acc(d['b'])}.")
        else:
            base = (f"PRONÓSTICO {dd.acc(d['a'])} contra {dd.acc(d['b'])}: favorito {dd.acc(d['fav'])} con "
                    f"{round(100*d['fp'])} por ciento; marcador previsto {dd.acc(d['a'])} {d['sx']} - {d['sy']} {dd.acc(d['b'])}.")
        detallado = eliminatorias or d.get("is_ko") or (i == feat)
        if detallado:
            sede = d.get("estadio", "")   # SOLO el estadio (sin ciudad ni país: el país 'Estados Unidos' disparaba falsos anclajes de tarjeta)
            det = (f" Hora: {hora}." if hora else "") + (f" Sede: {sede}." if sede else "")
            L.append("- [DETALLE] " + base + det)
            na, nb = _num_partido(d['a']), _num_partido(d['b'])
            if na and nb:
                L.append(f"  Número de partido en el torneo (úsalo EXACTO si lo mencionas, NO lo inventes): "
                         f"es el partido {na} de {dd.acc(d['a'])} y el partido {nb} de {dd.acc(d['b'])}.")
            if d.get("m_fav") is not None:           # contraste con el MERCADO (para el 'por qué' del destacado)
                dirc = ("el mercado lo subestima" if d["fp"] > d["m_fav"] + 0.04 else
                        ("el mercado lo ve aún más favorito" if d["m_fav"] > d["fp"] + 0.04 else "modelo y mercado casi coinciden"))
                L.append(f"  Modelo vs mercado: el modelo da {round(100*d['fp'])} por ciento al favorito y el "
                         f"consenso del mercado {round(100*d['m_fav'])} por ciento ({dirc}). Si hay contraste, "
                         f"explícalo en 1 frase como ANÁLISIS (NUNCA como apuesta).")
            n = contexto.noticia_partido(dd.acc(d['a']), dd.acc(d['b']), target) if contexto else None
            if n:
                L.append(f"  Ángulo noticioso del día para este partido (intégralo con naturalidad, "
                         f"SIN citar el medio ni decir 'según'): {n['title']}")
        else:
            L.append(f"- {base}" + (f" Hora: {hora}." if hora else ""))
    if pick:
        dpick = pick[0]; t, mpb, mkp, edge = pick[1]
        rival = dpick["b"] if t == dpick["a"] else dpick["a"]
        L.append(f"DONDE EL MODELO MÁS DISCREPA DEL CONSENSO: {dd.acc(t)} contra {dd.acc(rival)} — el modelo le da "
                 f"{round(100*mpb)} por ciento y el consenso del mercado solo {round(100*mkp)} por ciento; el mercado "
                 f"parece subestimarlo. Explica ESTE contraste en 1 frase como ANÁLISIS (jamás como apuesta ni cuota).")
    if clearest:
        L.append(f"Resultado más claro: {dd.acc(clearest['fav'])} con {round(100*clearest['fp'])} por ciento en {dd.acc(clearest['a'])} contra {dd.acc(clearest['b'])}.")
    if tr.get("n", 0) > 0:
        L.append(f"Historial del modelo: {tr['aciertos_1x2']} aciertos de {tr['n']} ({tr['tasa_1x2']} por ciento).")
    try:
        champ = dd.campeon_probs()   # ENSEMBLE modelo+mercado (cae al modelo si no hay)
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
    '"voiceover": el guion HABLADO, con TONO DE NARRADOR DEPORTIVO PROFESIONAL y PERSONALIDAD de creador: claro, '
    "enérgico, con autoridad y punto de vista; frases limpias, sin relleno ni muletillas. "
    "Escribe frases que FLUYAN con ritmo continuo de narrador; evita el staccato de muchas frases cortísimas "
    "seguidas y las comas innecesarias (esas causan pausas robóticas al leerlas la voz). "
    "ABRE CORTO Y DIRECTO, SIN gancho largo ni dato de ayer: UNA sola frase que diga que estos son los pronósticos "
    "de tu INTELIGENCIA ARTIFICIAL para HOY con la fecha, y JUSTO DESPUÉS el récord del modelo. Molde (VARÍA las "
    'palabras, NO lo copies idéntico): "Aquí están los pronósticos del Mundial 2026 de mi inteligencia artificial '
    'para hoy, <día de la semana> <número> de <mes>. Vamos <aciertos> de <total>." Usa EXACTAMENTE la fecha y el '
    "récord de los datos; "
    "NO digas 'el día N del torneo'. PROHIBIDO en el ARRANQUE: gancho o resultado de AYER, presumir "
    "'simulaciones'/'escenarios', cualquier MARCADOR con sede y cualquier OPINIÓN. El récord se dice UNA sola vez "
    "(aquí, al inicio), NO lo repitas al final. INMEDIATAMENTE después del récord empieza DIRECTO con lo que piensa "
    "el modelo: los pronósticos. "
    "Presenta CADA partido como 'el pronóstico de A contra B' con su MARCADOR PREVISTO, sin omitir ninguno, pero "
    "VARÍA cómo introduces cada uno (NO repitas la misma plantilla) pero SIEMPRE con frases GRAMATICALES y "
    "naturales: 'ojo con A contra B', 'A se mide ante B', 'A parte como favorito ante B', 'el modelo se inclina "
    "por A frente a B'. PROHIBIDO pegar el nombre y el giro sin conector (MAL: 'Alemania ojo con Costa de Marfil'; "
    "BIEN: 'ojo con Alemania contra Costa de Marfil'). NOMBRA al equipo (no digas 'el equipo favorito'). "
    "Si el dato dice 'el modelo ve EMPATE', NO inventes un favorito: di que el modelo PREVÉ UN EMPATE (p. ej. "
    "'el modelo ve un empate a 1' o 'partido parejo, igualada a 1'), coherente con el marcador. "
    "REGLA ABSOLUTA E INNEGOCIABLE DEL MARCADOR (la tarjeta muestra '<equipo A> <sx> - <sy> <equipo B>'): el "
    "PRIMER número que pronuncies para un partido es SIEMPRE el del PRIMER equipo (sx) y el SEGUNDO el del segundo "
    "equipo (sy) — pase lo que pase, GANE QUIEN GANE. NUNCA pongas primero el número del segundo equipo. "
    "Formas CORRECTAS: '<A> <sx>, <B> <sy>' (cada equipo con su gol; ej. 'Ecuador cero, Alemania uno') o, si "
    "quieres un verbo, '<A> cae <sx> a <sy> ante <B>' / '<A> gana <sx> a <sy>' (el primer número SIEMPRE es sx). "
    "Formas PROHIBIDÍSIMAS (invierten sx-sy y chocan con la tarjeta): '<B> gana <sy> a <sx>', '<sy> a <sx> para "
    "<B>', '<B> uno a cero', 'uno a cero para <B>', 'los visitantes ganando <sy> a <sx>'. Ej.: dato 'Paraguay "
    "0 - 1 Australia' (gana Australia) -> SOLO 'Paraguay cero, Australia uno' o 'Paraguay cae cero a uno ante "
    "Australia' (JAMÁS 'Australia uno a cero' ni 'uno a cero para Australia'). Puedes nombrar al ganador, pero los "
    "NÚMEROS van en orden sx-sy SIEMPRE. El ganador es el del número MAYOR. "
    "VARÍA el verbo/giro, NO el orden de los números. FIDELIDAD AL MARCADOR: NINGUNA palabra que implique PALIZA ('goleada', 'golea', 'aplasta', "
    "'destroza', 'arrasa/arrasando', 'masacra', 'vapulea', 'humilla', 'pasa por encima') salvo que el marcador tenga "
    "3 o más goles de diferencia; un 2 a 0 es 'gana con autoridad', 'se impone con claridad' o 'es favorita clara', "
    "NO una paliza. El favoritismo alto (85 por ciento) se dice como DOMINIO ('manda', 'no falla'), no como goleada. "
    "Y NUNCA digas '<Equipo> goleada' (suena a que PIERDE): di '<Equipo> golea' o 'goleada de <Equipo>'. "
    "EVITA relleno y frases huecas (nada de 'a toda velocidad' ni 'darle exactitud a lo que "
    "viene'). OBLIGATORIO: el PARTIDO DESTACADO ([DETALLE]) lleva SIEMPRE tu OPINIÓN PROPIA sobre ESE partido "
    "JUSTO DESPUÉS de su pronóstico/sede/noticia y pegada a él (tu lectura de ESE marcador: por qué el modelo lo "
    "ve así, si te parece contundente, ajustado o te sorprende —p. ej. 'este dos a cero me parece contundente: "
    "su defensa no ha encajado'). Esa opinión personal es SOLO para el destacado: NO la pongas sobre otro partido "
    "ni la dejes para el cierre. (El 'resultado más claro del día' es un DATO aparte; puedes mencionarlo, pero NO "
    "sustituye la opinión del destacado.) "
    "POR QUÉ (modelo + mercado + razón): si el destacado trae 'Modelo vs mercado', INTEGRA ese contraste en tu "
    "opinión como ANÁLISIS (p. ej. 'el mercado lo ve más parejo, pero mi modelo le da 85 por ciento, y tiene "
    "sentido: <razón real de la noticia o la forma dada>'). Y si viene 'DONDE EL MODELO MÁS DISCREPA DEL CONSENSO', "
    "menciónalo en 1 frase explicando el PORQUÉ. El 'porqué' DEBE salir de los datos dados (modelo, mercado, "
    "noticia, forma): NUNCA inventes la razón. PROHIBIDO el lenguaje de apuestas (apuesta, apostar, cuota, momio, "
    "'infravalorada' como tip): habla de 'el mercado/el consenso' y 'mi modelo discrepa', SIEMPRE como análisis. "
    "El marcador [DETALLE] es SOLO una etiqueta interna de los datos: NUNCA lo escribas en tu respuesta NI "
    "envuelvas NINGÚN texto entre corchetes [ ]. PROHIBIDAS también las etiquetas de emoción o acotaciones "
    "([excited], [pausa], [happy], etc.): el guion es SOLO lo que se dice en voz, sin corchetes de ningún tipo. "
    "Ese partido se narra como prosa normal y fluida. "
    "Los partidos marcados con [DETALLE] reciben el trato de narrador COMPLETO: además del pronóstico, di SIEMPRE "
    "la HORA (en formato HABLADO: 'a la 1 de la tarde', NUNCA '13 horas') Y dónde se juega: SOLO el nombre del "
    "ESTADIO (p. ej. 'en el NRG Stadium') —NUNCA la ciudad ni el país (di SOLO el estadio; el país confunde y "
    "no aporta)—, e integra con naturalidad LA NOTICIA del día como parte del comentario "
    "(SIN citar el medio ni decir 'según'). "
    "En fase de grupos suele venir marcado UNO (el más importante); en eliminatorias vienen marcados TODOS. "
    "Para LOS DEMÁS partidos (sin [DETALLE]) di SOLO el pronóstico (marcador y favorito) y la HORA; NO menciones su sede ni noticia. "
    "Usa SOLO los datos dados; NUNCA inventes nada —ni la hora, ni la sede, ni noticias, ni lesiones—: si un dato "
    "no está, NO lo menciones. "
    "Si dices qué número de partido lleva un equipo ('su segundo/tercer partido'), usa EXACTAMENTE el número que "
    "viene en los datos ('Número de partido en el torneo'); NUNCA lo deduzcas ni lo inventes. "
    "Menciona el récord del modelo de forma NATURAL y CERCA DEL CIERRE (p. ej. 'vamos 18 de 32'), nunca en el "
    "gancho ni con decimales raros. "
    "Ritmo de narrador: ágil y CONCISO, MÁXIMO ~175 palabras (~70 s). Frases cortas, CERO relleno (fuera 'listo "
    "para revelarte', 'mantener la confianza en la cancha', 'un duelo más parejo de lo que parece' y similares). "
    "Los partidos NO destacados: UNA sola frase mínima (favorito + marcador + hora), nada más. NO sacrifiques la "
    "hora ni el estadio del destacado. "
    "TODAS las horas en formato HABLADO ('a las 8 de la noche'), NUNCA en formato 24 horas ('20 horas'). "
    "CIERRA con una frase MEMORABLE y con chispa que mezcle ACTITUD + tu marca de IA, pero que sea UNA FRASE "
    "FLUIDA Y COMPLETA (algo ORIGINAL al estilo de 'el fútbol no tiene libreto, pero mi inteligencia artificial ya "
    "lo leyó' —NO copies ese ejemplo, inventa el tuyo). EVITA contrastes cortados o elípticos como 'el fútbol "
    "sorprende, mi inteligencia artificial no' (esa coma con la idea incompleta suena a PAUSA FORZADA): completa la "
    "idea. Luego invita a SUSCRIBIRSE a mi canal de YouTube y a ver el análisis completo en el link "
    "de mi bio (NO nombres 'Substack' en la voz) "
    "y firma la voz diciendo EXACTAMENTE: Soy éi ái uíz Pédro (así se pronuncia @aiwithpedro). SIN otros emojis ni "
    "símbolos (lo lee un sintetizador de voz). ÚNICA excepción: AÑADE 1 o 2 ETIQUETAS DE EMOCIÓN de "
    "eleven_v3 entre corchetes (p. ej. [excited], [confident], [serious]) en momentos clave —el gancho o una "
    "sorpresa— para dar energía; con moderación y NUNCA una etiqueta en la firma. MARCADORES y números SIEMPRE con "
    "DÍGITOS ('1 a 0', '2 a 1', '53 por ciento'), NUNCA en palabras (nada de 'un a cero' ni 'dos a cero'); "
    "'contra' en vez de 'vs'; varía el arranque para no repetir. Si en los datos hay CONTEXTO del "
    "torneo (resultados recientes, una sorpresa, el récord o un titular), téjelo en 1 frase para que suene al día.\n"
    '"caption": 1 o 2 líneas cortas para la descripción de YouTube Shorts, con gancho; puede llevar 1 o 2 emojis; menciona '
    "que el análisis completo está gratis en el Substack (link en bio). NO incluyas hashtags aquí.\n"
    '"hashtags": lista de EXACTAMENTE 5 hashtags, los más virales; incluye #Mundial2026, los 2 equipos más buscados '
    "que juegan hoy, y #IA y #parati.\n"
    + dd.VIRAL_TITULO + dd.VIRAL_DESC +
    '"youtube_hashtags": lista de EXACTAMENTE 5 hashtags buscables para YouTube; incluye #Mundial2026, los equipos clave '
    "del día y #Shorts.\n"
    "Español neutro, cercano y enérgico. Apto para todo público, nada de apuestas. "
    "CUIDA LA GRAMÁTICA y la CONCORDANCIA sujeto-verbo (revisa cada frase: 'los germanos se inclinaN', no 'se inclina'); "
    "frases bien construidas, sin errores. "
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
        champ = dd.campeon_probs()  # ENSEMBLE modelo+mercado, ordenado por prob desc
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
        champ = dd.campeon_probs()   # ENSEMBLE modelo+mercado (cae al modelo si no hay)
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
    clear = max(played, key=lambda d: d["fp"], default=None) if played else None
    if not yt_t:                                     # título VIRAL de respaldo (si la IA no lo dio)
        if clear:
            yt_t = f"🔥 Mundial 2026 HOY: {dd.acc(clear['fav'])} {clear['sx']}-{clear['sy']} y los pronósticos más claros con IA ⚽"
        else:
            yt_t = f"🔥 Mundial 2026: los pronósticos del día con IA ⚽ ({fh})"
    yt_t = yt_t[:100]                                # YouTube recorta títulos muy largos
    if not yt_d:
        yt_d = (f"El Mundial 2026 en 60 segundos al día ⚽ Pronósticos de hoy ({fh}) con inteligencia artificial: "
                f"{nombres}. Marcadores y probabilidades de cada partido. Suscríbete para el detalle diario, link en la bio.")
    yt_h = _yt_tags(yt_h, played)
    open(path, "w", encoding="utf-8").write(f"{yt_t}\n\n{yt_d}\n\n{' '.join(yt_h[:5])}")

def _limpiar_voz(text):
    """Corrige deslices frecuentes de Claude ANTES de la voz/subtítulos (determinista, garantizado):
    marcadores con 'un a X' -> 'uno a X', y tildes que el modelo a veces omite (Suscríbete)."""
    import re
    nums = r"\d|cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve"
    text = re.sub(rf"\bUn a (?={nums})", "Uno a ", text)
    text = re.sub(rf"\bun a (?={nums})", "uno a ", text)
    text = re.sub(r"\bSuscribete\b", "Suscríbete", text)
    text = re.sub(r"\bsuscribete\b", "suscríbete", text)
    # duplicaciones: 'Bélgica y Bélgica' -> 'Bélgica'  y  'Bélgica Bélgica' / 'la la' -> una sola
    text = re.sub(r"\b([A-ZÁÉÍÓÚÑ]\w*)\s+y\s+\1\b", r"\1", text)
    text = re.sub(r"\b(\w+)(?:\s+\1\b)+", r"\1", text, flags=re.IGNORECASE)
    # horas: "a la ocho" -> "a las ocho" (la 's' SIEMPRE salvo en "a la una")
    horas = r"(dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)"
    text = re.sub(rf"\ba la {horas}\b", r"a las \1", text)
    text = re.sub(rf"\bA la {horas}\b", r"A las \1", text)
    return re.sub(r"\s{2,}", " ", text).strip()

def build(target):
    games = dd.matches_on(target)
    atk,dfn,c,g,rho = pm.fit_model(); pm.apply_adjustments(atk,dfn)
    try:
        import schedule_2026 as _sched; _SCHED = _sched.load()   # sede/hora/viaje reales por partido
    except Exception:
        _SCHED = None
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
        # sede/hora/viaje reales del calendario -> aplica altura+calor+viaje en el marcador
        _ground,_hora,_ta,_tb=(None,None,None,None)
        if _SCHED is not None:
            _ground,_hora=_SCHED.factors_for(a,b); _ta,_tb=_SCHED.travel_for_pair(a,b)
        pw,pdr,pl,lh,la,(sx,sy)=pm.one_x_two(a,b,atk,dfn,c,g,rho,local_anfitrion=True,
                                             sede=_ground,kickoff_hour=_hora,home_travel=_ta,away_travel=_tb)
        mp=mkt.get(frozenset((a,b))); vc=[]
        if mp:
            ma,mb=mp.get(a),mp.get(b)
            if ma and pw>=VAL_FLOOR and pw>ma*VAL_MARGIN: vc.append((a,pw,ma,pw/ma))
            if mb and pl>=VAL_FLOOR and pl>mb*VAL_MARGIN: vc.append((b,pl,mb,pl/mb))
        if mp:                                  # ENSAMBLE: el marcador usa MODELO + MERCADO (todos los datos)
            m_w, m_l, m_d = mp.get(a), mp.get(b), mp.get("Draw")
            if m_w and m_l:
                sx, sy, pw, pdr, pl, _, _ = pm.ensamble_marcador(lh, la, rho, m_w, m_d, m_l)
        _oc = pm.outcome_de(sx, sy)             # favorito DERIVA del marcador más probable (concuerda con el pick y el recap)
        if _oc == "1":   fav, fp = a, pw
        elif _oc == "2": fav, fp = b, pl
        else:            fav, fp = "Empate", pdr   # marcador de empate -> el pronóstico ES empate (no hay favorito)
        mfav = (mp.get("Draw") if _oc == "X" else mp.get(fav)) if mp else None   # prob de mercado del resultado previsto
        played.append({"a":a,"b":b,"fav":fav,"fp":fp,"m_fav":mfav,"vc":vc,"sx":sx,"sy":sy,"pdr":pdr,
                       "utc":m.get("utc",""),"estadio":m.get("estadio",""),
                       "ciudad":m.get("ciudad",""),"pais":m.get("pais",""),"is_ko":m.get("is_ko",False)})
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

    # ---------- export para la INFOGRAFÍA VIRAL (Remotion): partidos (marcador ensamblado) + campeón ----------
    try:
        _fh = target[6:8] + "/" + target[4:6] + "/" + target[0:4]
        _ch = dd.campeon_probs()
        _feat = max(range(len(played)), key=lambda i: max(_ch.get(played[i]["a"], 0), _ch.get(played[i]["b"], 0))) if played else -1
        # En ELIMINATORIAS todos los partidos son decisivos: no hay "PICK DEL DÍA" (un solo destacado no aplica)
        _elim = target >= "20260628" or any(d.get("is_ko") for d in played)
        _ronda = dd.ronda_ko(target) or ("ELIMINATORIA" if _elim else "")   # badge de fase en eliminatorias
        viral = {"fecha": _fh, "target": target,
                 "intro": _INTRO_VARIANTS[int(target) % len(_INTRO_VARIANTS)],
                 "partidos": [{"a": dd.acc(d["a"]), "b": dd.acc(d["b"]), "fav": dd.acc(d["fav"]),
                               "fp": round(100 * d["fp"]), "sx": d["sx"], "sy": d["sy"],
                               "hora": dd.hora_hablada(d["utc"]) if d.get("utc") else "",
                               "hora_corta": dd.hora_et(d["utc"]) if d.get("utc") else "",
                               "sede": d.get("estadio", ""),   # SOLO el estadio (sin ciudad ni país)
                               "is_ko": bool(d.get("is_ko")) or _elim,   # en KO todos muestran sede (todos importantes)
                               "ronda": _ronda,                          # badge de fase (OCTAVOS, FINAL...) en KO; '' en grupos
                               "destacado": (i == _feat) and not _elim} for i, d in enumerate(played)],
                 "campeon": [[dd.acc(t), round(float(p), 1)] for t, p in list(_ch.items())[:6]],
                 "record": {"aciertos": tr.get("aciertos_1x2", 0), "n": tr.get("n", 0)}}
        _vp = os.devnull if os.environ.get("MAKESCRIPT_NO_EXPORT") else "viral_pronostico.json"   # tests no pisan el real
        json.dump(viral, open(_vp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"(viral_pronostico.json no exportado: {e})")

    # ---------- GUION (hablado, sin símbolos) ----------
    S=[]
    if not played:
        S.append("Hoy no hay partidos del Mundial, pero mi inteligencia artificial ya está lista para cuando ruede el balón.")
    else:
        _rec = f" Vamos {tr['aciertos_1x2']} de {tr['n']}." if tr.get("n", 0) > 0 else ""
        S.append(f"Aquí están los pronósticos del Mundial 2026 de mi inteligencia artificial para hoy, {dd.fecha_larga(target)}.{_rec}")
        S.append(". ".join(f"{dd.acc(d['a'])} {d['sx']} a {d['sy']} {dd.acc(d['b'])}" for d in played) + ".")
        if pick:
            d,(team,mpb,mkp,edge)=pick; riv=d["b"] if team==d["a"] else d["a"]
            S.append(f"La jugada del día es {dd.acc(team)}, contra {dd.acc(riv)}. Mi modelo le da {pct(mpb)} de ganar, "
                     f"pero las casas la pagan como si fuera mucho más difícil. Para mí, está infravalorada.")
        if clearest:
            S.append(f"El resultado más claro del día: en {dd.acc(clearest['a'])} contra {dd.acc(clearest['b'])}, "
                     f"el favorito es {dd.acc(clearest['fav'])}, con {pct(clearest['fp'])}.")
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
    return _limpiar_voz(voiceover), caption, len(played)

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
