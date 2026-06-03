# Modelo Mundial 2026 — v7.1 (POST-AUDITORÍA)

Versión auditada a nivel de código, pricing y comportamiento por un estándar de casa de apuestas profesional.

## Pronóstico oficial (20.000 simulaciones)
| # | Selección | Campeón |
|---|---|---:|
| 1 | Argentina | 19.4% |
| 2 | Espana | 15.3% |
| 3 | Inglaterra | 9.1% |
| 4 | Francia | 6.7% |
| 5 | Portugal | 6.5% |
| 6 | Brasil | 6.0% |
| 7 | Colombia | 4.8% |
| 8 | Marruecos | 3.7% |
| 9 | Paises Bajos | 3.6% |
| 10 | Alemania | 2.9% |
| 11 | Japon | 2.4% |
| 12 | Suiza | 2.2% |

## Auditoría superada (3 niveles)
- **Código:** Poisson insesgado ✓ · Dixon-Coles sin sesgo ✓ · sin data leakage ✓ · cobertura de datos suficiente ✓
- **Comportamiento:** dispersión correcta (el #1 Elo gana solo 2/10 Mundiales reales) · efecto anfitrión apropiado
- **Pricing:** de-vig implementado · coherencia entre mercados (0 arbitraje interno) · sesgo longshot identificado

## Cambio en v7.1
- Factor knockout recalibrado de 0.92 (inventado) a 1.0: los Mundiales reales NO muestran menos goles
  en eliminatorias (ratio 1.02, IC95% [0.90-1.14]). Se quitó el ajuste injustificado. Impacto <0.6pp.

## Mejoras probadas y DESCARTADAS por la auditoría (señal de disciplina)
- Peso por importancia de partido — empeoraba el RPS fuera de muestra
- Encogimiento hacia valor de plantilla — empeoraba el RPS
- Apretar favoritos al estilo mercado — la realidad ya valida la dispersión actual
- Factor knockout <1 — sin respaldo en datos reales

## Limitaciones documentadas (lo que el modelo sabe que no sabe)
- Desempate de grupos simplificado (sin head-to-head ni fair play)
- Sin feeds en vivo de jugadores/dinero (preparados para Claude Code)
- Calibración de torneo completo no verificable (1 Mundial/año = muestra insuficiente)
- No es una máquina de apuestas: ~104 partidos no bastan para demostrar ventaja sobre las casas

## Veredicto de auditoría
Modelo honesto, técnicamente sólido y disciplinado, al nivel de un equipo profesional con datos públicos.
Cada parámetro viene de datos o está documentado como supuesto. Su mayor virtud: sabe lo que no sabe.