"""
make_reel.py — convierte la INFOGRAFÍA + el AUDIO de ElevenLabs en un VIDEO listo para TikTok.
Usa el ffmpeg portátil de imageio-ffmpeg (no necesitas instalar nada del sistema).

FLUJO:
  1. python make_script.py            -> voiceover.txt
  2. Pega voiceover.txt en ElevenLabs (TU voz) y descarga el audio como  voice.mp3  (en esta carpeta)
  3. python make_reel.py              -> matchday.mp4  (1080x1920, listo para subir)

Música de fondo (opcional, royalty-free): pon un archivo `musica.mp3` en la carpeta (o usa --music /
env MUSIC_FILE). Se mezcla con DUCKING: suena de fondo pero baja sola cuando hablas (la voz manda).

Opciones:
  python make_reel.py --img matchday.png --audio voice.mp3 --out matchday.mp4 [--music musica.mp3]
El video dura lo que dure el audio, con un leve zoom para que no se vea estático.
"""
import sys, os, subprocess
import imageio_ffmpeg

VF = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
      "zoompan=z='min(zoom+0.0004,1.12)':d=1:fps=30:s=1080x1920")

def arg(flag, default):
    return sys.argv[sys.argv.index(flag)+1] if flag in sys.argv else default

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    img = arg("--img", "matchday.png")
    audio = arg("--audio", "voice.mp3")
    out = arg("--out", "matchday.mp4")
    music = arg("--music", os.environ.get("MUSIC_FILE", "musica.mp3"))
    vol = os.environ.get("MUSIC_VOLUME", "0.35")
    if not os.path.exists(img):
        print(f"No encuentro {img}. Genera la infografía primero (make_matchday.py)."); sys.exit(1)
    if not os.path.exists(audio):
        print(f"No encuentro {audio}. Descarga el audio de ElevenLabs y guárdalo como {audio} aquí."); sys.exit(1)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    base = [ff, "-y", "-loop", "1", "-i", img, "-i", audio]

    if music and os.path.exists(music):
        # voz + música con DUCKING (sidechain): la música suena de fondo y baja sola mientras hablas.
        fc = (f"[0:v]{VF}[v];"
              f"[2:a]volume={vol}[m];[1:a]asplit=2[voz][key];"
              f"[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[mduck];"
              f"[voz][mduck]amix=inputs=2:duration=first:dropout_transition=0,volume=1.1[a]")
        cmd = base + ["-stream_loop", "-1", "-i", music, "-filter_complex", fc,
                      "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-tune", "stillimage",
                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-r", "30", out]
        print(f"Generando video con música de fondo ({music}, ducking)...")
        r = _run(cmd)
        if r.returncode == 0:
            print(f"→ {out} listo ({os.path.getsize(out)/1e6:.1f} MB) con música de fondo (voz al frente)."); return
        print(f"(ducking falló, reintento con mezcla simple: {r.stderr[-200:]})")
        # fallback: mezcla simple a volumen bajo fijo
        fc2 = (f"[0:v]{VF}[v];[2:a]volume=0.12[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]")
        cmd = base + ["-stream_loop", "-1", "-i", music, "-filter_complex", fc2,
                      "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-tune", "stillimage",
                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-r", "30", out]
        r = _run(cmd)
        if r.returncode == 0:
            print(f"→ {out} listo con música (mezcla simple)."); return
        print(f"(música falló, hago el video solo con voz: {r.stderr[-200:]})")

    # sin música (o si la música falló): solo voz
    cmd = base + ["-vf", VF, "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                  "-c:a", "aac", "-b:a", "192k", "-shortest", "-r", "30", out]
    print("Generando video..."); r = _run(cmd)
    if r.returncode != 0:
        print("Error de ffmpeg:\n", r.stderr[-800:]); sys.exit(1)
    print(f"→ {out} listo ({os.path.getsize(out)/1e6:.1f} MB).")

if __name__ == "__main__":
    main()
