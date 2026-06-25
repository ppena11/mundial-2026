# Guía experta — operar el modelo para apuestas (de cero)

Modelo Mundial 2026 → valor en Mise-o-jeu+ (Quebec), estilo *grind* disciplinado.
**Recuerda:** esto es entretenimiento informado y medición de edge, NO ingreso garantizado.
Apuesta solo lo que puedas perder; define un límite y nunca lo persigas.

---

## 0) Setup (UNA vez por máquina)

```bash
git pull                                   # trae el código + las cuotas de cierre del cron
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # numpy, scipy, requests, matplotlib
# base de datos de resultados (NO está en git; se re-descarga):
python -c "import urllib.request;urllib.request.urlretrieve('https://raw.githubusercontent.com/martj42/international_results/master/results.csv','results.csv')"
```

Decide tu **banca** (ej. $1,500) y NO la toques. Abre cuenta en Mise-o-jeu+.

---

## 1) Las herramientas

| Comando | Qué hace |
|---|---|
| `python bet_today.py <banca> <fecha>` | Pronóstico por partido (1X2 + Over/Under) → pegas cuotas → marca VALOR ✅ + stake |
| `python bet_today.py <banca> --campeon` | Mercado de campeón/finalista (outright), stake conservador (tope 1%) |
| `python clv_tracker.py` | Mide tu **CLV** (¿le ganas al cierre?) y ROI — la señal de edge real |
| `python sim_live.py` | Refresca las probabilidades de campeón (condiciona a resultados) |

---

## 2) Rutina de día de partido (~10 min)

```bash
git pull                                   # 1. cuotas de cierre del cron + resultados nuevos
python sim_live.py                         # 2. (solo si vas a outright) refresca campeón
python bet_today.py 1500 2026-06-28        # 3. partidos del día
```
4. En el script, por cada partido **pega las cuotas de Mise-o-jeu**: `1,X,2,Over,Under`
   (deja en blanco las que no quieras; Enter vacío salta el partido).
5. Al final te lista las **✅ VALOR** con su stake. Cuando pregunte *¿registrar? (s/n)* → **s**.
6. (Opcional) `python bet_today.py 1500 --campeon` para el campeón.
7. **Apuesta en Mise-o-jeu SOLO las ✅**, con el stake EXACTO que dijo.
8. Cuando quieras: `python clv_tracker.py` para ver cómo va tu edge.

---

## 3) Cómo LEER las salidas (lo de experto)

**bet_today:**
- `p_mod` = probabilidad del modelo · `implic` = la que implica la cuota de la casa.
- `EV%` = ventaja esperada. **Solo apuestas si sale ✅** (EV ≥ 10%).
- `stake$` = cuánto, ya calculado (cuarto de Kelly, tope 2% / outright 1%).

**clv_tracker:**
- `CLV%` por apuesta y **CLV medio**: si es **positivo sostenido**, tienes edge REAL.
- `% que batió el cierre`: > 52-55% = buena señal.
- `ROI`: con pocas apuestas es **ruido** — no te obsesiones con él; mira el CLV.

---

## 4) Reglas de oro (no negociables)

1. **Solo ✅.** Si no marca valor, no se apuesta. Punto.
2. **El stake lo decide el script.** Nunca lo subas para "recuperar" una pérdida.
3. **Caza las grietas grandes:** altura (octavos en el Azteca), Over/Under. Ahí Mise-o-jeu suele estar blando.
4. **Argentina campeón:** posición chica (tope 1%); es donde el modelo más puede sobrevalorar.
5. **El juez es el CLV, no el resultado de hoy.** Registra siempre (`s` en bet_today).
6. **Límite de pérdida fijo.** Es un experimento, no un sueldo.

---

## 5) Qué esperar de verdad (honesto)

- En lo que queda del Mundial: harás **~10-20 apuestas**, ganancia esperada **modesta (decenas de $) y muy ruidosa** — puedes terminar arriba o abajo por suerte.
- Lo valioso es **descubrir si tienes edge** (CLV+). Si lo confirmas, el dinero de verdad estaría en **escalar a fútbol de clubes** (miles de partidos/año) después del Mundial.

---

## Apéndice — evaluación / diagnóstico (sin apostar)
```bash
python evaluate_wc_sofar.py     # cómo va el modelo vs resultados (RPS, acierto, goles)
python predict_today.py 2026-06-28   # pronóstico del día (sin cuotas)
```
