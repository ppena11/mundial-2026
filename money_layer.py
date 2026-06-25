"""
money_layer.py — CAPA DEL DINERO (sharp money / movimiento de línea).
EJECUTAR EN TU MÁQUINA con Claude Code. Requiere fetch_odds.py funcionando (ODDS_API_KEY).

QUÉ ES (y qué NO es):
  El "dinero inteligente" no se ve en una cuota suelta, sino en CÓMO se mueve la línea
  en el tiempo. Cuando una cuota se acorta sin noticia pública => entró dinero sharp.
  Esta capa: (1) guarda snapshots de cuotas, (2) detecta movimientos, (3) los convierte
  en una señal que ajusta el ensemble modelo+mercado.

ARQUITECTURA (3 piezas):
  A) snapshot()  -> guarda cuotas actuales con timestamp en odds_history.jsonl
  B) detect_moves() -> compara los 2 últimos snapshots, marca quién se acortó/alargó
  C) money_signal() -> convierte el movimiento en peso para el ensemble

CRON (clave): para tener histórico, corre snapshot() cada 1-2h.
  Claude Code te monta esto en crontab:  0 */2 * * *  python3 money_layer.py --snapshot
"""
import os,sys,json,math,time
from datetime import datetime, timezone

HIST="odds_history.jsonl"           # cuotas de campeón (outright), una línea JSON por snapshot
H2H_HIST="odds_h2h_history.jsonl"   # cuotas 1X2 POR PARTIDO (de-vigueadas), para el head-to-head vs mercado

def snapshot(odds_dict, label="outrights"):
    """Guarda un snapshot de cuotas {equipo: cuota_decimal} con timestamp."""
    rec={"ts": datetime.now(timezone.utc).isoformat(), "label": label, "odds": odds_dict}
    with open(HIST,"a",encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False)+"\n")
    return rec

def snapshot_h2h(matches):
    """Guarda las cuotas 1X2 por partido (de fetch_odds.h2h) con timestamp. Acumular estos snapshots
    permite, más adelante, comparar el RPS del modelo vs el del mercado partido a partido (el estándar
    de oro: 'ganarle a la línea de cierre')."""
    rec={"ts": datetime.now(timezone.utc).isoformat(), "matches": matches}
    with open(H2H_HIST,"a",encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False)+"\n")
    return rec

def _load():
    if not os.path.exists(HIST): return []
    return [json.loads(l) for l in open(HIST,encoding="utf-8") if l.strip()]

def detect_moves(min_pct=3.0):
    """Compara los 2 snapshots más recientes. Devuelve movimientos significativos (%)."""
    snaps=_load()
    if len(snaps)<2:
        return {"error":"Faltan snapshots. Corre --snapshot al menos 2 veces (idealmente con horas de diferencia)."}
    old,new=snaps[-2]["odds"],snaps[-1]["odds"]
    moves={}
    for t in new:
        if t in old and old[t] and new[t]:
            pct=100*(old[t]-new[t])/old[t]   # + = cuota BAJÓ (acortó) = dinero ENTRANDO
            if abs(pct)>=min_pct:
                moves[t]={"de":old[t],"a":new[t],"mov_pct":round(pct,1),
                          "lectura":"acortó (dinero entrando) 🔥" if pct>0 else "alargó (dinero saliendo) ❄️"}
    return {"desde":snaps[-2]["ts"],"hasta":snaps[-1]["ts"],"movimientos":moves}

def money_signal(model_probs, clean_market_probs, moves, k=0.15):
    """
    Ensemble inteligente: parte de 50/50 modelo+mercado, pero si hay movimiento sharp
    hacia un equipo, inclina un poco MÁS hacia el mercado para ese equipo (el dinero sabe).
    k = cuánto pesa la señal de dinero (conservador por defecto).
    """
    out={}
    mv=moves.get("movimientos",{}) if isinstance(moves,dict) else {}
    for t in model_probs:
        pm=model_probs[t]; pc=clean_market_probs.get(t,pm)
        w=0.5
        if t in mv:
            # si la línea se acortó (dinero entrando), subir peso del mercado para ese equipo
            w=min(0.8, 0.5 + k*math.copysign(1, mv[t]["mov_pct"]))
        out[t]=(1-w)*pm + w*pc
    # renormalizar
    s=sum(out.values())
    return {t:out[t]/s for t in out}

if __name__=="__main__":
    if "--snapshot" in sys.argv:
        # en uso real: odds vienen de fetch_odds.py (outrights()["odds"])
        try:
            import fetch_odds
            data=fetch_odds.outrights()
            snapshot(data["odds"])
            # guarda también el feed limpio para el ensemble (una sola llamada sirve para todo)
            json.dump(data, open("odds_live.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"Snapshot guardado: {len(data['odds'])} equipos @ {datetime.now(timezone.utc).isoformat()}")
            # NUEVO: snapshot de cuotas 1X2 POR PARTIDO (para comparar modelo vs mercado a futuro)
            try:
                h = fetch_odds.h2h()
                if h:
                    snapshot_h2h(h); print(f"Snapshot 1X2 por partido: {len(h)} partidos -> {H2H_HIST}")
            except Exception as e2:
                print(f"(sin snapshot 1X2 por partido: {e2})")
        except Exception as e:
            print("Para snapshot real necesitas fetch_odds.py + ODDS_API_KEY. Error:",e)
    elif "--moves" in sys.argv:
        print(json.dumps(detect_moves(),indent=2,ensure_ascii=False))
    else:
        print(__doc__)
