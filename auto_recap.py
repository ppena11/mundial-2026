"""
auto_recap.py — CIERRE DEL DÍA 100% automático: recap -> tarjeta -> voz -> video.
Produce recap.png, recap.mp4, recap_digest.* y recap_caption.txt (set aparte del pronóstico).
Si la jornada a recapitular no tiene partidos (pre-torneo / día sin partidos), sale sin hacer nada.

USO: python auto_recap.py [--date YYYYMMDD]   (por defecto: AYER en ET)
"""
import subprocess, sys
import recap

def run(args, critical=True):
    r = subprocess.run([sys.executable] + args)
    if r.returncode != 0 and critical:
        print(f"✗ Falló: {' '.join(args)}"); sys.exit(1)
    return r.returncode == 0

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else recap.yesterday_et()
    print(f"=== Cierre del día para {target} ===")
    cu = recap.build(target)                              # genera recap_today.json + voz + caption (+ digest abajo)
    if cu.get("empty"):
        print("No hay partidos que recapitular; no se genera cierre."); sys.exit(0)
    run(["recap.py", "--date", target])                  # escribe recap_digest.md/html
    run(["make_recap.py", "--date", target])             # recap.png
    if not run(["make_voice.py", "--in", "recap_voiceover.txt", "--out", "recap_voice.mp3"], critical=False):
        print("⚠️  Sin audio del cierre (revisa ElevenLabs). Queda la tarjeta y el digest."); sys.exit(0)
    run(["make_reel.py", "--img", "recap.png", "--audio", "recap_voice.mp3", "--out", "recap.mp4"])
    run(["subtitulos.py", "--video", "recap.mp4", "--audio", "recap_voice.mp3", "--text", "recap_voiceover.txt"], critical=False)
    print("✓ Listo: recap.mp4 + recap.png + recap_digest.html + recap_caption.txt.")
