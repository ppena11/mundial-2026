# Serie "Cómo lo construí en un día" — Post 2 (TikTok)

> El CEREBRO: cómo le pedí a la IA el modelo (Dixon-Coles + Montecarlo), explicado simple, sin código.
> Visual: b-roll con tus assets (carrera por el título, infografías).

---

## 🎬 Gancho (texto en pantalla, 0-3s)
**20.000 MUNDIALES. EN PARALELO.**
*(quemado sobre `champ_today.png`)*

## 🎙️ Guion de voz (pégalo en ElevenLabs → voice.mp3)

En el primer video te dije que construí una IA que predice el Mundial, sin código. Hoy te muestro su cerebro, y es más simple de lo que crees. Le pedí tres cosas. Una: que aprendiera la fuerza de cada selección con casi cincuenta mil partidos reales. Cada equipo queda con dos números, qué tan bien ataca y qué tan bien defiende. Dos: que ajustara el contexto. La ventaja de jugar en casa, y una corrección para los partidos de pocos goles, que son los más difíciles de predecir. Y tres, lo más potente: que jugara el Mundial completo veinte mil veces. En cada simulación inventa los goles de cada partido según esos números, resuelve los grupos, las eliminatorias y la final, y anota quién sale campeón. Al terminar, cuenta cuántas veces ganó cada selección. Eso es la probabilidad. No es opinión: son veinte mil mundiales en paralelo. Y yo solo se lo pedí, en español. En el siguiente video te muestro de dónde saco los datos, gratis. Soy aiwithpedro.

## 📱 Caption (TikTok — 5 hashtags)

El cerebro de mi IA que predice el Mundial: aprende de 50.000 partidos y juega el torneo 20.000 veces 🧠⚽ Y no escribí código. Pronósticos diarios gratis en mi Substack (link en bio). #Mundial2026 #IA #parati #Estadistica #NoCode

## 🎞️ Texto en pantalla / b-roll (concreto, con assets que ya tienes o capturas en 1 min)

| Seg | Voz dice… | Visual exacto |
|---|---|---|
| **0-3s** | "…te muestro su cerebro…" | `champ_today.png` con el texto **"20.000 MUNDIALES EN PARALELO"** quemado |
| **~3-12s** | "…la fuerza… 50.000 partidos… ataca y defiende…" | 🎥 **screen-recording scrolleando `results.csv`** (miles de filas) → corta a `champ_tiktok.png` |
| **~12-22s** | "…la ventaja de local… pocos goles…" | `matchday.png` (que se vea un marcador bajo tipo 1-0) o la infografía con la nota de bajas |
| **~22-40s** | "…jugara el Mundial veinte mil veces… grupos… campeón…" | 🎥 **screen-recording del terminal: `python sim_live.py`** mostrando "20.000 simulaciones" y la tabla de % apareciendo → cierra en `champ_today.png` |
| **~40-50s** | "…no es opinión… solo se lo pedí en español…" | 🎥 (opcional, el más potente) screen-recording de **ti escribiéndole un prompt a la IA** |
| **Cierre** | "…en el siguiente, los datos gratis. Soy aiwithpedro." | tarjeta final **@aiwithpedro · siguiente: los datos gratis** |

**Las 2 tomas que más impactan (captúralas en 1 min):**
1. 📜 **`results.csv` scrolleando** → prueba visual de "50.000 partidos reales" (ábrelo en Excel/VS Code y graba mientras bajas rápido).
2. 💻 **`python sim_live.py` en el terminal** → se ve "20.000 simulaciones" y las probabilidades imprimiéndose. Prueba pura del "20.000 mundiales".

## 💬 Comentario fijado (para generar debate)
> "¿A qué selección le darías tú más chance de ser campeón? El modelo ya tiene su favorita 👇"

---
*Siguiente post de la serie: los DATOS GRATIS (ESPN + The Odds API) — "cómo la conecté al mundo real sin pagar".*
