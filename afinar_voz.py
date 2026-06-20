"""
afinar_voz.py — AFINADOR OBJETIVO de la voz (herramienta de desarrollo, NO parte del pipeline diario).

Mide con datos, no a oído:
  - VELOCIDAD (palabras/min) y PAUSAS (huecos entre palabras)  -> con faster-whisper large-v3 (el más potente).
  - CLARIDAD/pronunciación (qué tan bien se entiende lo que enviamos) -> similitud transcripción vs texto.
  - FIDELIDAD a tu voz (¿sigue sonando como tú?) -> speaker embedding (Resemblyzer), comparado con una
    referencia fiel (por defecto, una generación v2, que ya confirmaste idéntica a ti).

Genera varias configuraciones (barrido de speed/stability/modelo), las puntúa y RECOMIENDA la mejor.
Cada configuración GASTA ElevenLabs (genera audio real con tu voz). No usa Claude.

REQUISITOS (instálalos solo para esta herramienta; NO van en la nube):
  pip install faster-whisper resemblyzer
  (large-v3 se descarga solo la primera vez, ~3 GB; Resemblyzer baja un modelo pequeño)

USO:
  python afinar_voz.py                          # usa voiceover.txt, barre speed 1.05/1.10/1.15 en v2
  python afinar_voz.py --speeds 1.0,1.1,1.2 --stabs 0.4,0.5
  python afinar_voz.py --model eleven_v3        # compara fidelidad de v3 vs la referencia v2
  python afinar_voz.py --ref mi_voz_real.mp3    # referencia = tu voz REAL (mejor aún que la v2)
"""
import os, sys, re, subprocess, tempfile, difflib, unicodedata
import make_voice as mv

def arg(flag, d=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else d

def _ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil; return shutil.which("ffmpeg") or "ffmpeg"

def _to_wav(mp3):
    """mp3 -> wav 16 kHz mono (lo que necesitan Whisper y Resemblyzer)."""
    wav = tempfile.mktemp(suffix=".wav")
    r = subprocess.run([_ff(), "-y", "-i", mp3, "-ar", "16000", "-ac", "1", wav], capture_output=True)
    return wav if r.returncode == 0 else None

def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()

_WMODEL = {}
def _whisper(mp3, texto_audio, modelo="large-v3"):
    """Devuelve (wpm, pausa_max_seg, claridad_0a1, duracion). Usa faster-whisper (CPU, int8)."""
    from faster_whisper import WhisperModel
    if modelo not in _WMODEL:
        print(f"  · cargando Whisper '{modelo}' (la 1ª vez descarga ~GB)...")
        _WMODEL[modelo] = WhisperModel(modelo, device="cpu", compute_type="int8")
    m = _WMODEL[modelo]
    segs, info = m.transcribe(mp3, language="es", word_timestamps=True)
    pals = [(w.word, w.start, w.end) for s in segs for w in (s.words or [])]
    dur = float(getattr(info, "duration", 0.0) or 0.0)
    if not pals or dur <= 0:
        return 0.0, 0.0, 0.0, dur
    n = len(pals)
    wpm = n / (dur / 60.0)
    gaps = [pals[i + 1][1] - pals[i][2] for i in range(n - 1)]
    pausa_max = max(gaps) if gaps else 0.0
    trans = " ".join(w for w, _, _ in pals)
    claridad = difflib.SequenceMatcher(None, _norm(texto_audio).split(), _norm(trans).split()).ratio()
    return wpm, pausa_max, claridad, dur

_ENC = []
def _fidelidad(ref_wav, cand_wav):
    """Similitud de hablante (0..1) entre referencia y candidato, con Resemblyzer. None si no está instalado."""
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav
        import numpy as np
    except Exception as e:
        print(f"  (Resemblyzer no disponible: {e}; sin medición de fidelidad)"); return None
    if not _ENC:
        _ENC.append(VoiceEncoder())
    enc = _ENC[0]
    try:
        e1 = enc.embed_utterance(preprocess_wav(ref_wav))
        e2 = enc.embed_utterance(preprocess_wav(cand_wav))
        return float(np.dot(e1, e2))   # embeddings ya normalizados -> coseno
    except Exception as e:
        print(f"  (fidelidad falló: {e})"); return None

def _gen(text, out, speed, stab, model):
    """Genera audio con una config (vía make_voice.synth, que lee estos env)."""
    os.environ["ELEVENLABS_MODEL"] = model
    os.environ["ELEVENLABS_SPEED"] = str(speed)
    os.environ["ELEVENLABS_STABILITY"] = str(stab)
    return mv.synth(text, out)

def main():
    src = arg("--text", "voiceover.txt")
    if not os.path.exists(src):
        print(f"No encuentro {src}. Corre make_script.py primero."); sys.exit(1)
    speeds = [float(x) for x in arg("--speeds", "1.05,1.10,1.15").split(",")]
    stabs = [float(x) for x in arg("--stabs", "").split(",")] if arg("--stabs") else None
    model = arg("--model", "eleven_multilingual_v2")
    wmodel = arg("--whisper", "large-v3")
    ref = arg("--ref")

    raw = open(src, encoding="utf-8").read().strip()
    texto_audio = mv.suavizar_tts(mv.numeros_a_palabras(mv.foneticizar(mv.quitar_tags(raw))))  # lo que oye el TTS

    # referencia de fidelidad: tu voz real (--ref) o, si no, una generación v2 fiel (speed 1.0, stab 0.45)
    if ref and os.path.exists(ref):
        ref_mp3 = ref
    else:
        print("Generando referencia fiel (v2, speed 1.0)...")
        ref_mp3 = "ref_voz.mp3"
        if not _gen(texto_audio, ref_mp3, 1.0, 0.45, "eleven_multilingual_v2"):
            print("No pude generar la referencia."); sys.exit(1)
    ref_wav = _to_wav(ref_mp3)

    configs = [(sp, st) for sp in speeds for st in (stabs or [0.45 if not model.startswith("eleven_v3") else 1.0])]
    print(f"\nObjetivo: WPM ~150-165, pausa_max < 0.8s, claridad alta, fidelidad alta.\n")
    print(f"{'config':28} {'WPM':>6} {'pausa':>6} {'clar':>6} {'fidel':>6}")
    print("-" * 60)
    res = []
    for sp, st in configs:
        out = f"cand_{model[:6]}_s{sp}_e{st}.mp3"
        if not _gen(texto_audio, out, sp, st, model):
            print(f"{model} sp{sp} st{st}: generación falló"); continue
        wpm, pausa, clar, dur = _whisper(out, texto_audio, wmodel)
        cw = _to_wav(out)
        fid = _fidelidad(ref_wav, cw) if cw else None
        if cw and os.path.exists(cw): os.remove(cw)
        res.append((model, sp, st, wpm, pausa, clar, fid, out))
        print(f"{model[:10]} sp{sp} st{st:<4} {wpm:6.0f} {pausa:6.2f} {clar:6.2f} {('%.2f'%fid) if fid is not None else '  n/a':>6}")

    if ref_wav and os.path.exists(ref_wav): os.remove(ref_wav)
    if not res:
        print("\nSin resultados."); sys.exit(1)

    # puntaje: cerca de 158 WPM, pausas cortas, claridad y fidelidad altas
    def score(r):
        _, sp, st, wpm, pausa, clar, fid, _ = r
        s = clar * 2 + (fid if fid is not None else 0.5) * 2
        s -= abs(wpm - 158) / 100.0
        s -= max(0, pausa - 0.8)
        return s
    best = max(res, key=score)
    print("\n=== RECOMENDACIÓN ===")
    print(f"Mejor: {best[0]}  speed={best[1]}  stability={best[2]}  "
          f"(WPM {best[3]:.0f}, pausa {best[4]:.2f}s, claridad {best[5]:.2f}, "
          f"fidelidad {('%.2f'%best[6]) if best[6] is not None else 'n/a'})")
    print(f"Para fijarlo:  ELEVENLABS_SPEED={best[1]}  ELEVENLABS_STABILITY={best[2]}  ELEVENLABS_MODEL={best[0]}")
    print(f"(Audios candidatos guardados como cand_*.mp3 para que los escuches.)")

if __name__ == "__main__":
    main()
