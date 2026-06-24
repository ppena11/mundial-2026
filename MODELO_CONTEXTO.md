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

## Re-ejecutar

```bash
python validate_layers.py --cut 2024-06-01   # RPS altura + sobredispersión
python build_context.py                       # regenerar wc2026_context.json desde la investigación
python build_altitude_validation.py           # regenerar altitude_validation.json
pytest test_context_factors.py test_format_engine.py test_schedule_2026.py test_validate_layers.py
python test_suite.py                          # batería completa (incluye lo anterior)
```
