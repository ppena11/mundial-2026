# Serie "Cómo lo construí en un día" — Post 3 (TikTok)

> Los DATOS GRATIS: cómo conecté la IA al mundo real sin pagar (ESPN + The Odds API), con el
> giro honesto de la API de pago que me bloqueó. Visual: b-roll con tus assets + 2 capturas rápidas.

---

## 🎬 Gancho (texto en pantalla, 0-3s)
**DATOS DEL MUNDIAL. GRATIS.**
*(quemado sobre `matchday.png`)*

## 🎙️ Guion de voz (pégalo en ElevenLabs → voice.mp3)

Un modelo es inútil sin datos frescos. Y los datos buenos suelen costar dinero. Así que el reto del día tres fue: cómo alimento mi IA del Mundial sin pagar nada. Primero, resultados y alineaciones: los saco de ESPN, que tiene una puerta de datos pública y gratis. Segundo, las cuotas de las casas: uso una API con plan gratuito, y con eso detecto cuándo mi modelo ve algo distinto al mercado. A eso le llamo valor. Y un detalle honesto: una API de pago me bloqueó los datos del Mundial. En vez de soltar la billetera, le pedí a la IA que buscara una alternativa gratis. La encontró en minutos. Resultado: el sistema se alimenta solo, en tiempo real, sin costo de datos. Lo que parecía necesitar presupuesto, lo resolví dirigiendo a una IA. Mañana, lo más loco: cómo lo puse a correr solo en la nube. Soy aiwithpedro.

## 📱 Caption (TikTok — 5 hashtags)

Alimenté mi IA del Mundial con datos en tiempo real… sin pagar nada 🆓⚽ Y cuando una API de pago me bloqueó, la IA encontró otra gratis. Pronósticos diarios gratis en mi Substack (link en bio). #Mundial2026 #IA #parati #NoCode #DatosGratis

## 🎞️ Texto en pantalla / b-roll (concreto, con assets que ya tienes + 2 capturas)

| Seg | Voz dice… | Visual exacto |
|---|---|---|
| **0-3s** | "…un modelo es inútil sin datos frescos…" | `matchday.png` con el texto **"DATOS DEL MUNDIAL. GRATIS."** quemado |
| **~3-15s** | "…los saco de ESPN, pública y gratis…" | 🎥 **screen-recording del sitio de ESPN** (Mundial) o de `injuries.json`/alineaciones → corta a `matchday.png` (que se vea la nota de bajas) |
| **~15-25s** | "…las cuotas de las casas… a eso le llamo valor…" | `matchday.png` con el **sello "VALOR"** resaltado (zoom) / `odds_live.json` |
| **~25-38s** | "…una API de pago me bloqueó… la IA encontró otra gratis…" | texto en pantalla **"API de pago ❌ → ESPN gratis ✅"** (el giro más compartible) |
| **~38-48s** | "…el sistema se alimenta solo, en tiempo real…" | 🎥 **screen-recording de GitHub Actions**: paso "Datos + simulación" en **verde** |
| **Cierre** | "…mañana: cómo lo puse a correr solo en la nube. Soy aiwithpedro." | tarjeta final **@aiwithpedro · mañana: la nube** |

**La toma que más engancha (captúrala en 30s):**
- 🆚 Una placa simple **"API DE PAGO ❌ vs ESPN GRATIS ✅"** — el "truco" gratis es lo que la gente comenta y comparte.

## 💬 Comentario fijado (para generar debate)
> "¿Pagarías por los datos… o le pedirías a una IA que te encuentre la forma gratis? 👇"

---
*Siguiente post de la serie: la AUTOMATIZACIÓN en la nube (GitHub Actions) — "cómo corre solo cada mañana sin que yo toque nada".*
