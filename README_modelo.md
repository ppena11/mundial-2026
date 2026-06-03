# 📦 Modelo Mundial 2026 — Paquete para Claude Code

## Qué hay aquí
- **fetch_live.py** — conecta con API-Football (lesiones + XI confirmado en vivo). ⚠️ Correr en TU máquina.
- **player_layer.py** — capa que ajusta ataque/defensa de cada selección según el XI disponible.
- **v7.py** — el modelo validado (Dixon-Coles + Poisson + Montecarlo, 20.000 sims).
- **fit_dc.py / engine.py** — motor de ajuste y simulación.
- **results.csv** — base de datos (49.000+ partidos). *Re-descargable.*
- **namemap.json** — mapeo de nombres de selección.
- **modelo_mundial2026.md** — documento vivo con metodología y pronóstico.

## Flujo diario (con Claude Code en tu compu)
1. `python3 fetch_live.py --today`  → ves los IDs de los partidos de hoy
2. `python3 fetch_live.py --lineup <ID>`  → XI confirmado (1h antes)
3. Claude Code mete ese XI en `player_layer.py`, corre `v7.py` y reemite probabilidades
4. Genera el gráfico + te paso el guion del video

## Lo que le pides a Claude Code al abrir esto:
> "Lee README_modelo.md. Tengo mi API key de API-Football en la variable de entorno
>  API_FOOTBALL_KEY. Conecta fetch_live.py con player_layer.py y v7.py para que, dado
>  el XI confirmado de un partido, reajuste las probabilidades y regenere el gráfico."

## Setup único (~10 min)
- Instalar Python 3 + `pip install requests numpy scipy matplotlib`
- Cuenta gratis en api-football.com → API key
- `export API_FOOTBALL_KEY="tu_key"`

---

## 🎰 CAPA DE TRADING (nuevo)
- **fetch_odds.py** — feed de cuotas en vivo (The Odds API) con de-vig. ⚠️ Correr en TU máquina.
- **combine.py** — une modelo + feed: ensemble 50/50, value real, corrige sesgo longshot vía mercado.
- **trader.py / trader2.py** — coherencia entre mercados, de-vig, diagnóstico favorito-longshot.
- **markets.json** — todos los mercados del modelo (campeón/final/semi/gana-grupo) coherentes.

### Hallazgo clave del análisis de trader
El modelo SOBREVALORA longshots (25% vs 16% del mercado limpio). El "value" en longshots
es sesgo del modelo, NO oportunidad real. El feed de cuotas corrige esto objetivamente.
La única discrepancia defendible: Argentina (modelo 19% vs mercado 9%).

### Qué pedirle a Claude Code para las cuotas:
> "Lee README. Tengo ODDS_API_KEY en variable de entorno. Corre fetch_odds.py --outrights,
>  guarda en odds_live.json, y ejecuta combine.py para darme ensemble + value real.
>  Ajusta el mapeo de nombres del feed (inglés) a los del modelo (markets.json)."

### Lo que NO se puede hacer ni con feed (límites honestos):
- Closing line value: necesita histórico de líneas de cierre
- Sharp money / movimiento de línea: necesita guardar cuotas en el tiempo (Claude Code puede
  programar un cron que las guarde cada hora -> con eso SÍ se construye)

---

## 💰 CAPA DEL DINERO (money_layer.py) — la única mejora que sobrevivió a la auditoría
El sharp money se detecta en el MOVIMIENTO de la línea, no en una cuota suelta.

### Las 3 piezas
- **snapshot()** — guarda cuotas con timestamp en odds_history.jsonl
- **detect_moves()** — compara los 2 últimos snapshots; marca quién se acortó (dinero entrando 🔥) o alargó (❄️)
- **money_signal()** — inclina el ensemble un poco más hacia el mercado para los equipos con dinero sharp entrando

### Setup con Claude Code
1. Que fetch_odds.py ya funcione (ODDS_API_KEY puesta)
2. Montar un cron para acumular histórico (CLAVE — sin histórico no hay señal):
   `0 */2 * * *  cd /ruta && python3 money_layer.py --snapshot`
3. Tras 2+ snapshots:  `python3 money_layer.py --moves`  → ves los movimientos
4. Pídele a Claude Code:
   > "Conecta money_layer.money_signal() con markets.json (modelo) y las clean_probs
   >  del feed, para darme el ensemble ajustado por dinero. Monta el cron de snapshots."

### Por qué esta capa SÍ y las demás NO (resultado de la auditoría)
- Sobre-dispersión: FALSA (el #1 Elo gana solo 2/10 Mundiales → el modelo está bien calibrado)
- Efecto anfitrión: apropiado (anfitriones débiles como MEX/EEUU/CAN no sobre-rinden históricamente)
- Movimiento de línea: la ÚNICA pieza real que falta, porque es información que el modelo
  no puede tener (dinero = conocimiento privado de miles de apostadores).

### Honestidad final
Ni con esta capa se puede "demostrar" que le ganas a las casas en 1 Mundial (~104 partidos,
muestra insuficiente). Es excelente para CONTENIDO y para razonar como un trader; no es una
máquina de dinero. No prometer ganancias en redes.
