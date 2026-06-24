import csv, math, numpy as np
from scipy.optimize import minimize
from datetime import date

# Peso por importancia de competición: los amistosos son ruido; eliminatorias/Mundial pesan más.
def importance(t):
    """Factor de peso por tipo de torneo (eliminatorias/Mundial > amistosos)."""
    t = t or ""
    if t == "Friendly": return 1.0
    if t == "FIFA World Cup": return 4.0
    if any(m in t for m in ("UEFA Euro", "Copa Am", "African Cup of Nations",
                            "AFC Asian Cup", "Gold Cup", "Confederations", "Finalissima")) \
       and "qualification" not in t: return 3.5
    if "Nations League" in t: return 2.5
    if "qualification" in t: return 2.0
    return 1.2

def load(window_start="2019-01-01", end="2026-06-01", with_tournament=False):
    """Carga partidos de results.csv. with_tournament=True añade el torneo como 7º campo."""
    rows=[]
    for r in csv.DictReader(open("results.csv",encoding="utf-8")):
        if r["home_score"] in ("NA","") : continue
        if not (window_start<=r["date"]<=end): continue
        row=(r["date"],r["home_team"],r["away_team"],int(r["home_score"]),int(r["away_score"]),r["neutral"]=="TRUE")
        if with_tournament: row=row+(r["tournament"],)
        rows.append(row)
    return rows

def build(rows, ref_date, min_matches=6, halflife=730, importance_fn=None):
    """Construye la matriz de diseño. Si importance_fn se da y las filas traen torneo (7º campo),
    el peso de cada partido se multiplica por importance_fn(torneo) (competitivos > amistosos)."""
    cnt={}
    for row in rows:
        h, a = row[1], row[2]
        cnt[h]=cnt.get(h,0)+1; cnt[a]=cnt.get(a,0)+1
    teams=sorted([t for t,c in cnt.items() if c>=min_matches])
    idx={t:i for i,t in enumerate(teams)}; OTH=len(teams); n=len(teams)+1
    def gi(t): return idx.get(t,OTH)
    ref=date.fromisoformat(ref_date); xi=math.log(2)/halflife
    H=[];A=[];GH=[];GA=[];W=[];NEU=[]
    for row in rows:
        d,h,a,gh,ga,neu = row[:6]
        tour = row[6] if len(row) > 6 else None
        dt=(ref-date.fromisoformat(d)).days
        w=math.exp(-xi*dt)
        if importance_fn is not None and tour is not None:
            w*=importance_fn(tour)
        H.append(gi(h));A.append(gi(a));GH.append(gh);GA.append(ga);W.append(w);NEU.append(0.0 if neu else 1.0)
    return (np.array(H),np.array(A),np.array(GH,float),np.array(GA,float),
            np.array(W),np.array(NEU),teams,n,OTH)

def fit(data, separate=True, ridge=0.02):
    H,A,GH,GA,W,NEU,teams,n,OTH=data
    # params: [atk(n), def(n), gamma, c]  (single: atk==def -> usar atk como s, def ligado)
    def unpack(p):
        atk=p[:n]; 
        if separate: dfn=p[n:2*n]; g=p[2*n]; c=p[2*n+1]
        else: dfn=atk; g=p[n]; c=p[n+1]
        return atk,dfn,g,c
    def negll(p):
        atk,dfn,g,c=unpack(p)
        lh=np.exp(c+atk[H]-dfn[A]+g*NEU); la=np.exp(c+atk[A]-dfn[H])
        ll=np.sum(W*(GH*np.log(lh)-lh)) + np.sum(W*(GA*np.log(la)-la))
        ll-=ridge*(np.sum(atk**2)+(np.sum(dfn**2) if separate else 0))
        return -ll
    def grad(p):
        atk,dfn,g,c=unpack(p)
        lh=np.exp(c+atk[H]-dfn[A]+g*NEU); la=np.exp(c+atk[A]-dfn[H])
        rh=W*(GH-lh); ra=W*(GA-la)              # residuos ponderados
        gatk=np.zeros(n); gdef=np.zeros(n)
        np.add.at(gatk,H,rh); np.add.at(gatk,A,ra)        # atk aparece +1 cuando el equipo anota
        np.add.at(gdef,A,-rh); np.add.at(gdef,H,-ra)      # def aparece -1 cuando concede
        gg=np.sum(rh*NEU); gc=np.sum(rh)+np.sum(ra)
        if separate:
            gatk-=2*ridge*atk; gdef-=2*ridge*dfn
            return -np.concatenate([gatk,gdef,[gg,gc]])
        else:
            gs=gatk+gdef-2*ridge*atk
            return -np.concatenate([gs,[gg,gc]])
    p0=np.zeros((2*n+2) if separate else (n+2)); p0[-1]=0.0
    res=minimize(negll,p0,jac=grad,method="L-BFGS-B")
    atk,dfn,g,c=unpack(res.x)
    # estimar rho (Dixon-Coles) por 1-D sobre marcadores bajos
    lh=np.exp(c+atk[H]-dfn[A]+g*NEU); la=np.exp(c+atk[A]-dfn[H])
    def rll(rho):
        s=0.0
        for k in range(len(H)):
            x,y=GH[k],GA[k]
            if x<=1 and y<=1:
                if x==0 and y==0: t=1-lh[k]*la[k]*rho
                elif x==0 and y==1: t=1+lh[k]*rho
                elif x==1 and y==0: t=1+la[k]*rho
                else: t=1-rho
                if t>0: s+=W[k]*math.log(t)
                else: s-=1e6
        return s
    best=-0.2;bs=-1e18
    for rho in np.linspace(-0.2,0.15,36):
        v=rll(rho)
        if v>bs: bs=v;best=rho
    return dict(atk=atk,dfn=dfn,g=g,c=c,rho=best,teams=teams,OTH=OTH)

def dc_probs(M,h,a,neutral):
    ti={t:i for i,t in enumerate(M['teams'])}
    hi=ti.get(h,M['OTH']); ai=ti.get(a,M['OTH'])
    lh=math.exp(M['c']+M['atk'][hi]-M['dfn'][ai]+M['g']*(0 if neutral else 1))
    la=math.exp(M['c']+M['atk'][ai]-M['dfn'][hi])
    K=11; ph=[math.exp(-lh)*lh**k/math.factorial(k) for k in range(K)]
    pa=[math.exp(-la)*la**k/math.factorial(k) for k in range(K)]
    pw=pd=pl=0.0; rho=M['rho']
    for x in range(K):
        for y in range(K):
            p=ph[x]*pa[y]
            if x<=1 and y<=1:
                if x==0 and y==0: p*= (1-lh*la*rho)
                elif x==0 and y==1: p*=(1+lh*rho)
                elif x==1 and y==0: p*=(1+la*rho)
                else: p*=(1-rho)
            if p<0:p=0
            if x>y: pw+=p
            elif x==y: pd+=p
            else: pl+=p
    s=pw+pd+pl; return pw/s,pd/s,pl/s

def rps(probs,outcome):  # outcome 0=home,1=draw,2=away ; ordered
    c=[0,0,0]; c[outcome]=1
    cp=[probs[0],probs[0]+probs[1]]; co=[c[0],c[0]+c[1]]
    return 0.5*((cp[0]-co[0])**2+(cp[1]-co[1])**2)

if __name__=="__main__":
    rows=load("2019-01-01","2026-06-01")
    cut="2025-06-01"
    train=[r for r in rows if r[0]<cut]; test=[r for r in rows if r[0]>=cut]
    print(f"Entrenamiento: {len(train)} partidos | Prueba (último año, fuera de muestra): {len(test)}")
    dB=build(train,cut); MB=fit(dB,separate=True)
    dA=build(train,cut); MA=fit(dA,separate=False)
    rB=[];rA=[]
    for d,h,a,gh,ga,neu in test:
        o=0 if gh>ga else (1 if gh==ga else 2)
        rB.append(rps(dc_probs(MB,h,a,neu),o)); rA.append(rps(dc_probs(MA,h,a,neu),o))
    print(f"\nRPS fuera de muestra (menor = mejor):")
    print(f"   Rating ÚNICO  (como v3): {np.mean(rA):.4f}")
    print(f"   ATAQUE/DEFENSA (v4 DC) : {np.mean(rB):.4f}")
    print(f"   Mejora: {100*(np.mean(rA)-np.mean(rB))/np.mean(rA):.1f}%  | home advantage γ={MB['g']:.3f}  ρ={MB['rho']:.3f}")
