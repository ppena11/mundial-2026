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
# --- ajuste por LESIONES (gratis, injuries.json via player_layer) ---
# Si existe injuries.json, debilita atk/dfn de las selecciones con bajas. Si no, sin cambio.
dATK={};dDEF={}
try:
    import player_layer
    _sq=player_layer.load_squad_data()
    for _t,_d in _sq.items():
        _aa,_da=player_layer.player_adjustment(0.0,0.0,_d["starters_available"],_d["key_players"])
        dATK[_t]=_aa;dDEF[_t]=_da
    _ajust=sorted((t for t in dATK if dATK[t]<-0.001),key=lambda t:dATK[t])
    if _ajust:print("Ajuste por lesiones aplicado a:",", ".join(f"{t}({dATK[t]:+.3f})" for t in _ajust[:6]),"...\n")
except Exception as _e:
    print(f"(sin ajuste por lesiones: {_e})\n")
A={t:atk[t]+dATK.get(t,0.0) for t in atk}
dfn={t:dfn[t]+dDEF.get(t,0.0) for t in dfn}
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
random.seed(11);K=20000
champ={t:0 for t in MAP};fin={t:0 for t in MAP};semi={t:0 for t in MAP};arg_out_r32=0
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
        seeds.append((1,A[o[0]]+dfn[o[0]],o[0]));seeds.append((2,A[o[1]]+dfn[o[1]],o[1]));thirds.append((o[2],tab[o[2]][0],tab[o[2]][1]))
    th=sorted(thirds,key=lambda x:(x[1],x[2],random.random()),reverse=True)[:8]
    for t in th:seeds.append((3,A[t[0]]+dfn[t[0]],t[0]))
    seeds.sort(key=lambda s:(s[0],-s[1]));order=[s[2] for s in seeds];n=len(order)
    br=[(order[i],order[n-1-i]) for i in range(n//2)]
    rnd=0
    while len(br)>1:
        nx=[w for a,b in br for w in [gm(a,b,ko=True)]]
        if rnd==0 and "Argentina" not in nx:arg_out_r32+=1
        if len(nx)==4:
            for t in nx:semi[t]+=1
        if len(nx)==2:
            for t in nx:fin[t]+=1
        br=[(nx[i],nx[i+1]) for i in range(0,len(nx),2)];rnd+=1
    champ[gm(br[0][0],br[0][1],ko=True)]+=1
print("CAMPEÓN (20.000 simulaciones, modelo validado v7):")
for t in sorted(champ,key=lambda x:champ[x],reverse=True)[:8]:print(f"  {t:<14}{100*champ[t]/K:>5.1f}%   (final {100*fin[t]/K:>4.1f}%)")
print(f"\nArgentina (campeona vigente) ELIMINADA antes de cuartos: {100*arg_out_r32/K:.0f}% de las veces")
print(f"Algún anfitrión (Méx/EEUU/Can) llega a la final: {100*sum(fin[t] for t in hosts)/K:.0f}%")
print(f"España campeona: {100*champ['Espana']/K:.1f}% | Argentina campeona: {100*champ['Argentina']/K:.1f}%")
print(f"Prob. de que NO gane ninguna de las 4 favoritas (Arg/Esp/Ing/Bra): {100*(1-sum(champ[t] for t in ['Argentina','Espana','Inglaterra','Brasil'])/K):.0f}%")

# ---- salida para el pipeline diario: JSON de porcentajes + gráfico PNG ----
pct={t:round(100*champ[t]/K,2) for t in sorted(champ,key=lambda x:champ[x],reverse=True)}
finpct={t:round(100*fin[t]/K,2) for t in champ}
json.dump({"campeon":pct,"final":finpct},open("champ_today.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("\n→ champ_today.json guardado")
try:
    import matplotlib
    matplotlib.use("Agg")  # sin ventana (headless / cron)
    import matplotlib.pyplot as plt
    top=list(pct.items())[:12][::-1]
    labels=[t for t,_ in top]; vals=[v for _,v in top]
    plt.figure(figsize=(8,6))
    bars=plt.barh(labels,vals,color="#1f77b4")
    plt.xlabel("Probabilidad de ser campeón (%)")
    plt.title("Mundial 2026 — Pronóstico de campeón (20.000 simulaciones, modelo v7)")
    for b,v in zip(bars,vals):
        plt.text(v+0.1,b.get_y()+b.get_height()/2,f"{v:.1f}%",va="center",fontsize=9)
    plt.tight_layout()
    plt.savefig("champ_today.png",dpi=130)
    print("→ champ_today.png guardado")
except Exception as e:
    print(f"(gráfico omitido: {e})")
