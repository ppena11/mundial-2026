"""
subtitulos.py — quema SUBTÍTULOS (frase por frase) en un video ya producido.
Transcribe el audio con faster-whisper (ligero, CPU) y quema un SRT con ffmpeg.

Sirve para cualquier video; en el pipeline lo usamos para matchday.mp4 y recap.mp4.
Es robusto: si falta faster-whisper o el ffmpeg no soporta el filtro de subtítulos,
deja el video TAL CUAL (no rompe nada).

USO:
  python subtitulos.py --video matchday.mp4 [--audio voice.mp3] [--text voiceover.txt] [--out matchday.mp4]
"""
import os, sys, shutil, subprocess, tempfile, re, unicodedata

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
    """minúsculas, sin acentos, solo letras (para comparar fonemas)."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]", "", s.lower())

# Sílabas que Whisper puede transcribir de la marca hablada "éi ái uíz Pédro" (= @aiwithpedro).
_FONEMAS_MARCA = {"ei", "ai", "ay", "a", "e", "i", "hey", "eye",
                  "uiz", "uis", "uith", "with", "wiz", "wis", "guis", "ui", "is"}

def fusionar_marca(palabras):
    """Colapsa la pronunciación fonética de la marca (p.ej. 'éi ái uíz Pédro') en un
    único token 'aiwithpedro', conservando los tiempos. Whisper transcribe la VOZ
    (fonética, para que ElevenLabs suene bien); en el subtítulo queremos la marca escrita.
    Funciona aunque la frase quede partida en varias palabras/cues."""
    out = []
    for w, a, b in palabras:
        if _norm(w) == "pedro":
            # ¿cuántos fonemas de la marca preceden inmediatamente a "Pedro"?
            k = 0
            while k < 4 and len(out) - 1 - k >= 0 and _norm(out[-1 - k][0]) in _FONEMAS_MARCA:
                k += 1
            if k >= 1:
                start = out[-k][1]
                del out[-k:]
                tail = re.search(r"[.,!?;:]+$", w.strip())
                out.append(("aiwithpedro" + (tail.group(0) if tail else ""), start, b))
                continue
        out.append((w, a, b))
    return out

def construir_srt(palabras, max_palabras=4, gap=0.6):
    """palabras: lista de (texto, inicio, fin). Agrupa frase por frase (3-4 palabras / pausas / puntuación)."""
    cues, buf, t0, t1 = [], [], None, None
    for w, a, b in palabras:
        if t0 is None: t0 = a
        buf.append(w); t1 = b
        # cortar la frase al llegar al máximo de palabras o al terminar en puntuación
        if len(buf) >= max_palabras or w.strip().endswith((".", "?", "!", ",", ":", ";")):
            cues.append((t0, t1, " ".join(buf).strip())); buf, t0, t1 = [], None, None
    if buf:
        cues.append((t0, t1, " ".join(buf).strip()))
    out = []
    for i, (a, b, txt) in enumerate(cues, 1):
        if not txt: continue
        b = max(b, a + 0.4)  # mínimo legible
        out.append(f"{i}\n{_segundos_a_srt(a)} --> {_segundos_a_srt(b)}\n{txt}\n")
    return "\n".join(out)

def transcribir(audio, texto=None, modelo=None):
    """Devuelve lista de (palabra, inicio, fin) con faster-whisper. [] si no está disponible."""
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        print(f"(faster-whisper no disponible: {e}); video sin subtítulos."); return []
    name = modelo or os.environ.get("WHISPER_MODEL", "base")
    try:
        m = WhisperModel(name, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(audio, language="es", word_timestamps=True,
                               initial_prompt=(texto or "")[:600] or None)
        palabras = []
        for s in segs:
            for w in (s.words or []):
                palabras.append((w.word, w.start, w.end))
        return palabras
    except Exception as e:
        print(f"(transcripción falló: {e}); video sin subtítulos."); return []

def extraer_audio(video):
    wav = tempfile.mktemp(suffix=".wav")
    cmd = [_ffmpeg(), "-y", "-i", video, "-ar", "16000", "-ac", "1", wav]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return wav if r.returncode == 0 else None

def quemar(video, srt_path, out):
    ff = _ffmpeg(con_subs=True)
    # estilo Shorts: grande, negrita, blanco con borde negro, centrado en el tercio inferior
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
        audio = extraer_audio(video)
        quitar = audio
        if not audio:
            print("No se pudo extraer el audio; video sin subtítulos."); sys.exit(0)

    palabras = transcribir(audio, text)
    if quitar:
        try: os.remove(quitar)
        except Exception: pass
    if not palabras:
        sys.exit(0)   # sin subtítulos, pero no es un error

    palabras = fusionar_marca(palabras)   # "éi ái uíz Pédro" (voz) -> "aiwithpedro" (subtítulo)
    srt = construir_srt(palabras)
    srt_path = os.path.splitext(out)[0] + ".srt"
    open(srt_path, "w", encoding="utf-8").write(srt)
    if quemar(video, srt_path, out):
        print(f"→ {out} con subtítulos quemados.")
    sys.exit(0)

if __name__ == "__main__":
    main()
