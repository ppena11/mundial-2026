# 🤖 Cómo automatizar TODO con Claude Code

## La verdad sobre la automatización
Claude.ai (la conversación) NO puede automatizar: no persiste, no tiene servidor ni red abierta.
Claude Code en TU máquina SÍ puede: tu compu está siempre ahí, con internet y tareas programadas.

## Qué se automatiza y qué no
| Tarea | ¿Automatizable? | Cómo |
|---|---|---|
| Resultados de partidos | ✅ Sí | re-descarga results.csv |
| Lesiones + XI confirmado | ✅ Sí | fetch_live.py (API key) |
| Movimiento de cuotas (sharp money) | ✅ Sí | money_layer.py + cron |
| Simulación 20.000 | ✅ Sí | sim20k.py |
| Pronóstico + gráficos | ✅ Sí | run_all.py |
| **Noticias blandas** (vestuario, rumores) | ❌ No | Requiere criterio humano |
| **Edición/subida del video** | ❌ No | Tú + HeyGen + CapCut |

## El comando único
`python3 run_all.py`  -> corre todo el pipeline de una vez.

## Para que corra SOLO cada día (lo que pediste):
Pídele esto a Claude Code:
> "Lee AUTOMATIZACION.md. Monta un cron que corra run_all.py cada día a las 8am
>  y otro que corra 'money_layer.py --snapshot' cada 2 horas. Configura mis API keys
>  (API_FOOTBALL_KEY, ODDS_API_KEY) en un archivo .env y haz que run_all.py las lea.
>  Si algún paso falla, que me mande el log por email/Slack."

Claude Code puede montar TODO eso: cron, .env, manejo de errores, notificaciones.
Eso es 'automatizar todo' de verdad — en tu infra, no en la conversación.

## Lo que seguirá necesitando tu mano (y por qué está bien)
- Decidir el peso de una noticia blanda ("vestuario roto" -> ¿-0.05? lo decides tú o me preguntas)
- Grabar el avatar y editar (HeyGen + CapCut)
- Publicar y responder comentarios
Esto NO es un defecto: es donde tu criterio humano añade el valor que ningún bot replica.
