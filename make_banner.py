"""
make_banner.py — banner horizontal estilo Mundial (portada para el post de Substack / redes).
USO: python make_banner.py "TITULO" "Subtítulo"   (por defecto: banner del post de bienvenida)
Genera: banner.png (1280x720)
"""
import sys, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

GOLD="#F7C548"; WHITE="#FFFFFF"; MUTE="#cfe8da"; LINE="#F7C548"
_FD=[os.path.join(os.environ.get("WINDIR",r"C:\Windows"),"Fonts"),
     "/usr/share/fonts/truetype/liberation","/usr/share/fonts/truetype/dejavu"]
def _fp(size,*names):
    for d in _FD:
        for n in names:
            p=os.path.join(d,n)
            if os.path.exists(p): return font_manager.FontProperties(fname=p,size=size)
    return font_manager.FontProperties(weight="bold",size=size)
def blk(s): return _fp(s,"ariblk.ttf","LiberationSans-Bold.ttf","DejaVuSans-Bold.ttf")
def hvy(s): return _fp(s,"arialbd.ttf","LiberationSans-Bold.ttf","DejaVuSans-Bold.ttf")

def main(title, subtitle, tags):
    fig=plt.figure(figsize=(12.8,7.2),dpi=100); ax=fig.add_axes([0,0,1,1]); ax.axis("off")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    # fondo: degradado diagonal verde césped
    g=np.linspace(0,1,256)
    ct=np.array([18,150,94])/255.; cb=np.array([5,42,30])/255.
    grad=cb+(ct-cb)*g.reshape(-1,1)
    ax.imshow(grad.reshape(256,1,3),extent=[0,1,0,1],aspect="auto",zorder=0)
    # franja superior dorada fina
    ax.add_patch(plt.Rectangle((0,0.93),1,0.02,fc=GOLD,ec="none",zorder=2))
    ax.add_patch(plt.Rectangle((0,0.055),1,0.02,fc=GOLD,ec="none",zorder=2))
    # marca
    ax.text(0.5,0.80,"@aiwithpedro",ha="center",va="center",color=MUTE,fontproperties=hvy(26),zorder=5)
    # título (puede ser 1-2 líneas)
    lines=title.split("\n")
    y0=0.55 if len(lines)>1 else 0.50
    for i,ln in enumerate(lines):
        ax.text(0.5,y0-i*0.16,ln,ha="center",va="center",color=GOLD,fontproperties=blk(78),zorder=5)
    ax.plot([0.32,0.68],[0.30,0.30],color=LINE,lw=3,zorder=5)
    ax.text(0.5,0.225,subtitle,ha="center",va="center",color=WHITE,fontproperties=hvy(27),zorder=5)
    ax.text(0.5,0.135,tags,ha="center",va="center",color=MUTE,fontproperties=hvy(20),zorder=5)
    fig.savefig("banner.png",facecolor="#052a1e")
    print("→ banner.png guardado (1280x720)")

if __name__=="__main__":
    args=[a for a in sys.argv[1:]]
    title    = args[0] if len(args)>0 else "EL MUNDIAL\nCON IA"
    subtitle = args[1] if len(args)>1 else "Pronósticos del Mundial 2026 con Inteligencia Artificial"
    tags     = args[2] if len(args)>2 else "20.000 simulaciones  ·  IA agéntica  ·  pronóstico diario"
    main(title, subtitle, tags)
