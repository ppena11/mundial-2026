import csv,math,random,json,numpy as np
import fit_dc,engine
engine.setconf(["Rep. Checa","Serbia y Montenegro"],"UEFA");engine.setconf(["Cabo Verde"],"CAF")
MAP=json.load(open("namemap.json",encoding="utf-8"));inv={v:k for k,v in MAP.items()}
def importance(t):
    if t=="Friendly":return 1.0
    if "qualification" in t:return 2.0
    if "Nations League" in t:return 2.5
    if t=="FIFA World Cup":return 4.0
    if any(m in t for m in ["UEFA Euro","Copa Am","African Cup of Nations","AFC Asian Cup","Gold Cup","Confederations","Finalissima"]):return 3.5
    return 1.2
from datetime import date
rows=[]
for r in csv.DictReader(open("results.csv",encoding="utf-8")):
    if r["home_score"] in("NA",""):continue
    if not("2019-01-01"<=r["date"]<="2026-06-01"):continue
    rows.append((r["date"],r["home_team"],r["away_team"],int(r["home_score"]),int(r["away_score"]),r["neutral"]=="TRUE",importance(r["tournament"])))
cnt={}
for _,h,a,_,_,_,_ in rows:cnt[h]=cnt.get(h,0)+1;cnt[a]=cnt.get(a,0)+1
teams=sorted([t for t,c in cnt.items() if c>=6]);idx={t:i for i,t in enumerate(teams)};OTH=len(teams);n=len(teams)+1
ref=date.fromisoformat("2026-06-01");xi=math.log(2)/730
H=[];A=[];GH=[];GA=[];W=[];NEU=[]
for d,h,a,gh,ga,neu,imp in rows:
    dt=(ref-date.fromisoformat(d)).days
    H.append(idx.get(h,OTH));A.append(idx.get(a,OTH));GH.append(gh);GA.append(ga);W.append(math.exp(-xi*dt)*imp);NEU.append(0.0 if neu else 1.0)
M=fit_dc.fit((np.array(H),np.array(A),np.array(GH,float),np.array(GA,float),np.array(W),np.array(NEU),teams,n,OTH),separate=True)
ti={t:i for i,t in enumerate(M['teams'])}
atk={es:M['atk'][ti[dn]] for es,dn in MAP.items()};dfn={es:M['dfn'][ti[dn]] for es,dn in MAP.items()};c=M['c'];g=M['g'];rho=M['rho']
VAL={"Inglaterra":1320,"Francia":1300,"Espana":1170,"Brasil":950,"Portugal":900,"Alemania":900,"Paises Bajos":750,"Argentina":600,"Belgica":550,"Noruega":470,"Turquia":513,"Japon":400,"Austria":400,"Croacia":350,"Uruguay":380,"Colombia":380,"Marruecos":380,"Suecia":380,"Suiza":350,"Senegal":350,"Estados Unidos":350,"Ecuador":320,"Costa de Marfil":320,"Mexico":300,"Argelia":300,"Chequia":300,"Ghana":255,"Canada":250,"Escocia":250,"Egipto":250,"Corea del Sur":220,"Bosnia":200,"R.D. Congo":200,"Iran":120,"Australia":120,"Paraguay":120,"Tunez":120,"Sudafrica":80,"Arabia Saudi":80,"Uzbekistan":70,"Cabo Verde":70,"Catar":60,"Panama":60,"Haiti":50,"Irak":50,"Jordania":40,"Nueva Zelanda":40,"Curazao":40}
elite={"Spain","France","England","Brazil","Argentina","Portugal","Germany","Netherlands","Belgium","Italy","Croatia","Uruguay","Colombia"}
xconf={es:0 for es in MAP}
for d,h,a,gh,ga,neu,imp in rows:
    for tm,op in ((h,a),(a,h)):
        es=inv.get(tm)
        if es and op in elite and op!=tm:xconf[es]+=1
strength={es:atk[es]+dfn[es] for es in MAP};wc=[es for es in MAP if xconf[es]>=15]
X=np.array([math.log(VAL[es]) for es in wc]);Y=np.array([strength[es] for es in wc])
b1=np.cov(X,Y,bias=True)[0,1]/np.var(X);b0=Y.mean()-b1*X.mean();vs={es:b0+b1*math.log(VAL[es]) for es in MAP}
atk2={};dfn2={}
for es in MAP:
    w=12.0/(12.0+xconf[es]);delta=w*(vs[es]-strength[es]);atk2[es]=atk[es]+delta/2;dfn2[es]=dfn[es]+delta/2
atk2["Mexico"]+=0.04;dfn2["Mexico"]+=0.04
for t,v in {"Argentina":-0.015,"Espana":-0.018,"Francia":-0.004}.items():atk2[t]+=v
hosts={"Mexico","Estados Unidos","Canada"}
GROUPS={"A":["Mexico","Sudafrica","Corea del Sur","Chequia"],"B":["Canada","Bosnia","Catar","Suiza"],"C":["Brasil","Marruecos","Haiti","Escocia"],"D":["Estados Unidos","Paraguay","Australia","Turquia"],"E":["Alemania","Curazao","Costa de Marfil","Ecuador"],"F":["Paises Bajos","Japon","Suecia","Tunez"],"G":["Belgica","Egipto","Iran","Nueva Zelanda"],"H":["Espana","Cabo Verde","Arabia Saudi","Uruguay"],"I":["Francia","Senegal","Irak","Noruega"],"J":["Argentina","Argelia","Austria","Jordania"],"K":["Portugal","R.D. Congo","Uzbekistan","Colombia"],"L":["Inglaterra","Croacia","Ghana","Panama"]}
def pois(l):
    L=math.exp(-l);k=0;p=1.0
    while True:
        k+=1;p*=random.random()
        if p<=L:return k-1
def goals(a,b):
    lh=math.exp(c+atk2[a]-dfn2[b]+(g if a in hosts else 0));la=math.exp(c+atk2[b]-dfn2[a]+(g if b in hosts else 0))
    ga,gb=pois(lh),pois(la)
    if ga<=1 and gb<=1:
        w={(0,0):(1-lh*la*rho),(0,1):la*(1+lh*rho),(1,0):lh*(1+la*rho),(1,1):lh*la*(1-rho)};tot=sum(v for v in w.values() if v>0);r=random.random()*tot;ac=0
        for cc_,v in w.items():
            if v>0:
                ac+=v
                if ac>=r:ga,gb=cc_;break
    return ga,gb
# proyección de tabla (20k) por grupo
random.seed(7);K=20000
win={t:0 for t in MAP};adv={t:0 for t in MAP};pts={t:0.0 for t in MAP}
for _ in range(K):
    thirds=[]
    for gN,T in GROUPS.items():
        tab={t:[0,0,0] for t in T}
        for i in range(4):
            for j in range(i+1,4):
                a,b=T[i],T[j];ga,gb=goals(a,b)
                tab[a][1]+=ga;tab[a][2]+=gb;tab[b][1]+=gb;tab[b][2]+=ga
                if ga>gb:tab[a][0]+=3
                elif gb>ga:tab[b][0]+=3
                else:tab[a][0]+=1;tab[b][0]+=1
        for t in T:pts[t]+=tab[t][0]
        o=sorted(T,key=lambda t:(tab[t][0],tab[t][1]-tab[t][2],tab[t][1],random.random()),reverse=True)
        win[o[0]]+=1;adv[o[0]]+=1;adv[o[1]]+=1;thirds.append((o[2],tab[o[2]][0],tab[o[2]][1]-tab[o[2]][2],tab[o[2]][1]))
    th=sorted(thirds,key=lambda x:(x[1],x[2],x[3],random.random()),reverse=True)[:8]
    for t in th:adv[t[0]]+=1
# predicción de partido
def mp(a,b,n=40000):
    w=d=l=0;tg=0;sc={}
    for _ in range(n):
        ga,gb=goals(a,b);tg+=ga+gb
        if ga>gb:w+=1
        elif gb>ga:l+=1
        else:d+=1
        sc[(ga,gb)]=sc.get((ga,gb),0)+1
    top=max(sc,key=sc.get);return w/n,d/n,l/n,tg/n,top
PAT=[(0,1),(2,3),(0,2),(3,1),(3,0),(1,2)];MD=["J1","J1","J2","J2","J3","J3"]
for gN,T in GROUPS.items():
    print(f"\n===== GRUPO {gN} =====")
    for t in sorted(T,key=lambda x:adv[x],reverse=True):
        print(f"  {t:<15} pts~{pts[t]/K:.1f}  gana {100*win[t]/K:>3.0f}%  clasifica {100*adv[t]/K:>3.0f}%")
    for k,(i,j) in enumerate(PAT):
        a,b=T[i],T[j];pw,pd,pl,tg,sc=mp(a,b)
        print(f"   [{MD[k]}] {a[:12]} {pw*100:.0f}-{pd*100:.0f}-{pl*100:.0f} {b[:12]}  | {sc[0]}-{sc[1]} (tot {tg:.1f})")
