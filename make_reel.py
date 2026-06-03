"""
make_reel.py — convierte la INFOGRAFÍA + el AUDIO de ElevenLabs en un VIDEO listo para TikTok.
Usa el ffmpeg portátil de imageio-ffmpeg (no necesitas instalar nada del sistema).

FLUJO:
  1. python make_script.py            -> voiceover.txt
  2. Pega voiceover.txt en ElevenLabs (TU voz) y descarga el audio como  voice.mp3  (en esta carpeta)
  3. python make_reel.py              -> matchday.mp4  (1080x1920, listo para subir)

Opciones:
  python make_reel.py --img matchday.png --audio voice.mp3 --out matchday.mp4
El video dura lo que dure el audio, con un leve zoom para que no se vea estático.
"""
import sys, os, subprocess
import imageio_ffmpeg

def arg(flag, default):
    return sys.argv[sys.argv.index(flag)+1] if flag in sys.argv else default

def main():
    img = arg("--img", "matchday.png")
    audio = arg("--audio", "voice.mp3")
    out = arg("--out", "matchday.mp4")
    if not os.path.exists(img):
        print(f"No encuentro {img}. Genera la infografía primero (make_matchday.py)."); sys.exit(1)
    if not os.path.exists(audio):
        print(f"No encuentro {audio}. Descarga el audio de ElevenLabs y guárdalo como {audio} aquí."); sys.exit(1)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    # imagen fija + audio -> mp4 vertical 1080x1920, con leve zoom (Ken Burns) para dar vida
    vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "zoompan=z='min(zoom+0.0004,1.12)':d=1:fps=30:s=1080x1920")
    cmd = [ff, "-y", "-loop", "1", "-i", img, "-i", audio,
           "-vf", vf, "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-r", "30", out]
    print("Generando video..."); r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("Error de ffmpeg:\n", r.stderr[-800:]); sys.exit(1)
    mb = os.path.getsize(out)/1e6
    print(f"→ {out} listo ({mb:.1f} MB). Súbelo a TikTok con el caption de caption.txt.")

if __name__ == "__main__":
    main()
