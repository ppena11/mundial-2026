"""
run_all.py — ORQUESTADOR. Encadena TODO el pipeline en un solo comando.
EJECUTAR EN TU MÁQUINA con Claude Code. Esto es lo que el cron correrá solo cada día.

PIPELINE COMPLETO (lo que antes hacíamos a mano, ahora en 1 paso):
  1. Actualiza resultados reales (re-descarga results.csv)
  2. Baja lesiones + XI confirmado de los partidos de hoy (fetch_live.py)
  3. Baja cuotas y guarda snapshot para el sharp money (fetch_odds.py + money_layer.py)
  4. Reentrena ratings y corre 20.000 simulaciones (v7.py)
  5. Aplica capa de jugador + capa de dinero (player_layer + money_layer)
  6. Genera el pronóstico actualizado + gráfico del día
  7. (opcional) escribe un borrador de guion para el video

Lo ÚNICO que no se puede automatizar: las "noticias blandas" (vestuario, rumores) y
la edición final del video. El resto, corre solo.
"""
import subprocess, sys, json, os
from datetime import datetime

# Ejecuta siempre desde la carpeta del proyecto (los scripts usan rutas relativas)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Carga las API keys desde .env
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

# Fuerza UTF-8 en este proceso y en todos los subprocesos (acentos en consola/logs)
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

LOG=lambda m: print(f"[{datetime.now():%H:%M:%S}] {m}")

FALLOS=[]      # todos los fallos (para la notificación)
CRITICOS=[]    # solo los que deben marcar el run como fallido

def step(name, fn, critico=False):
    LOG(f"▶ {name}")
    try:
        fn(); LOG(f"  ✓ {name}")
    except Exception as e:
        LOG(f"  ✗ {name} falló: {e}  (sigue con lo demás)")
        FALLOS.append(f"{name}: {e}")
        if critico:
            CRITICOS.append(name)

def notify_failures(fallos):
    """Avisa de los fallos por Slack o email, según lo que esté configurado en .env.
    - Slack: define SLACK_WEBHOOK_URL en .env
    - Email: define SMTP_HOST, SMTP_USER, SMTP_PASS, MAIL_TO (y opc. SMTP_PORT)
    Si no hay nada configurado, solo queda en el log."""
    if not fallos:
        return
    msg = "⚠️ Pipeline Mundial 2026 — fallos:\n- " + "\n- ".join(fallos)
    hook = os.environ.get("SLACK_WEBHOOK_URL","").strip()
    if hook:
        try:
            import requests
            requests.post(hook, json={"text": msg}, timeout=15)
            LOG("  → aviso enviado a Slack")
            return
        except Exception as e:
            LOG(f"  (no se pudo avisar por Slack: {e})")
    host=os.environ.get("SMTP_HOST","").strip()
    if host:
        try:
            import smtplib
            from email.mime.text import MIMEText
            m=MIMEText(msg, _charset="utf-8")
            m["Subject"]="Pipeline Mundial 2026: fallos"
            m["From"]=os.environ.get("SMTP_USER","")
            m["To"]=os.environ.get("MAIL_TO", os.environ.get("SMTP_USER",""))
            s=smtplib.SMTP(host, int(os.environ.get("SMTP_PORT","587")), timeout=20)
            s.starttls(); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            s.send_message(m); s.quit()
            LOG("  → aviso enviado por email")
            return
        except Exception as e:
            LOG(f"  (no se pudo avisar por email: {e})")
    LOG("  (sin canal de aviso configurado en .env; los fallos quedan en el log)")

def update_results():
    import urllib.request
    url="https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
    urllib.request.urlretrieve(url, "results.csv")

def fetch_players():
    # Lesiones GRATIS desde ESPN (scraper). Genera injuries.json para player_layer.
    subprocess.run([sys.executable,"fetch_injuries.py"], timeout=60, check=True)

def snapshot_odds():
    subprocess.run([sys.executable,"money_layer.py","--snapshot"], timeout=60, check=True)

def run_sim():
    subprocess.run([sys.executable,"sim20k.py"], timeout=600, check=True)

def detect_money():
    subprocess.run([sys.executable,"money_layer.py","--moves"], timeout=30, check=True)

def make_ensemble():
    # combina modelo (champ_today.json) + mercado (odds_live.json) -> champ_ensemble.png/json
    subprocess.run([sys.executable,"make_ensemble.py"], timeout=60, check=True)

def make_tiktok():
    # gráfico vertical 9:16 estilo TikTok con bajas anotadas -> champ_tiktok.png
    subprocess.run([sys.executable,"make_tiktok.py"], timeout=60, check=True)

if __name__=="__main__":
    LOG("=== PIPELINE DIARIO MUNDIAL 2026 ===")
    step("1. Actualizar resultados reales", update_results, critico=True)
    step("2. Lesiones (scraper ESPN gratis -> injuries.json)", fetch_players)   # opcional
    step("3. Snapshot de cuotas (sharp money)", snapshot_odds)                   # opcional
    step("4. Simulación 20.000 (modelo v7 + lesiones)", run_sim, critico=True)
    step("5. Detección de movimiento de línea", detect_money)                   # opcional
    step("6. Ensemble modelo+mercado (gráfico)", make_ensemble, critico=True)
    step("7. Gráfico TikTok 9:16 (con bajas)", make_tiktok, critico=True)
    notify_failures(FALLOS)
    LOG("=== LISTO. Gráficos: champ_today.png, champ_ensemble.png y champ_tiktok.png ===")
    LOG("Nota: las noticias blandas y el video final siguen siendo manuales.")
    if CRITICOS:
        LOG(f"Fallaron pasos críticos: {CRITICOS}"); sys.exit(1)
    sys.exit(0)
