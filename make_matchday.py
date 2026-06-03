"""
make_matchday.py — INFOGRAFÍA del día (tarjeta vertical, una banda por partido).
Diseño tipo redes: barra de probabilidad 1X2 por partido, Pick del día, carrera al
título e historial de aciertos. Sale matchday.png (1080x1920, listo para redes/email).

USO: python make_matchday.py [--date YYYYMMDD]
Lee: el calendario/odds vía daily_digest, champ_today.json y track_record.json.
"""
import sys, os, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
from datetime import date
import daily_digest as dd
import predict_match as pm

BG="#0a1024"; CARD="#141d3a"; CYAN="#27E1C1"; GOLD="#FFD23F"; GREY="#7f8db0"
WHITE="#F5F7FF"; MUTE="#8AA0C8"; RED="#FF5C7A"
_FONTDIRS=[os.path.join(os.environ.get("WINDIR",r"C:\Windows"),"Fonts"),
           "/usr/share/fonts/truetype/liberation","/usr/share/fonts/truetype/dejavu"]
def _fp(size,*names):
    for d in _FONTDIRS:
        for n in names:
            p=os.path.join(d,n)
            if os.path.exists(p): return font_manager.FontProperties(fname=p,size=size)
    return font_manager.FontProperties(weight="bold",size=size)
def blk(s): return _fp(s,"ariblk.ttf","LiberationSans-Bold.ttf","DejaVuSans-Bold.ttf")
def hvy(s): return _fp(s,"arialbd.ttf","LiberationSans-Bold.ttf","DejaVuSans-Bold.ttf")
def reg(s): return _fp(s,"arial.ttf","LiberationSans-Regular.ttf","DejaVuSans.ttf")

VAL_MARGIN, VAL_FLOOR = 1.20, 0.20

def collect(target):
    games = dd.matches_on(target)
    atk,dfn,c,g,rho = pm.fit_model(); sq = pm.apply_adjustments(atk,dfn)
    mkt={}
    try:
        import fetch_odds
        for ev in fetch_odds.h2h():
            pe={dd.EN2ES.get(k,k):v for k,v in ev["clean_probs"].items()}
            ts=[t for t in pe if t!="Draw"]
            if len(ts)==2: mkt[frozenset(ts)]=pe
    except Exception: pass
    rows=[]
    for m in sorted(games,key=lambda x:x["utc"]):
        a,b=m["a"],m["b"]
        if a not in pm.MAP or b not in pm.MAP:
            rows.append({"m":m,"a":a,"b":b,"skip":True}); continue
        pw,pdr,pl,lh,la,(sx,sy)=pm.one_x_two(a,b,atk,dfn,c,g,rho,local_anfitrion=True)
        mp=mkt.get(frozenset((a,b))); vc=[]
        if mp:
            ma,mb=mp.get(a),mp.get(b)
            if ma and pw>=VAL_FLOOR and pw>ma*VAL_MARGIN: vc.append((a,pw,ma,pw/ma))
            if mb and pl>=VAL_FLOOR and pl>mb*VAL_MARGIN: vc.append((b,pl,mb,pl/mb))
        rows.append({"m":m,"a":a,"b":b,"pw":pw,"pdr":pdr,"pl":pl,"sx":sx,"sy":sy,"vc":vc})
    allv=[(d,v) for d in rows if not d.get("skip") for v in d["vc"]]
    pick=max(allv,key=lambda x:x[1][3]) if allv else None
    return rows, pick

def main(target):
    rows, pick = collect(target)
    try: champ=list(json.load(open("champ_today.json",encoding="utf-8"))["campeon"].items())[:5]
    except Exception: champ=[]
    try: tr=json.load(open("track_record.json",encoding="utf-8"))
    except Exception: tr={"n":0}
    fh=f"{target[6:8]}/{target[4:6]}/{target[0:4]}"

    fig=plt.figure(figsize=(10.8,19.2),dpi=100); ax=fig.add_axes([0,0,1,1]); ax.axis("off")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    grad=(np.array([5,8,20])/255.)+((np.array([14,22,52])-np.array([5,8,20]))/255.)*np.linspace(0,1,256).reshape(-1,1)
    ax.imshow(grad.reshape(256,1,3),extent=[0,1,0,1],aspect="auto",zorder=0)

    # cabecera
    ax.text(0.5,0.972,"@aiwithpedro",ha="center",color=CYAN,fontproperties=blk(22),zorder=5)
    ax.text(0.5,0.945,"MUNDIAL 2026",ha="center",color=GOLD,fontproperties=blk(50),zorder=5)
    ax.text(0.5,0.917,f"Pronóstico del {fh} · horas ET",ha="center",color=MUTE,fontproperties=hvy(17),zorder=5)

    # pick del día
    if pick:
        d,(team,mpb,mkp,edge)=pick; riv=d["b"] if team==d["a"] else d["a"]
        ax.add_patch(FancyBboxPatch((0.06,0.862),0.88,0.044,boxstyle="round,pad=0.006,rounding_size=0.012",
                     fc="#2a2410",ec=GOLD,lw=2,zorder=3))
        ax.text(0.085,0.884,"PICK DEL DÍA",ha="left",va="center",color=GOLD,fontproperties=blk(16),zorder=5)
        ax.text(0.52,0.884,f"{team}  ·  {d['m']['label']}",ha="center",va="center",color=WHITE,fontproperties=blk(19),zorder=5)
        ax.text(0.915,0.884,f"+{(edge-1)*100:.0f}% valor",ha="right",va="center",color=CYAN,fontproperties=blk(16),zorder=5)

    # ---- bandas de partidos ----
    games=[r for r in rows]
    ytop,ybot=0.845,0.34; n=max(1,len(games)); rh=(ytop-ybot)/n
    for i,d in enumerate(games):
        yc=ytop-(i+0.5)*rh; m=d["m"]
        # tarjeta de fondo
        ax.add_patch(FancyBboxPatch((0.05,yc-rh*0.40),0.90,rh*0.80,boxstyle="round,pad=0.004,rounding_size=0.010",
                     fc=CARD,ec="none",zorder=2))
        chip=f"{dd.hora_et(m['utc'])}   ·   {m['label']}"
        ax.text(0.075,yc+rh*0.30,chip,ha="left",va="center",color=MUTE,fontproperties=hvy(14),zorder=5)
        if d.get("skip"):
            ax.text(0.5,yc-rh*0.05,f"{d['a']}  vs  {d['b']}",ha="center",va="center",color=GREY,fontproperties=hvy(16),zorder=5)
            continue
        a,b=d["a"],d["b"]; pw,pdr,pl=d["pw"],d["pdr"],d["pl"]
        if d["vc"]:
            ax.text(0.925,yc+rh*0.30,f"VALOR: {d['vc'][0][0]}",ha="right",va="center",color="#46d39a",fontproperties=blk(14),zorder=5)
        # nombres (centro de la banda) + marcador previsto al centro
        ax.text(0.075,yc+rh*0.04,a.upper(),ha="left",va="center",color=WHITE,fontproperties=blk(19),zorder=5)
        ax.text(0.925,yc+rh*0.04,b.upper(),ha="right",va="center",color=WHITE,fontproperties=blk(19),zorder=5)
        ax.text(0.5,yc+rh*0.04,f"{d['sx']}–{d['sy']}",ha="center",va="center",color=MUTE,fontproperties=blk(16),zorder=5)
        # barra de probabilidad 1X2
        x0,x1=0.32,0.68; W=x1-x0; ybar=yc-rh*0.24; hb=rh*0.15
        x=x0
        for frac,col in [(pw,CYAN),(pdr,GREY),(pl,GOLD)]:
            ax.add_patch(plt.Rectangle((x,ybar),W*frac,hb,fc=col,ec="none",zorder=4)); x+=W*frac
        ax.text(x0-0.012,ybar+hb/2,f"{100*pw:.0f}%",ha="right",va="center",color=CYAN,fontproperties=blk(16),zorder=5)
        ax.text(x1+0.012,ybar+hb/2,f"{100*pl:.0f}%",ha="left",va="center",color=GOLD,fontproperties=blk(16),zorder=5)
        ax.text((x0+x1)/2,ybar-rh*0.14,f"empate {100*pdr:.0f}%",ha="center",va="center",color=GREY,fontproperties=hvy(12),zorder=5)

    # ---- carrera al título ----
    ax.text(0.075,0.30,"CARRERA POR EL TÍTULO",ha="left",color=GOLD,fontproperties=blk(20),zorder=5)
    if champ:
        cmax=max(v for _,v in champ); yy=0.265
        for t,v in champ:
            ax.text(0.075,yy,t,ha="left",va="center",color=WHITE,fontproperties=hvy(15),zorder=5)
            ax.add_patch(plt.Rectangle((0.34,yy-0.009),0.45*(v/cmax),0.018,fc=GOLD,ec="none",zorder=4))
            ax.text(0.34+0.45*(v/cmax)+0.01,yy,f"{v:.1f}%",ha="left",va="center",color=GOLD,fontproperties=blk(14),zorder=5)
            yy-=0.034

    # ---- historial ----
    if tr.get("n",0)>0:
        ax.add_patch(FancyBboxPatch((0.06,0.055),0.88,0.05,boxstyle="round,pad=0.006,rounding_size=0.012",
                     fc="#10221a",ec="#46d39a",lw=1.5,zorder=3))
        ax.text(0.085,0.08,"HISTORIAL DEL MODELO",ha="left",va="center",color="#46d39a",fontproperties=blk(15),zorder=5)
        ax.text(0.915,0.08,f"{tr['aciertos_1x2']}/{tr['n']} aciertos 1X2  ·  {tr['tasa_1x2']}%  ·  Brier {tr['brier']}",
                ha="right",va="center",color=WHITE,fontproperties=hvy(15),zorder=5)
    else:
        ax.text(0.5,0.08,"El historial aparece cuando se jueguen partidos",ha="center",color=MUTE,fontproperties=hvy(14),zorder=5)

    ax.text(0.5,0.022,"Contenido informativo · no es consejo de apuestas · +18",ha="center",color=MUTE,fontproperties=reg(12),zorder=5)
    fig.savefig("matchday.png",facecolor=BG)
    print("→ matchday.png guardado (1080x1920)")

if __name__=="__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    main(target)
