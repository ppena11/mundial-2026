"""
render_viral.py — renderiza los videos VIRALES (Remotion) del pronóstico y del recap, sincronizados al audio
ya generado (voice.mp3 / recap_voice.mp3) con los timestamps de palabra (voice_words.json / recap_voice_words.json).

Salidas NUEVAS (no toca matchday.mp4 / recap.mp4):
  - pronostico_viral.mp4
  - recap_viral.mp4

USO:  python render_viral.py [pronostico|recap|both]
Local: pon TEMP en un disco con espacio (en Windows usa E: por defecto). Nube: ejecuta tras npm ci.
"""
import os, sys, json, subprocess, shutil, re

ROOT = os.path.dirname(os.path.abspath(__file__))
VR = os.path.join(ROOT, "video_remotion")
PUB = os.path.join(VR, "public")

def _ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def _dur(path):
    r = subprocess.run([_ff(), "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr or "")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0

def render(comp, audio_src, words_file, data_file, pub_audio, props_name, out_name, avatar_pub):
    if not (os.path.exists(audio_src) and os.path.exists(words_file)):
        print(f"({comp}: faltan {audio_src} o {words_file}; omito)"); return False
    os.makedirs(PUB, exist_ok=True); os.makedirs(os.path.join(VR, "out"), exist_ok=True)
    shutil.copy(audio_src, os.path.join(PUB, pub_audio))
    mus = os.path.join(ROOT, "musica.mp3")
    if os.path.exists(mus): shutil.copy(mus, os.path.join(PUB, "musica.mp3"))
    # avatar HeyGen (opcional): genera tu clon hablando con la voz -> webm transparente -> público
    avatar_name = ""
    keep = ("--keep-avatar" in sys.argv) or os.environ.get("RENDER_KEEP_AVATAR")
    if keep and os.path.exists(os.path.join(PUB, avatar_pub)):
        avatar_name = avatar_pub; print(f"(avatar: reuso {avatar_pub}, sin regenerar)")
    else:
        try:
            import heygen
            if heygen.KEY and heygen.AVATAR:
                webm = os.path.splitext(audio_src)[0] + "_avatar.webm"
                if heygen.generar(audio_src, webm) and os.path.exists(webm):
                    shutil.copy(webm, os.path.join(PUB, avatar_pub)); avatar_name = avatar_pub
        except Exception as e:
            print(f"(avatar HeyGen omitido: {e})")
    words = json.load(open(words_file, encoding="utf-8"))
    data = json.load(open(data_file, encoding="utf-8")) if os.path.exists(data_file) else {}
    props = {"words": words, "data": data, "audio": pub_audio, "durationSec": round(_dur(audio_src), 2), "avatar": avatar_name}
    json.dump(props, open(os.path.join(PUB, props_name), "w", encoding="utf-8"), ensure_ascii=False)
    env = dict(os.environ)
    if sys.platform == "win32" and not env.get("TEMP", "").lower().startswith("e:"):
        tmp = "E:\\remotion_tmp"; os.makedirs(tmp, exist_ok=True)
        env["TEMP"] = env["TMP"] = env["TMPDIR"] = tmp
    conc = os.environ.get("RENDER_CONCURRENCY", "2")   # 2 en local (disco/CPU justos); en la nube se sube a $(nproc)
    cmd = (f'npx remotion render src/index.ts {comp} out/{out_name} '
           f'--props=public/{props_name} --codec h264 --crf 18 --concurrency {conc}')
    print(f"render {comp} ({props['durationSec']}s)...")
    r = subprocess.run(cmd, cwd=VR, env=env, shell=True)
    if r.returncode != 0 or not os.path.exists(os.path.join(VR, "out", out_name)):
        print(f"({comp}: render falló, rc={r.returncode})"); return False
    shutil.copy(os.path.join(VR, "out", out_name), os.path.join(ROOT, out_name))
    print(f"→ {out_name} listo"); return True

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    ok = True
    if what in ("pronostico", "both"):
        ok = render("PronosticoViral", "voice.mp3", "voice_words.json", "viral_pronostico.json",
                    "voz.mp3", "pronostico_props.json", "pronostico_viral.mp4", "voz_avatar.webm") and ok
    if what in ("recap", "both"):
        ok = render("RecapViral", "recap_voice.mp3", "recap_voice_words.json", "viral_recap.json",
                    "recap_voz.mp3", "recap_props.json", "recap_viral.mp4", "recap_avatar.webm") and ok
    sys.exit(0 if ok else 1)
