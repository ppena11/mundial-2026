import random, math
from collections import defaultdict

# ============================================================
# CONFEDERACIONES
# ============================================================
CONF = {}
def setconf(names, c):
    for n in names: CONF[n]=c
setconf(["Argentina","Brasil","Uruguay","Colombia","Paraguay","Chile","Ecuador","Peru","Bolivia"],"CONMEBOL")
setconf(["Alemania","Alemania FR","Francia","Espana","Inglaterra","Italia","Paises Bajos","Belgica","Portugal",
 "Croacia","Suiza","Suecia","Dinamarca","Polonia","Serbia","Serbia y Montenegro","Yugoslavia","Rep. Checa","Chequia",
 "Checoslovaquia","Rumania","Bulgaria","Rusia","URSS","Austria","Escocia","Irlanda","Irlanda N.","Gales","Noruega",
 "Ucrania","Eslovaquia","Eslovenia","Grecia","Hungria","Turquia","Islandia","Bosnia"],"UEFA")
setconf(["Mexico","Estados Unidos","Canada","Costa Rica","Honduras","Panama","Jamaica","Trinidad","Haiti","Curazao","Cabo Verde"],"CONCACAF")
setconf(["Marruecos","Camerun","Nigeria","Senegal","Ghana","Costa de Marfil","Argelia","Tunez","Egipto","Sudafrica",
 "Angola","Togo","R.D. Congo","Zaire"],"CAF")
setconf(["Japon","Corea del Sur","Corea del Norte","Arabia Saudi","Iran","Australia","Catar","China","Irak","Uzbekistan",
 "Jordania","EAU","Kuwait"],"AFC")
setconf(["Nueva Zelanda","Nueva Caledonia"],"OFC")

def conf(t): return CONF.get(t,"UEFA")

# ============================================================
# MOTOR DE SIMULACIÓN (genérico, parámetros ajustables)
# ============================================================
def poisson(lam):
    L=math.exp(-lam); k=0; p=1.0
    while True:
        k+=1; p*=random.random()
        if p<=L: return k-1

def eff_strength(elo, hosts, P):
    s={}
    sig=P["form_sigma"]
    for t,r in elo.items():
        v=r+random.gauss(0,sig)
        c=conf(t)
        if c=="UEFA": v+=P["conf_uefa"]
        elif c=="CONMEBOL": v+=P["conf_conmebol"]
        if t in hosts: v+=P["home_adv"]
        s[t]=v
    return s

def goals(a,b,s,P,knockout=False,group=False):
    d=(s[a]-s[b])/P["goal_scale"]
    base=P["base_goals"]*(P["ko_compress"] if knockout else 1.0)
    la=max(0.12,base*(10**( d/2)))
    lb=max(0.12,base*(10**(-d/2)))
    ga,gb=poisson(la),poisson(lb)
    if group and abs(ga-gb)==1 and random.random()<P["draw_inflate"]:
        if ga>gb: ga-=1
        else: gb-=1
    if knockout and ga==gb:
        we=1/(1+10**(-(s[a]-s[b])/400))
        if random.random()<we: ga+=1
        else: gb+=1
    return ga,gb

def pot_draw(teams, elo, n_groups):
    order=sorted(teams,key=lambda t:elo[t],reverse=True)
    pots=[order[i*n_groups:(i+1)*n_groups] for i in range(4)]
    grp=[[] for _ in range(n_groups)]
    for pot in pots:
        pp=pot[:]; random.shuffle(pp)
        for i in range(n_groups): grp[i].append(pp[i])
    return grp

def simulate(elo, hosts, n_groups, P):
    s=eff_strength(elo,hosts,P)
    grp=pot_draw(list(elo.keys()),elo,n_groups)
    qualifiers=[]; thirds=[]
    for teams in grp:
        tab={t:[0,0,0] for t in teams}  # pts, gf, gc
        for i in range(len(teams)):
            for j in range(i+1,len(teams)):
                a,b=teams[i],teams[j]
                ga,gb=goals(a,b,s,P,group=True)
                tab[a][1]+=ga; tab[a][2]+=gb; tab[b][1]+=gb; tab[b][2]+=ga
                if ga>gb: tab[a][0]+=3
                elif gb>ga: tab[b][0]+=3
                else: tab[a][0]+=1; tab[b][0]+=1
        o=sorted(teams,key=lambda t:(tab[t][0],tab[t][1]-tab[t][2],tab[t][1],random.random()),reverse=True)
        qualifiers+=[o[0],o[1]]
        thirds.append((o[2],tab[o[2]][0],tab[o[2]][1]-tab[o[2]][2],tab[o[2]][1]))
    if n_groups in (6,12):  # +mejores terceros (4 en 1986-94 ; 8 en 2026)
        th=sorted(thirds,key=lambda x:(x[1],x[2],x[3],random.random()),reverse=True)
        qualifiers+=[t[0] for t in th[:(4 if n_groups==6 else 8)]]
    # bracket 16 sembrado por fuerza
    q=sorted(set(qualifiers),key=lambda t:s[t],reverse=True)
    n=len(q)
    br=[(q[i],q[n-1-i]) for i in range(n//2)]
    semis=set(); finalists=set()
    while len(br)>1:
        nx=[]
        for a,b in br:
            ga,gb=goals(a,b,s,P,knockout=True)
            nx.append(a if ga>gb else b)
        if len(nx)==4: semis=set(nx)
        if len(nx)==2: finalists=set(nx)
        br=[(nx[i],nx[i+1]) for i in range(0,len(nx),2)]
    a,b=br[0]
    ga,gb=goals(a,b,s,P,knockout=True)
    champ=a if ga>gb else b
    if not finalists: finalists={a,b}
    return champ, finalists, semis

DEFAULT=dict(home_adv=70,goal_scale=420,base_goals=1.2,conf_uefa=0,conf_conmebol=0,
             form_sigma=55,ko_compress=0.9,draw_inflate=0.12)
