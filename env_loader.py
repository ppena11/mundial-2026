"""
env_loader.py — cargador minimalista de variables desde un archivo .env.
Sin dependencias externas. Lo usan fetch_live.py, fetch_odds.py y run_all.py
para leer API_FOOTBALL_KEY y ODDS_API_KEY sin tener que ponerlas en el código.

Formato del .env (una variable por línea):
    API_FOOTBALL_KEY=tu_clave_aqui
    ODDS_API_KEY=tu_clave_aqui
Se ignoran líneas vacías y las que empiezan con #.
"""
import os

def load_env(path=".env"):
    """Carga el .env en os.environ (no sobreescribe variables ya definidas)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # no pisar lo que ya venga del entorno real del sistema
            os.environ.setdefault(key, val)
