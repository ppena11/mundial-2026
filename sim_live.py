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
import csv, math, random, json, os, urllib.parse
import fit_dc, engine
import context_factors as cf, format_engine as fe, schedule_2026 as _sched
from datetime import date, timedelta

# Toggles SOLO para auditoría/ablación (ablation.py). Defaults = producción (todo activado).
_ABL_INJ = os.environ.get("SL_INJ", "1") not in ("0", "false")
_ABL_HOST = os.environ.get("SL_HOST", "1") not in ("0", "false")
_ABL_BRACKET = os.environ.get("SL_BRACKET", "1") not in ("0", "false")
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
if not _ABL_HOST: g = 0.0   # ablación: sin ventaja de anfitrión

# ajuste por lesiones/XI (igual que sim20k)
dATK={}; dDEF={}
if _ABL_INJ:
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

def gm(a,b,ko=False,fa=1.0,fb=1.0):
    """Simula un partido y devuelve el ganador (o None si empate en grupos).
    fa/fb = multiplicadores de contexto (altura/calor/viaje) sobre λ de a y b.
    El muestreo va por format_engine (Dixon-Coles + binomial negativa opcional)."""
    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0))*fa*cf.WC_GOAL_LEVEL
    la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))*fb*cf.WC_GOAL_LEVEL
    ga,gb=fe.sample_score(lh,la,rho,dispersion_r=cf.DISPERSION_R)
    if ko and ga==gb:return (a if random.random()<lh/(lh+la) else b)
    return a if ga>gb else (b if gb>ga else None)

# ---------- ESTADO REAL DEL TORNEO (ESPN, con proxy de respaldo) ----------
HEAD={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PROXY="https://api.codetabs.com/v1/proxy/?quest="
ESPN="https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
EN2ES={en:es for es,en in MAP.items()}
EN2ES.update({"Czechia":"Chequia","Czech Republic":"Chequia","USA":"Estados Unidos","United States":"Estados Unidos",
              "South Korea":"Corea del Sur","Korea Republic":"Corea del Sur","IR Iran":"Iran","Türkiye":"Turquia",
              "Bosnia & Herzegovina":"Bosnia","Bosnia and Herzegovina":"Bosnia","Bosnia-Herzegovina":"Bosnia","Côte d'Ivoire":"Costa de Marfil"})

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

# ---------- CALENDARIO + FACTORES DE CONTEXTO (altura/calor/viaje) ----------
# Se precomputan UNA vez por par de equipos (la sede, hora y viaje son fijos; solo los goles
# son aleatorios). Así no se recalculan en cada una de las 20.000 simulaciones.
try:
    SCHED = _sched.load()
except Exception as _e:
    print(f"(sin calendario para factores de contexto: {_e})"); SCHED = _sched.Schedule([])
PAIR_FACTORS = {}   # frozenset({a,b}) -> {a: f_a, b: f_b}
for _gN, _T in GROUPS.items():
    for _i in range(4):
        for _j in range(_i+1, 4):
            _a, _b = _T[_i], _T[_j]
            _ground, _hour = SCHED.factors_for(_a, _b)
            _ta, _tb = SCHED.travel_for_pair(_a, _b)
            _fa, _fb = cf.match_factors(_a, _b, _ground, _hour, home_travel=_ta, away_travel=_tb,
                                        enable_alt=cf.USE_ALTITUDE, enable_heat=cf.USE_HEAT,
                                        enable_travel=cf.USE_TRAVEL)
            PAIR_FACTORS[frozenset((_a, _b))] = {_a: _fa, _b: _fb}
_nf = sum(1 for v in PAIR_FACTORS.values() if any(abs(x-1.0) > 1e-9 for x in v.values()))
print(f"Factores de contexto en {_nf}/{len(PAIR_FACTORS)} partidos de grupo "
      f"(altura={cf.USE_ALTITUDE}, calor={cf.USE_HEAT}, viaje={cf.USE_TRAVEL}, dispersión_r={cf.DISPERSION_R})")

# ---------- BRACKET OFICIAL DE ELIMINATORIAS (con sedes) ----------
TEAM_GROUP = {t: gN for gN, T in GROUPS.items() for t in T}
BRACKET = _sched.build_bracket(SCHED.matches, TEAM_GROUP)
BR_OK = BRACKET["ok"] and _ABL_BRACKET   # ablación: si se apaga, cae a siembra por fuerza
# último partido de grupo de cada equipo (origen del viaje hacia la R32)
LAST_GROUP = {}
for _t, _ms in SCHED.by_team.items():
    if _ms:
        _m = _ms[-1]; LAST_GROUP[_t] = (_m["ground"], _m["date"], _m["utc_offset"])
_alt_ko = sum(1 for n in BRACKET["match"] if (cf.venue(BRACKET["match"][n]["ground"]) or {}).get("elevation_m", 0) > cf.ALT_THRESHOLD) if BR_OK else 0
print(f"Bracket oficial de eliminatorias: {'OK' if BR_OK else 'NO disponible (uso siembra por fuerza)'}"
      f"{f' — {_alt_ko} partidos KO en altura con factores' if BR_OK else ''}")

def ko_travel(team, ground, date_str, offset, last_played):
    """Viaje/descanso/jet lag de un equipo en un partido KO, desde su partido anterior."""
    prev = last_played.get(team)
    if not prev:
        return None
    pg, pd, po = prev
    out = {"rest_days": None, "km_travel": 0.0, "tz_change": 0}
    try:
        if date_str and pd:
            out["rest_days"] = (date.fromisoformat(date_str) - date.fromisoformat(pd)).days
    except Exception:
        pass
    vN = cf.venue(ground); vP = cf.venue(pg)
    if vN and vP and None not in (vN.get("lat"), vN.get("lon"), vP.get("lat"), vP.get("lon")):
        out["km_travel"] = cf.haversine(vP["lat"], vP["lon"], vN["lat"], vN["lon"])
    if offset is not None and po is not None:
        out["tz_change"] = offset - po
    return out

def resolve_slot(slot, num, pos1, pos2, third_team, tassign, winner, loser):
    """Equipo concreto que ocupa un slot del bracket en una simulación dada."""
    k, v = slot
    if k == "W": return pos1[v]
    if k == "R": return pos2[v]
    if k == "3": return third_team[tassign[num]]
    if k == "M": return winner[v]
    return loser[v]   # "LM" (perdedor, para el 3er puesto)

# ---------- SIMULACIÓN CONDICIONADA ----------
# K=100.000 (≈90 s) baja el ruido Monte Carlo del pronóstico de campeón a ~1pp (vs ~2.4pp a 20k).
# Configurable con SL_K (la batería de pruebas usa un K bajo para correr rápido).
random.seed(int(os.environ.get("SL_SEED", "11"))); K=int(os.environ.get("SL_K", "100000"))
champ={t:0 for t in MAP}; fin={t:0 for t in MAP}
for _ in range(K):
    pos1={}; pos2={}; third_team={}; thirds=[]
    for gN,T in GROUPS.items():
        gmatches=[]
        for i in range(4):
            for j in range(i+1,4):
                a,b=T[i],T[j]; key=frozenset((a,b))
                if key in PLAYED:                      # resultado REAL
                    ga,gb=PLAYED[key][a],PLAYED[key][b]
                else:                                  # simula el que falta (con factores de contexto)
                    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0))*cf.WC_GOAL_LEVEL
                    la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))*cf.WC_GOAL_LEVEL
                    _f=PAIR_FACTORS.get(key,{}); lh*=_f.get(a,1.0); la*=_f.get(b,1.0)
                    ga,gb=fe.sample_score(lh,la,0.0,dispersion_r=cf.DISPERSION_R)
                gmatches.append((a,b,ga,gb))
        order=fe.rank_group(T,gmatches)                # cascada FIFA 2026 (head-to-head, etc.)
        tabg=fe.group_table(T,gmatches)
        pos1[gN]=order[0]; pos2[gN]=order[1]; third_team[gN]=order[2]
        thirds.append((order[2],tabg[order[2]]["pts"],tabg[order[2]]["gd"],tabg[order[2]]["gf"]))
    top8=set(fe.rank_thirds(thirds)[:8])               # 8 mejores terceros (criterios oficiales 2026)

    if BR_OK:
        # --- BRACKET OFICIAL: casillas reales + sede/hora por partido + factores en KO ---
        qual_groups={gN for gN in GROUPS if third_team[gN] in top8}
        tassign=fe.assign_thirds(qual_groups, candidates=BRACKET["third_candidates"])
        last_played=dict(LAST_GROUP)
        winner={}; loser={}
        for num in BRACKET["order"]:
            mm=BRACKET["match"][num]
            a=resolve_slot(mm["a"],num,pos1,pos2,third_team,tassign,winner,loser)
            b=resolve_slot(mm["b"],num,pos1,pos2,third_team,tassign,winner,loser)
            ta=ko_travel(a,mm["ground"],mm["date"],mm["offset"],last_played)
            tb=ko_travel(b,mm["ground"],mm["date"],mm["offset"],last_played)
            fa,fb=cf.match_factors(a,b,mm["ground"],mm["hour"],home_travel=ta,away_travel=tb,
                                   enable_alt=cf.USE_ALTITUDE,enable_heat=cf.USE_HEAT,enable_travel=cf.USE_TRAVEL)
            w=gm(a,b,ko=True,fa=fa,fb=fb); winner[num]=w; loser[num]=a if w==b else b
            last_played[w]=(mm["ground"],mm["date"],mm["offset"])
        for t in (winner[101],winner[102]): fin[t]+=1   # finalistas
        champ[winner[104]]+=1
    else:
        # --- RESPALDO: siembra por fuerza (sin factores en KO) si el bracket no está disponible ---
        seeds=[]
        for gN in GROUPS:
            seeds.append((1,A[pos1[gN]]+dfn[pos1[gN]],pos1[gN]));seeds.append((2,A[pos2[gN]]+dfn[pos2[gN]],pos2[gN]))
        for t in top8: seeds.append((3,A[t]+dfn[t],t))
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
