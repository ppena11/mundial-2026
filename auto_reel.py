"""
auto_reel.py — REEL DIARIO 100% automático: infografía -> guion -> voz (ElevenLabs) -> video.
Un solo comando produce matchday.mp4 listo para subir a TikTok (+ caption.txt).

Requiere en .env / Secrets: ELEVENLABS_API_KEY y ELEVENLABS_VOICE_ID (ver make_voice.py).

USO: python auto_reel.py [--date YYYYMMDD]
"""
import subprocess, sys
from datetime import date

def run(args, critical=True):
    r = subprocess.run([sys.executable] + args)
    if r.returncode != 0 and critical:
        print(f"✗ Falló: {' '.join(args)}"); sys.exit(1)
    return r.returncode == 0

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    print(f"=== Reel automático para {target} ===")
    run(["make_matchday.py", "--date", target])      # 1) infografía -> matchday.png
    run(["make_script.py", "--date", target])        # 2) guion -> voiceover.txt + caption.txt
    if not run(["make_voice.py"], critical=False):   # 3) voz ElevenLabs -> voice.mp3
        print("⚠️  Sin audio (revisa las claves de ElevenLabs). No se arma el video."); sys.exit(1)
    run(["make_reel.py"])                             # 4) infografía + voz -> matchday.mp4
    print("✓ Listo: matchday.mp4 + caption.txt. Súbelo a TikTok.")
