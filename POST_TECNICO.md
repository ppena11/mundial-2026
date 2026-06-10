# Cómo funciona, por dentro, una IA que predice el Mundial 2026
### Arquitectura técnica completa — modelo, datos, nube, voz y pruebas. Todo dirigido a una IA, sin escribir código a mano. Para que lo audites.

*@aiwithpedro · documento técnico · informativo y educativo*

---

Este post es para los curiosos técnicos: ingenieros, data scientists, programadores. Voy a abrir el capó y mostrar **exactamente** cómo está construido el sistema que cada mañana predice el Mundial 2026, pieza por pieza, con las fórmulas y los parámetros reales. Y el detalle que lo hace especial: **no escribí una sola línea de código a mano**. Todo —el modelo estadístico, la automatización, la voz, los gráficos— lo construí **dirigiendo a una IA en lenguaje natural**, en un día. El repositorio es auditable. Aquí está el cómo.

## 0) Vista de pájaro

```
results.csv (~49.000 partidos) ─┐
ESPN API (resultados/XI/lesiones)├─► MODELO (Dixon-Coles) ─► 1X2 por partido
The Odds API (cuotas)           ─┘        │
                                          ├─► + capa LESIONES (XI confirmado)
                                          ├─► + capa MERCADO (de-vig + ensemble)
                                          └─► MONTE CARLO 20.000 torneos ─► P(campeón)
                                                       │
        GitHub Actions (cron 6 AM, gratis) orquesta todo y se auto-commitea
                                                       │
            Claude (texto exacto) + ElevenLabs (voz) + matplotlib (infografía) + ffmpeg (reel)
```

Todo corre solo en la nube. Mi computadora puede estar apagada.

---

## 1) El cerebro: un modelo Dixon-Coles (no es "opinión")

El núcleo es un **modelo de goles bivariado tipo Dixon-Coles (1997)** sobre Poisson. No predice "quién gana"; modela **cuántos goles** marca cada selección y de ahí derivan todas las probabilidades.

**Datos:** ~49.000 partidos internacionales (dataset abierto `martj42/international_results`), filtrados a una ventana 2019→2026.

**Parámetros aprendidos:** a cada selección se le estima un **ataque** `atk[i]` y una **defensa** `dfn[i]` (modelo separado, no un único rating). Más un intercepto global `c` y una **ventaja de localía** `γ`. Los goles esperados de un partido son:

```
λ_local    = exp( c + atk[local]  − dfn[visit] + γ·(local juega en casa) )
λ_visitante= exp( c + atk[visit]  − dfn[local] )
```

**Estimación:** máxima verosimilitud Poisson, optimizada con **L-BFGS-B** y **gradiente analítico** (no diferencias finitas). La log-verosimilitud que maximiza:

```
ℓ = Σ w_k · [ g_local·log(λ_local) − λ_local ]  +  (idem visitante)
```

con tres refinamientos que un experto reconocerá:

- **Decaimiento temporal:** cada partido pesa `w_k = exp(−ξ·días_atrás)` con **vida media de 730 días** (`ξ = ln2/730`). Un amistoso de 2019 pesa mucho menos que una Eliminatoria reciente.
- **Regularización ridge** (`λ_ridge = 0.02`) sobre ataque/defensa para que selecciones con pocos partidos no exploten.
- **Equipos con < 6 partidos** se agrupan en un cubo "otros" para no sobreajustar.

**La corrección Dixon-Coles (ρ):** el Poisson puro asume que los goles de local y visitante son independientes. Empíricamente **no lo son** en marcadores bajos (hay exceso de 0-0, 1-1, etc.). DC corrige las cuatro celdas bajas con un parámetro `ρ`:

```
τ(0,0)=1−λ_l·λ_v·ρ   τ(0,1)=1+λ_l·ρ   τ(1,0)=1+λ_v·ρ   τ(1,1)=1−ρ
```

`ρ` se estima por **búsqueda 1-D** sobre [−0.2, 0.15] maximizando la verosimilitud de los marcadores bajos.

**De goles a 1X2:** se arma la **matriz de marcadores** Poisson (hasta 11×11), se aplica la corrección DC a las celdas bajas, y se suma:

```
P(1) = Σ_{x>y} P(x,y)     P(X) = Σ_{x=y} P(x,y)     P(2) = Σ_{x<y} P(x,y)
```

El marcador más probable es simplemente la celda de mayor masa.

**¿Funciona?** Lo valido **fuera de muestra** con **RPS (Ranked Probability Score)**: entreno hasta junio-2025, predigo el último año sin verlo, y comparo. El modelo ataque/defensa con DC **mejora** sobre un rating único — y ese delta es la diferencia entre "intuición" y "modelo calibrado".

---

## 2) Capa de lesiones y XI confirmado (escala log-goles)

La fuerza base de cada selección se **ajusta por partido** según quién está disponible. Cada jugador clave tiene un **peso** (share de la fuerza ofensiva del equipo; afinado a mano para las estrellas, p. ej. Messi 0.22, Mbappé 0.20, Lamine Yamal 0.18). Si una estrella está fuera:

```
aporte_perdido += peso · (1 − SUB_RECOVERY)        # el suplente recupera ~55%
atk_ajustado = atk_base + 0.5 · ln(max(1 − aporte_perdido, 0.4))
dfn_ajustado = dfn_base + 0.3 · ln(max(disponibilidad_XI, 0.7))
```

Es decir: la pérdida se traduce a **escala log-goles** (suave, acotada). Un "duda" cuenta a medias. Y el **XI confirmado** (cuando se publica una hora antes) **tiene prioridad** sobre el parte de lesiones: es la realidad del partido. Las lesiones se scrapean gratis de ESPN.

---

## 3) Capa de mercado: de-vig + ensemble + sharp money

El mercado de apuestas agrega información que el modelo no ve (rumores, vestuario). Lo incorporo en tres pasos:

1. **De-vigueado:** las cuotas traen el margen de la casa (overround). Se convierten a probabilidad implícita `1/cuota` y se **renormalizan** para quitar el margen → probabilidades limpias.
2. **Ensemble:** combino modelo y mercado: `P = (1−W)·P_modelo + W·P_mercado`, con `W=0.5` (50/50) y renormalizado sobre las 48 selecciones. Esto **corrige el sesgo del modelo hacia los outsiders**.
3. **Sharp money (movimiento de línea):** guardo *snapshots* de cuotas cada 2 h en `odds_history.jsonl`. El dinero inteligente no se ve en una cuota suelta sino en **cómo se mueve**: si una línea se acorta sin noticia pública, entró dinero. Cuando detecto ese movimiento, inclino un poco más el ensemble hacia el mercado para ese equipo (`W` sube hasta 0.8).

La "jugada de valor" del día es, simplemente, donde el **modelo discrepa del mercado** por encima de un margen.

---

## 4) Monte Carlo: jugar el Mundial 20.000 veces

La probabilidad de **campeón** no sale de una fórmula cerrada: sale de **simular el torneo completo 20.000 veces** y contar. Cada simulación:

- **Sortea** los grupos por bombos según fuerza (con ruido gaussiano de forma `σ` para que no sea determinista).
- Juega los **partidos de grupo** muestreando goles de un Poisson cuya media depende de la diferencia de fuerza; resuelve la tabla (pts, dif, GF).
- Aplica el formato real 2026: **2 primeros + 8 mejores terceros** → 32 a eliminatorias.
- Arma el **bracket sembrado** por fuerza y lo juega hasta la final; en eliminatoria, los empates se rompen con una probabilidad tipo Elo (prórroga/penales).
- Anota al **campeón**, finalistas y semifinalistas.

Contando los 20.000 campeones → `P(campeón)` por selección. Y es **consciente del torneo**: una vez que empieza, condiciona la simulación a los **resultados reales** (toma las posiciones de grupo como hecho y simula solo lo que falta). Los equipos eliminados caen solos a ~0 %.

---

## 5) Datos gratis + ingeniería

Cero costo de datos. Fuentes:
- **`martj42/international_results`** — histórico (~49k partidos) para entrenar.
- **API oculta de ESPN** (`site.api.espn.com/.../fifa.world/...`) — resultados, alineaciones y lesiones, en JSON, gratis.
- **The Odds API** (plan gratuito) — cuotas de campeón.
- **flagcdn.com** — banderas.

Detalles de ingeniería que importan: ESPN **bloquea IPs de datacenter** (la nube), así que hay un **fallback vía proxy** (`api.codetabs.com`). Todo el I/O es **utf-8 con `ensure_ascii=False`** (cero mojibake en acentos — clave cuando el texto va a una voz sintética). Y la sede 2026 es Norteamérica: el manejo de **zona horaria** filtra los partidos por **fecha en hora del Este (EDT, UTC-4)**, no por UTC.

---

## 6) Automatización agéntica (lo que lo vuelve "vivo")

Todo el pipeline corre solo en **GitHub Actions** (gratis), con un `cron` a las **6 AM ET**. Cada mañana, sin que yo toque nada:

1. Descarga resultados, lesiones y cuotas.
2. Reentrena los ratings y corre las 20.000 simulaciones.
3. Aplica las capas (jugador + mercado) y arma el pronóstico.
4. Genera la infografía, el guion, la voz y el video.
5. **Se auto-commitea el estado** al repo (persistencia entre corridas) y sube los artefactos.

Detalles de robustez: **`concurrency group`** para serializar corridas, guardado con **`git merge -X ours` + reintentos** (a prueba de colisiones), y subida de artefactos **`if: always()`** aunque algún paso falle. Esto **no es IA que responde — es IA que *actúa***: un agente autónomo que hace el trabajo y entrega el resultado.

---

## 7) Generación de contenido: el híbrido exacto

Aquí hay una decisión de diseño importante. El texto viral (guion de voz, captions, el resumen) lo escribe **Claude (API de Anthropic)** — pero los **números siempre los pone el modelo**. Le paso a Claude los datos **exactos** y le pido solo la redacción. Así el contenido es **viral *y* fiable**: cero riesgo de que la IA alucine un porcentaje o un marcador.

- **Voz:** el guion va a **ElevenLabs** (mi voz clonada). Gotcha real que resolví: si el *system prompt* va sin tildes, el modelo devuelve español sin acentos y la voz suena plana → los prompts **exigen tildes** y los nombres de equipos se pre-acentúan ("España", no "Espana"). Hasta la marca va en **fonética** para que el sintetizador la diga bien.
- **Infografías:** **matplotlib** (1080×1920), banderas de flagcdn, y los sellos ✓/✗ dibujados como **vectores** (matplotlib no renderiza emojis).
- **Reel:** ensamblado con el **ffmpeg portátil** de `imageio-ffmpeg` (sin instalar nada del sistema).

---

## 8) Calidad: no es un script suelto

Antes de cualquier lanzamiento corro una **batería de 37 pruebas** que valida, entre otras cosas: que cada probabilidad 1X2 **suma exactamente 1** (en los 1.128 cruces posibles), que **todas las fechas del torneo** (los 104 partidos) generan contenido sin crashear, casos borde (días sin partido, placeholders de eliminatoria), la integridad de la simulación, las 495 combinaciones del cuadro de terceros, el **Brier score** del historial, y un **ensayo general**: meto los 72 resultados de grupos y verifico que solo los 32 clasificados conservan opción al título. Y un validador (`check_voz.py`) que revisa, sin gastar audio, que el texto que va a ElevenLabs lleva acentos y pausas.

El historial es **honesto**: cada día se publican los aciertos **y** los fallos, con **Brier score** y tasa de acierto. Si el favorito al 84 % pierde, el modelo no "falló": ese 16 % también existía.

---

## 9) Lo que de verdad importa

Nada de esto es nuevo en lo académico — Dixon-Coles es de 1997, Monte Carlo es más viejo. **Lo nuevo es cómo se construyó:** todo este sistema —modelo, capas, simulación, scraping, automatización en la nube, voz, gráficos y pruebas— lo levanté **dirigiendo a una IA en español**, sin escribir el código a mano, en un día. Lo que antes pedía un equipo de analistas y programadores y semanas de trabajo, hoy lo arma una persona conversando con una IA.

Ese es el mensaje del canal: con las herramientas de hoy, **construir cosas que parecían imposibles ya no requiere ser programador — requiere saber dirigir a la IA**.

---

*Si llegaste hasta aquí, eres justo el tipo de persona que quería impresionar. Sígueme para ver el modelo en acción durante todo el Mundial — con sus aciertos y sus fallos. Contenido informativo y educativo; no es consejo de apuestas.*

**— @aiwithpedro**
