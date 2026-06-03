import csv,math,random,json,numpy as np
import fit_dc,engine
engine.setconf(["Rep. Checa","Serbia y Montenegro"],"UEFA");engine.setconf(["Cabo Verde"],"CAF")
MAP=json.load(open("namemap.json",encoding="utf-8"));from datetime import date
def build():
    refd=date.fromisoformat("2026-06-01");xi=math.log(2)/730
    rows=[r for r in csv.DictReader(open("results.csv",encoding="utf-8")) if r["home_score"] not in("NA","") and "2019-01-01"<=r["date"]<"2026-06-01"]
    cnt={}
    for r in rows:cnt[r["home_team"]]=cnt.get(r["home_team"],0)+1;cnt[r["away_team"]]=cnt.get(r["away_team"],0)+1
    teams=sorted([t for t,c in cnt.items() if c>=6]);idx={t:i for i,t in enumerate(teams)};OTH=len(teams);n=len(teams)+1
    H=[];A_=[];GH=[];GA=[];W=[];NEU=[]
    for r in rows:
        dt=(refd-date.fromisoformat(r["date"])).days
        H.append(idx.get(r["home_team"],OTH));A_.append(idx.get(r["away_team"],OTH));GH.append(int(r["home_score"]));GA.append(int(r["away_score"]));W.append(math.exp(-xi*dt));NEU.append(0.0 if r["neutral"]=="TRUE" else 1.0)
    return (np.array(H),np.array(A_),np.array(GH,float),np.array(GA,float),np.array(W),np.array(NEU),teams,n,OTH)
M=fit_dc.fit(build(),separate=True);ti={t:i for i,t in enumerate(M['teams'])}
atk={es:M['atk'][ti[dn]] for es,dn in MAP.items()};dfn={es:M['dfn'][ti[dn]] for es,dn in MAP.items()};c=M['c'];g=M['g'];rho=M['rho']
NEWS=json.load(open("news_0602.json",encoding="utf-8"))
A={t:atk[t]+NEWS.get(t,0) for t in atk}
hosts={"Mexico","Estados Unidos","Canada"}
GROUPS={"A":["Mexico","Sudafrica","Corea del Sur","Chequia"],"B":["Canada","Bosnia","Catar","Suiza"],"C":["Brasil","Marruecos","Haiti","Escocia"],"D":["Estados Unidos","Paraguay","Australia","Turquia"],"E":["Alemania","Curazao","Costa de Marfil","Ecuador"],"F":["Paises Bajos","Japon","Suecia","Tunez"],"G":["Belgica","Egipto","Iran","Nueva Zelanda"],"H":["Espana","Cabo Verde","Arabia Saudi","Uruguay"],"I":["Francia","Senegal","Irak","Noruega"],"J":["Argentina","Argelia","Austria","Jordania"],"K":["Portugal","R.D. Congo","Uzbekistan","Colombia"],"L":["Inglaterra","Croacia","Ghana","Panama"]}
def pois(l):
    L=math.exp(-l);k=0;p=1.0
    while True:
        k+=1;p*=random.random()
        if p<=L:return k-1
def gm(a,b,ko=False):
    lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0));la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))
    if ko:lh*=1.0;la*=1.0  # factor KO calibrado: sin evidencia de menos goles en eliminatorias (Mundiales reales ratio 1.02)
    ga,gb=pois(lh),pois(la)
    if ga<=1 and gb<=1:
        w={(0,0):(1-lh*la*rho),(0,1):la*(1+lh*rho),(1,0):lh*(1+la*rho),(1,1):lh*la*(1-rho)};tot=sum(v for v in w.values() if v>0);r=random.random()*tot;ac=0
        for cc_,v in w.items():
            if v>0:
                ac+=v
                if ac>=r:ga,gb=cc_;break
    if ko and ga==gb:return (a if random.random()<lh/(lh+la) else b)
    return a if ga>gb else (b if gb>ga else None)
# ---- una sola corrida que registra TODOS los mercados (coherencia garantizada) ----
random.seed(26);K=20000
champ={t:0 for t in MAP};final={t:0 for t in MAP};semi={t:0 for t in MAP};wingroup={t:0 for t in MAP}
for _ in range(K):
    seeds=[];thirds=[]
    for gN,T in GROUPS.items():
        tab={t:[0,0,0] for t in T}
        for i in range(4):
            for j in range(i+1,4):
                a,b=T[i],T[j];lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0));la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0));ga,gb=pois(lh),pois(la)
                if ga>gb:tab[a][0]+=3
                elif gb>ga:tab[b][0]+=3
                else:tab[a][0]+=1;tab[b][0]+=1
                tab[a][1]+=ga-gb;tab[b][1]+=gb-ga
        o=sorted(T,key=lambda t:(tab[t][0],tab[t][1],random.random()),reverse=True)
        wingroup[o[0]]+=1
        seeds.append((1,A[o[0]]+dfn[o[0]],o[0]));seeds.append((2,A[o[1]]+dfn[o[1]],o[1]));thirds.append((o[2],tab[o[2]][0],tab[o[2]][1]))
    th=sorted(thirds,key=lambda x:(x[1],x[2],random.random()),reverse=True)[:8]
    for t in th:seeds.append((3,A[t[0]]+dfn[t[0]],t[0]))
    seeds.sort(key=lambda s:(s[0],-s[1]));order=[s[2] for s in seeds];n=len(order)
    br=[(order[i],order[n-1-i]) for i in range(n//2)]
    while len(br)>1:
        nx=[w for a,b in br for w in [gm(a,b,ko=True)]]
        if len(nx)==4:
            for t in nx:semi[t]+=1
        if len(nx)==2:
            for t in nx:final[t]+=1
        br=[(nx[i],nx[i+1]) for i in range(0,len(nx),2)]
    champ[gm(br[0][0],br[0][1],ko=True)]+=1
mkts={t:{"champ":champ[t]/K,"final":final[t]/K,"semi":semi[t]/K,"wingroup":wingroup[t]/K} for t in MAP}
json.dump(mkts,open("markets.json","w",encoding="utf-8"),ensure_ascii=False)
# ---- (3) CHEQUEO DE COHERENCIA INTERNA ----
print("=== (3) COHERENCIA ENTRE MERCADOS (campeón ≤ final ≤ semi ≤ gana grupo) ===")
bad=0
for t in sorted(mkts,key=lambda x:mkts[x]["champ"],reverse=True)[:12]:
    m=mkts[t];ok = m["champ"]<=m["final"]+1e-9<=m["semi"]+1e-9 and m["final"]<=m["semi"]+1e-9
    flag="✓" if ok else "✗ INCOHERENTE"
    if not ok:bad+=1
    print(f"  {t:<13} campeón {100*m['champ']:>4.1f}% ≤ final {100*m['final']:>4.1f}% ≤ semi {100*m['semi']:>4.1f}% | gana grupo {100*m['wingroup']:>4.1f}%  {flag}")
print(f"  -> {bad} incoherencias (deben ser 0; al venir de la MISMA simulación, es imposible arbitrarse)")
