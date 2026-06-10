"""
check_voz.py — VALIDADOR (dry-run) del voiceover que genera la IA (Claude) ANTES de ElevenLabs.

Genera el guion hablado llamando a Claude igual que el pipeline y muestra el TEXTO EXACTO que se
enviaría a ElevenLabs, con un reporte de acentos, pausas, tokens en inglés (que pueden hacer que
ElevenLabs pierda la acentuación española) y mojibake. NO llama a ElevenLabs (cero audio, cero gasto).

USO:
  python check_voz.py --kind curio [--date YYYYMMDD]
  python check_voz.py --kind pronostico [--date YYYYMMDD]
  python check_voz.py --kind recap [--date YYYYMMDD]
"""
import sys, re
from datetime import date
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag)+1] if flag in sys.argv else default

ACC = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
BRANDS = ("aiwithpedro", "github", "espn", "api", "tiktok", "substack", "elevenlabs", "dixon")

def report(text):
    palabras = re.findall(r"[^\W\d_]+", text, flags=re.UNICODE)
    acc = sorted({w for w in palabras if any(c in ACC for c in w)}, key=str.lower)
    pausas = {"puntos": text.count("."), "comas": text.count(","),
              "puntos_susp": text.count("…") + text.count("..."), "saltos_de_linea": text.count("\n")}
    riesgo = sorted({w for w in re.findall(r"[A-Za-z]+", text)
                     if w.lower() in BRANDS or re.search(r"w|k|th|sh", w.lower())}, key=str.lower)
    n_words = len(palabras)

    print("===== TEXTO EXACTO QUE SE ENVIARÍA A ELEVENLABS =====\n")
    print(text)
    print("\n===== REPORTE =====")
    print(f"Palabras: {n_words}  ·  ~{round(n_words/2.6)} s aprox. de voz")
    print(f"\n✓ Acentos detectados ({len(acc)}):")
    print("  " + (", ".join(acc) if acc else "NINGUNO ⚠️ (sospechoso: un guion en español debería tener tildes)"))
    print(f"\n⏸  Pausas: {pausas['puntos']} puntos · {pausas['comas']} comas · "
          f"{pausas['puntos_susp']} puntos suspensivos · {pausas['saltos_de_linea']} saltos de línea")
    print(f"\n🇬🇧 Tokens en inglés (riesgo de que ElevenLabs pierda el acento):")
    print("  " + (", ".join(riesgo) if riesgo else "ninguno ✓"))
    if "Ã" in text or "Â" in text or " Â" in text:
        print("\n❌ POSIBLE MOJIBAKE (encoding roto): aparecen 'Ã'/'Â' — los acentos NO están en Unicode correcto.")
    else:
        print("\n✓ Sin mojibake: los acentos están en Unicode correcto (utf-8).")
    print("\n— Recuerda: esto valida el TEXTO de entrada. Cómo SUENA (pronunciación) se confirma escuchando el mp3.")

if __name__ == "__main__":
    kind = arg("--kind", "pronostico")
    target = arg("--date", date.today().strftime("%Y%m%d"))
    print(f"Generando voiceover con Claude (kind={kind}, fecha={target})...\n")
    if kind == "curio":
        import curio; text = curio.build(target).get("voz", "")
    elif kind == "recap":
        import recap; cu = recap.build(target); text = "" if cu.get("empty") else cu.get("voz", "")
    else:
        import make_script; vo, cap, n = make_script.build(target); text = vo
    if not text.strip():
        print("(sin voiceover para esa fecha/kind — p. ej. recap sin jornada previa)"); sys.exit(0)
    report(text)
