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
            except Exception:
                continue
            res[_key(a, b, dd.et_date(e.get("date", "")))] = {"a": a, "b": b, "ga": ga, "gb": gb}
    return res

def log_predictions(target):
    """Registra las predicciones de los partidos de la fecha `target` (con la info de ese día,
    para que el historial sea justo: lo que de verdad se publicó)."""
    rows = load_log()
    have = {r["key"] for r in rows}
    atk, dfn, c, g, rho = pm.fit_model(); pm.apply_adjustments(atk, dfn)
    nuevos = 0
    for m in dd.matches_on(target):
        a, b = m["a"], m["b"]
        if a not in pm.MAP or b not in pm.MAP: continue   # KO con equipos por definir -> aún no
        k = _key(a, b, dd.et_date(m["utc"]))
        if k in have: continue
        pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=True)
        pick = pm.outcome_de(sx, sy)   # el pick DERIVA del marcador más probable (lo que se publica), para que concuerden
        rows.append({"key": k, "fecha": dd.et_date(m["utc"]), "a": a, "b": b, "label": m["label"],
                     "p1": round(pw, 4), "pX": round(pdr, 4), "p2": round(pl, 4),
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
        r["actual"] = outcome
        r["marcador_real"] = f"{ga}-{gb}"
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
