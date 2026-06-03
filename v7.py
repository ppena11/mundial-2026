import csv,math,random,json,numpy as np
import fit_dc,engine
engine.setconf(["Rep. Checa","Serbia y Montenegro"],"UEFA");engine.setconf(["Cabo Verde"],"CAF")
MAP=json.load(open("namemap.json",encoding="utf-8"))
from datetime import date
# ---- BASE VALIDADA: solo recencia (sin importancia, sin encogimiento) ----
def build(end="2026-06-01",start="2019-01-01"):
    refd=date.fromisoformat(end);xi=math.log(2)/730
    rows=[r for r in csv.DictReader(open("results.csv",encoding="utf-8")) if r["home_score"] not in("NA","") and start<=r["date"]<end]
    cnt={}
    for r in rows:cnt[r["home_team"]]=cnt.get(r["home_team"],0)+1;cnt[r["away_team"]]=cnt.get(r["away_team"],0)+1
    teams=sorted([t for t,c in cnt.items() if c>=6]);idx={t:i for i,t in enumerate(teams)};OTH=len(teams);n=len(teams)+1
    H=[];A=[];GH=[];GA=[];W=[];NEU=[]
    for r in rows:
        dt=(refd-date.fromisoformat(r["date"])).days
        H.append(idx.get(r["home_team"],OTH));A.append(idx.get(r["away_team"],OTH));GH.append(int(r["home_score"]));GA.append(int(r["away_score"]))
        W.append(math.exp(-xi*dt));NEU.append(0.0 if r["neutral"]=="TRUE" else 1.0)
    return (np.array(H),np.array(A),np.array(GH,float),np.array(GA,float),np.array(W),np.array(NEU),teams,n,OTH)
def rat(M):
    ti={t:i for i,t in enumerate(M['teams'])}
    return ({es:M['atk'][ti[dn]] for es,dn in MAP.items()},{es:M['dfn'][ti[dn]] for es,dn in MAP.items()},M['c'],M['g'],M['rho'])
hosts={"Mexico","Estados Unidos","Canada"}
GROUPS={"A":["Mexico","Sudafrica","Corea del Sur","Chequia"],"B":["Canada","Bosnia","Catar","Suiza"],"C":["Brasil","Marruecos","Haiti","Escocia"],"D":["Estados Unidos","Paraguay","Australia","Turquia"],"E":["Alemania","Curazao","Costa de Marfil","Ecuador"],"F":["Paises Bajos","Japon","Suecia","Tunez"],"G":["Belgica","Egipto","Iran","Nueva Zelanda"],"H":["Espana","Cabo Verde","Arabia Saudi","Uruguay"],"I":["Francia","Senegal","Irak","Noruega"],"J":["Argentina","Argelia","Austria","Jordania"],"K":["Portugal","R.D. Congo","Uzbekistan","Colombia"],"L":["Inglaterra","Croacia","Ghana","Panama"]}
NEWS={"Argentina":-0.015,"Espana":-0.018,"Francia":-0.004}
def pois(l):
    L=math.exp(-l);k=0;p=1.0
    while True:
        k+=1;p*=random.random()
        if p<=L:return k-1
def mk(atk,dfn,c,g,rho):
    A={t:atk[t]+NEWS.get(t,0) for t in atk}
    def goals(a,b,ko=False):
        lh=math.exp(c+A[a]-dfn[b]+(g if a in hosts else 0));la=math.exp(c+A[b]-dfn[a]+(g if b in hosts else 0))
        if ko:lh*=1.0;la*=1.0  # factor KO calibrado: sin evidencia de menos goles en eliminatorias (Mundiales reales ratio 1.02)
        ga,gb=pois(lh),pois(la)
        if ga<=1 and gb<=1:
            w={(0,0):(1-lh*la*rho),(0,1):la*(1+lh*rho),(1,0):lh*(1+la*rho),(1,1):lh*la*(1-rho)};tot=sum(v for v in w.values() if v>0);r=random.random()*tot;ac=0
            for cc_,v in w.items():
                if v>0:
                    ac+=v
                    if ac>=r:ga,gb=cc_;break
        if ko and ga==gb:
            if random.random()<lh/(lh+la):ga+=1
            else:gb+=1
        return ga,gb
    def sim(track):
        seeds=[];thirds=[]
        for gN,T in GROUPS.items():
            tab={t:[0,0,0] for t in T}
            for i in range(4):
                for j in range(i+1,4):
                    a,b=T[i],T[j];ga,gb=goals(a,b)
                    tab[a][1]+=ga;tab[a][2]+=gb;tab[b][1]+=gb;tab[b][2]+=ga
                    if ga>gb:tab[a][0]+=3
                    elif gb>ga:tab[b][0]+=3
                    else:tab[a][0]+=1;tab[b][0]+=1
            o=sorted(T,key=lambda t:(tab[t][0],tab[t][1]-tab[t][2],tab[t][1],random.random()),reverse=True)
            track['win'][o[0]]+=1;track['adv'][o[0]]+=1;track['adv'][o[1]]+=1
            seeds.append((1,A[o[0]]+dfn[o[0]],o[0]));seeds.append((2,A[o[1]]+dfn[o[1]],o[1]))
            thirds.append((o[2],tab[o[2]][0],tab[o[2]][1]-tab[o[2]][2],tab[o[2]][1]))
        th=sorted(thirds,key=lambda x:(x[1],x[2],x[3],random.random()),reverse=True)[:8]
        for t in th:track['adv'][t[0]]+=1;seeds.append((3,A[t[0]]+dfn[t[0]],t[0]))
        seeds.sort(key=lambda s:(s[0],-s[1]));order=[s[2] for s in seeds];n=len(order)
        br=[(order[i],order[n-1-i]) for i in range(n//2)]
        while len(br)>1:
            nx=[]
            for a,b in br:ga,gb=goals(a,b,ko=True);nx.append(a if ga>gb else b)
            br=[(nx[i],nx[i+1]) for i in range(0,len(nx),2)]
        a,b=br[0];ga,gb=goals(a,b,ko=True);track['champ'][a if ga>gb else b]+=1
    return sim
def newtrack():return {'champ':{t:0 for t in MAP},'adv':{t:0 for t in MAP},'win':{t:0 for t in MAP}}

# ---- central (punto, 20k) ----
M=fit_dc.fit(build(),separate=True);atk,dfn,c,g,rho=rat(M);sim=mk(atk,dfn,c,g,rho)
random.seed(1);K=20000;T0=newtrack()
for _ in range(K):sim(T0)
champ={t:T0['champ'][t]/K for t in MAP};adv={t:T0['adv'][t]/K for t in MAP};win={t:T0['win'][t]/K for t in MAP}
# ---- bootstrap (incertidumbre) ----
H,Aa,GH,GA,W,NEU,teams,n,OTH=build();B=20;KB=3000
bs={'champ':{t:[] for t in MAP},'adv':{t:[] for t in MAP}}
for b in range(B):
    idx=np.random.randint(0,len(H),len(H))
    Mb=fit_dc.fit((H[idx],Aa[idx],GH[idx],GA[idx],W[idx],NEU[idx],teams,n,OTH),separate=True)
    ab,db,cb,gb_,rb=rat(Mb);simb=mk(ab,db,cb,gb_,rb);Tb=newtrack()
    for _ in range(KB):simb(Tb)
    for t in MAP:bs['champ'][t].append(Tb['champ'][t]/KB);bs['adv'][t].append(Tb['adv'][t]/KB)
def ci(v):s=sorted(v);return s[int(.05*len(s))],s[min(len(s)-1,int(.95*len(s)))]
json.dump({'champ':champ,'adv':adv,'win':win,'bs_champ':bs['champ'],'bs_adv':bs['adv']},open("v7.json","w",encoding="utf-8"))
# ---- capa de consenso (mercado) ----
mkt={"Espana":15.1,"Argentina":8.3,"Francia":14.4,"Inglaterra":11.1,"Brasil":9.8,"Portugal":7.9,"Alemania":5.9,"Paises Bajos":4.6,"Belgica":3.2,"Uruguay":1.4,"Croacia":1.2,"Colombia":1.6,"Marruecos":1.1,"Mexico":2.0,"Estados Unidos":2.2,"Japon":0.8,"Senegal":1.0,"Suiza":1.3,"Ecuador":0.6,"Noruega":1.5}
def ens(t):return 0.5*champ.get(t,0)*100+0.5*mkt[t] if t in mkt else champ.get(t,0)*100
print("== CAMPEÓN: modelo validado (IC 90%) vs consenso (modelo+mercado) ==")
print(f"{'Selección':<14}{'Modelo':>7}{'IC 90%':>15}{'Consenso':>10}")
for t in sorted(champ,key=lambda x:champ[x],reverse=True)[:10]:
    lo,hi=ci(bs['champ'][t])
    print(f"{t:<14}{100*champ[t]:>6.1f}% [{100*lo:>4.1f}-{100*hi:>4.1f}]{ens(t):>8.1f}%")
print("\n== CLASIFICAR DE GRUPO con IC 90% (corrige la sobreconfianza) ==")
for gN,Tg in GROUPS.items():
    print(f"Grupo {gN}: "+" | ".join(f"{t[:11]} {100*adv[t]:.0f}% [{100*ci(bs['adv'][t])[0]:.0f}-{100*ci(bs['adv'][t])[1]:.0f}]" for t in sorted(Tg,key=lambda x:adv[x],reverse=True)))
