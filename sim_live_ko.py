"""
sim_live_ko.py — simulación con CUADRO REAL de eliminatorias (DORMIDO / en pruebas).
Extiende sim_live: además de condicionar la fase de grupos, usa el cuadro REAL del
Mundial 2026 (estructura de ESPN, transcrita abajo) y condiciona los resultados de
eliminatoria ya jugados (el perdedor de un partido KO queda fuera de verdad).

ESTADO: NO está conectado a run_all (sigue usando sim_live.py). Es para validar el
~28 de junio con datos reales antes de activarlo.

SUPOSICIÓN A VALIDAR EL 28-JUN: que la numeración R32 #1..#16 (y R16 #1..#8) coincide
con el orden en que ESPN devuelve los eventos. La topología (quién juega contra quién)
está transcrita de la API de ESPN. Si la numeración no calza, se reordena BRACKET aquí.

Escribe champ_today.json / champ_today.png (mismo formato).
"""
import csv, math, random, json, urllib.parse
import fit_dc, engine
from datetime import date
try:
    import requests
except ImportError:
    requests = None

engine.setconf(["Rep. Checa","Serbia y Montenegro"],"UEFA"); engine.setconf(["Cabo Verde"],"CAF")
MAP = json.load(open("namemap.json", encoding="utf-8"))

# ---------- RATINGS (idéntico a sim20k/sim_live) ----------
def build():
    refd=date.fromisoformat("2026-06-01");xi=math.log(2)/730
    rows=[r for r in csv.DictReader(open("results.csv",encoding="utf-8"))
          if r["home_score"] not in("NA","") and "2019-01-01"<=r["date"]<"2026-06-01"]
    cnt={}
    for r in rows:cnt[r["home_team"]]=cnt.get(r["home_team"],0)+1;cnt[r["away_team"]]=cnt.get(r["away_team"],0)+1
    teams=sorted([t for t,c in cnt.items() if c>=6]);idx={t:i for i,t in enumerate(teams)};OTH=len(teams);n=len(teams)+1
    H=[];A_=[];GH=[];GA=[];W=[];NEU=[]
    for r in rows:
        dt=(refd-date.fromisoformat(r["date"])).days
        H.append(idx.get(r["home_team"],OTH));A_.append(idx.get(r["away_team"],OTH))
        GH.append(int(r["home_score"]));GA.append(int(r["away_score"]));W.append(math.exp(-xi*dt))
        NEU.append(0.0 if r["neutral"]=="TRUE" else 1.0)
    import numpy as np
    return (np.array(H),np.array(A_),np.array(GH,float),np.array(GA,float),np.array(W),np.array(NEU),teams,n,OTH)

M=fit_dc.fit(build(),separate=True);ti={t:i for i,t in enumerate(M['teams'])}
atk={es:M['atk'][ti[dn]] for es,dn in MAP.items()};dfn={es:M['dfn'][ti[dn]] for es,dn in MAP.items()}
c=M['c'];g=M['g'];rho=M['rho']
dATK={};dDEF={}
try:
    import player_layer
    for _t,_d in player_layer.load_squad_data().items():
        _aa,_da=player_layer.player_adjustment(0.0,0.0,_d["starters_available"],_d["key_players"]);dATK[_t]=_aa;dDEF[_t]=_da
except Exception as _e:
    print(f"(sin ajuste por lesiones: {_e})")
A={t:atk[t]+dATK.get(t,0.0) for t in atk}; dfn={t:dfn[t]+dDEF.get(t,0.0) for t in dfn}
hosts={"Mexico","Estados Unidos","Canada"}
GROUPS={"A":["Mexico","Sudafrica","Corea del Sur","Chequia"],"B":["Canada","Bosnia","Catar","Suiza"],
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

def winner(a,b):
    """Ganador de un partido de eliminatoria (sin empate)."""
    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0));la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))
    ga,gb=pois(lh),pois(la)
    if ga==gb:return a if random.random()<lh/(lh+la) else b
    return a if ga>gb else b

# ---------- CUADRO REAL 2026 (transcrito de la API de ESPN) ----------
# Cada R32 es (slotA, slotB). slot: ("W",G)=ganador grupo, ("R",G)=2º, ("3",frozenset(grupos candidatos))
R32_SLOTS = [
 (("R","A"),("R","B")),                                  # 1
 (("W","C"),("R","F")),                                  # 2
 (("W","E"),("3",frozenset("ABCDF"))),                   # 3
 (("W","F"),("R","C")),                                  # 4
 (("R","E"),("R","I")),                                  # 5
 (("W","I"),("3",frozenset("CDFGH"))),                   # 6
 (("W","A"),("3",frozenset("CEFHI"))),                   # 7
 (("W","L"),("3",frozenset("EHIJK"))),                   # 8
 (("W","G"),("3",frozenset("AEHIJ"))),                   # 9
 (("W","D"),("3",frozenset("BEFIJ"))),                   # 10
 (("W","H"),("R","J")),                                  # 11
 (("R","K"),("R","L")),                                  # 12
 (("W","B"),("3",frozenset("EFGIJ"))),                   # 13
 (("R","D"),("R","G")),                                  # 14
 (("W","J"),("R","H")),                                  # 15
 (("W","K"),("3",frozenset("DEIJL"))),                   # 16
]
# pares de la siguiente ronda (1-indexados como ESPN): ganador de match i vs ganador de match j
R16_PAIRS=[(1,3),(2,5),(4,6),(11,12),(7,8),(13,15),(14,16),(9,10)]
QF_PAIRS =[(1,2),(5,6),(3,4),(7,8)]
SF_PAIRS =[(1,2),(3,4)]
F_PAIR   =(1,2)
THIRD_SLOTS=[(i,s[1][1]) for i,s in enumerate(R32_SLOTS) if s[1][0]=="3"]  # (idx_R32, frozenset candidatos)

def assign_thirds(qualified_groups):
    """Asigna los grupos de los 8 mejores terceros a las 8 casillas (matching por candidatos)."""
    slots=sorted(THIRD_SLOTS,key=lambda x:len(x[1]))  # menos candidatos primero
    res={}
    def bt(i,used):
        if i==len(slots):return True
        idx,cands=slots[i]
        for grp in cands:
            if grp in qualified_groups and grp not in used:
                res[idx]=grp;used.add(grp)
                if bt(i+1,used):return True
                used.discard(grp);del res[idx]
        return False
    if bt(0,set()):return res
    # fallback raro: asigna lo que quede
    rem=list(qualified_groups)
    for idx,_ in slots:
        if idx not in res and rem: res[idx]=rem.pop()
    return res

# ---------- ESTADO REAL (ESPN, con proxy) ----------
HEAD={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PROXY="https://api.codetabs.com/v1/proxy/?quest="
ESPN="https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
EN2ES={en:es for es,en in MAP.items()}
EN2ES.update({"Czechia":"Chequia","Czech Republic":"Chequia","USA":"Estados Unidos","United States":"Estados Unidos",
              "South Korea":"Corea del Sur","Korea Republic":"Corea del Sur","IR Iran":"Iran","Türkiye":"Turquia",
              "Bosnia & Herzegovina":"Bosnia","Bosnia and Herzegovina":"Bosnia","Bosnia-Herzegovina":"Bosnia","Côte d'Ivoire":"Costa de Marfil"})
KO_SLUGS={"round-of-32","round-of-16","quarterfinals","semifinals","final","3rd-place"}

def _get(url):
    if requests is None: raise RuntimeError("requests no disponible")
    try: return requests.get(url,headers=HEAD,timeout=20).json()
    except Exception: return requests.get(PROXY+urllib.parse.quote(url,safe=""),headers=HEAD,timeout=45).json()

def fetch_state():
    """Devuelve (group_played {frozenset:{a:ga,b:gb}}, ko_winner {frozenset:ganador})."""
    gp={}; ko={}
    # simulacros locales para pruebas (tienen prioridad)
    try:
        for m in json.load(open("wc_results_mock.json",encoding="utf-8")):
            gp[frozenset((m[0],m[1]))]={m[0]:m[2],m[1]:m[3]}
    except FileNotFoundError: pass
    try:
        for m in json.load(open("wc_ko_mock.json",encoding="utf-8")):  # [teamA, teamB, ganador]
            ko[frozenset((m[0],m[1]))]=m[2]
    except FileNotFoundError: pass
    if gp or ko:
        print("(usando simulacros locales wc_*_mock.json)"); return gp,ko
    if date.today() < date(2026,6,11): return gp,ko
    try:
        data=_get(f"{ESPN}/scoreboard?dates=20260611-20260720")
    except Exception as e:
        print(f"(sin estado ESPN: {e})"); return gp,ko
    for e in data.get("events",[]):
        comp=(e.get("competitions") or [{}])[0]
        if comp.get("status",{}).get("type",{}).get("state")!="post": continue
        cs=comp.get("competitors",[])
        if len(cs)!=2: continue
        try:
            nm=[EN2ES.get(x["team"]["displayName"],x["team"]["displayName"]) for x in cs]
            gl=[int(x.get("score",0)) for x in cs]
        except Exception: continue
        slug=e.get("season",{}).get("slug","")
        if slug in KO_SLUGS:
            w = cs[0] if gl[0]>gl[1] else cs[1]
            ko[frozenset(nm)] = EN2ES.get(w["team"]["displayName"],w["team"]["displayName"])
        else:
            gp[frozenset(nm)]={nm[0]:gl[0],nm[1]:gl[1]}
    return gp,ko

GP, KO = fetch_state()
n_grp=sum(1 for grp in GROUPS.values() for i in range(4) for j in range(i+1,4) if frozenset((grp[i],grp[j])) in GP)
print(f"Partidos jugados detectados — grupos: {n_grp} | eliminatorias: {len(KO)}")

def play(a,b):
    """Condiciona por resultado real si existe; si no, simula."""
    k=frozenset((a,b))
    if k in KO: return KO[k]
    return winner(a,b)

# ---------- SIMULACIÓN ----------
random.seed(11); Ksims=20000
champ={t:0 for t in MAP}; fin={t:0 for t in MAP}
for _ in range(Ksims):
    pos={}; thirds=[]
    for gN,T in GROUPS.items():
        tab={t:[0,0,0] for t in T}
        for i in range(4):
            for j in range(i+1,4):
                a,b=T[i],T[j];key=frozenset((a,b))
                if key in GP: ga,gb=GP[key][a],GP[key][b]
                else:
                    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0));la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0));ga,gb=pois(lh),pois(la)
                if ga>gb:tab[a][0]+=3
                elif gb>ga:tab[b][0]+=3
                else:tab[a][0]+=1;tab[b][0]+=1
                tab[a][1]+=ga-gb;tab[b][1]+=gb-ga;tab[a][2]+=ga;tab[b][2]+=gb
        o=sorted(T,key=lambda t:(tab[t][0],tab[t][1],tab[t][2],random.random()),reverse=True)
        pos[("W",gN)]=o[0];pos[("R",gN)]=o[1]
        thirds.append((gN,o[2],tab[o[2]][0],tab[o[2]][1],tab[o[2]][2]))
    best=sorted(thirds,key=lambda x:(x[2],x[3],x[4],random.random()),reverse=True)[:8]
    qgroups={x[0] for x in best}; third_team={x[0]:x[1] for x in best}
    amap=assign_thirds(qgroups)   # idx_R32 -> grupo
    winners={}
    for idx,(sA,sB) in enumerate(R32_SLOTS):
        ta = third_team[amap[idx]] if sA[0]=="3" else pos[sA]
        tb = third_team[amap[idx]] if sB[0]=="3" else pos[sB]
        winners[("R32",idx+1)] = play(ta,tb)
    def round_play(pairs,name,src):
        out={}
        for n,(i,j) in enumerate(pairs,1):
            out[(name,n)] = play(winners[(src,i)],winners[(src,j)])
        winners.update(out)
    round_play(R16_PAIRS,"R16","R32")
    round_play(QF_PAIRS,"QF","R16")
    round_play(SF_PAIRS,"SF","QF")
    f1,f2=winners[("SF",F_PAIR[0])],winners[("SF",F_PAIR[1])]
    fin[f1]+=1;fin[f2]+=1
    champ[play(f1,f2)]+=1

fase = "PRE-TORNEO" if (n_grp==0 and len(KO)==0) else f"EN CURSO (grupos:{n_grp}, KO:{len(KO)})"
print(f"\nCAMPEÓN — CUADRO REAL [{fase}]:")
for t in sorted(champ,key=lambda x:champ[x],reverse=True)[:8]:
    print(f"  {t:<14}{100*champ[t]/Ksims:>5.1f}%   (final {100*fin[t]/Ksims:>4.1f}%)")

pct={t:round(100*champ[t]/Ksims,2) for t in sorted(champ,key=lambda x:champ[x],reverse=True)}
finpct={t:round(100*fin[t]/Ksims,2) for t in champ}
json.dump({"campeon":pct,"final":finpct,"fase":fase},open("champ_today.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("\n→ champ_today.json guardado (sim_live_ko)")
