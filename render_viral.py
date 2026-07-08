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
                _keepbg = bool(os.environ.get("HEYGEN_KEEP_BG"))   # avatar con fondo (estadio): sin chroma-key
                if heygen.generar(audio_src, webm, keep_bg=_keepbg) and os.path.exists(webm):
                    shutil.copy(webm, os.path.join(PUB, avatar_pub)); avatar_name = avatar_pub
        except Exception as e:
            print(f"(avatar HeyGen omitido: {e})")
    words = json.load(open(words_file, encoding="utf-8"))
    data = json.load(open(data_file, encoding="utf-8")) if os.path.exists(data_file) else {}
    props = {"words": words, "data": data, "audio": pub_audio, "durationSec": round(_dur(audio_src), 2),
             "avatar": avatar_name, "avatarStadium": bool(os.environ.get("HEYGEN_KEEP_BG"))}
    json.dump(props, open(os.path.join(PUB, props_name), "w", encoding="utf-8"), ensure_ascii=False)
    env = dict(os.environ)
    if sys.platform == "win32" and not env.get("TEMP", "").lower().startswith("e:"):
        tmp = "E:\\remotion_tmp"; os.makedirs(tmp, exist_ok=True)
        env["TEMP"] = env["TMP"] = env["TMPDIR"] = tmp
    conc = os.environ.get("RENDER_CONCURRENCY") or str(os.cpu_count() or 4)   # local: TODOS los núcleos; nube: $(nproc); override por env
    cmd = (f'npx remotion render src/index.ts {comp} out/{out_name} '
           f'--props=public/{props_name} --codec h264 --crf 18 --concurrency {conc}')
    print(f"render {comp} ({props['durationSec']}s)...")
    r = subprocess.run(cmd, cwd=VR, env=env, shell=True)
    if r.returncode != 0 or not os.path.exists(os.path.join(VR, "out", out_name)):
        print(f"({comp}: render falló, rc={r.returncode})"); return False
    shutil.copy(os.path.join(VR, "out", out_name), os.path.join(ROOT, out_name))
    print(f"→ {out_name} listo"); return True

def _bracket_data():
    """Archivo data para BracketViral ({'fecha','bracket'}) desde viral_bracket.json; None si no hay cuadro."""
    try:
        br = json.load(open(os.path.join(ROOT, "viral_bracket.json"), encoding="utf-8"))
        if len(br.get("qf") or []) != 4: return None
    except Exception:
        return None
    from datetime import date
    d = {"fecha": date.today().strftime("%d/%m/%Y"), "bracket": br}
    p = os.path.join(ROOT, "viral_bracket_video.json")
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p

def still_bracket():
    """PNG del cuadro (frame con la animación ya asentada) -> bracket.png (post de imagen en días sin partido)."""
    dfile = _bracket_data()
    if not dfile: print("(bracket.png: sin viral_bracket.json; omito)"); return False
    os.makedirs(PUB, exist_ok=True); os.makedirs(os.path.join(VR, "out"), exist_ok=True)
    props = {"words": [], "data": json.load(open(dfile, encoding="utf-8")), "audio": "", "durationSec": 8,
             "avatar": "", "avatarStadium": False}
    json.dump(props, open(os.path.join(PUB, "bracket_still_props.json"), "w", encoding="utf-8"), ensure_ascii=False)
    r = subprocess.run("npx remotion still src/index.ts BracketViral out/bracket.png "
                       "--props=public/bracket_still_props.json --frame=170", cwd=VR, shell=True)
    if r.returncode == 0 and os.path.exists(os.path.join(VR, "out", "bracket.png")):
        shutil.copy(os.path.join(VR, "out", "bracket.png"), os.path.join(ROOT, "bracket.png"))
        print("→ bracket.png listo"); return True
    return False

def _hay_partidos_hoy():
    try:
        vp = json.load(open(os.path.join(ROOT, "viral_pronostico.json"), encoding="utf-8"))
        from datetime import date
        if vp.get("target") and vp["target"] != date.today().strftime("%Y%m%d"):
            return False   # export VIEJO (de un día anterior): hoy no hubo pronóstico (día sin partidos)
        return bool(vp.get("partidos"))
    except Exception:
        return True   # ante la duda, comportamiento clásico

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    ok = True
    if what in ("pronostico", "both") and not _hay_partidos_hoy() and _bracket_data():
        print("(día sin partidos: el CUADRO es el contenido -> BracketViral en vez de PronosticoViral)")
        what = {"pronostico": "bracket", "both": "bracket+recap"}[what]
    if what in ("pronostico", "both"):
        ok = render("PronosticoViral", "voice.mp3", "voice_words.json", "viral_pronostico.json",
                    "voz.mp3", "pronostico_props.json", "pronostico_viral.mp4", "voz_avatar.webm") and ok
    if what in ("bracket", "bracket+recap"):
        dfile = _bracket_data()
        if dfile:
            ok = render("BracketViral", "voice.mp3", "voice_words.json", dfile,
                        "voz.mp3", "bracket_props.json", "bracket_viral.mp4", "voz_avatar.webm") and ok
        still_bracket()   # PNG del cuadro para el post de imagen (aunque no haya voz)
    if what in ("recap", "both", "bracket+recap"):
        ok = render("RecapViral", "recap_voice.mp3", "recap_voice_words.json", "viral_recap.json",
                    "recap_voz.mp3", "recap_props.json", "recap_viral.mp4", "recap_avatar.webm") and ok
    sys.exit(0 if ok else 1)
