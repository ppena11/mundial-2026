"""
make_voice.py — convierte voiceover.txt en voice.mp3 usando TU voz de ElevenLabs (API).
Así el reel se arma SOLO, sin pegar texto a mano.

CONFIG (en .env o GitHub Secrets):
  ELEVENLABS_API_KEY   — tu API key de ElevenLabs
  ELEVENLABS_VOICE_ID  — el ID de tu voz clonada (en ElevenLabs: Voices -> tu voz -> ID)
  ELEVENLABS_MODEL     — (opcional) por defecto eleven_multilingual_v2 (mejor para español)

USO: python make_voice.py [--in voiceover.txt] [--out voice.mp3]
"""
import os, sys
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

def synth(text, out="voice.mp3"):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2").strip()
    if not key or not voice:
        print("⚠️  Faltan ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID (ponlos en .env o Secrets)."); return False
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    body = {"text": text, "model_id": model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True}}
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
    ok = synth(text, out)
    sys.exit(0 if ok else 1)
