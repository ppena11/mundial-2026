"""
pausas.py — CONTROL DE CALIDAD de pausas: normaliza los silencios del audio SEGÚN la puntuación del
voiceover, para que suene lo más natural posible.

Idea: ElevenLabs a veces mete pausas donde NO hay puntuación (suenan robóticas/forzadas) o pausas demasiado
largas. Aquí, cada vez que se genera el audio:
  1) faster-whisper da los tiempos de cada palabra.
  2) se alinean a las palabras del guion (que SÍ tiene la puntuación correcta).
  3) cada hueco se ajusta a su signo: sin signo -> casi sin pausa; coma -> pausa corta; punto -> pausa media.
Solo se recorta SILENCIO (nunca habla) -> sin clics ni palabras cortadas. Si algo falla, deja el audio igual.

Determinista, ligero (no usa torch). Pensado para correr en el pipeline diario tras make_voice.
"""
import os, re, subprocess, tempfile, difflib, unicodedata

# duración (segundos) que se DEJA en cada hueco según el signo que lo precede en el guion
SIN_SIGNO = 0.10    # mitad de frase (sin puntuación): pausa mínima -> quita la pausa injustificada
COMA      = 0.25    # , ; :
PUNTO     = 0.45    # . ! ?
MARGEN    = 0.04    # no tocar los últimos ms antes de la siguiente palabra (seguridad de timestamps)

def _ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil; return shutil.which("ffmpeg") or "ffmpeg"

def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)

def _dur(audio):
    r = subprocess.run([_ff(), "-i", audio], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr or "")
    if not m: return 0.0
    h, mi, s = m.groups(); return int(h)*3600 + int(mi)*60 + float(s)

def _palabras(audio, texto, modelo=None):
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return []
    name = modelo or os.environ.get("WHISPER_PAUSAS", "base")
    try:
        m = WhisperModel(name, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(audio, language="es", word_timestamps=True,
                               condition_on_previous_text=False, temperature=0.0,
                               initial_prompt=(texto or "")[:400] or None)
        return [(w.word, float(w.start), float(w.end)) for s in segs for w in (s.words or [])]
    except Exception as e:
        print(f"(pausas: transcripción falló: {e})"); return []

def _signo_destino(tok):
    """Cuánta pausa dejar después de una palabra del guion según su puntuación final."""
    t = tok.strip()
    if re.search(r"[.!?]+$", t): return PUNTO
    if re.search(r"[,;:]+$", t): return COMA
    return SIN_SIGNO

def normalizar_pausas(audio_in, texto, audio_out=None, modelo=None):
    """Ajusta los silencios del audio a la puntuación del `texto`. Devuelve True si reescribió el audio."""
    audio_out = audio_out or audio_in
    pals = _palabras(audio_in, texto, modelo)
    if len(pals) < 4:
        return False
    toks = texto.split()
    tn = [_norm(t) for t in toks]
    wn = [_norm(w) for w, _, _ in pals]
    # alinear palabra-de-audio -> palabra-de-guion (para saber qué signo sigue a cada una)
    w2t = {}
    for i, j, n in difflib.SequenceMatcher(None, wn, tn).get_matching_blocks():
        for k in range(n):
            w2t[i + k] = j + k
    total = _dur(audio_in)
    if total <= 0:
        return False
    # Ajustar CADA hueco a su pausa objetivo según la puntuación: recortar si sobra, INSERTAR si falta.
    # ops: ("cut", a, b) elimina el silencio sobrante [a,b]; ("ins", p, d) inserta d s de silencio en p.
    ops, recortado, insertado = [], 0.0, 0.0
    for i in range(len(pals) - 1):
        fin, ini_sig = pals[i][2], pals[i + 1][1]
        hueco = ini_sig - fin
        tj = w2t.get(i)
        destino = _signo_destino(toks[tj]) if (tj is not None and tj < len(toks)) else SIN_SIGNO
        if hueco > destino + 0.06:                        # sobra silencio -> recortar
            a, b = fin + destino, ini_sig - MARGEN
            if b - a > 0.05:
                ops.append(("cut", a, b)); recortado += (b - a)
        elif destino > SIN_SIGNO and hueco < destino - 0.06:   # FALTA pausa donde hay signo -> insertar
            ops.append(("ins", fin + max(hueco, 0.02), destino - hueco)); insertado += (destino - hueco)
    if not ops:
        return False
    # Construir la secuencia de segmentos (audio a conservar + silencios insertados), en orden.
    segs, cur = [], 0.0
    for op in sorted(ops, key=lambda o: o[1]):
        if op[0] == "cut":
            a, b = op[1], op[2]
            if a > cur: segs.append(("a", cur, a))
            cur = max(cur, b)
        else:  # ins
            p, d = op[1], op[2]
            if p > cur: segs.append(("a", cur, p))
            segs.append(("s", d)); cur = p
    if cur < total: segs.append(("a", cur, total))
    if len(segs) < 2:
        return False
    AF = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=mono"
    parts, labels = [], []
    for i, seg in enumerate(segs):
        if seg[0] == "a":
            parts.append(f"[0:a]atrim=start={seg[1]:.3f}:end={seg[2]:.3f},asetpts=PTS-STARTPTS,{AF}[s{i}]")
        else:
            parts.append(f"aevalsrc=0:d={seg[1]:.3f}:s=44100,{AF}[s{i}]")   # silencio generado
        labels.append(f"[s{i}]")
    fc = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(segs)}:v=0:a=1[out]"
    ff = _ff()
    tmp = audio_out + ".pn.mp3"
    r = subprocess.run([ff, "-y", "-i", audio_in, "-filter_complex", fc, "-map", "[out]",
                        "-c:a", "libmp3lame", "-q:a", "2", tmp], capture_output=True)
    if r.returncode != 0 or not os.path.exists(tmp):
        print(f"(pausas: ffmpeg falló, audio sin cambios: {(r.stderr[-150:] if r.stderr else '')})")
        return False
    import shutil
    shutil.move(tmp, audio_out)
    ncut = sum(1 for o in ops if o[0] == "cut"); nins = len(ops) - ncut
    print(f"  · pausas normalizadas a la puntuación: {ncut} recortadas (−{recortado:.1f}s), "
          f"{nins} insertadas donde faltaban (+{insertado:.1f}s)")
    return True

if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "voice.mp3"
    t = open("voiceover.txt", encoding="utf-8").read() if os.path.exists("voiceover.txt") else ""
    print("reescrito" if normalizar_pausas(a, t) else "sin cambios")
