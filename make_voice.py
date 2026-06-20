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
    "AT&T Stadium": "estadio ei ti an ti", "Arrowhead Stadium": "estadio árrou jed",
    "Mercedes-Benz Stadium": "estadio mercédes bens", "Lincoln Financial Field": "campo línkon fainánshal",
    "Hard Rock Stadium": "estadio jard rok", "Gillette Stadium": "estadio yilét",
    "Levi's Stadium": "estadio lívais", "MetLife Stadium": "estadio métlaif",
    "NRG Stadium": "estadio ene erre ge", "SoFi Stadium": "estadio soufái",
    "Lumen Field": "campo lúmen", "BMO Field": "campo bi em o", "BC Place": "bi si pleis",
    "Estadio BBVA": "estadio be be uve a",
    # ciudades / estados de EE.UU. y Canadá (México y nombres ya españoles se dejan igual)
    "East Rutherford": "íst rázerford", "New Jersey": "niú yérsi", "Kansas City": "kánsas síti",
    "Mexico City": "Ciudad de México", "Miami Gardens": "maiámi gárdens", "Houston": "jiúston",
    "Arlington": "árlinton", "Atlanta": "atlánta", "Foxborough": "fóxboro",
    "Massachusetts": "másachúsets", "Inglewood": "íngluud", "Missouri": "misúri", "Miami": "maiámi",
    "Philadelphia": "filadélfia", "Pennsylvania": "pensilvánia", "Seattle": "siátel",
    "Washington": "wáshinton", "Vancouver": "vankúver", "Texas": "téxas",
}
def foneticizar(text):
    """Reemplaza estadios/ciudades por su fonética en español (solo para el audio de ElevenLabs)."""
    for real in sorted(_FONETICO, key=len, reverse=True):   # los más largos primero (evita reemplazos parciales)
        text = text.replace(real, _FONETICO[real])
    return text

def suavizar_tts(text):
    """Quita lo que ElevenLabs lee como PAUSAS raras: rayas largas, puntos suspensivos, espacios/saltos
    múltiples. Mejora el ritmo y evita cortes bruscos. Solo para el audio (no toca voiceover.txt)."""
    text = text.replace("—", ", ").replace("–", ", ").replace("…", ". ")   # rayas/elipsis -> coma/punto
    text = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s+", " ", text)).strip()  # espacios dobles y antes de signos
    return text

def synth(text, out="voice.mp3"):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2").strip()
    if not key or not voice:
        print("⚠️  Faltan ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID (ponlos en .env o Secrets)."); return False
    fmt = os.environ.get("ELEVENLABS_FORMAT", "").strip()   # p.ej. mp3_44100_192 (Creator+); vacío = default del API
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}" + (f"?output_format={fmt}" if fmt else "")
    def _f(env, d):
        try: return float(os.environ.get(env, d))
        except Exception: return d
    # Ajustes VERIFICADOS (doc + foros) para que suene HUMANA y NO sintética:
    #  - stability ~0.40: rango emocional natural sin caer en inestabilidad (no bajar de 0.30).
    #  - style 0.0: subirlo amplifica emoción PERO causa artefactos y pausas raras -> se deja en 0 (la emoción
    #    sale de la stability baja). Configurable por si se quiere experimentar.
    #  - similarity 0.80: 0.75–0.85 es el punto dulce; al 100% sobre-enuncia ("locutor de noticias").
    vs = {"stability": _f("ELEVENLABS_STABILITY", 0.40),
          "similarity_boost": _f("ELEVENLABS_SIMILARITY", 0.80),
          "style": _f("ELEVENLABS_STYLE", 0.0),
          "use_speaker_boost": os.environ.get("ELEVENLABS_SPEAKER_BOOST", "1") not in ("0", "false", "False")}
    spd = os.environ.get("ELEVENLABS_SPEED", "").strip()   # 0.7–1.2; opcional (solo si se define)
    if spd:
        try: vs["speed"] = float(spd)
        except Exception: pass
    body = {"text": text, "model_id": model, "voice_settings": vs}
    r = requests.post(url, headers={"xi-api-key": key, "Content-Type": "application/json",
                                    "Accept": "audio/mpeg"}, json=body, timeout=60)
    if r.status_code != 200:
        print(f"⚠️  ElevenLabs respondió {r.status_code}: {r.text[:300]}"); return False
    with open(out, "wb") as f:
        f.write(r.content)
    print(f"→ {out} generado con tu voz ({len(r.content)/1000:.0f} KB)")
    return True

if __name__ == "__main__":
    src = arg("--in", "voiceover.txt"); out = arg("--out", "voice.mp3")
    if not os.path.exists(src):
        print(f"No encuentro {src}. Corre make_script.py primero."); sys.exit(1)
    text = open(src, encoding="utf-8").read().strip()
    text = suavizar_tts(foneticizar(text))   # fonética + limpieza de pausas; SOLO para el audio (el .txt no cambia)
    ok = synth(text, out)
    sys.exit(0 if ok else 1)
