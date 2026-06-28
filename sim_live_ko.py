"""
sim_live_ko.py — simulador de CAMPEÓN del Mundial 2026 (ACTIVO en producción desde 28-jun-2026).

Combina el MODELO COMPLETO (idéntico a sim_live: ratings que APRENDEN del Mundial con boost de forma,
lesiones, motor Dixon-Coles + dispersión binomial negativa, factores de contexto altura/calor/viaje en
grupos Y eliminatorias, desempates FIFA oficiales, 100.000 simulaciones) con el CUADRO REAL de ESPN.

CUADRO (validado 28-jun-2026 contra los placeholders EN VIVO de ESPN, no solo transcrito):
  - Terminada la fase de grupos, ANCLA los 16 emparejamientos REALES de Dieciseisavos de ESPN
    (compute_fixed_r32) en lugar de reconstruirlos — así no depende de la tabla de asignación de
    terceros, que es la parte frágil. Verificado: 16/16 emparejamientos.
  - R32_SLOTS coincide posición-a-posición con la numeración nativa de ESPN; R16/QF/SF se
    contrastaron con round-of-16 / quarterfinals / semifinals (R16 pares, QF grupos y SF mitades = ESPN).
  - Condiciona los resultados KO ya jugados (el perdedor de un partido de eliminatoria queda fuera de verdad).
  - Antes de terminar los grupos cae a la reconstrucción (R32_SLOTS + assign_thirds).
  - Sedes de cada partido KO leídas de ESPN y mapeadas a context_factors por nombre de estadio (altura/calor/viaje).

NOTA: el bracket de schedule_2026 (openfootball) NO coincide con el real de ESPN, por eso aquí se usa el
cuadro de ESPN y NO build_bracket. De schedule_2026 solo se reutiliza el CALENDARIO de grupos (sedes/viaje).

Escribe champ_today.json (clave 'campeon') y champ_today.png (mismo formato que sim_live; lo consume make_ensemble).
"""
import csv, math, random, json, os, urllib.parse
import fit_dc, engine
import context_factors as cf, format_engine as fe, schedule_2026 as _sched
from datetime import date, timedelta
try:
    import requests
except ImportError:
    requests = None

# Toggles SOLO para auditoría/ablación (iguales que sim_live). Defaults = producción (todo activado).
_ABL_INJ  = os.environ.get("SL_INJ",  "1") not in ("0", "false")
_ABL_HOST = os.environ.get("SL_HOST", "1") not in ("0", "false")

engine.setconf(["Rep. Checa","Serbia y Montenegro"],"UEFA"); engine.setconf(["Cabo Verde"],"CAF")
MAP = json.load(open("namemap.json", encoding="utf-8"))

# ---------- RATINGS (con ACTUALIZACIÓN EN TORNEO: aprende de los partidos del Mundial jugados) ----------
def build():
    refd = date.today(); xi = math.log(2)/730        # ref móvil: los partidos del Mundial son los más recientes
    end = (refd + timedelta(days=1)).isoformat()
    rows = [r for r in csv.DictReader(open("results.csv", encoding="utf-8"))
            if r["home_score"] not in ("NA","") and "2019-01-01" <= r["date"] < end]
    cnt = {}
    for r in rows: cnt[r["home_team"]] = cnt.get(r["home_team"],0)+1; cnt[r["away_team"]] = cnt.get(r["away_team"],0)+1
    teams = sorted([t for t,c in cnt.items() if c>=6]); idx = {t:i for i,t in enumerate(teams)}; OTH = len(teams); n = len(teams)+1
    redcards = {}
    if cf.USE_WC_FORM:
        try:
            import wc_form; redcards = wc_form.load_red_cards()
        except Exception:
            redcards = {}
    inv = {v: k for k, v in MAP.items()}   # nombre EN (results.csv) -> ES (para casar rojas)
    def _is_wc(r): return r["date"] >= "2026-06-11" and r.get("tournament") == "FIFA World Cup"
    wc_count = {}
    if cf.USE_WC_FORM:
        for r in rows:
            if _is_wc(r):
                wc_count[r["home_team"]] = wc_count.get(r["home_team"], 0) + 1
                wc_count[r["away_team"]] = wc_count.get(r["away_team"], 0) + 1
    nwc = 0
    H=[];A_=[];GH=[];GA=[];W=[];NEU=[]
    for r in rows:
        d = r["date"]; gh = int(r["home_score"]); ga = int(r["away_score"])
        w = math.exp(-xi*(refd-date.fromisoformat(d)).days)
        if cf.USE_WC_FORM and _is_wc(r):
            import wc_form
            rm = redcards.get(frozenset((inv.get(r["home_team"]), inv.get(r["away_team"]))))
            w *= wc_form.reliability(gh, ga, rm)
            if wc_count.get(r["home_team"], 0) >= cf.WC_FORM_MIN and wc_count.get(r["away_team"], 0) >= cf.WC_FORM_MIN:
                w *= cf.WC_FORM_BOOST
            nwc += 1
        H.append(idx.get(r["home_team"],OTH));A_.append(idx.get(r["away_team"],OTH))
        GH.append(gh);GA.append(ga);W.append(w);NEU.append(0.0 if r["neutral"]=="TRUE" else 1.0)
    if cf.USE_WC_FORM and nwc:
        print(f"Actualización en torneo: {nwc} partidos del Mundial incorporados al rating (forma×fiabilidad, FORM_BOOST={cf.WC_FORM_BOOST})")
    import numpy as np
    return (np.array(H),np.array(A_),np.array(GH,float),np.array(GA,float),np.array(W),np.array(NEU),teams,n,OTH)

M = fit_dc.fit(build(), separate=True); ti = {t:i for i,t in enumerate(M['teams'])}
atk = {es:M['atk'][ti[dn]] for es,dn in MAP.items()}; dfn = {es:M['dfn'][ti[dn]] for es,dn in MAP.items()}
c = M['c']; g = M['g']; rho = M['rho']
if not _ABL_HOST: g = 0.0   # ablación: sin ventaja de anfitrión

# ajuste por lesiones/XI (igual que sim_live)
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

def gscore(a,b,fa=1.0,fb=1.0):
    """Marcador muestreado (Dixon-Coles + dispersión) con factores de contexto fa/fb sobre λ."""
    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0))*fa*cf.WC_GOAL_LEVEL
    la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))*fb*cf.WC_GOAL_LEVEL
    return fe.sample_score(lh,la,0.0,dispersion_r=cf.DISPERSION_R)

def gm(a,b,fa=1.0,fb=1.0):
    """Ganador de un partido de ELIMINATORIA (sin empate), con factores de contexto."""
    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0))*fa*cf.WC_GOAL_LEVEL
    la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))*fb*cf.WC_GOAL_LEVEL
    ga,gb=fe.sample_score(lh,la,rho,dispersion_r=cf.DISPERSION_R)
    if ga==gb: return a if random.random()<lh/(lh+la) else b
    return a if ga>gb else b

# ---------- CUADRO REAL 2026 (transcrito de la API de ESPN, VALIDADO 28-jun en vivo) ----------
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
#   R16 #4=(7,8) y #5=(11,12) — el orden importa porque QF empareja por número de octavo.
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
EN2ES.update(_dd_names.EN2ES)   # mapeo COMPLETO de daily_digest (incluye 'Congo DR'->R.D. Congo; sin él se perdían los 3 partidos del grupo K)
EN2ES.update({"Korea Republic":"Corea del Sur"})
KO_SLUGS={"round-of-32","round-of-16","quarterfinals","semifinals","final","3rd-place"}

def _get(url):
    if requests is None: raise RuntimeError("requests no disponible")
    try: return requests.get(url,headers=HEAD,timeout=20).json()
    except Exception: return requests.get(PROXY+urllib.parse.quote(url,safe=""),headers=HEAD,timeout=45).json()

def fetch_state():
    """(group_played {frozenset:{a:ga,b:gb}}, ko_winner {frozenset:ganador}, r32_matchups [(a,b)...])."""
    gp={}; ko={}; r32=[]
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

# ---------- CALENDARIO + FACTORES DE CONTEXTO EN GRUPOS (altura/calor/viaje) ----------
try:
    SCHED = _sched.load()
except Exception as _e:
    print(f"(sin calendario para factores de contexto: {_e})"); SCHED = _sched.Schedule([])
PAIR_FACTORS = {}
for _gN, _T in GROUPS.items():
    for _i in range(4):
        for _j in range(_i+1, 4):
            _a, _b = _T[_i], _T[_j]
            _ground, _hour = SCHED.factors_for(_a, _b)
            _ta, _tb = SCHED.travel_for_pair(_a, _b)
            _fa, _fb = cf.match_factors(_a, _b, _ground, _hour, home_travel=_ta, away_travel=_tb,
                                        enable_alt=cf.USE_ALTITUDE, enable_heat=cf.USE_HEAT, enable_travel=cf.USE_TRAVEL)
            PAIR_FACTORS[frozenset((_a, _b))] = {_a: _fa, _b: _fb}
_nf = sum(1 for v in PAIR_FACTORS.values() if any(abs(x-1.0) > 1e-9 for x in v.values()))
print(f"Factores de contexto en {_nf}/{len(PAIR_FACTORS)} partidos de grupo "
      f"(altura={cf.USE_ALTITUDE}, calor={cf.USE_HEAT}, viaje={cf.USE_TRAVEL}, dispersión_r={cf.DISPERSION_R})")

# último partido de grupo de cada equipo (origen del viaje hacia la R32)
LAST_GROUP = {}
for _t, _ms in SCHED.by_team.items():
    if _ms:
        _m = _ms[-1]; LAST_GROUP[_t] = (_m["ground"], _m["date"], _m["utc_offset"])

# ---------- SEDES DE LOS PARTIDOS KO (de ESPN, mapeadas a context_factors por nombre de estadio) ----------
def _norm(s): return "".join(ch for ch in str(s).lower() if ch.isalnum())
_CF_GROUNDS = sorted({m["ground"] for m in SCHED.matches if m.get("ground")})
_STAD2GROUND = {}
for _gd in _CF_GROUNDS:
    _v = cf.venue(_gd)
    if _v and _v.get("stadium"): _STAD2GROUND[_norm(_v["stadium"])] = _gd

def _espn_ground(fullname):
    """Sede cf-compatible desde el fullName de ESPN (match por nombre de estadio). None si no calza."""
    n = _norm(fullname)
    if not n: return None
    if n in _STAD2GROUND: return _STAD2GROUND[n]
    for k, gd in _STAD2GROUND.items():
        if n in k or k in n: return gd
    return None

def fetch_ko_venues():
    """{(ronda, pos): (ground_cf, hora_local, fecha_iso, utc_offset)} para los partidos KO, en orden nativo de ESPN
    (= posiciones del cuadro validado). Permite aplicar altura/calor/viaje en eliminatorias."""
    rounds={"round-of-32":"R32","round-of-16":"R16","quarterfinals":"QF","semifinals":"SF","final":"F"}
    bypos={}; seen=set()
    try:
        chunks=[_get(f"{ESPN}/scoreboard?dates=20260611-20260720"),
                _get(f"{ESPN}/scoreboard?dates=20260714-20260725")]
    except Exception as _e:
        print(f"(sin sedes KO de ESPN: {_e})"); return {}
    for data in chunks:
        for e in data.get("events",[]):
            slug=e.get("season",{}).get("slug","")
            if slug not in rounds or e.get("id") in seen: continue
            seen.add(e.get("id"))
            comp=(e.get("competitions") or [{}])[0]
            gd=_espn_ground(comp.get("venue",{}).get("fullName",""))
            bypos.setdefault(rounds[slug],[]).append((e.get("date",""), gd))
    out={}
    for rnd,lst in bypos.items():
        for i,(dt,gd) in enumerate(lst,1):
            off=None
            if gd:
                v=cf.venue(gd)
                if v: off=v.get("utc_offset")
            hour=18
            try:
                uh=int(dt[11:13])
                if off is not None: hour=(uh+off)%24
            except Exception: pass
            out[(rnd,i)]=(gd, hour, dt[:10], off if off is not None else 0)
    return out

KO_VENUE = fetch_ko_venues()
_nkv = sum(1 for v in KO_VENUE.values() if v[0])
print(f"Sedes KO resueltas: {_nkv}/{len(KO_VENUE)} (altura/calor/viaje en eliminatorias)")

def ko_travel(team, ground, date_str, offset, last_played):
    """Viaje/descanso/jet lag de un equipo en un partido KO, desde su partido anterior."""
    prev = last_played.get(team)
    if not prev: return None
    pg, pd, po = prev
    out = {"rest_days": None, "km_travel": 0.0, "tz_change": 0}
    try:
        if date_str and pd:
            out["rest_days"] = (date.fromisoformat(date_str) - date.fromisoformat(pd)).days
    except Exception: pass
    vN = cf.venue(ground); vP = cf.venue(pg)
    if vN and vP and None not in (vN.get("lat"), vN.get("lon"), vP.get("lat"), vP.get("lon")):
        out["km_travel"] = cf.haversine(vP["lat"], vP["lon"], vN["lat"], vN["lon"])
    if offset is not None and po is not None:
        out["tz_change"] = offset - po
    return out

def _standings_real(gp):
    """W/R/3º por grupo con desempates FIFA (fe.rank_group). {team: ('W'/'R'/'3', grupo)} o None si falta un grupo."""
    tslot={}
    for g_,T in GROUPS.items():
        gmatches=[]
        for i in range(4):
            for j in range(i+1,4):
                a,b=T[i],T[j]; k=frozenset((a,b))
                if k not in gp: return None
                gmatches.append((a,b,gp[k][a],gp[k][b]))
        o=fe.rank_group(T,gmatches)
        tslot[o[0]]=('W',g_); tslot[o[1]]=('R',g_); tslot[o[2]]=('3',g_)
    return tslot

def compute_fixed_r32(gp, r32_matchups):
    """Posiciona los 16 emparejamientos R32 REALES de ESPN en el cuadro (R32_SLOTS) usando el standing real.
    Devuelve {idx 0..15: (a,b)} si todos los grupos están jugados y los 16 calzan en posiciones únicas; si no, None."""
    if len(r32_matchups) != 16: return None
    tslot = _standings_real(gp)
    if tslot is None: return None
    grp_of = {t:g_ for g_,T in GROUPS.items() for t in T}
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
FIXED_R32 = compute_fixed_r32(GP, R32M)
n_grp=sum(1 for grp in GROUPS.values() for i in range(4) for j in range(i+1,4) if frozenset((grp[i],grp[j])) in GP)
print(f"Partidos jugados detectados — grupos: {n_grp} | eliminatorias: {len(KO)}")
print("  -> Dieciseisavos REALES de ESPN ANCLADOS (16 emparejamientos)" if FIXED_R32 else "  -> cuadro RECONSTRUIDO (grupos sin terminar)")

def play_ko(a, b, rnd, pos, last_played):
    """Juega un partido KO en la casilla (rnd,pos): condiciona por el resultado real si existe; si no, simula
    con los factores de contexto (altura/calor/viaje) de esa sede. Actualiza last_played del ganador."""
    info = KO_VENUE.get((rnd, pos))
    fa = fb = 1.0
    if info and info[0]:
        ground, hour, dstr, off = info
        ta = ko_travel(a, ground, dstr, off, last_played)
        tb = ko_travel(b, ground, dstr, off, last_played)
        fa, fb = cf.match_factors(a, b, ground, hour, home_travel=ta, away_travel=tb,
                                  enable_alt=cf.USE_ALTITUDE, enable_heat=cf.USE_HEAT, enable_travel=cf.USE_TRAVEL)
    k = frozenset((a, b))
    w = KO[k] if k in KO else gm(a, b, fa, fb)        # resultado REAL si ya se jugó; si no, simulación
    if info and info[0]:
        last_played[w] = (info[0], info[2], info[3])
    return w

# ---------- SIMULACIÓN ----------
random.seed(int(os.environ.get("SL_SEED", "11"))); Ksims=int(os.environ.get("SL_K", "100000"))
champ={t:0 for t in MAP}; fin={t:0 for t in MAP}
for _ in range(Ksims):
    winners={}; last_played=dict(LAST_GROUP)
    if FIXED_R32 is not None:                          # cuadro KO REAL anclado: solo se simulan los RESULTADOS
        for idx,(a,b) in FIXED_R32.items():
            winners[("R32",idx+1)] = play_ko(a,b,"R32",idx+1,last_played)
    else:                                              # pre-KO: simular grupos (con factores) y reconstruir el cuadro
        pos={}; third_team={}; thirds=[]
        for gN,T in GROUPS.items():
            gmatches=[]
            for i in range(4):
                for j in range(i+1,4):
                    a,b=T[i],T[j]; key=frozenset((a,b))
                    if key in GP: ga,gb=GP[key][a],GP[key][b]
                    else:
                        _f=PAIR_FACTORS.get(key,{}); ga,gb=gscore(a,b,_f.get(a,1.0),_f.get(b,1.0))
                    gmatches.append((a,b,ga,gb))
            order=fe.rank_group(T,gmatches); tabg=fe.group_table(T,gmatches)
            pos[("W",gN)]=order[0]; pos[("R",gN)]=order[1]; third_team[gN]=order[2]
            thirds.append((order[2],tabg[order[2]]["pts"],tabg[order[2]]["gd"],tabg[order[2]]["gf"]))
        top8=set(fe.rank_thirds(thirds)[:8])
        qgroups={gN for gN in GROUPS if third_team[gN] in top8}
        amap=assign_thirds(qgroups)
        for idx,(sA,sB) in enumerate(R32_SLOTS):
            ta = third_team[amap[idx]] if sA[0]=="3" else pos[sA]
            tb = third_team[amap[idx]] if sB[0]=="3" else pos[sB]
            winners[("R32",idx+1)] = play_ko(ta,tb,"R32",idx+1,last_played)
    def round_play(pairs,name,src):
        out={}
        for n,(i,j) in enumerate(pairs,1):
            out[(name,n)] = play_ko(winners[(src,i)],winners[(src,j)],name,n,last_played)
        winners.update(out)
    round_play(R16_PAIRS,"R16","R32")
    round_play(QF_PAIRS,"QF","R16")
    round_play(SF_PAIRS,"SF","QF")
    f1,f2=winners[("SF",F_PAIR[0])],winners[("SF",F_PAIR[1])]
    fin[f1]+=1;fin[f2]+=1
    champ[play_ko(f1,f2,"F",1,last_played)]+=1

# ---------- SALIDA (mismo formato que sim_live) ----------
fase = "PRE-TORNEO" if (n_grp==0 and len(KO)==0) else (f"EN CURSO (grupos:{n_grp}, KO:{len(KO)})")
print(f"\nCAMPEÓN — CUADRO REAL [{fase}]:")
for t in sorted(champ,key=lambda x:champ[x],reverse=True)[:8]:
    print(f"  {t:<14}{100*champ[t]/Ksims:>5.1f}%   (final {100*fin[t]/Ksims:>4.1f}%)")

pct={t:round(100*champ[t]/Ksims,2) for t in sorted(champ,key=lambda x:champ[x],reverse=True)}
finpct={t:round(100*fin[t]/Ksims,2) for t in champ}
json.dump({"campeon":pct,"final":finpct,"fase":fase},open("champ_today.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("\n→ champ_today.json guardado (sim_live_ko)")
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    top=list(pct.items())[:12][::-1]; labels=[t for t,_ in top]; vals=[v for _,v in top]
    plt.figure(figsize=(8,6)); bars=plt.barh(labels,vals,color="#1f77b4")
    plt.xlabel("Probabilidad de ser campeón (%)"); plt.title(f"Mundial 2026 — Campeón ({fase})")
    for b,v in zip(bars,vals): plt.text(v+0.1,b.get_y()+b.get_height()/2,f"{v:.1f}%",va="center",fontsize=9)
    plt.tight_layout(); plt.savefig("champ_today.png",dpi=130); print("→ champ_today.png guardado")
except Exception as e:
    print(f"(gráfico omitido: {e})")
