"""
subtitulos.py — quema SUBTÍTULOS (frase por frase) en un video ya producido.

ESTRATEGIA (a prueba de balas):
  El texto que se MUESTRA es SIEMPRE nuestro guion (voiceover.txt) -> nombres y marcadores
  nunca salen mal. Whisper se usa SOLO para el TIEMPO (sincronía con el habla):
    1) transcribe el audio,
    2) validamos su transcripción contra el guion (ratio de coincidencia),
    3) si es confiable -> alineamos el guion a los tiempos de Whisper (forced alignment ligero),
    4) si NO es confiable -> repartimos el guion por la duración (cobertura completa garantizada).
  Así, aunque Whisper alucine un día, el subtítulo nunca queda en galimatías.

Es robusto: si falta faster-whisper o el ffmpeg no soporta subtítulos, deja el video TAL CUAL.

USO:
  python subtitulos.py --video matchday.mp4 [--audio voice.mp3] [--text voiceover.txt] [--out matchday.mp4]
"""
import os, sys, shutil, subprocess, tempfile, re, unicodedata, difflib

def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag)+1] if flag in sys.argv else default

def _ffmpeg(con_subs=False):
    """Devuelve un ffmpeg. Para quemar subs prefiere el del sistema (trae libass)."""
    if con_subs:
        sysff = shutil.which("ffmpeg")
        if sysff:
            return sysff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"

def _segundos_a_srt(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _norm(s):
    """minúsculas, sin acentos, solo letras (para comparar palabras/fonemas)."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]", "", s.lower())

def _tokens(texto):
    """Palabras del guion conservando la puntuación pegada (para cortar frases)."""
    return texto.split()

# La firma de marca se habla fonética ("Soy éi ái uíz Pédro") para que ElevenLabs suene bien;
# en el subtítulo la queremos escrita. Como es NUESTRO texto, basta un reemplazo directo.
_FIRMA_RE = re.compile(r"\b[eé]i\s+[aá]i\s+u[ií]z\s+p[eé]dro\b", re.IGNORECASE)

def normalizar_marca_texto(s):
    """'(Soy) éi ái uíz Pédro' -> '(Soy) aiwithpedro' en el guion (100% fiable)."""
    return _FIRMA_RE.sub("aiwithpedro", s)

# ------------------------------------------------------------------ Whisper (solo TIEMPO)

def transcribir(audio, texto=None, modelo=None):
    """Devuelve (palabras, duracion). palabras = [(palabra, inicio, fin)]; ([], 0.0) si no disponible.
    Flags anti-alucinación: vad_filter, condition_on_previous_text=False, temperature=0."""
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        print(f"(faster-whisper no disponible: {e})"); return [], 0.0
    name = modelo or os.environ.get("WHISPER_MODEL", "small")
    try:
        m = WhisperModel(name, device="cpu", compute_type="int8")
        segs, info = m.transcribe(audio, language="es", word_timestamps=True,
                                  vad_filter=True, condition_on_previous_text=False,
                                  temperature=0.0, initial_prompt=(texto or "")[:400] or None)
        palabras = []
        for s in segs:
            for w in (s.words or []):
                palabras.append((w.word, w.start, w.end))
        dur = float(getattr(info, "duration", 0.0) or 0.0)
        return palabras, dur
    except Exception as e:
        print(f"(transcripción falló con '{name}': {e})"); return [], 0.0

def similitud(palabras_whisper, texto_real):
    """Ratio 0..1 de coincidencia entre lo que oyó Whisper y nuestro guion (validación)."""
    wn = [n for n in (_norm(w) for w, _, _ in palabras_whisper) if n]
    tn = [n for n in (_norm(t) for t in _tokens(texto_real)) if n]
    if not wn or not tn:
        return 0.0
    return difflib.SequenceMatcher(None, tn, wn).ratio()

def transcribir_validado(audio, texto, umbral=0.55):
    """Transcribe y VALIDA contra el guion; reintenta escalando el modelo si no coincide.
    Devuelve (palabras, duracion, confiable)."""
    intentos = [os.environ.get("WHISPER_MODEL", "small"), "medium"]
    mejor = ([], 0.0, 0.0)   # palabras, dur, ratio
    for name in intentos:
        palabras, dur = transcribir(audio, texto, modelo=name)
        if not palabras:
            continue
        r = similitud(palabras, texto)
        print(f"  Whisper '{name}': {len(palabras)} palabras, similitud con el guion = {r:.2f}")
        if r > mejor[2]:
            mejor = (palabras, dur, r)
        if r >= umbral:
            return palabras, dur, True
    palabras, dur, r = mejor
    return palabras, dur, (r >= umbral)

# ------------------------------------------------------------------ alineación / reparto

def alinear(texto_real, palabras_whisper, dur):
    """Asigna a CADA palabra del guion un tiempo: ancla en las palabras que Whisper acertó
    (difflib) e interpola linealmente los huecos. Devuelve [(palabra, inicio, fin)]."""
    toks = _tokens(normalizar_marca_texto(texto_real))
    if not toks:
        return []
    tn = [_norm(t) for t in toks]
    wn = [_norm(w) for w, _, _ in palabras_whisper]
    wt = [(a, b) for _, a, b in palabras_whisper]
    N = len(toks)
    ini = [None] * N
    for i, j, n in difflib.SequenceMatcher(None, tn, wn).get_matching_blocks():
        for k in range(n):
            if i + k < N and j + k < len(wt):
                ini[i + k] = wt[j + k][0]
    # anclas conocidas + bordes virtuales (0 al inicio, dur al final) para interpolar
    known = [(i, ini[i]) for i in range(N) if ini[i] is not None]
    fin_dur = max(dur, (known[-1][1] if known else 0.0) + 0.5)
    pts = [(-1, 0.0)] + known + [(N, fin_dur)]
    ts = [0.0] * N
    for idx in range(N):
        left = max((p for p in pts if p[0] <= idx), key=lambda p: p[0])
        right = min((p for p in pts if p[0] > idx), key=lambda p: p[0])
        ts[idx] = left[1] if right[0] == left[0] else \
            left[1] + (idx - left[0]) / (right[0] - left[0]) * (right[1] - left[1])
    for idx in range(1, N):            # forzar monotonía
        if ts[idx] < ts[idx - 1]:
            ts[idx] = ts[idx - 1]
    palabras = []
    for i, tok in enumerate(toks):
        a = ts[i]
        b = ts[i + 1] if i + 1 < N else min(fin_dur, a + 0.6)
        if b <= a:
            b = a + 0.3
        palabras.append((tok, a, b))
    return palabras

def srt_proporcional(texto_real, dur):
    """Fallback: reparte el guion por la duración (proporcional a los caracteres). Cobertura completa."""
    toks = _tokens(normalizar_marca_texto(texto_real))
    if not toks:
        return ""
    if dur <= 0:
        dur = max(2.0, 0.4 * len(toks))
    pesos = [max(1, len(t)) for t in toks]
    total = sum(pesos)
    palabras, t = [], 0.0
    for tok, p in zip(toks, pesos):
        d = dur * p / total
        palabras.append((tok, t, t + d))
        t += d
    return construir_srt(palabras)

# ------------------------------------------------------------------ respaldo whisper-crudo (sin guion)

_LETRAS_FONEMA = set("aeiouywhzstg")

def _es_fonema_marca(w):
    """¿El token parece una sílaba de la marca hablada (éi, ái, uíz, with, eiu...)? (solo respaldo)."""
    n = _norm(w)
    return bool(n) and 1 <= len(n) <= 5 and n != "soy" and all(c in _LETRAS_FONEMA for c in n)

def fusionar_marca(palabras):
    """Colapsa la pronunciación fonética de la marca en 'aiwithpedro' (solo para el respaldo
    whisper-crudo, cuando NO hay guion). Ancla en cualquier palabra que contenga 'pedro'."""
    out = []
    for w, a, b in palabras:
        n = _norm(w)
        if "pedro" in n:
            k = 0
            while k < 4 and len(out) - 1 - k >= 0 and _es_fonema_marca(out[-1 - k][0]):
                k += 1
            prev_soy = (len(out) - 1 - k >= 0) and _norm(out[-1 - k][0]) == "soy"
            if k >= 1 or len(n) > len("pedro") or prev_soy:
                start = out[-k][1] if k >= 1 else a
                if k >= 1:
                    del out[-k:]
                tail = re.search(r"[.,!?;:]+$", w.strip())
                out.append(("aiwithpedro" + (tail.group(0) if tail else ""), start, b))
                continue
        out.append((w, a, b))
    return out

# ------------------------------------------------------------------ armado / quemado

def construir_srt(palabras, max_palabras=4):
    """palabras: lista de (texto, inicio, fin). Agrupa frase por frase (≤4 palabras o puntuación)."""
    cues, buf, t0, t1 = [], [], None, None
    for w, a, b in palabras:
        if t0 is None: t0 = a
        buf.append(w); t1 = b
        if len(buf) >= max_palabras or w.strip().endswith((".", "?", "!", ",", ":", ";")):
            cues.append((t0, t1, " ".join(buf).strip())); buf, t0, t1 = [], None, None
    if buf:
        cues.append((t0, t1, " ".join(buf).strip()))
    out = []
    for i, (a, b, txt) in enumerate(cues, 1):
        if not txt: continue
        b = max(b, a + 0.4)   # mínimo legible
        out.append(f"{i}\n{_segundos_a_srt(a)} --> {_segundos_a_srt(b)}\n{txt}\n")
    return "\n".join(out)

def duracion_audio(ruta):
    """Segundos del medio, parseando 'Duration:' del ffmpeg portátil. 0.0 si falla."""
    if not ruta or not os.path.exists(ruta):
        return 0.0
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = shutil.which("ffmpeg") or "ffmpeg"
    r = subprocess.run([ff, "-i", ruta], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr or "")
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)

def extraer_audio(video):
    wav = tempfile.mktemp(suffix=".wav")
    cmd = [_ffmpeg(), "-y", "-i", video, "-ar", "16000", "-ac", "1", wav]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return wav if r.returncode == 0 else None

def quemar(video, srt_path, out):
    ff = _ffmpeg(con_subs=True)
    # Blanco clásico pro: blanco negrita, borde negro grueso, sombra suave; centrado en el tercio inferior.
    estilo = ("Fontname=Arial,Bold=1,Fontsize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
              "BackColour=&H80000000,BorderStyle=1,Outline=4,Shadow=2,Alignment=2,MarginV=60")
    srt_ff = srt_path.replace("\\", "/").replace(":", "\\:")   # escape para Windows en el filtro
    vf = f"subtitles='{srt_ff}':force_style='{estilo}'"
    tmp = out + ".tmp.mp4"
    cmd = [ff, "-y", "-i", video, "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-r", "30", tmp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"(no se pudieron quemar subtítulos: {r.stderr[-300:]}); se deja el video sin subtítulos.")
        return False
    shutil.move(tmp, out)
    return True

def main():
    video = arg("--video")
    if not video or not os.path.exists(video):
        print("Falta --video válido."); sys.exit(1)
    audio = arg("--audio")
    text = ""
    tpath = arg("--text")
    if tpath and os.path.exists(tpath):
        text = open(tpath, encoding="utf-8").read().strip()
    out = arg("--out", video)

    quitar = None
    if not (audio and os.path.exists(audio)):
        audio = extraer_audio(video); quitar = audio
        if not audio:
            print("No se pudo extraer el audio; video sin subtítulos."); sys.exit(0)

    srt = ""
    if text:
        # CAMINO PRINCIPAL: el guion manda el texto; Whisper solo aporta el tiempo.
        palabras, dur, confiable = transcribir_validado(audio, text)
        if dur <= 0:
            dur = duracion_audio(audio) or duracion_audio(video)
        if confiable and palabras:
            print("  Tiempos de Whisper confiables → alineo el guion a esos tiempos.")
            srt = construir_srt(alinear(text, palabras, dur))
        else:
            print(f"  Tiempos NO confiables → reparto el guion por la duración ({dur:.1f}s).")
            srt = srt_proporcional(text, dur)
    else:
        # SIN guion (no ocurre en producción): respaldo whisper-crudo.
        palabras, _ = transcribir(audio, text)
        if palabras:
            srt = construir_srt(fusionar_marca(palabras))

    if quitar:
        try: os.remove(quitar)
        except Exception: pass
    if not srt.strip():
        print("(sin subtítulos)"); sys.exit(0)
    srt_path = os.path.splitext(out)[0] + ".srt"
    open(srt_path, "w", encoding="utf-8").write(srt)
    if quemar(video, srt_path, out):
        print(f"→ {out} con subtítulos quemados.")
    sys.exit(0)

if __name__ == "__main__":
    main()
