"""
track_record.py — HISTORIAL DE ACIERTOS del modelo (transparencia / confianza).
Registra cada predicción 1X2 y, cuando el partido se juega, la califica.

QUÉ CALCULA:
  - Aciertos 1X2: % de veces que el resultado más probable del modelo acertó (1/X/2).
  - Brier score: calidad de la probabilidad (más bajo = mejor calibrado; ~0.55-0.62 es bueno).
  - Aciertos de marcador exacto (bonus; suele ser bajo, ~10-15%).

ARCHIVOS:
  predictions_log.jsonl  — una línea por predicción (se acumula; persiste en el repo).
  track_record.json      — resumen acumulado (lo lee daily_digest para mostrarlo).

USO (lo ideal: correr cada día tras el pipeline):
  python track_record.py            # 1) califica lo pendiente 2) registra lo nuevo 3) resume
  python track_record.py --summary  # solo imprime el resumen
"""
import sys, json
from datetime import date
import daily_digest as dd
import predict_match as pm

LOG = "predictions_log.jsonl"
OUT = "track_record.json"

def _key(a, b, d10):
    return f"{d10}|" + "|".join(sorted([a, b]))

def load_log():
    try:
        return [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        return []

def save_log(rows):
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

def fetch_results():
    """Partidos jugados: {key: {'a':a,'b':b,'ga':x,'gb':y}} (key con equipos ordenados)."""
    res = {}
    for rng in ("20260611-20260704", "20260705-20260720"):
        try:
            evs = dd._get(f"{dd.ESPN}/scoreboard?dates={rng}").get("events", [])
        except Exception:
            evs = []
        for e in evs:
            comp = (e.get("competitions") or [{}])[0]
            if comp.get("status", {}).get("type", {}).get("state") != "post": continue
            cs = comp.get("competitors", [])
            if len(cs) != 2: continue
            try:
                home = next((c for c in cs if c.get("homeAway") == "home"), cs[0])
                away = next((c for c in cs if c.get("homeAway") == "away"), cs[1])
                a = dd.EN2ES.get(home["team"]["displayName"], home["team"]["displayName"])
                b = dd.EN2ES.get(away["team"]["displayName"], away["team"]["displayName"])
                ga, gb = int(home.get("score", 0)), int(away.get("score", 0))
                # equipo que AVANZA según ESPN (flag winner/advance) — vale para partidos definidos en PENALES
                adv = next((dd.EN2ES.get(c["team"]["displayName"], c["team"]["displayName"])
                            for c in cs if c.get("winner") or c.get("advance")), None)
            except Exception:
                continue
            res[_key(a, b, dd.et_date(e.get("date", "")))] = {"a": a, "b": b, "ga": ga, "gb": gb, "adv": adv}
    return res

def log_predictions(target):
    """Registra las predicciones del día `target` EXACTAMENTE como se PUBLICAN en el pronóstico.
    Usa la MISMA fuente que el video (make_script._played_modelo: ensamble modelo+mercado), para que el recap
    califique y muestre lo que de verdad se dijo — NO una versión solo-modelo distinta (transparencia)."""
    rows = load_log()
    have = {r["key"] for r in rows}
    import make_script as _ms
    played = _ms._played_modelo(target)   # marcador/favorito PUBLICADOS (modelo+mercado), una sola fuente de verdad
    nuevos = 0
    for d in played:
        a, b = d["a"], d["b"]
        if a not in pm.MAP or b not in pm.MAP: continue   # KO con equipos por definir -> aún no
        iso = dd.et_date(d.get("utc", ""))
        k = _key(a, b, iso)
        if k in have: continue
        sx, sy = d["sx"], d["sy"]
        pick = pm.outcome_de(sx, sy)   # el pick DERIVA del marcador publicado, para que todo concuerde
        rows.append({"key": k, "fecha": iso, "a": a, "b": b, "label": d.get("label", ""),
                     "is_ko": d.get("is_ko", False),
                     "p1": round(d.get("p1", 0.0), 4), "pX": round(d.get("pdr", 0.0), 4), "p2": round(d.get("p2", 0.0), 4),
                     "pick": pick, "marcador_pred": f"{sx}-{sy}", "actual": None})
        nuevos += 1
    save_log(rows)
    return nuevos

def grade():
    """Califica las predicciones cuyos partidos ya se jugaron."""
    rows = load_log(); res = fetch_results(); graded = 0
    for r in rows:
        if r.get("actual") is not None: continue
        m = res.get(r["key"])
        if not m: continue
        # alinear marcador a la orientación (a,b) de la predicción
        if m["a"] == r["a"]: ga, gb = m["ga"], m["gb"]
        else:               ga, gb = m["gb"], m["ga"]
        outcome = "1" if ga > gb else ("X" if ga == gb else "2")
        r["actual"] = outcome                       # resultado reglamentario (lo usa el Brier)
        r["marcador_real"] = f"{ga}-{gb}"
        if r.get("is_ko") and m.get("adv"):         # ELIMINATORIA: acierto = predecir QUIÉN AVANZA (penales incluidos)
            if r["pick"] == "1":   adv_pick = r["a"]
            elif r["pick"] == "2": adv_pick = r["b"]
            else:                  adv_pick = r["a"] if r.get("p1", 0) >= r.get("p2", 0) else r["b"]  # empate previsto -> favorito
            r["avanza_real"] = m["adv"]
            r["acierto_1x2"] = (adv_pick == m["adv"])
        else:
            r["acierto_1x2"] = (r["pick"] == outcome)
        r["acierto_exacto"] = (r["marcador_pred"] == f"{ga}-{gb}")
        graded += 1
    save_log(rows)
    return graded

def summary():
    rows = [r for r in load_log() if r.get("actual") is not None]
    n = len(rows)
    if n == 0:
        s = {"n": 0, "mensaje": "Aún no hay partidos calificados."}
        json.dump(s, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return s
    hits = sum(1 for r in rows if r.get("acierto_1x2"))
    exact = sum(1 for r in rows if r.get("acierto_exacto"))
    # Brier multiclase: suma (p_o - 1{resultado=o})^2 sobre {1,X,2}
    brier = 0.0
    for r in rows:
        o = r["actual"]
        for k, lab in [("p1", "1"), ("pX", "X"), ("p2", "2")]:
            brier += (r[k] - (1.0 if lab == o else 0.0)) ** 2
    brier /= n
    s = {"n": n, "aciertos_1x2": hits, "tasa_1x2": round(100*hits/n, 1),
         "aciertos_exactos": exact, "tasa_exacta": round(100*exact/n, 1),
         "brier": round(brier, 3)}
    json.dump(s, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return s

if __name__ == "__main__":
    if "--summary" in sys.argv:
        print(json.dumps(summary(), ensure_ascii=False, indent=2)); sys.exit(0)
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    gr = grade()
    nv = log_predictions(target)
    s = summary()
    print(f"Calificadas: {gr} · Nuevas registradas: {nv}")
    if s["n"] == 0:
        print("Aún no hay partidos calificados (el historial se llena cuando empiece el Mundial).")
    else:
        print(f"Historial: {s['aciertos_1x2']}/{s['n']} aciertos 1X2 ({s['tasa_1x2']}%) · "
              f"marcador exacto {s['tasa_exacta']}% · Brier {s['brier']}")
