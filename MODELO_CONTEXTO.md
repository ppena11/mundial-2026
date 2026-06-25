# Capas de contexto físico — Mundial 2026

Extensión del modelo Dixon-Coles (v7) con cuatro capas que casi nadie modela: **altura, calor,
viaje/jet lag** y un **motor de formato** afinado para 48 equipos. Todo se enchufa al Monte Carlo
de `sim_live.py` como:

```
λ_ajustado = λ_base × f_alt × f_calor × f_viaje
```

**Disciplina (clave):** todos los multiplicadores están acotados a **[0.90, 1.08]** y cada capa se
**valida con RPS fuera de muestra** (`validate_layers.py`). Si una capa no mejora, se apaga en
`context_factors.py`. Los datos del mundo real (elevaciones, techos, coordenadas, husos, bases de
aclimatación) están **verificados por web con fuentes** en `wc2026_context.json` — no se inventa nada.

## Archivos

| Archivo | Qué hace |
|---|---|
| `context_factors.py` | Lógica pura: `f_altitude`, `f_heat`, `f_travel`, `haversine`, `match_factors` + config de capas |
| `format_engine.py` | Muestreo Poisson/Binomial-Negativa + Dixon-Coles, desempates FIFA (head-to-head), mejores terceros |
| `schedule_2026.py` | Calendario real (openfootball) → sede/hora por partido y derivación de viaje/descanso/husos |
| `validate_layers.py` | Arnés de validación RPS (altura) y de sobredispersión (NB vs Poisson) |
| `wc2026_context.json` | 16 sedes + 48 selecciones, **verificado por web** (cada valor con fuentes) |
| `altitude_validation.json` | Elevaciones de ciudades de altura del histórico (verificadas) + bases derivadas de datos |
| `build_context.py`, `build_altitude_validation.py` | Conversores que arman los JSON anteriores |

## 1) Altura

```
f_alt = 1 − k · max(0, (elev_sede − elev_base)/1000)      k = 0.04, solo si elev_sede > 1500 m, piso 0.90
```

- Se aplica al λ ofensivo de **cada equipo según su propia base** (la sede más frecuente de local en
  results.csv). Un nativo de altura tiene gap ≈ 0 → ≈ 1.0; un equipo de nivel del mar en el Azteca
  (2240 m) → ≈ 0.91. Al equipo más aclimatado se le da un pequeño plus.
- **Bases de altura reales** (derivadas de datos): Bolivia 3650, Ecuador 2850, México 2240, Etiopía
  2355, Sudáfrica 1753, Kenia 1795… Colombia juega en **Barranquilla** (nivel del mar), no Bogotá.
- **Validación RPS (laboratorio CONMEBOL, La Paz/Quito/Bogotá):** mejora fuera de muestra y de forma
  consistente. Corte 2024-06: en partidos de altura RPS 0.20190 → **0.19949** (Δ +0.0024, ~1.2% mejor).
  Corte 2022-01: 0.20628 → **0.20449**. ✅ **Capa ON.**

## 2) Calor (carga térmica, proxy WBGT)

- La evidencia sobre el efecto del calor en el total de goles es **ambigua/neutra** (verificado). El
  movimiento limpio: **comprimir ambos λ** un poco (≤ 6 %) según riesgo de la sede y hora (mediodía/
  tarde pega más). Esto reduce el ritmo del favorito → más empates, más varianza.
- Se **apaga** con techo cerrado + aire (Atlanta, Dallas, Houston → `effective_ac_during_play`).
  Sedes abiertas y calurosas (Miami, Kansas City, Filadelfia, NY/NJ) → activa.
- Calibrado conservador por literatura + mecanismo probado en tests. No tiene laboratorio histórico
  con WBGT etiquetado, así que se mantiene pequeña y acotada.

## 3) Viaje, descanso y jet lag

Tres features por equipo, **derivadas del calendario real** (no de un dataset externo):

- `rest_days` (días desde su partido anterior), `km_travel` (great-circle entre sedes),
  `tz_change` (husos cruzados; **el este es peor**, confirmado en la literatura NBA/MLB).
- Se mapean a una penalización de fatiga sobre el λ del equipo (cada uno el suyo), acotada al piso 0.90.

## 4) Motor del formato (48 equipos)

- **Colas más gordas:** el Poisson puro subestima goleadas. Los goles están **sobredispersos**
  (var 2.19 vs media 1.39). Se activó **binomial negativa con r = 17** (validado: supera a Poisson en
  log-verosimilitud de goles, Δ +9.7). Mantiene la corrección Dixon-Coles en marcadores bajos.
- **Desempates FIFA 2026 (verificado):** puntos → **head-to-head** (pts → dif → gf entre empatados) →
  global (dif → gf) → fair play → ranking FIFA. Implementado con resolución recursiva del subgrupo
  empatado (`rank_group`). El head-to-head **antes** del gol-average global es el orden 2026.
- **Mejores terceros:** ranking oficial (puntos → dif → gf → fair play → ranking; sin head-to-head) y
  asignación de los 8 a las casillas de la ronda de 32 con la **tabla oficial de candidatos**
  (`assign_thirds`, matching por backtracking) — donde la mayoría de los sims falla.

## Integración y dónde se aplica

- **`sim_live.py`** (pipeline diario, 20.000 sims):
  - **Fase de grupos:** factores precomputados por par de equipos (sede, hora y viaje son fijos),
    aplicados a los partidos que faltan; ranking de grupo y terceros por el motor FIFA.
  - **Eliminatorias:** usa el **bracket OFICIAL 2026** con sedes (`schedule_2026.build_bracket`):
    cada partido KO conoce su sede/hora reales, así que altura/calor/viaje se aplican también ahí
    (incluidos los 2 partidos en altura de Ciudad de México: R32 y R16). El viaje en KO se deriva del
    recorrido real del equipo a medida que avanza. Si el calendario fuese inconsistente, cae con
    elegancia a siembra por fuerza sin factores (`BR_OK=False`).
  - Muestreo con binomial negativa en todo el torneo.
- **`predict_match.py`**: `--sede "Mexico City" --hora 14` activa altura + calor para un partido suelto.

## Limitaciones conscientes (honestidad)

- **Calor y viaje** no tienen laboratorio histórico etiquetado, así que están calibrados por
  literatura y probados a nivel de mecanismo, pero **no** validados con RPS como la altura. Por eso son
  pequeños y acotados, y se pueden apagar con un flag en `context_factors.py`.
- El **bracket oficial** se reconstruye del calendario abierto (openfootball) numerando los KO por
  orden de aparición y **validando** la consistencia del árbol; si la fuente cambiara su formato, el
  validador lo detecta y el sim no aplica un bracket roto.

## Recomendaciones evaluadas y su veredicto (disciplina)

Se implementó la **infraestructura** de varias recomendaciones y se midió su aporte con
backtesting fuera de muestra. La disciplina manda: si no mejora, se deja apagada.

| Recomendación | Estado | Veredicto (held-out) |
|---|---|---|
| Dixon-Coles + decaimiento temporal | ✅ producción | base del modelo |
| Corrección DC marcadores bajos | ✅ producción | — |
| Lesiones / disponibilidad | ✅ producción | `player_layer` |
| Contexto físico 2026 (altura/calor/viaje) | ✅ producción | altura mejora RPS |
| Colas pesadas (binomial negativa) | ✅ producción | r=17 valida |
| Cuotas/mercado (ensamble) | ✅ producción | `money_layer` |
| **Backtest Mundiales 2010–2022** | ✅ `backtest.py` | **nueva pieza de credibilidad** |
| **Peso por importancia de competición** | ⚙️ disponible, **OFF** | no mejora el held-out de Mundiales |
| **Calibración (vector scaling)** | ⚙️ disponible, **OFF** | el modelo DC ya está bien calibrado |
| xG (StatsBomb/FBref) | ❌ no | sin cobertura de eliminatorias recientes de las 48 → sería inventar |
| XGBoost/LightGBM | ❌ no | sustituido por stacker logístico; con datos escasos de selecciones no aporta |

**Backtest (promedio 4 Mundiales, RPS menor = mejor):** base **0.2013**, +competición 0.2037,
+calibración 0.2051. Es decir: las dos perillas no mejoran y se quedan apagadas — justo la
disciplina ("si no mejora, se apaga, sin piedad"). El backtest queda como herramienta para volver
a medir cuando cambien los datos. La calibración se puede activar puntualmente con
`predict_match.py … --calibrar` (requiere generar `calibration.json` con `backtest.py`).

| Archivo nuevo | Qué hace |
|---|---|
| `backtest.py` | Backtest held-out sobre Mundiales 2010–2022 (RPS/log-loss/Brier) comparando variantes |
| `calibration.py` | Vector scaling multinomial (Platt/temperatura generalizado) + métricas |
| `fit_dc.importance()` | Peso por tipo de competición (usado por el backtest; off en producción) |

## Análisis 2026 (predicciones vs realidad) → mejora validada

`evaluate_2026.py` compara, fuera de muestra (modelo entrenado con datos < 2026-06-01), las
predicciones contra los partidos REALES ya jugados. Hallazgos sobre 50 partidos de grupo:

- Rendimiento sólido: **RPS 0.155, acierto 1X2 66%**; en **sedes de altura 100%** de acierto (5).
- **Sesgo detectado:** el modelo **subestima los goles** (previstos 2.46 vs reales 2.96/partido).
- Las "sorpresas" del 2026 eran empates de favoritos — pero con 50 partidos eso es ruido.

**Disciplina anti-sobreajuste:** en vez de calibrar a 50 partidos, se convirtió el sesgo en
hipótesis y se validó en el held-out de los **4 Mundiales históricos (256 partidos)**:

- El sub-conteo de goles se **replica** (histórico: previstos 2.24 vs reales 2.57). ✅ real.
- **Compresión de favoritos: RECHAZADA** (empeora el RPS monotónicamente).
- **Inflar empates: RECHAZADO** (históricamente el modelo ya predice de más: 27.7% vs 22.3%).

**Mejora implementada (un solo knob, validado):** `WC_GOAL_LEVEL = 1.15` — nivel de goles
mundialista (el modelo entrena con amistosos/eliminatorias, más defensivos). Multiplica ambos λ.
En el held-out histórico calibra los goles (previstos 2.57 = reales 2.57), **mejora el RPS**
(0.2012→0.2006) y acerca los empates (27.7%→25.0%). En el 2026: goles 2.46→**2.83**, RPS 0.1559→**0.1552**.
Aplicado en `sim_live.py` y `predict_match.py`.

| Archivo nuevo | Qué hace |
|---|---|
| `evaluate_2026.py` | Predicciones vs resultados reales del Mundial 2026 (RPS/acierto/calibración + desgloses) |
| `backtest.goal_level_scan()` | Escaneo del nivel de goles (mu) sobre el held-out de Mundiales |
| `context_factors.WC_GOAL_LEVEL` | Nivel de goles mundialista (1.15), validado |

## Actualización EN TORNEO ("ver el Mundial") — aprende de cada partido jugado

El `sim_live` no solo CONDICIONA a los resultados reales (fija quién avanza): además **actualiza la
fuerza de cada equipo** con los partidos del Mundial ya jugados, para que las predicciones de las
rondas siguientes reflejen la forma actual. Se incorpora al fit con:

```
peso_partido = recencia × FORM_BOOST × fiabilidad(contexto)
```

- **FORM_BOOST = 2.0** (validado). Incluir la fase de grupos mejora el RPS de las eliminatorias en
  el held-out de 4 Mundiales: **0.1872 → 0.1812** (~3% mejor). Pesos muy altos (8) sobre-reaccionan
  a pocos partidos → peor; 2-3 es el punto óptimo (`validate_form_update.py`).
- **Fiabilidad por contexto (clave, "leer el partido"):** una goleada está a menudo DISTORSIONADA
  (rival expulsado, garbage time) y dice menos sobre la fuerza repetible. Por eso el peso baja con el
  margen (`margin_reliability`) y baja MÁS si hubo una **roja temprana** (`red_card_reliability`,
  con datos de API-Football en CI). Ejemplo real: **Canadá 6-0 Catar** se pondera a ~0.55, no como
  un 6-0 limpio. Así un marcador inflado no sube de más el rating de Canadá.
- Toggle `CF_FORM` / `CF_FORM_BOOST`. La evaluación held-out (`evaluate_2026.py`) usa un fit LIMPIO
  pre-torneo (no incluye la forma) para no entrenar sobre lo que evalúa.

| Archivo nuevo | Qué hace |
|---|---|
| `wc_form.py` | Fiabilidad por contexto (margen + roja) + carga de rojas (API-Football, best-effort) |
| `validate_form_update.py` | Valida que actualizar con la fase de grupos mejora el RPS de eliminatorias |

## Validación contra resultados reales — TODAS las etapas, incluido el campeón

**Importante:** el Mundial 2026 aún no tiene eliminatorias (la ronda de 32 empieza el 28-jun), así
que contra la realidad del 2026 solo hay **fase de grupos** (`evaluate_2026.py`, 50 partidos:
RPS 0.155, acierto 1X2 66%). El **campeón y las eliminatorias se validan sobre los 4 Mundiales
pasados** corriendo la **simulación completa** (`backtest_tournament.py`).

`backtest_tournament.py` entrena el modelo solo con datos previos a cada Mundial y simula el torneo
entero (grupos → R16 → QF → SF → Final → campeón) con la misma maquinaria del pipeline, sobre el
formato real de 32 equipos (grupos y bracket reales de openfootball). Resultados (K=10.000):

| | 2010 | 2014 | 2018 | 2022 | promedio |
|---|---|---|---|---|---|
| Campeón real | España | Alemania | Francia | Argentina | — |
| Ranking del campeón real (de 32) | **1** | 6 | 4 | **2** | **3.2** |
| P(campeón real) | 21% | 4% | 6% | 16% | ~12% |

- **Campeón: −logP(real) = 2.37** vs **3.47** del azar uniforme (1/32) → el pronóstico de campeón
  es claramente informativo (asigna al campeón real ~4× la prob. del azar; rank medio 3/32).
- **Calibración por etapa (Brier, menor=mejor):** R16 0.192 · QF 0.122 · SF 0.079 · Final 0.054.
- 2014 (Alemania, rank 6) y 2018 (Francia, rank 4) fueron campeones "sorpresa" frente a los ratings;
  el modelo no los daba favoritos, lo cual es honesto (ningún modelo serio los daba).

**Cobertura de herramientas por comparación (honestidad):**

| Comparación | DC | desempates FIFA | NB colas | nivel goles | altura/calor/viaje | mercado | lesiones |
|---|---|---|---|---|---|---|---|
| Pipeline diario (`sim_live`+ensemble) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2026 grupos (`evaluate_2026`) | ✅ | — | (1X2 analítico) | ✅ | ✅ | n/d | n/d |
| Campeón histórico (`backtest_tournament`) | ✅ | ✅ | ✅ | ✅ | n/d* | n/d* | n/d* |

\* No hay datos históricos de sede/cuotas/lesiones de Mundiales pasados, así que esas capas no se
pueden aplicar al backtest histórico (no se inventan). El **motor** validado es el mismo del pipeline.

## Re-ejecutar

```bash
python validate_layers.py --cut 2024-06-01   # RPS altura + sobredispersión
python backtest.py                            # backtest 1X2 Mundiales 2010-2022 + escaneo de nivel de goles
python backtest_tournament.py                 # validación de CAMPEÓN y todas las etapas (sim completa)
python validate_form_update.py                # valida la actualización en torneo (forma) en eliminatorias
python evaluate_2026.py                       # predicciones vs resultados reales del Mundial 2026 (grupos)
python build_context.py                       # regenerar wc2026_context.json desde la investigación
python build_altitude_validation.py           # regenerar altitude_validation.json
pytest test_context_factors.py test_format_engine.py test_schedule_2026.py test_validate_layers.py test_calibration.py test_backtest.py
python test_suite.py                          # batería completa (incluye lo anterior)
```
