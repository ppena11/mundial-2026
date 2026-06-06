# 🎬 Guía de sesión de grabación — Serie "Cómo lo construí en un día"

> Graba los 5 de una sentada. Aquí tienes TODO en orden: las 5 voces, el b-roll a capturar una vez,
> y el armado. Captions + comentarios fijados están en cada `serie_diaN.md`. Calendario: `CALENDARIO_SERIE.md`.

---

## A) 🎙️ VOCES — pega en ElevenLabs en orden (descarga `voz1.mp3 … voz5.mp3`)

### 🟢 VOZ 1 — Overview
Me propuse algo que sonaba imposible: construir una inteligencia artificial que prediga el Mundial 2026, en un solo día, y sin escribir una sola línea de código. Spoiler: lo logré. Te cuento cómo, en tres pasos. Uno: le pedí a la IA que creara el cerebro. Un modelo que aprende de casi cincuenta mil partidos y simula el Mundial veinte mil veces para estimar quién gana cada juego. Dos: la conecté a datos gratis. Resultados, lesiones y alineaciones, en tiempo real. Tres, y esto es lo mejor: la puse a vivir en la nube. Cada mañana, sola, baja los datos, corre las simulaciones, arma la infografía y hasta narra el video con mi voz. Yo no muevo un dedo. Lo que antes le tomaba semanas a un equipo, lo dirigí en horas, solo conversando con una IA. Y el punto es este: hoy, tú también puedes. Esta semana te muestro cada paso. Sígueme. Soy aiwithpedro.

### 🟢 VOZ 2 — El cerebro (modelo)
En el primer video te dije que construí una IA que predice el Mundial, sin código. Hoy te muestro su cerebro, y es más simple de lo que crees. Le pedí tres cosas. Una: que aprendiera la fuerza de cada selección con casi cincuenta mil partidos reales. Cada equipo queda con dos números, qué tan bien ataca y qué tan bien defiende. Dos: que ajustara el contexto. La ventaja de jugar en casa, y una corrección para los partidos de pocos goles, que son los más difíciles de predecir. Y tres, lo más potente: que jugara el Mundial completo veinte mil veces. En cada simulación inventa los goles de cada partido según esos números, resuelve los grupos, las eliminatorias y la final, y anota quién sale campeón. Al terminar, cuenta cuántas veces ganó cada selección. Eso es la probabilidad. No es opinión: son veinte mil mundiales en paralelo. Y yo solo se lo pedí, en español. En el siguiente video te muestro de dónde saco los datos, gratis. Soy aiwithpedro.

### 🟢 VOZ 3 — Datos gratis
Mi inteligencia artificial predice el Mundial. Pero una IA sin datos es como un cerebro sin ojos: no ve nada. Y los buenos datos casi siempre cuestan dinero. Mi reto del día tres fue conseguirlos gratis. Los resultados y las alineaciones los saco de ESPN, gratis y en vivo. Y para saber si mi IA ve algo que los demás no ven, comparo sus números con los de los expertos. Pero pasó algo: una página de datos de pago me bloqueó el Mundial. ¿Y sabes qué hice? No pagué nada. Le pedí a la IA que buscara otra forma gratis, y la encontró en minutos. Así mi sistema se alimenta solo, en vivo, sin gastar un peso. Lo que parecía costar una fortuna, lo resolví solo hablándole a una IA. En el siguiente video, lo más loco: cómo trabaja solo mientras yo duermo. Soy aiwithpedro.

### 🟢 VOZ 4 — La nube (corre solo)
Ya tenía el cerebro y los datos. Pero no quería ejecutar todo a mano cada mañana. Así que puse un robot a trabajar por mí, gratis, en la nube. Usé GitHub Actions, una herramienta gratuita para programar tareas, y le di una orden: todos los días, a las seis de la mañana, despiértate y haz todo. Y lo hace solo. Baja resultados, lesiones y cuotas, corre las veinte mil simulaciones, arma la infografía, escribe el guion y guarda todo, sin que yo toque nada. Mi computadora puede estar apagada. Esto tiene nombre: inteligencia artificial agéntica. No es una IA que responde, es una IA que actúa. Y lo monté gratis, solo describiéndole lo que quería. Lo que sonaba a tener un equipo y servidores, lo hace un agente solo, cada amanecer. En el siguiente, la guinda: le di mi propia voz. Soy aiwithpedro.

### 🟢 VOZ 5 — La voz + cierre/lanzamiento
Escucha bien esta voz, la que te habla ahora mismo. No la grabé hoy, ni ayer: es un clon de mi voz, hecho con inteligencia artificial. Esta es la última pieza. Cloné mi voz una sola vez, con unos minutos de audio. Desde entonces, cada día el sistema escribe el guion con IA y se lo entrega a mi voz clonada, que lo narra sola. El video del Mundial se arma completo, con mi voz, sin que yo abra el micrófono. Lo grabé una vez, narra para siempre. Y con esto se cierra la magia: un modelo que predice, datos gratis, un agente que corre solo en la nube, y mi voz contándolo. Todo en un día, dirigiendo a una IA, sin escribir código. Ahora viene lo mejor: el Mundial empieza el once de junio, y te voy a mostrar los aciertos, y también los fallos, con total honestidad. Sígueme. Soy aiwithpedro.

---

## B) 🎞️ B-ROLL — captura cada toma UNA vez y reúsala

**Capturas a grabar (screen-recording, ~10-20s c/u):**
- **A.** Lista de corridas **verdes** de GitHub Actions
- **B.** El commit `github-actions[bot] · Contenido del día`
- **C.** `results.csv` scrolleando (miles de filas) — abre en Excel/VS Code
- **D.** Terminal corriendo `python sim_live.py` ("20.000 simulaciones" + % imprimiéndose)
- **E.** Pantalla de **ElevenLabs** con tu voz clonada
- **F.** Sitio de **ESPN** (Mundial) / `injuries.json`
- **G.** Placa simple **"API de pago ❌  vs  ESPN gratis ✅"**
- **H.** Una **onda de audio** (tu voz sonando)

**Assets que YA existen (en el artifact / repo):** `champ_today.png`, `champ_tiktok.png`, `matchday.png`, `recap.png`, `matchday.mp4`.

**Qué toma usa cada post (para reusar sin recapturar):**
| Post | Tomas / assets |
|---|---|
| 1 — Overview | `matchday.png` · `champ_today.png` · **F** (ESPN) · **A** (Actions) · `matchday.mp4` |
| 2 — Cerebro | `champ_today.png` · **C** (results.csv) · `champ_tiktok.png` · `matchday.png` · **D** (terminal sim) |
| 3 — Datos | `matchday.png` (sello VALOR) · **F** (ESPN) · **G** (placa API❌/ESPN✅) · **A** (Actions) |
| 4 — Nube | **A** (Actions verde) · **B** (commit bot) · artifact descargándose |
| 5 — Voz | `matchday.mp4` / **H** (onda) · **E** (ElevenLabs) · montaje de 1-4 · `recap.png` |

> Con grabar A–H una vez + los PNG/MP4 que ya tienes, cubres los 5 videos.

---

## 📐 Pasar el b-roll del PC (horizontal) a vertical 9:16
- Los **PNG ya son verticales** (1080x1920) → van directos.
- Las **grabaciones de pantalla del PC son horizontales (16:9)**. En **CapCut** (gratis, móvil o PC), proyecto **9:16** y por cada clip elige una de dos:
  - **Recortar/zoom:** acercas a la parte importante hasta llenar el alto (pierdes los lados, pero se ve grande).
  - **Clip centrado sobre fondo:** encoges el clip al centro de un lienzo 9:16 con **fondo verde Mundial** y un texto arriba (se ve todo, queda on-brand).
- **Truco al grabar:** haz zoom DENTRO de la app (zoom del navegador, fuente grande en el terminal, ventana angosta) para que al recortar a vertical el texto se lea bien.

## C) 🧩 ARMADO Y PROGRAMACIÓN
1. Por cada video: **voz (vozN.mp3) + b-roll** → quema el **gancho 0-3s** (texto del `serie_diaN.md`) → exporta **9:16 (1080x1920)**.
2. **Programa** con el scheduler nativo de TikTok (gratis) según `CALENDARIO_SERIE.md` (2 viernes + 3 sábado). **Mantén el orden 1→5.**
3. Al publicar cada uno: pega el **caption** (del `serie_diaN.md`, ya con 5 hashtags) + **fija el comentario** de debate.
4. Responde comentarios la 1ª hora.

> Tip: graba las 5 voces y captura A–H **hoy**; mañana solo montas y programas. Después, el sistema toma el relevo (ver `PUBLICAR.md`).
