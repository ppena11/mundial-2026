"""
combine.py — une tu modelo (markets.json) con el feed limpio (odds del feed).
Hace: ensemble 50/50, detección de value REAL (vs mercado limpio), y corrección
del sesgo longshot dejando que el mercado tire de la cola larga.

USO (en tu máquina, tras correr fetch_odds.py):
  python3 fetch_odds.py --outrights > odds_live.json
  python3 combine.py odds_live.json
"""
import json,sys

# Alias: nombres del feed (The Odds API) que NO coinciden con namemap.json
FEED_ALIASES={
    "USA":"United States",
    "Bosnia & Herzegovina":"Bosnia and Herzegovina",
}

def feed_to_model_probs(clean, namemap):
    """Traduce {nombre_ingles_feed: prob} -> {nombre_espanol_modelo: prob}."""
    eng2es={en:es for es,en in namemap.items()}   # inglés -> español
    out={}
    for name_en,prob in clean.items():
        name_en=FEED_ALIASES.get(name_en,name_en)
        es=eng2es.get(name_en)
        if es is not None:
            out[es]=prob
    return out

def main(odds_file):
    namemap=json.load(open("namemap.json",encoding="utf-8"))
    model={t:v["champ"] for t,v in json.load(open("markets.json",encoding="utf-8")).items()}
    feed=json.load(open(odds_file,encoding="utf-8"))
    clean=feed_to_model_probs(feed["clean_probs"], namemap)   # feed ya viene de-vigueado
    rows=[]
    for t in model:
        pm=model[t]; pc=clean.get(t)
        if pc is None: continue
        ens=0.5*pm+0.5*pc
        value = pm>pc*1.10   # value real solo si el modelo supera al mercado LIMPIO con margen
        rows.append((t,pm,pc,ens,value))
    rows.sort(key=lambda x:-x[3])
    print(f"{'Equipo':<14}{'Modelo':>8}{'Mkt limpio':>12}{'Ensemble':>10}{'Value':>8}")
    for t,pm,pc,ens,v in rows[:15]:
        print(f"{t:<14}{100*pm:>7.1f}%{100*pc:>11.1f}%{100*ens:>9.1f}%{'★' if v else '':>8}")
    print("\nNota: el ensemble corrige el sesgo longshot del modelo usando el mercado real,")
    print("sin meter opinión a mano. El value ★ es contra mercado LIMPIO (de-vigueado).")
if __name__=="__main__":
    main(sys.argv[1] if len(sys.argv)>1 else "odds_live.json")
