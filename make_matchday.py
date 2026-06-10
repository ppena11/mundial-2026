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
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from datetime import date
import daily_digest as dd
import predict_match as pm
import flags

# Paleta Mundial: fondo verde césped + TARJETAS BLANCAS (legible y amigable) + dorado
BG_TOP="#16965e"; BG_BOT="#06382a"; BG=BG_BOT
CARD="#FFFFFF"; CARD_EDGE="#e2ebe5"
INK="#0d2c20"; SUB="#83948b"                       # texto sobre tarjeta clara
GREEN="#16A34A"; GOLDBAR="#F2B400"; GREYBAR="#e3e9e4"; GOLD_DK="#BE8400"
GOLD="#F7C548"; WHITE="#FFFFFF"; MUTE="#cfe8da"     # dorado/blanco para cabecera sobre verde
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
    if not any(not r.get("skip") for r in rows):       # día sin partidos jugables -> tarjeta de dato curioso
        import make_curio_card; make_curio_card.render(target); return
    try: champ=list(json.load(open("champ_today.json",encoding="utf-8"))["campeon"].items())[:5]
    except Exception: champ=[]
    try: tr=json.load(open("track_record.json",encoding="utf-8"))
    except Exception: tr={"n":0}
    fh=f"{target[6:8]}/{target[4:6]}/{target[0:4]}"

    fig=plt.figure(figsize=(10.8,19.2),dpi=100); ax=fig.add_axes([0,0,1,1]); ax.axis("off")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ct=np.array([12,122,82])/255.; cb=np.array([4,35,26])/255.
    grad=cb+(ct-cb)*np.linspace(0,1,256).reshape(-1,1)
    ax.imshow(grad.reshape(256,1,3),extent=[0,1,0,1],aspect="auto",zorder=0)

    def flag(team,x,y,zoom=0.30):
        p=flags.flag_path(team)
        if not p: return
        try:
            ax.add_artist(AnnotationBbox(OffsetImage(plt.imread(p),zoom=zoom),(x,y),frameon=False,zorder=6,box_alignment=(0.5,0.5)))
        except Exception: pass

    # ===== cabecera =====
    # marca en badge dorado (bien visible)
    ax.add_patch(FancyBboxPatch((0.325,0.949),0.35,0.035,boxstyle="round,pad=0.003,rounding_size=0.017",fc=GOLD,ec="none",zorder=4))
    ax.text(0.5,0.9665,"@aiwithpedro",ha="center",va="center",color="#0b3b29",fontproperties=blk(23),zorder=6)
    ax.text(0.5,0.927,"MUNDIAL 2026",ha="center",va="center",color=GOLD,fontproperties=blk(52),zorder=5)
    ax.text(0.5,0.898,f"¿Quién gana hoy?  ·  {fh}  ·  hora ET",ha="center",va="center",color=WHITE,fontproperties=blk(19),zorder=5)

    # ===== tarjetas de partido (claras, con aire) =====
    games=[r for r in rows]
    ytop,ybot=0.878,0.355; n=max(1,len(games)); rh=(ytop-ybot)/n
    for i,d in enumerate(games):
        yc=ytop-(i+0.5)*rh; m=d["m"]
        ax.add_patch(FancyBboxPatch((0.055,yc-rh*0.40),0.89,rh*0.80,boxstyle="round,pad=0.004,rounding_size=0.018",
                     fc=CARD,ec=CARD_EDGE,lw=1,zorder=2))
        ax.text(0.085,yc+rh*0.28,f"{dd.hora_et(m['utc'])}   ·   {m['label']}",ha="left",va="center",
                color=SUB,fontproperties=hvy(13),zorder=5)
        if d.get("skip"):
            ax.text(0.5,yc-rh*0.06,f"{dd.acc(d['a'])}  vs  {dd.acc(d['b'])}",ha="center",va="center",color=SUB,fontproperties=hvy(16),zorder=5)
            continue
        a,b=d["a"],d["b"]; pw,pdr,pl=d["pw"],d["pdr"],d["pl"]
        if d["vc"]:
            ax.text(0.915,yc+rh*0.28,f"VALOR: {dd.acc(d['vc'][0][0])}",ha="right",va="center",color=GOLD_DK,fontproperties=blk(13),zorder=5)
        afav = pw>=pl
        # nombres + banderas (favorito resaltado en su color) + MARCADOR PREVISTO al centro
        flag(a,0.095,yc+rh*0.10,zoom=0.25); ax.text(0.135,yc+rh*0.10,dd.acc(a).upper(),ha="left",va="center",
             color=(GREEN if afav else INK),fontproperties=blk(17),zorder=5)
        flag(b,0.905,yc+rh*0.10,zoom=0.25); ax.text(0.865,yc+rh*0.10,dd.acc(b).upper(),ha="right",va="center",
             color=(GOLD_DK if not afav else INK),fontproperties=blk(17),zorder=5)
        ax.text(0.50,yc+rh*0.28,"marcador previsto",ha="center",va="center",color=SUB,fontproperties=hvy(10),zorder=5)
        ax.text(0.50,yc+rh*0.10,f"{d['sx']} - {d['sy']}",ha="center",va="center",color=INK,fontproperties=blk(19),zorder=5)
        # porcentajes grandes (favorito más grande)
        ax.text(0.135,yc-rh*0.13,f"{100*pw:.0f}%",ha="left",va="center",color=GREEN,fontproperties=blk(20 if afav else 15),zorder=5)
        ax.text(0.50,yc-rh*0.13,f"empate {100*pdr:.0f}%",ha="center",va="center",color=SUB,fontproperties=hvy(13),zorder=5)
        ax.text(0.865,yc-rh*0.13,f"{100*pl:.0f}%",ha="right",va="center",color=GOLD_DK,fontproperties=blk(20 if not afav else 15),zorder=5)
        # barra fina de proporción
        x0,x1=0.135,0.865; W=x1-x0; ybar=yc-rh*0.31; hb=rh*0.075; x=x0
        for frac,col in [(pw,GREEN),(pdr,GREYBAR),(pl,GOLDBAR)]:
            ax.add_patch(plt.Rectangle((x,ybar),W*frac,hb,fc=col,ec="none",zorder=4)); x+=W*frac

    # ===== carrera al título (tarjeta clara) =====
    ax.text(0.5,0.330,"CARRERA POR EL TÍTULO",ha="center",color=GOLD,fontproperties=blk(22),zorder=5)
    ax.add_patch(FancyBboxPatch((0.055,0.105),0.89,0.205,boxstyle="round,pad=0.004,rounding_size=0.018",
                 fc=CARD,ec=CARD_EDGE,lw=1,zorder=2))
    if champ:
        cmax=max(v for _,v in champ); yy=0.280
        for j,(t,v) in enumerate(champ):
            flag(t,0.10,yy,zoom=0.24)
            ax.text(0.145,yy,f"{j+1}. {dd.acc(t)}",ha="left",va="center",color=INK,fontproperties=hvy(15),zorder=5)
            ax.add_patch(plt.Rectangle((0.46,yy-0.009),0.34*(v/cmax),0.018,fc=GOLDBAR,ec="none",zorder=4))
            ax.text(0.46+0.34*(v/cmax)+0.012,yy,f"{v:.1f}%",ha="left",va="center",color=GOLD_DK,fontproperties=blk(14),zorder=5)
            yy-=0.040

    # ===== historial + pie (sutil, sobre el verde) =====
    if tr.get("n",0)>0:
        ax.text(0.5,0.072,f"Le venimos atinando: {tr['aciertos_1x2']} de {tr['n']} aciertos ({tr['tasa_1x2']:.0f}%)",
                ha="center",va="center",color=MUTE,fontproperties=hvy(15),zorder=5)
    else:
        ax.text(0.5,0.072,"El historial de aciertos aparece cuando arranque el torneo",ha="center",va="center",color=MUTE,fontproperties=hvy(14),zorder=5)
    ax.text(0.5,0.040,"Modelo propio · 20.000 simulaciones · contenido informativo y de entretenimiento",ha="center",va="center",color=MUTE,fontproperties=reg(11),zorder=5)
    fig.savefig("matchday.png",facecolor=BG)
    print("→ matchday.png guardado (1080x1920)")

if __name__=="__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    main(target)
