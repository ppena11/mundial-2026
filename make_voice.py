"""
make_voice.py — convierte voiceover.txt en voice.mp3 usando TU voz de ElevenLabs (API).
Así el reel se arma SOLO, sin pegar texto a mano.

CONFIG (en .env o GitHub Secrets):
  ELEVENLABS_API_KEY   — tu API key de ElevenLabs
  ELEVENLABS_VOICE_ID  — el ID de tu voz clonada (en ElevenLabs: Voices -> tu voz -> ID)
  ELEVENLABS_MODEL     — (opcional) por defecto eleven_multilingual_v2 (mejor para español)

USO: python make_voice.py [--in voiceover.txt] [--out voice.mp3]
"""
import os, sys, re
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
    # estadios (sílabas separadas por ESPACIOS, no guiones: el guion provoca microcortes en ElevenLabs)
    "AT&T Stadium": "estadio ei ti and ti", "Arrowhead Stadium": "estadio árrou jed",
    "Mercedes-Benz Stadium": "estadio mercédes bens", "Lincoln Financial Field": "campo línkon fainánchal",
    "Hard Rock Stadium": "estadio jard rok", "Gillette Stadium": "estadio yilét",
    "Levi's Stadium": "estadio lívais", "MetLife Stadium": "estadio métlaif",
    "NRG Stadium": "estadio ene erre ye", "SoFi Stadium": "estadio soufái",
    "Lumen Field": "campo lúmen", "BMO Field": "campo bi em ou", "BC Place": "bi si pléis",
    "Estadio BBVA": "estadio be be uve a",
    # ciudades / estados de EE.UU. y Canadá (México y nombres ya españoles se dejan igual)
    "East Rutherford": "íst ráderford", "New Jersey": "niú yérsi", "Kansas City": "kánsas síti",
    "Mexico City": "Ciudad de México", "Miami Gardens": "maiámi gárdens", "Houston": "jiúston",
    "Arlington": "árlinton", "Atlanta": "atlánta", "Foxborough": "fóksboro",
    "Massachusetts": "masachúsets", "Inglewood": "ínguelud", "Missouri": "misúri", "Miami": "maiámi",
    "Philadelphia": "filadélfia", "Pennsylvania": "pensilvánia", "Seattle": "siátel",
    "Washington": "guáchinton", "Vancouver": "vankúver", "Texas": "téksas",
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
    las leerían en voz alta). Se usa para el fallback a v2 y como respaldo."""
    return re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", text)).strip()

_NUM_U = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
          "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve"]
_NUM_D = ["", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
def _num_es(n):
    n = int(n)
    if n < 20: return _NUM_U[n]
    if n < 30: return "veinte" if n == 20 else "veinti" + _NUM_U[n - 20]
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
    vs = {"stability": _f("ELEVENLABS_STABILITY", 0.5 if v3 else 0.45),
          "similarity_boost": _f("ELEVENLABS_SIMILARITY", 0.88),
          "style": _f("ELEVENLABS_STYLE", 0.0),
          "use_speaker_boost": os.environ.get("ELEVENLABS_SPEAKER_BOOST", "1") not in ("0", "false", "False")}
    vs["speed"] = _f("ELEVENLABS_SPEED", 1.07)   # un pelín más ágil que 1.0 (rango 0.7–1.2); configurable
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

def synth(text, out="voice.mp3"):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2").strip()   # v2 = MÁS FIEL a tu voz clonada
    if not key or not voice:
        print("⚠️  Faltan ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID (ponlos en .env o Secrets)."); return False
    fmt = os.environ.get("ELEVENLABS_FORMAT", "").strip()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}" + (f"?output_format={fmt}" if fmt else "")
    hdr = {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"}

    def _attempt(model_id):
        """Devuelve (audio_bytes|None, ultima_respuesta). Hace STITCHING frase a frase con previous/next_text
        para prosodia continua; si solo hay 1 bloque, una sola llamada."""
        v3 = model_id.startswith("eleven_v3")
        speak = text if v3 else quitar_tags(text)   # las etiquetas [..] solo las entiende v3
        vs = _voice_settings(v3)
        bloques = _bloques(speak)
        if len(bloques) <= 1:
            r = requests.post(url, headers=hdr, json={"text": speak, "model_id": model_id, "voice_settings": vs}, timeout=90)
            return (r.content if r.status_code == 200 else None), r
        segs, prev_ids, last = [], [], None
        for i, ch in enumerate(bloques):
            body = {"text": ch, "model_id": model_id, "voice_settings": vs,
                    "previous_text": (" ".join(bloques[:i])[-600:] or None),     # contexto previo (no se factura)
                    "next_text": (" ".join(bloques[i+1:])[:600] or None)}        # contexto siguiente
            if prev_ids:
                body["previous_request_ids"] = prev_ids[-3:]                     # stitching de prosodia
            r = requests.post(url, headers=hdr, json=body, timeout=90); last = r
            if r.status_code != 200:
                return None, r
            segs.append(r.content)
            rid = r.headers.get("request-id") or r.headers.get("x-request-id")
            if rid: prev_ids.append(rid)
        return _concat_mp3(segs), last

    audio, r = _attempt(model)
    if audio is None and model.startswith("eleven_v3"):   # RED DE SEGURIDAD: si v3 falla, usa v2
        print(f"(eleven_v3 no disponible: {getattr(r,'status_code','?')}; uso eleven_multilingual_v2)")
        model = "eleven_multilingual_v2"; audio, r = _attempt(model)
    if audio is None:
        print(f"⚠️  ElevenLabs respondió {getattr(r,'status_code','?')}: {(r.text[:300] if r is not None else '')}"); return False
    with open(out, "wb") as f:
        f.write(audio)
    print(f"→ {out} generado con tu voz ({model}, {len(audio)/1000:.0f} KB, {len(_bloques(quitar_tags(text)))} frases unidas)")
    return True

if __name__ == "__main__":
    src = arg("--in", "voiceover.txt"); out = arg("--out", "voice.mp3")
    if not os.path.exists(src):
        print(f"No encuentro {src}. Corre make_script.py primero."); sys.exit(1)
    text = open(src, encoding="utf-8").read().strip()
    text = suavizar_tts(numeros_a_palabras(foneticizar(text)))   # fonética + números en palabras + limpieza (SOLO audio)
    ok = synth(text, out)
    sys.exit(0 if ok else 1)
