"""
make_voice.py — convierte voiceover.txt en voice.mp3 usando TU voz de ElevenLabs (API).
Así el reel se arma SOLO, sin pegar texto a mano.

CONFIG (en .env o GitHub Secrets):
  ELEVENLABS_API_KEY   — tu API key de ElevenLabs
  ELEVENLABS_VOICE_ID  — el ID de tu voz clonada (en ElevenLabs: Voices -> tu voz -> ID)
  ELEVENLABS_MODEL     — (opcional) por defecto eleven_multilingual_v2 (mejor para español)

USO: python make_voice.py [--in voiceover.txt] [--out voice.mp3]
"""
import os, sys, re, base64, json, unicodedata
try:
    import requests
except ImportError:
    print("Falta requests:  pip install requests"); sys.exit(1)
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

def arg(flag, default):
    return sys.argv[sys.argv.index(flag)+1] if flag in sys.argv else default

# Nombres de estadios y ciudades de EE.UU./Canadá escritos FONÉTICAMENTE en español, SOLO para que
# ElevenLabs los pronuncie bien. Se aplica al texto que va al TTS; voiceover.txt conserva el nombre real
# (así los subtítulos muestran "Houston"/"NRG Stadium", no la fonética).
_FONETICO = {
    # ESTADIOS: NO se foneticizan los nombres COMERCIALES/propios (ElevenLabs los pronuncia bien, como "Hard
    # Rock"); el respelling los arruina. Solo traducimos el genérico Stadium->estadio y Field->campo.
    "AT&T Stadium": "estadio ei ti and ti", "Arrowhead Stadium": "estadio Arrowhead",  # AT&T deletreado (si no, dice "Ati")
    "Mercedes-Benz Stadium": "estadio Mercedes-Benz", "Lincoln Financial Field": "campo Lincoln Financial",
    "Hard Rock Stadium": "estadio Hard Rock", "Gillette Stadium": "estadio Gillette",
    "Levi's Stadium": "estadio Levi's", "MetLife Stadium": "estadio MetLife",
    "NRG Stadium": "estadio NRG", "SoFi Stadium": "estadio SoFi",
    "Lumen Field": "campo Lumen", "BMO Field": "campo BMO",
    # (BC Place y Estadio BBVA se dejan tal cual: ya se leen bien)
    # ciudades / estados de EE.UU. y Canadá (México y nombres ya españoles se dejan igual)
    "East Rutherford": "íst ráderford", "New Jersey": "niú yérsi", "Kansas City": "kánsas síti",
    "Mexico City": "Ciudad de México", "Miami Gardens": "maiámi gárdens", "Houston": "jiúston",
    "Arlington": "árlinton", "Atlanta": "atlánta", "Foxborough": "fóksboro",
    "Massachusetts": "masachúsets", "Inglewood": "ínguelud", "Missouri": "misúri", "Miami": "maiámi",
    "Philadelphia": "filadélfia", "Pennsylvania": "pensilvánia", "Seattle": "siátel",
    "Washington": "guáchinton", "Vancouver": "vankúver", "Texas": "téksas",
    # equipos que el TTS angliciza mal (la H de "Haití" debe ser MUDA, no "jaiti")
    "Haití": "aití", "Haiti": "aití",
}
def foneticizar(text):
    """Reemplaza estadios/ciudades por su fonética en español (solo para el audio de ElevenLabs)."""
    for real in sorted(_FONETICO, key=len, reverse=True):   # los más largos primero (evita reemplazos parciales)
        text = text.replace(real, _FONETICO[real])
    return text

def suavizar_tts(text):
    """Quita lo que ElevenLabs lee como PAUSAS raras: rayas largas, puntos suspensivos, punto y coma y dos
    puntos (pausas pesadas), espacios/saltos múltiples. Mejora el ritmo. Solo para el audio (no toca el .txt)."""
    text = text.replace("—", ", ").replace("–", ", ").replace("…", ". ")   # rayas/elipsis -> coma/punto
    text = text.replace(";", ",").replace(":", ",")                        # ; y : -> coma (pausa más suave)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)                             # sin espacio antes del signo
    text = re.sub(r",\s*(?=[,.])", "", text)                               # comas pegadas a otro signo
    text = re.sub(r"\.\s*\.+", ". ", text)                                 # puntos repetidos
    return text.strip()

def quitar_tags(text):
    """Quita las etiquetas de emoción [excited], [confident]... (las entiende eleven_v3; otros modelos
    las leerían en voz alta). BLINDAJE: si por error llega un corchete con CONTENIDO real (p. ej.
    '[DETALLE: Escocia recibe a Brasil...]'), NO se borra el contenido —solo los corchetes y la etiqueta—
    para no perder parte del guion (antes se eliminaba el partido destacado entero)."""
    def _rep(m):
        inner = m.group(1).strip()
        if len(inner) <= 20 and ":" not in inner and not re.search(r"[.;]", inner):
            return ""                                              # etiqueta de emoción corta -> fuera
        return re.sub(r"^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ]*\s*:\s*", "", inner)   # contenido -> conservar (sin 'LABEL:')
    out = re.sub(r"\[([^\]]*)\]", _rep, text)
    out = re.sub(r"\s+([.,;:!?])", r"\1", out)                    # sin espacio antes de puntuación
    return re.sub(r"\s+", " ", out).strip()

_NUM_U = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
          "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve"]
_NUM_D = ["", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
# 20-29 con sus TILDES correctas (veintidós/veintitrés/veintiséis); concatenar "veinti"+base las perdía
_NUM_20 = ["veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco",
           "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
def _num_es(n):
    n = int(n)
    if n < 20: return _NUM_U[n]
    if n < 30: return _NUM_20[n - 20]
    d, u = divmod(n, 10)
    return _NUM_D[d] + (" y " + _NUM_U[u] if u else "")

def numeros_a_palabras(text):
    """Escribe los números de 0 a 99 en palabras SOLO para el audio (ElevenLabs mete micro-pausas alrededor
    de las cifras; en palabras fluyen). Deja años y números grandes (3+ dígitos) tal cual."""
    return re.sub(r"\b\d{1,2}\b", lambda m: _num_es(m.group()), text)

def _f(env, d):
    try: return float(os.environ.get(env, d))
    except Exception: return d

def _voice_settings(v3):
    # Ajustes VERIFICADOS (doc + foros) para sonar HUMANA y NO sintética:
    #  - stability baja = rango emocional (no robótica); v3 usa modo "Natural" ~0.5, v2 ~0.40.
    #  - style 0.0: subirlo causa artefactos/pausas raras -> la emoción sale de la stability, no del style.
    #  - similarity 0.80: 0.75–0.85 es el punto dulce; al 100% sobre-enuncia ("locutor de noticias").
    # v3: modo ROBUST (stability 1.0) = el más FIEL a la voz clonada (la doc lo describe "similar a v2");
    # v2: 0.45 (ya suena idéntica). Similarity alta para pegarse a tu voz (0.75–0.90; 100% sobre-enuncia).
    vs = {"stability": _f("ELEVENLABS_STABILITY", 1.0 if v3 else 0.45),
          "similarity_boost": _f("ELEVENLABS_SIMILARITY", 0.90 if v3 else 0.88),
          "style": _f("ELEVENLABS_STYLE", 0.0),
          "use_speaker_boost": os.environ.get("ELEVENLABS_SPEAKER_BOOST", "1") not in ("0", "false", "False")}
    vs["speed"] = _f("ELEVENLABS_SPEED", 1.05)   # 1.05 = ágil pero mantiene la fidelidad (1.10 baja a 0.88); configurable
    return vs

def _frases(text):
    """Parte en frases por . ! ? (conservando el signo)."""
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]

def _bloques(text, maxlen=240):
    """Agrupa frases en bloques de ~maxlen caracteres (ni muy cortos ni muy largos)."""
    bloques, cur = [], ""
    for f in _frases(text):
        if cur and len(cur) + 1 + len(f) > maxlen:
            bloques.append(cur); cur = f
        else:
            cur = (cur + " " + f).strip() if cur else f
    if cur:
        bloques.append(cur)
    return bloques or [text]

def _concat_mp3(segs, gap=0.25):
    """Une varios mp3 en uno, intercalando un SILENCIO corto (~gap s) entre frases para recuperar la pausa
    natural que el stitching elimina (si no, las frases se pegan y suena confuso). Fallback: bytes crudos."""
    import tempfile, subprocess
    try:
        import imageio_ffmpeg; ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    d = tempfile.mkdtemp(); files = []
    try:
        for i, b in enumerate(segs):
            p = os.path.join(d, f"s{i}.mp3"); open(p, "wb").write(b); files.append(p)
        sil = os.path.join(d, "sil.mp3")   # silencio breve entre frases
        rs = subprocess.run([ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(gap),
                             "-c:a", "libmp3lame", "-q:a", "4", sil], capture_output=True)
        usar_sil = rs.returncode == 0 and os.path.exists(sil)
        seq = []
        for i, p in enumerate(files):
            if i > 0 and usar_sil: seq.append(sil)
            seq.append(p)
        lst = os.path.join(d, "l.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for p in seq: f.write("file '%s'\n" % p.replace("\\", "/"))
        outp = os.path.join(d, "o.mp3")
        # re-encode (no -c copy) para unificar segmentos + silencio en un solo flujo limpio
        r = subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame", "-q:a", "2", outp],
                           capture_output=True)
        data = open(outp, "rb").read() if r.returncode == 0 and os.path.exists(outp) else b"".join(segs)
    except Exception:
        data = b"".join(segs)
    finally:
        try:
            for p in files + [os.path.join(d, x) for x in ("sil.mp3", "l.txt", "o.mp3")]:
                if os.path.exists(p): os.remove(p)
            os.rmdir(d)
        except Exception:
            pass
    return data

_STITCH_GAP = 0.25   # = gap por defecto de _concat_mp3 (silencio insertado entre bloques cosidos)

def _dur_bytes(b):
    """Duración (s) de un mp3 en memoria, vía ffmpeg (para acumular offsets exactos del stitching)."""
    import tempfile, subprocess
    try:
        import imageio_ffmpeg; ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    p = tempfile.mktemp(suffix=".mp3")
    try:
        open(p, "wb").write(b)
        r = subprocess.run([ff, "-i", p], capture_output=True, text=True)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr or "")
        return (int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))) if m else 0.0
    finally:
        try: os.remove(p)
        except Exception: pass

def _palabras_de_alineacion(al, offset):
    """Agrega los caracteres de la alineación de ElevenLabs en PALABRAS con (inicio, fin), sumando 'offset'
    (segundos acumulados de los bloques previos del stitching)."""
    chars = al.get("characters", []) or []
    st = al.get("character_start_times_seconds", []) or []
    en = al.get("character_end_times_seconds", []) or []
    out, cur, ws, we = [], "", None, None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                out.append({"w": cur, "t": round(ws + offset, 3), "e": round(we + offset, 3)}); cur = ""
        else:
            if not cur: ws = s
            cur += c; we = e
    if cur:
        out.append({"w": cur, "t": round(ws + offset, 3), "e": round(we + offset, 3)})
    return out

def synth(text, out="voice.mp3"):
    """Genera el audio con tu voz y guarda los tiempos de cada palabra. Devuelve la lista de palabras
    [{w,t,e}] (línea de tiempo del audio COSIDO, antes de pausas.py) o False si falla."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2").strip()   # v2 = MÁS FIEL a tu voz clonada
    if not key or not voice:
        print("⚠️  Faltan ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID (ponlos en .env o Secrets)."); return False
    fmt = os.environ.get("ELEVENLABS_FORMAT", "").strip()
    # endpoint WITH-TIMESTAMPS: mismo audio + alineación por carácter (para sincronizar las infografías virales)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps" + (f"?output_format={fmt}" if fmt else "")
    hdr = {"xi-api-key": key, "Content-Type": "application/json", "Accept": "application/json"}

    def _attempt(model_id):
        """Devuelve (audio_bytes|None, palabras|None, ultima_respuesta). STITCHING frase a frase con
        previous/next_text para prosodia continua; acumula el offset de tiempo de cada bloque."""
        v3 = model_id.startswith("eleven_v3")
        speak = text if v3 else quitar_tags(text)   # las etiquetas [..] solo las entiende v3
        vs = _voice_settings(v3)
        bloques = _bloques(speak)
        segs, prev_ids, words, offset, last = [], [], [], 0.0, None
        for i, ch in enumerate(bloques):
            body = {"text": ch, "model_id": model_id, "voice_settings": vs}
            if len(bloques) > 1:
                body["previous_text"] = (" ".join(bloques[:i])[-600:] or None)     # contexto previo (no se factura)
                body["next_text"] = (" ".join(bloques[i+1:])[:600] or None)        # contexto siguiente
                if prev_ids:
                    body["previous_request_ids"] = prev_ids[-3:]                   # stitching de prosodia
            r = requests.post(url, headers=hdr, json=body, timeout=90); last = r
            if r.status_code != 200:
                return None, None, r
            j = r.json()
            audio_b = base64.b64decode(j["audio_base64"])
            segs.append(audio_b)
            words.extend(_palabras_de_alineacion(j.get("alignment") or {}, offset))
            offset += _dur_bytes(audio_b) + (_STITCH_GAP if i < len(bloques) - 1 else 0.0)
            rid = r.headers.get("request-id") or r.headers.get("x-request-id")
            if rid: prev_ids.append(rid)
        audio = _concat_mp3(segs) if len(segs) > 1 else (segs[0] if segs else None)
        return audio, words, last

    audio, words, r = _attempt(model)
    if audio is None and model.startswith("eleven_v3"):   # RED DE SEGURIDAD: si v3 falla, usa v2
        print(f"(eleven_v3 no disponible: {getattr(r,'status_code','?')}; uso eleven_multilingual_v2)")
        model = "eleven_multilingual_v2"; audio, words, r = _attempt(model)
    if audio is None:
        print(f"⚠️  ElevenLabs respondió {getattr(r,'status_code','?')}: {(r.text[:300] if r is not None else '')}"); return False
    with open(out, "wb") as f:
        f.write(audio)
    print(f"→ {out} generado con tu voz ({model}, {len(audio)/1000:.0f} KB, {len(_bloques(quitar_tags(text)))} frases unidas, {len(words)} palabras con timestamp)")
    return words

def _norm_tok(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)

def _display_text(raw):
    """Texto de PANTALLA para los subtítulos virales: sin etiquetas [..] y con la firma fonética
    'éi ái uíz Pédro' mostrada como 'aiwithpedro' (lo que la gente debe LEER, no lo que se pronuncia)."""
    s = quitar_tags(raw)
    s = re.sub(r"éi\s+ái\s+u[íi]z\s+p[ée]dro", "aiwithpedro", s, flags=re.IGNORECASE)
    return s

def alinear_display(words, display_text):
    """Asigna a cada palabra del texto de PANTALLA el tiempo de la palabra HABLADA correspondiente
    (alineación difflib hablado<->pantalla; interpola las pocas que no casan: números, firma)."""
    import difflib
    disp = display_text.split()
    if not words or not disp:
        return [{"w": w, "t": 0.0, "e": 0.0} for w in disp]
    sn = [_norm_tok(x["w"]) for x in words]
    dn = [_norm_tok(d) for d in disp]
    d2s = {}
    for i, j, n in difflib.SequenceMatcher(None, dn, sn).get_matching_blocks():
        for k in range(n): d2s[i + k] = j + k
    out, last = [], 0.0
    for jx, tok in enumerate(disp):
        si = d2s.get(jx)
        if si is not None:
            t, e = words[si]["t"], words[si]["e"]
        else:
            nxt = next((d2s[k] for k in range(jx + 1, len(disp)) if k in d2s), None)
            t = last; e = (words[nxt]["t"] if nxt is not None else last + 0.3)
        t = max(t, last); e = max(e, t + 0.05); last = e
        out.append({"w": tok, "t": round(t, 3), "e": round(e, 3)})
    return out

if __name__ == "__main__":
    src = arg("--in", "voiceover.txt"); out = arg("--out", "voice.mp3")
    words_out = arg("--words", os.path.splitext(out)[0] + "_words.json")   # voice_words.json / recap_voice_words.json
    if not os.path.exists(src):
        print(f"No encuentro {src}. Corre make_script.py primero."); sys.exit(1)
    raw = open(src, encoding="utf-8").read().strip()
    text = suavizar_tts(numeros_a_palabras(foneticizar(raw)))   # fonética + números en palabras + limpieza (SOLO audio)
    words = synth(text, out)                                    # lista de palabras habladas (o False) + voice.mp3
    ok = words is not False
    if ok:
        try:
            import pausas
            # pausas re-temporiza el audio; remapea los timestamps de palabra al audio FINAL
            remap = pausas.normalizar_pausas(out, quitar_tags(text), out, words=words)
            words = remap if isinstance(remap, list) else words
        except Exception as e:
            print(f"(pausas: omitido, audio sin cambios: {e})")
        try:   # alinear palabras HABLADAS -> texto de PANTALLA (Haití, 3 a 0, aiwithpedro) y guardar
            disp = alinear_display(words or [], _display_text(raw))
            json.dump(disp, open(words_out, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  · {len(disp)} palabras con timestamp → {words_out}")
        except Exception as e:
            print(f"(timestamps: no guardados: {e})")
    sys.exit(0 if ok else 1)
