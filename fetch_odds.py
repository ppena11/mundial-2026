"""
fetch_odds.py — feed de cuotas en vivo para el Mundial 2026 (The Odds API).
EJECUTAR EN TU MÁQUINA con Claude Code (Claude.ai no tiene red abierta a esta API).

QUÉ HACE:
  - Baja las cuotas de campeón (outright) y de partidos (1X2) de varias casas
  - Hace de-vig (quita el margen) -> probabilidad LIMPIA del mercado
  - Las deja listas para: (a) ensemble con tu modelo, (b) detección de value real,
    (c) corrección del sesgo longshot SIN meter opinión (lo corrige el mercado)

SETUP (~5 min):
  1) Cuenta gratis en https://the-odds-api.com  (500 req/mes gratis) -> API key
  2) pip install requests
  3) export ODDS_API_KEY="tu_key"
  4) python3 fetch_odds.py --outrights        # cuotas de campeón
     python3 fetch_odds.py --h2h              # cuotas 1X2 próximos partidos
"""
import os,sys,json,math
try:
    import requests
except ImportError:
    print("Falta requests:  pip install requests"); sys.exit(1)
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

KEY=os.environ.get("ODDS_API_KEY","PEGA_TU_KEY_AQUI")
BASE="https://api.the-odds-api.com/v4"
# Slugs verificados en /sports (jun 2026):
SPORT_MATCHES="soccer_fifa_world_cup"          # partidos 1X2 (h2h)
SPORT_WINNER ="soccer_fifa_world_cup_winner"   # cuotas de campeón (outrights)
SPORT=SPORT_MATCHES   # compat: usado por h2h()

def get(path,**params):
    params["apiKey"]=KEY
    r=requests.get(f"{BASE}/{path}",params=params,timeout=20)
    r.raise_for_status();return r.json()

def list_sports():
    """Para encontrar el slug correcto del Mundial si SPORT no funciona."""
    return [(s["key"],s["title"]) for s in get("sports") if "world" in s["title"].lower() or "fifa" in s["title"].lower()]

def devig_multiplicative(odds_dict):
    """odds_dict: {equipo: cuota_decimal} -> {equipo: prob_limpia}."""
    raw={k:1/v for k,v in odds_dict.items()}
    s=sum(raw.values())
    return {k:raw[k]/s for k in raw}, s-1   # (probs, overround)

def outrights():
    """Cuotas de campeón del Mundial, promediadas entre casas, ya de-vigueadas."""
    data=get(f"sports/{SPORT_WINNER}/odds",regions="us,uk,eu",markets="outrights",oddsFormat="decimal")
    # promedia la mejor cuota por equipo entre casas
    best={}
    for ev in data:
        for bk in ev.get("bookmakers",[]):
            for mk in bk.get("markets",[]):
                if mk["key"]!="outrights":continue
                for oc in mk["outcomes"]:
                    best[oc["name"]]=max(best.get(oc["name"],0),oc["price"])
    if not best:return {},0
    probs,ov=devig_multiplicative(best)
    return {"odds":best,"clean_probs":probs,"overround":ov}

def h2h():
    """Cuotas 1X2 de los próximos partidos, de-vigueadas por partido."""
    data=get(f"sports/{SPORT}/odds",regions="us,uk,eu",markets="h2h",oddsFormat="decimal")
    out=[]
    for ev in data:
        home=ev.get("home_team");away=ev.get("away_team")
        # promedio simple de casas por resultado
        agg={}
        for bk in ev.get("bookmakers",[]):
            for mk in bk.get("markets",[]):
                if mk["key"]!="h2h":continue
                for oc in mk["outcomes"]:
                    agg.setdefault(oc["name"],[]).append(oc["price"])
        if not agg:continue
        avg={k:sum(v)/len(v) for k,v in agg.items()}
        probs,ov=devig_multiplicative(avg)
        out.append({"home":home,"away":away,"clean_probs":probs,"overround":ov})
    return out

if __name__=="__main__":
    if KEY=="PEGA_TU_KEY_AQUI":
        print("⚠️  Pon tu ODDS_API_KEY primero (paso 3)."); sys.exit(1)
    if "--sports" in sys.argv: print(json.dumps(list_sports(),indent=2,ensure_ascii=False))
    elif "--outrights" in sys.argv: print(json.dumps(outrights(),indent=2,ensure_ascii=False))
    elif "--h2h" in sys.argv: print(json.dumps(h2h(),indent=2,ensure_ascii=False))
    else: print(__doc__)
