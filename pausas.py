"""
pausas.py — NORMALIZADOR DE AUDIO NIVEL EXPERTO: deja el voiceover sonando como grabado por un humano,
ajustando las pausas a la PUNTUACIÓN del guion y aplicando pulido profesional.

Cómo funciona (cada vez que ElevenLabs devuelve el audio):
  1) faster-whisper da los tiempos exactos de cada palabra.
  2) se alinean a las palabras del guion (que tiene la puntuación correcta).
  3) cada hueco se lleva a su PAUSA OBJETIVO según el signo, con VARIACIÓN NATURAL (un humano no pausa
     siempre igual: la pausa tras un punto es mayor cuando la frase fue larga). Si sobra silencio se recorta;
     si FALTA (no hizo la pausa de un punto/coma) se INSERTA. Solo se toca SILENCIO -> nunca corta habla.
  4) se recorta el silencio de entrada/salida (take limpio) y se pule: HIGH-PASS (quita retumbe) +
     LOUDNORM EBU R128 (nivel de broadcast, voz pareja) + micro-fade de entrada (cero clics).

Determinista, ligero (no usa torch). Si algo falla, deja el audio igual. Pensado para correr tras make_voice.
"""
import os, re, subprocess, difflib, unicodedata

# pausas base (segundos); la variación natural se aplica encima
SIN_SIGNO = 0.10    # mitad de frase (sin puntuación): casi sin pausa
COMA_BASE = 0.24    # , ; :
PUNTO_BASE = 0.42   # . ! ?
MARGEN = 0.04       # no tocar los últimos ms antes de la siguiente palabra (seguridad de timestamps)
PREROLL = 0.06      # silencio que se deja ANTES de la primera palabra
POSTROLL = 0.30     # silencio que se deja DESPUÉS de la última
MAX_HUECO = 1.4     # SEGURIDAD: un silencio real nunca supera esto; un "hueco" mayor = Whisper se saltó
                    #            habla -> NO se toca (jamás cortar voz por un fallo de transcripción)

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
    h, mi, s = m.groups(); return int(h) * 3600 + int(mi) * 60 + float(s)

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

def _objetivo(tok, clause_len):
    """Pausa objetivo (s) tras una palabra, según su signo y con VARIACIÓN NATURAL por largo de frase."""
    t = (tok or "").strip()
    if re.search(r"[.!?]+$", t):                       # fin de oración: más aire si la frase fue larga
        return round(min(0.58, PUNTO_BASE + 0.018 * min(clause_len, 12)), 3)
    if re.search(r"[,;:]+$", t):                       # pausa de coma: leve variación
        return round(min(0.30, COMA_BASE + 0.010 * min(clause_len, 6)), 3)
    return SIN_SIGNO

def _clause_lens(toks):
    """Para cada token, cuántas palabras lleva la frase/cláusula actual (se reinicia en cada signo)."""
    out, c = [], 0
    for t in toks:
        c += 1; out.append(c)
        if re.search(r"[.,;:!?]$", t): c = 0
    return out

def _segmentos(ops, total):
    """Convierte los ajustes (cortes/inserciones) en una lista ORDENADA de tramos a unir, SIN solapes:
    ('a', inicio, fin) = audio a conservar; ('s', dur) = silencio insertado. Devuelve None si quedaría un
    solape (entonces no se toca el audio). Nunca deja que el cursor retroceda -> nunca se solapan los mensajes."""
    segs, cur = [], 0.0
    for op in sorted(ops, key=lambda o: o[1]):
        if op[0] == "cut":
            a, b = max(op[1], cur), op[2]       # nunca retroceder
            if b <= a:                           # corte inválido o ya cubierto -> ignorar
                continue
            if a > cur: segs.append(("a", cur, a))
            cur = b
        else:                                    # ins
            p, d = op[1], op[2]
            if p < cur - 0.001:                  # inserción que retrocedería (solaparía) -> ignorar
                continue
            if p > cur: segs.append(("a", cur, p))
            segs.append(("s", d)); cur = max(cur, p)
    if cur < total: segs.append(("a", cur, total))
    if not segs:
        segs = [("a", 0.0, total)]
    prev = -1.0                                  # verificación final: audio en orden y sin solapes
    for seg in segs:
        if seg[0] == "a":
            if seg[1] < prev - 0.001 or seg[2] <= seg[1]:
                return None
            prev = seg[2]
    return segs

def normalizar_pausas(audio_in, texto, audio_out=None, modelo=None):
    """Ajusta las pausas a la puntuación del `texto` y pule el audio (loudness/high-pass). True si reescribió."""
    audio_out = audio_out or audio_in
    total = _dur(audio_in)
    if total <= 0:
        return False
    pulir = os.environ.get("PAUSAS_POLISH", "1") not in ("0", "false", "False")
    lufs = os.environ.get("PAUSAS_LUFS", "-16")

    pals = _palabras(audio_in, texto, modelo)
    ops, recortado, insertado = [], 0.0, 0.0
    if len(pals) >= 4:
        toks = texto.split()
        clen = _clause_lens(toks)
        tn = [_norm(t) for t in toks]
        wn = [_norm(w) for w, _, _ in pals]
        w2t = {}
        for i, j, n in difflib.SequenceMatcher(None, wn, tn).get_matching_blocks():
            for k in range(n):
                w2t[i + k] = j + k
        # recortar silencio de ENTRADA y SALIDA (solo si es plausible; si es enorme, Whisper falló -> no tocar)
        if PREROLL + 0.05 < pals[0][1] < MAX_HUECO:
            ops.append(("cut", 0.0, pals[0][1] - PREROLL)); recortado += pals[0][1] - PREROLL
        cola = total - pals[-1][2]
        if POSTROLL + 0.05 < cola < MAX_HUECO:
            ops.append(("cut", pals[-1][2] + POSTROLL, total)); recortado += cola - POSTROLL
        # ajustar cada hueco a su objetivo (solo huecos plausibles)
        for i in range(len(pals) - 1):
            fin, ini_sig = pals[i][2], pals[i + 1][1]
            hueco = ini_sig - fin
            if hueco >= MAX_HUECO:                                   # "hueco" sospechoso = Whisper se saltó habla
                continue                                            # -> NO tocar (seguridad ante todo)
            tj = w2t.get(i)
            dest = _objetivo(toks[tj], clen[tj]) if (tj is not None and tj < len(toks)) else SIN_SIGNO
            if hueco > dest + 0.06:                                  # sobra -> recortar el exceso
                a, b = fin + dest, ini_sig - MARGEN
                if b - a > 0.05:
                    ops.append(("cut", a, b)); recortado += (b - a)
            elif dest > SIN_SIGNO and hueco < dest - 0.06:           # falta -> insertar pausa
                ops.append(("ins", fin + max(hueco, 0.02), dest - hueco)); insertado += (dest - hueco)

    if not ops and not pulir:
        return False

    segs = _segmentos(ops, total)
    if segs is None:                            # se detectó solape -> no tocar el audio (seguridad)
        print("(pausas: se detectó posible solape -> audio sin cambios)")
        return False

    AF = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=mono"
    parts, labels = [], []
    for i, seg in enumerate(segs):
        if seg[0] == "a":
            parts.append(f"[0:a]atrim=start={seg[1]:.3f}:end={seg[2]:.3f},asetpts=PTS-STARTPTS,{AF}[s{i}]")
        else:
            parts.append(f"aevalsrc=0:d={seg[1]:.3f}:s=44100,{AF}[s{i}]")
        labels.append(f"[s{i}]")
    cadena = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(segs)}:v=0:a=1[cc]"
    # pulido profesional: high-pass (quita retumbe) + loudness EBU R128 + micro-fade de entrada
    if pulir:
        cadena += (f";[cc]highpass=f=60,loudnorm=I={lufs}:TP=-2.0:LRA=11,"
                   f"afade=t=in:d=0.02[out]")
    else:
        cadena += ";[cc]anull[out]"

    ff = _ff()
    tmp = audio_out + ".pn.mp3"
    r = subprocess.run([ff, "-y", "-i", audio_in, "-filter_complex", cadena, "-map", "[out]",
                        "-c:a", "libmp3lame", "-q:a", "2", tmp], capture_output=True)
    if r.returncode != 0 or not os.path.exists(tmp):
        print(f"(pausas: ffmpeg falló, audio sin cambios: {(r.stderr[-160:] if r.stderr else '')})")
        return False
    import shutil
    shutil.move(tmp, audio_out)
    ncut = sum(1 for o in ops if o[0] == "cut"); nins = len(ops) - ncut
    print(f"  · audio pro: {ncut} pausas recortadas (−{recortado:.1f}s), {nins} insertadas (+{insertado:.1f}s)"
          + (f", loudness {lufs} LUFS" if pulir else ""))
    return True

if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "voice.mp3"
    t = open("voiceover.txt", encoding="utf-8").read() if os.path.exists("voiceover.txt") else ""
    print("reescrito" if normalizar_pausas(a, t) else "sin cambios")
