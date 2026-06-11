# ⚽🤖 Mundial 2026 — predicho por IA

Un sistema que **predice el Mundial 2026 con inteligencia artificial** y publica un pronóstico nuevo cada día — comparándolo, sin esconder nada, con el resultado real (aciertos **y** fallos).

> ### Lo construyó una IA
> Todo este repositorio —el modelo estadístico, la automatización en la nube, la voz, las infografías y las pruebas— se levantó **dirigiendo a una IA en lenguaje natural, sin escribir código a mano**, en un día. Este repo es la prueba, abierta para que la **audites**.

📲 **Míralo en acción:** TikTok **[@aiwithpedro](https://www.tiktok.com/@aiwithpedro)** · Substack: *El Mundial con IA*

---

## 🧠 ¿Cómo funciona? (resumen)

- **Modelo (el cerebro):** Dixon-Coles + Poisson sobre ~49.000 partidos internacionales. Ataque/defensa por equipo estimados por **máxima verosimilitud** (L-BFGS-B + gradiente analítico), con **decaimiento temporal** (vida media 730 d), **ridge** y la **corrección de marcadores bajos (ρ)** del paper original.
- **Ajustes:** **lesiones y XI confirmado** (capa de jugador, en escala log-goles) + **corrección de mercado** (de-vig de cuotas + *ensemble* 50/50 + detección de *sharp money* por movimiento de línea).
- **Campeón:** **Monte Carlo** — 20.000 simulaciones del torneo completo, **condicionadas a los resultados reales** según avanza.
- **Contenido:** **Claude** redacta el texto (los **números siempre los pone el modelo**, no se inventan), **ElevenLabs** la voz clonada, **matplotlib** las infografías y **ffmpeg** el video.
- **Automatización:** **GitHub Actions** corre todo solo cada mañana (gratis) y **se auto-commitea** el estado.

📄 **Explicación técnica completa (con fórmulas + una auditoría simulada):** [`POST_TECNICO.md`](POST_TECNICO.md)

---

## 🤖 Automatizado (GitHub Actions)

| Workflow | Cuándo (UTC) | Qué hace |
|---|---|---|
| **Contenido diario** | 10:10 (6:10 AM ET) | resultados → lesiones → cuotas → 20.000 sims → infografía + voz + video + digest |
| **Snapshot de cuotas** | cada 2 h (min :30) | guarda cuotas en `odds_history.jsonl` para detectar *sharp money* |
| **Predecir partido** | botón manual | 1X2 de un partido con XI confirmado + lesiones |

## ▶️ Correr a mano (opcional, en tu PC)

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python run_all.py                       # pipeline completo (datos + 20.000 sims)
venv\Scripts\python predict_match.py "Espana" "Francia"   # 1X2 de un partido
venv\Scripts\python test_suite.py                    # batería de 37 pruebas
```

## 🗂️ Mapa del código (lo esencial)

| Archivo | Qué es |
|---|---|
| `fit_dc.py` | El modelo Dixon-Coles (ajuste por MLE + ρ). |
| `predict_match.py` | Probabilidad 1X2 de un partido (con lesiones/XI). |
| `engine.py` / `sim_live.py` | Motor Monte Carlo del torneo (consciente de resultados). |
| `player_layer.py` | Ajuste por lesiones (escala log-goles). |
| `money_layer.py` / `make_ensemble.py` | De-vig, *ensemble* modelo+mercado y *sharp money*. |
| `make_*.py` | Infografías, voz, video, digest. `test_suite.py` | 37 pruebas. |

## 📦 Fuentes de datos (todas gratis)

- **Histórico** (~49k partidos): [`martj42/international_results`](https://github.com/martj42/international_results)
- **Resultados, XI y lesiones:** API pública de ESPN (con *fallback* por proxy)
- **Cuotas:** The Odds API · **Banderas:** flagcdn

## 🔐 Claves

Las API keys van en **Settings → Secrets and variables → Actions** (encriptadas, **nunca** en el código). En local, en un `.env` (ignorado por git).

---

*Contenido informativo y educativo. Son predicciones de un modelo estadístico, **no certezas**, y **no constituyen consejo de apuestas**. El fútbol es hermoso justamente porque sorprende.*
