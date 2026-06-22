"""
heygen.py — genera TU clon (avatar HeyGen) hablando con TU voz (voice.mp3) y lo deja como WebM TRANSPARENTE
para incrustarlo en el video viral (círculo abajo-centro). El audio se usa de entrada (lipsync); el avatar va
mudo en el montaje (la voz la pone el video viral).

FLUJO (API): subir audio -> generar video del avatar con fondo verde -> esperar -> descargar -> chroma-key -> webm alfa.
Nota de HeyGen: el WebM transparente NO admite avatares personalizados; por eso pedimos fondo verde (#008000)
y le quitamos el verde con ffmpeg.

CONFIG (.env / Secrets):
  HEYGEN_API_KEY     — tu API token de HeyGen (Settings -> API)
  HEYGEN_AVATAR_ID   — el id de tu avatar (usa  python heygen.py --list-avatars  para verlo)

USO:
  python heygen.py --list-avatars                 # lista tus avatares (id + nombre)
  python heygen.py --audio voice.mp3 --out voice_avatar.webm     # genera tu clon -> webm transparente
"""
import os, sys, time, json, subprocess, tempfile
try:
    import requests
except ImportError:
    print("Falta requests: pip install requests"); sys.exit(1)
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

KEY = os.environ.get("HEYGEN_API_KEY", "").strip()
AVATAR = os.environ.get("HEYGEN_AVATAR_ID", "").strip()
API = "https://api.heygen.com"
HDR = {"X-Api-Key": KEY}

def _ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def list_avatars():
    r = requests.get(f"{API}/v2/avatars", headers=HDR, timeout=30)
    if r.status_code != 200:
        print(f"⚠️  HeyGen {r.status_code}: {r.text[:200]}"); return
    d = r.json().get("data", {}) or {}
    print("=== AVATARES (avatar_id) ===")
    for a in (d.get("avatars") or []):
        print(f"  {a.get('avatar_id')}   {a.get('avatar_name','')}")
    print("=== TALKING PHOTOS (talking_photo_id) ===")
    for t in (d.get("talking_photos") or []):
        print(f"  {t.get('talking_photo_id')}   {t.get('talking_photo_name','')}")
    print("\nPon el id elegido en .env como HEYGEN_AVATAR_ID=...")

def _upload_audio(path):
    """Sube el mp3 como asset y devuelve su id (o url)."""
    with open(path, "rb") as f:
        data = f.read()
    r = requests.post("https://upload.heygen.com/v1/asset", headers={"X-Api-Key": KEY, "Content-Type": "audio/mpeg"},
                      data=data, timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"upload audio {r.status_code}: {r.text[:200]}")
    j = r.json().get("data", {}) or {}
    return j.get("id") or j.get("asset_id"), j.get("url")

def _generate(audio_id, audio_url, w=720, h=720):
    voice = {"type": "audio"}
    if audio_id: voice["audio_asset_id"] = audio_id
    elif audio_url: voice["audio_url"] = audio_url
    body = {"video_inputs": [{
        "character": {"type": "avatar", "avatar_id": AVATAR, "avatar_style": "normal"},
        "voice": voice,
        "background": {"type": "color", "value": "#008000"}}],   # verde -> chroma-key -> recorte limpio
        "dimension": {"width": w, "height": h}}
    r = requests.post(f"{API}/v2/video/generate", headers={**HDR, "Content-Type": "application/json"},
                      json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"generate {r.status_code}: {r.text[:300]}")
    return r.json()["data"]["video_id"]

def _wait(video_id, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/v1/video_status.get", headers=HDR, params={"video_id": video_id}, timeout=30)
        d = r.json().get("data", {}) or {}
        st = d.get("status")
        if st == "completed":
            return d.get("video_url")
        if st in ("failed", "error"):
            raise RuntimeError(f"HeyGen falló: {d.get('error') or d}")
        print(f"  HeyGen: {st}... ({int(time.time()-t0)}s)"); time.sleep(8)
    raise RuntimeError("HeyGen: timeout esperando el render")

def _chromakey(mp4_path, out_webm):
    """Quita el verde -> WebM con alfa (VP9 yuva420p) para incrustar."""
    ff = _ff()
    vf = "chromakey=0x008000:0.20:0.10,despill=type=green,format=yuva420p"
    r = subprocess.run([ff, "-y", "-i", mp4_path, "-vf", vf, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                        "-an", "-b:v", "2M", out_webm], capture_output=True)
    return r.returncode == 0 and os.path.exists(out_webm)

def generar(audio="voice.mp3", out="voice_avatar.webm"):
    if not KEY or not AVATAR:
        print("(HeyGen: faltan HEYGEN_API_KEY / HEYGEN_AVATAR_ID; sin avatar)"); return False
    if not os.path.exists(audio):
        print(f"(HeyGen: no encuentro {audio})"); return False
    try:
        aid, aurl = _upload_audio(audio)
        vid = _generate(aid, aurl)
        print(f"  HeyGen: video {vid} en cola...")
        url = _wait(vid)
        tmp = tempfile.mktemp(suffix=".mp4")
        open(tmp, "wb").write(requests.get(url, timeout=180).content)
        ok = _chromakey(tmp, out)
        try: os.remove(tmp)
        except Exception: pass
        print(f"→ {out} listo (clon transparente)" if ok else "(HeyGen: chroma-key falló)")
        return ok
    except Exception as e:
        print(f"(HeyGen: {e})"); return False

if __name__ == "__main__":
    def arg(f, d=None): return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d
    if "--list-avatars" in sys.argv:
        if not KEY: print("Pon HEYGEN_API_KEY en .env primero."); sys.exit(1)
        list_avatars()
    else:
        ok = generar(arg("--audio", "voice.mp3"), arg("--out", "voice_avatar.webm"))
        sys.exit(0 if ok else 1)
