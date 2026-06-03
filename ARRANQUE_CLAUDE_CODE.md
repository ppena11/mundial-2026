# 🚀 Mensaje de arranque para Claude Code — copia y pega

Cuando tengas el zip descargado en tu máquina, abre Claude Code en esa carpeta
y pégale este mensaje completo. Está pensado para que no tengas que decidir nada.

---

## PASO 0 — antes de pegar (3 minutos, una sola vez)
1. Descomprime `modelo_mundial2026.zip`
2. Instala Python 3 si no lo tienes (python.org)
3. Saca tus API keys gratis:
   - API-Football → https://www.api-football.com  (lesiones + XI)
   - The Odds API → https://the-odds-api.com  (cuotas, 500 req/mes gratis)
4. Abre Claude Code dentro de la carpeta descomprimida

---

## MENSAJE PARA PEGAR EN CLAUDE CODE (todo de una vez):

> Hola. Esta carpeta tiene un modelo de simulación del Mundial 2026. Lee primero
> README_modelo.md y AUTOMATIZACION.md para entender la arquitectura. Luego:
>
> 1. Crea un entorno virtual e instala dependencias:
>    numpy, scipy, matplotlib, requests.
>
> 2. Verifica que el modelo base corre sin internet:
>    ejecuta `python3 sim20k.py` y muéstrame los porcentajes de campeón.
>
> 3. Crea un archivo .env con mis claves (yo las pego cuando me lo pidas):
>    API_FOOTBALL_KEY y ODDS_API_KEY. Haz que fetch_live.py, fetch_odds.py y
>    run_all.py las lean desde .env.
>
> 4. Prueba los feeds uno por uno y arregla lo que falle:
>    - `python3 fetch_live.py --injuries`  (lesiones)
>    - `python3 fetch_odds.py --sports`  (encuentra el slug correcto del Mundial)
>    - `python3 fetch_odds.py --outrights`  (cuotas de campeón)
>    El mapeo de nombres del feed (inglés) a los del modelo (español, ver namemap.json)
>    seguramente necesita ajuste: hazlo y verifícalo.
>
> 5. Conecta el pipeline completo en run_all.py y córrelo una vez para confirmar
>    que encadena todo: resultados → feeds → simulación → gráfico.
>
> 6. Automatiza:
>    - cron diario a las 8am: `python3 run_all.py`
>    - cron cada 2 horas: `python3 money_layer.py --snapshot`  (para el sharp money)
>    - si algún paso falla, mándame el log (email o Slack, lo que prefieras).
>
> 7. Explícame en lenguaje simple qué quedó automático y qué tengo que hacer yo
>    a mano cada día (las noticias blandas y la edición del video).
>
> Trabaja paso a paso, muéstrame el resultado de cada uno antes de seguir, y avísame
> en cuanto necesites que pegue una API key.

---

## DESPUÉS, cada día (tu rutina real)
- El cron ya corrió y dejó los porcentajes + gráfico actualizados
- Tú revisas si hay alguna NOTICIA BLANDA importante (vestuario, rumor) y decides su peso
  (o me preguntas a mí en una conversación normal)
- 1 hora antes de un partido clave: `python3 fetch_live.py --lineup <ID>` para el XI confirmado
- Grabas el video con HeyGen, editas en CapCut, publicas

## Si algo se rompe
Pégame el mensaje de error aquí (en Claude.ai). Aunque yo no ejecuto código en vivo,
leo el error y te digo exactamente qué cambiar.
