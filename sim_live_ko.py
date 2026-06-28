"""
sim_live_ko.py — simulación con CUADRO REAL de eliminatorias (ACTIVO desde 28-jun-2026).
Extiende sim_live: además de condicionar la fase de grupos, usa el cuadro REAL del
Mundial 2026 y condiciona los resultados de eliminatoria ya jugados (el perdedor de un
partido KO queda fuera de verdad).

ESTADO: conectado a run_all.py (run_sim). Es el simulador de campeón en producción.

CUADRO (validado 28-jun-2026 contra los placeholders EN VIVO de ESPN, no solo transcrito):
  - Terminada la fase de grupos, ANCLA los 16 emparejamientos REALES de Dieciseisavos de
    ESPN (compute_fixed_r32) en lugar de reconstruirlos — así no depende de la tabla de
    asignación de terceros, que es la parte frágil. Verificado: 16/16 emparejamientos.
  - R32_SLOTS coincide posición-a-posición con la numeración nativa de ESPN; R16/QF/SF
    se contrastaron con round-of-16 / quarterfinals / semifinals (R16 pares, QF grupos y
    SF mitades = ESPN). Antes había un error en el ORDEN de R16_PAIRS (ya corregido).
  - Antes de terminar los grupos cae a la reconstrucción (R32_SLOTS + assign_thirds).

Escribe champ_today.json (clave 'campeon', mismo formato que sim_live; lo consume make_ensemble).
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
# VALIDADO 28-jun-2026 contra los placeholders en vivo de ESPN (round-of-16/quarterfinals/semifinals/final):
#   R16 #4=(7,8) y #5=(11,12) — el orden importa porque QF empareja por número de octavo (antes estaban permutados).
R16_PAIRS=[(1,3),(2,5),(4,6),(7,8),(11,12),(9,10),(14,16),(13,15)]
QF_PAIRS =[(1,2),(5,6),(3,4),(7,8)]   # QF1=R16(1,2) QF2=R16(5,6) QF3=R16(3,4) QF4=R16(7,8)  ✓ ESPN
SF_PAIRS =[(1,2),(3,4)]               # SF1=QF1+QF2  SF2=QF3+QF4  ✓ ESPN
F_PAIR   =(1,2)                       # Final=SF1+SF2  ✓ ESPN
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
import daily_digest as _dd_names
EN2ES={en:es for es,en in MAP.items()}
EN2ES.update(_dd_names.EN2ES)   # mapeo COMPLETO de daily_digest (incluye 'Congo DR'->R.D. Congo, que faltaba: sin él se perdían los 3 partidos del grupo K)
EN2ES.update({"Korea Republic":"Corea del Sur"})   # extra propio que daily_digest no trae
KO_SLUGS={"round-of-32","round-of-16","quarterfinals","semifinals","final","3rd-place"}

def _get(url):
    if requests is None: raise RuntimeError("requests no disponible")
    try: return requests.get(url,headers=HEAD,timeout=20).json()
    except Exception: return requests.get(PROXY+urllib.parse.quote(url,safe=""),headers=HEAD,timeout=45).json()

def fetch_state():
    """Devuelve (group_played {frozenset:{a:ga,b:gb}}, ko_winner {frozenset:ganador}, r32_matchups [(a,b)...]).
    r32_matchups = los 16 emparejamientos REALES de Dieciseisavos de ESPN (aunque no se hayan jugado), para anclarlos."""
    gp={}; ko={}; r32=[]
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
        print("(usando simulacros locales wc_*_mock.json)"); return gp,ko,r32
    if date.today() < date(2026,6,11): return gp,ko,r32
    try:
        data=_get(f"{ESPN}/scoreboard?dates=20260611-20260720")
    except Exception as e:
        print(f"(sin estado ESPN: {e})"); return gp,ko,r32
    for e in data.get("events",[]):
        comp=(e.get("competitions") or [{}])[0]
        cs=comp.get("competitors",[])
        if len(cs)!=2: continue
        try:
            nm=[EN2ES.get(x["team"]["displayName"],x["team"]["displayName"]) for x in cs]
        except Exception: continue
        slug=e.get("season",{}).get("slug","")
        if slug=="round-of-32": r32.append((nm[0],nm[1]))          # emparejamiento real (cualquier estado)
        if comp.get("status",{}).get("type",{}).get("state")!="post": continue
        try: gl=[int(x.get("score",0)) for x in cs]
        except Exception: continue
        if slug in KO_SLUGS:
            w = cs[0] if gl[0]>gl[1] else cs[1]
            ko[frozenset(nm)] = EN2ES.get(w["team"]["displayName"],w["team"]["displayName"])
        else:
            gp[frozenset(nm)]={nm[0]:gl[0],nm[1]:gl[1]}
    return gp,ko,r32

def _standings_real(gp):
    """W/R/3º por grupo desde los resultados reales (pts, GD, GF). {team: ('W'/'R'/'3', grupo)} o None si falta algún grupo."""
    tslot={}
    for g,T in GROUPS.items():
        s={t:[0,0,0] for t in T}
        for i in range(4):
            for j in range(i+1,4):
                a,b=T[i],T[j]; k=frozenset((a,b))
                if k not in gp: return None
                ga,gb=gp[k][a],gp[k][b]
                if ga>gb: s[a][0]+=3
                elif gb>ga: s[b][0]+=3
                else: s[a][0]+=1; s[b][0]+=1
                s[a][1]+=ga-gb; s[b][1]+=gb-ga; s[a][2]+=ga; s[b][2]+=gb
        o=sorted(T,key=lambda t:(s[t][0],s[t][1],s[t][2]),reverse=True)
        tslot[o[0]]=('W',g); tslot[o[1]]=('R',g); tslot[o[2]]=('3',g)
    return tslot

def compute_fixed_r32(gp, r32_matchups):
    """Posiciona los 16 emparejamientos R32 REALES de ESPN en el cuadro (R32_SLOTS) usando el standing real.
    Devuelve {idx 0..15: (a,b)} si todos los grupos están jugados y los 16 calzan en posiciones únicas; si no, None
    (se cae a la reconstrucción con assign_thirds). Así el cuadro KO es EXACTO sin depender de la tabla de terceros."""
    if len(r32_matchups) != 16: return None
    tslot = _standings_real(gp)
    if tslot is None: return None
    grp_of = {t:g for g,T in GROUPS.items() for t in T}
    def fits(team, slot):
        if slot[0]=='3': return tslot.get(team,('?',))[0]=='3' and grp_of.get(team) in slot[1]
        return tslot.get(team)==slot
    fixed={}; used=set()
    for (x,y) in r32_matchups:
        hit=None
        for i,(sA,sB) in enumerate(R32_SLOTS):
            if i in used: continue
            if fits(x,sA) and fits(y,sB): hit=(i,(x,y)); break
            if fits(x,sB) and fits(y,sA): hit=(i,(y,x)); break
        if hit is None: return None
        used.add(hit[0]); fixed[hit[0]]=hit[1]
    return fixed if len(fixed)==16 else None

GP, KO, R32M = fetch_state()
FIXED_R32 = compute_fixed_r32(GP, R32M)   # cuadro KO REAL anclado de ESPN (si los grupos terminaron); si no, None -> reconstrucción
n_grp=sum(1 for grp in GROUPS.values() for i in range(4) for j in range(i+1,4) if frozenset((grp[i],grp[j])) in GP)
print(f"Partidos jugados detectados — grupos: {n_grp} | eliminatorias: {len(KO)}")
print("  -> Dieciseisavos REALES de ESPN ANCLADOS (16 emparejamientos)" if FIXED_R32 else "  -> cuadro RECONSTRUIDO (grupos sin terminar)")

def play(a,b):
    """Condiciona por resultado real si existe; si no, simula."""
    k=frozenset((a,b))
    if k in KO: return KO[k]
    return winner(a,b)

# ---------- SIMULACIÓN ----------
random.seed(11); Ksims=20000
champ={t:0 for t in MAP}; fin={t:0 for t in MAP}
for _ in range(Ksims):
    winners={}
    if FIXED_R32 is not None:                          # cuadro KO REAL anclado: solo se simulan los RESULTADOS
        for idx,(a,b) in FIXED_R32.items():
            winners[("R32",idx+1)] = play(a,b)
    else:                                              # pre-KO: simular grupos y reconstruir el cuadro
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
