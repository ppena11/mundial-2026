"""
sim_live.py — simulación CONSCIENTE DEL TORNEO (20.000 sims).
Igual que sim20k pero condicionada a los RESULTADOS REALES del Mundial (ESPN):
  - Toma las posiciones reales de cada grupo (partidos ya jugados) como hecho.
  - Simula SOLO los partidos que faltan.
  - Los equipos eliminados caen solos a ~0%; los que van bien suben.

Auto-adapta por fase:
  - ANTES del torneo (sin partidos jugados) -> idéntico a sim20k.
  - Durante la fase de grupos -> condiciona grupos y simula lo que resta + eliminatorias.

Para PROBAR sin esperar al Mundial: crea wc_results_mock.json con una lista
  [["Mexico","Sudafrica",2,1], ["Espana","Uruguay",0,3], ...]
y se usará en vez de ESPN.

Escribe champ_today.json y champ_today.png (mismo formato que sim20k).
"""
import csv, math, random, json, urllib.parse
import fit_dc, engine
from datetime import date, timedelta
try:
    import requests
except ImportError:
    requests = None

engine.setconf(["Rep. Checa","Serbia y Montenegro"],"UEFA"); engine.setconf(["Cabo Verde"],"CAF")
MAP = json.load(open("namemap.json", encoding="utf-8"))

# ---------- RATINGS (idéntico a sim20k) ----------
def build():
    refd = date.fromisoformat("2026-06-01"); xi = math.log(2)/730
    rows = [r for r in csv.DictReader(open("results.csv", encoding="utf-8"))
            if r["home_score"] not in ("NA","") and "2019-01-01" <= r["date"] < "2026-06-01"]
    cnt = {}
    for r in rows: cnt[r["home_team"]] = cnt.get(r["home_team"],0)+1; cnt[r["away_team"]] = cnt.get(r["away_team"],0)+1
    teams = sorted([t for t,c in cnt.items() if c>=6]); idx = {t:i for i,t in enumerate(teams)}; OTH = len(teams); n = len(teams)+1
    H=[];A_=[];GH=[];GA=[];W=[];NEU=[]
    for r in rows:
        dt=(refd-date.fromisoformat(r["date"])).days
        H.append(idx.get(r["home_team"],OTH));A_.append(idx.get(r["away_team"],OTH))
        GH.append(int(r["home_score"]));GA.append(int(r["away_score"]));W.append(math.exp(-xi*dt))
        NEU.append(0.0 if r["neutral"]=="TRUE" else 1.0)
    import numpy as np
    return (np.array(H),np.array(A_),np.array(GH,float),np.array(GA,float),np.array(W),np.array(NEU),teams,n,OTH)

M = fit_dc.fit(build(), separate=True); ti = {t:i for i,t in enumerate(M['teams'])}
atk = {es:M['atk'][ti[dn]] for es,dn in MAP.items()}; dfn = {es:M['dfn'][ti[dn]] for es,dn in MAP.items()}
c = M['c']; g = M['g']; rho = M['rho']

# ajuste por lesiones/XI (igual que sim20k)
dATK={}; dDEF={}
try:
    import player_layer
    for _t,_d in player_layer.load_squad_data().items():
        _aa,_da = player_layer.player_adjustment(0.0,0.0,_d["starters_available"],_d["key_players"])
        dATK[_t]=_aa; dDEF[_t]=_da
except Exception as _e:
    print(f"(sin ajuste por lesiones: {_e})")
A = {t:atk[t]+dATK.get(t,0.0) for t in atk}
dfn = {t:dfn[t]+dDEF.get(t,0.0) for t in dfn}

hosts = {"Mexico","Estados Unidos","Canada"}
GROUPS = {"A":["Mexico","Sudafrica","Corea del Sur","Chequia"],"B":["Canada","Bosnia","Catar","Suiza"],
 "C":["Brasil","Marruecos","Haiti","Escocia"],"D":["Estados Unidos","Paraguay","Australia","Turquia"],
 "E":["Alemania","Curazao","Costa de Marfil","Ecuador"],"F":["Paises Bajos","Japon","Suecia","Tunez"],
 "G":["Belgica","Egipto","Iran","Nueva Zelanda"],"H":["Espana","Cabo Verde","Arabia Saudi","Uruguay"],
 "I":["Francia","Senegal","Irak","Noruega"],"J":["Argentina","Argelia","Austria","Jordania"],
 "K":["Portugal","R.D. Congo","Uzbekistan","Colombia"],"L":["Inglaterra","Croacia","Ghana","Panama"]}

def pois(l):
    L=math.exp(-l);k=0;p=1.0
    while True:
        k+=1;p*=random.random()
        if p<=L:return k-1

def gm(a,b,ko=False):
    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0));la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))
    ga,gb=pois(lh),pois(la)
    if ga<=1 and gb<=1:
        w={(0,0):(1-lh*la*rho),(0,1):la*(1+lh*rho),(1,0):lh*(1+la*rho),(1,1):lh*la*(1-rho)}
        tot=sum(v for v in w.values() if v>0);r=random.random()*tot;ac=0
        for cc_,v in w.items():
            if v>0:
                ac+=v
                if ac>=r:ga,gb=cc_;break
    if ko and ga==gb:return (a if random.random()<lh/(lh+la) else b)
    return a if ga>gb else (b if gb>ga else None)

# ---------- ESTADO REAL DEL TORNEO (ESPN, con proxy de respaldo) ----------
HEAD={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PROXY="https://api.codetabs.com/v1/proxy/?quest="
ESPN="https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
EN2ES={en:es for es,en in MAP.items()}
EN2ES.update({"Czechia":"Chequia","Czech Republic":"Chequia","USA":"Estados Unidos","United States":"Estados Unidos",
              "South Korea":"Corea del Sur","Korea Republic":"Corea del Sur","IR Iran":"Iran","Türkiye":"Turquia",
              "Bosnia & Herzegovina":"Bosnia","Bosnia and Herzegovina":"Bosnia","Côte d'Ivoire":"Costa de Marfil"})

def _get(url):
    if requests is None: raise RuntimeError("requests no disponible")
    try:
        r=requests.get(url,headers=HEAD,timeout=20); return r.json()
    except Exception:
        return requests.get(PROXY+urllib.parse.quote(url,safe=""),headers=HEAD,timeout=45).json()

def fetch_played():
    """Partidos del Mundial ya jugados, como {frozenset({a,b}): {a:ga, b:gb}} (nombres en español)."""
    played={}
    d=date(2026,6,11); end=min(date.today(), date(2026,7,20))
    while d<=end:
        try:
            data=_get(f"{ESPN}/scoreboard?dates={d:%Y%m%d}")
        except Exception:
            data={}
        for e in data.get("events",[]):
            comp=(e.get("competitions") or [{}])[0]
            if comp.get("status",{}).get("type",{}).get("state")!="post": continue
            cs=comp.get("competitors",[])
            if len(cs)!=2: continue
            try:
                nm=[EN2ES.get(x["team"]["displayName"],x["team"]["displayName"]) for x in cs]
                gl=[int(x.get("score",0)) for x in cs]
            except Exception:
                continue
            played[frozenset(nm)]={nm[0]:gl[0],nm[1]:gl[1]}
        d+=timedelta(days=1)
    return played

def load_played():
    # 1) mock local para pruebas
    try:
        mock=json.load(open("wc_results_mock.json",encoding="utf-8"))
        print("(usando wc_results_mock.json para pruebas)")
        return {frozenset((m[0],m[1])):{m[0]:m[2],m[1]:m[3]} for m in mock}
    except FileNotFoundError:
        pass
    # 2) ESPN
    try:
        return fetch_played()
    except Exception as e:
        print(f"(sin estado de ESPN, simulo todo desde cero: {e})"); return {}

PLAYED = load_played()
n_real = sum(1 for grp in GROUPS.values() for i in range(4) for j in range(i+1,4)
             if frozenset((grp[i],grp[j])) in PLAYED)
print(f"Partidos de grupo ya jugados detectados: {n_real}")

# ---------- SIMULACIÓN CONDICIONADA ----------
random.seed(11); K=20000
champ={t:0 for t in MAP}; fin={t:0 for t in MAP}
for _ in range(K):
    seeds=[]; thirds=[]
    for gN,T in GROUPS.items():
        tab={t:[0,0,0] for t in T}   # pts, dif, gf
        for i in range(4):
            for j in range(i+1,4):
                a,b=T[i],T[j]; key=frozenset((a,b))
                if key in PLAYED:                      # resultado REAL
                    ga,gb=PLAYED[key][a],PLAYED[key][b]
                else:                                  # simula el que falta
                    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0));la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))
                    ga,gb=pois(lh),pois(la)
                if ga>gb:tab[a][0]+=3
                elif gb>ga:tab[b][0]+=3
                else:tab[a][0]+=1;tab[b][0]+=1
                tab[a][1]+=ga-gb;tab[b][1]+=gb-ga;tab[a][2]+=ga;tab[b][2]+=gb
        o=sorted(T,key=lambda t:(tab[t][0],tab[t][1],tab[t][2],random.random()),reverse=True)
        seeds.append((1,A[o[0]]+dfn[o[0]],o[0]));seeds.append((2,A[o[1]]+dfn[o[1]],o[1]))
        thirds.append((o[2],tab[o[2]][0],tab[o[2]][1]))
    th=sorted(thirds,key=lambda x:(x[1],x[2],random.random()),reverse=True)[:8]
    for t in th:seeds.append((3,A[t[0]]+dfn[t[0]],t[0]))
    seeds.sort(key=lambda s:(s[0],-s[1]));order=[s[2] for s in seeds];n=len(order)
    br=[(order[i],order[n-1-i]) for i in range(n//2)]
    while len(br)>1:
        nx=[w for a,b in br for w in [gm(a,b,ko=True)]]
        if len(nx)==2:
            for t in nx:fin[t]+=1
        br=[(nx[i],nx[i+1]) for i in range(0,len(nx),2)]
    champ[gm(br[0][0],br[0][1],ko=True)]+=1

# ---------- SALIDA (mismo formato que sim20k) ----------
fase = "PRE-TORNEO (sin partidos)" if n_real==0 else f"EN CURSO ({n_real} partidos de grupo jugados)"
print(f"\nCAMPEÓN — modelo CONSCIENTE DEL TORNEO [{fase}]:")
for t in sorted(champ,key=lambda x:champ[x],reverse=True)[:8]:
    print(f"  {t:<14}{100*champ[t]/K:>5.1f}%   (final {100*fin[t]/K:>4.1f}%)")

pct={t:round(100*champ[t]/K,2) for t in sorted(champ,key=lambda x:champ[x],reverse=True)}
finpct={t:round(100*fin[t]/K,2) for t in champ}
json.dump({"campeon":pct,"final":finpct,"fase":fase,"partidos_jugados":n_real},
          open("champ_today.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("\n→ champ_today.json guardado")
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    top=list(pct.items())[:12][::-1]; labels=[t for t,_ in top]; vals=[v for _,v in top]
    plt.figure(figsize=(8,6)); bars=plt.barh(labels,vals,color="#1f77b4")
    plt.xlabel("Probabilidad de ser campeón (%)")
    plt.title(f"Mundial 2026 — Campeón ({fase})")
    for b,v in zip(bars,vals): plt.text(v+0.1,b.get_y()+b.get_height()/2,f"{v:.1f}%",va="center",fontsize=9)
    plt.tight_layout(); plt.savefig("champ_today.png",dpi=130); print("→ champ_today.png guardado")
except Exception as e:
    print(f"(gráfico omitido: {e})")
