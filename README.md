# Modelo Mundial 2026 ⚽

Simulación del Mundial 2026 (Dixon-Coles + Poisson + Montecarlo, 20.000 sims) con
ajuste por lesiones y XI confirmado, corrección de mercado y gráficos para redes.
Corre **solo en la nube** con GitHub Actions (no necesita tu PC encendida).

## Automatizado (GitHub Actions)
| Workflow | Cuándo | Qué hace |
|---|---|---|
| **Pronóstico diario** | 08:00 (UTC-4) | resultados → lesiones → cuotas → 20.000 sims → 3 gráficos |
| **Snapshot de cuotas** | cada 2h | guarda cuotas para detectar *sharp money* |
| **Predecir partido** | botón manual | 1X2 de un partido con XI confirmado + lesiones |

## Gráficos que genera (en la raíz del repo)
- `champ_today.png` — modelo puro (con lesiones)
- `champ_ensemble.png` — modelo + corrección de mercado
- `champ_tiktok.png` — vertical 9:16 con bajas, para TikTok/Reels
- `champ_match.png` — pronóstico de un partido concreto

## Correr a mano (opcional, en tu PC)
```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python run_all.py                       # pipeline completo
venv\Scripts\python fetch_lineup.py "Espana" "Francia"   # XI confirmado (~1h antes)
venv\Scripts\python predict_match.py "Espana" "Francia"  # 1X2 del partido
```

## Claves
Las API keys (`ODDS_API_KEY`, `API_FOOTBALL_KEY`) van en **Settings → Secrets and variables → Actions**
del repo. En local, en un archivo `.env` (no se sube).

## Fuentes de datos (gratis)
- Resultados: martj42/international_results · Calendario: openfootball
- Cuotas: The Odds API · Lesiones y XI: API pública de ESPN

*Contenido informativo. No es consejo de apuestas.*
