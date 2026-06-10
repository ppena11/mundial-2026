"""
make_curio_card.py — TARJETA VERTICAL (1080x1920) para días SIN partido.
Un dato curioso grande + cuenta regresiva + mini carrera al título. La voz (ElevenLabs)
lee el guion de curio.py. Sale matchday.png (mismo nombre, para reusar make_reel.py).

USO: python make_curio_card.py [--date YYYYMMDD]
"""
import sys, os, json, textwrap
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from datetime import date
import curio, flags, daily_digest as dd
from make_matchday import blk, hvy, reg, GOLD, WHITE, MUTE, BG, CARD, CARD_EDGE, INK, SUB, GOLD_DK, GOLDBAR

def render(target):
    cu = curio.ensure(target)
    try:
        champ = list(json.load(open("champ_today.json", encoding="utf-8"))["campeon"].items())[:3]
    except Exception:
        champ = []
    days = cu.get("days", 0)
    fh = f"{target[6:8]}/{target[4:6]}/{target[0:4]}"

    fig = plt.figure(figsize=(10.8, 19.2), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ct = np.array([12, 122, 82]) / 255.; cb = np.array([4, 35, 26]) / 255.
    grad = cb + (ct - cb) * np.linspace(0, 1, 256).reshape(-1, 1)
    ax.imshow(grad.reshape(256, 1, 3), extent=[0, 1, 0, 1], aspect="auto", zorder=0)

    # ===== cabecera =====
    ax.add_patch(FancyBboxPatch((0.325, 0.945), 0.35, 0.035, boxstyle="round,pad=0.003,rounding_size=0.017", fc=GOLD, ec="none", zorder=4))
    ax.text(0.5, 0.9625, "@aiwithpedro", ha="center", va="center", color="#0b3b29", fontproperties=blk(23), zorder=6)
    ax.text(0.5, 0.921, "MUNDIAL 2026", ha="center", va="center", color=GOLD, fontproperties=blk(50), zorder=5)
    # cuenta regresiva / día de descanso
    cd = (("FALTA 1 DÍA" if days == 1 else f"FALTAN {days} DÍAS") if days > 0 else "HOY DESCANSAN")
    ax.text(0.5, 0.884, cd, ha="center", va="center", color=WHITE, fontproperties=blk(30), zorder=5)
    ax.text(0.5, 0.856, f"{fh}  ·  hoy no hay partidos", ha="center", va="center", color=MUTE, fontproperties=hvy(16), zorder=5)

    # ===== tarjeta del dato curioso (grande, central) =====
    ax.add_patch(FancyBboxPatch((0.06, 0.40), 0.88, 0.42,
                 boxstyle="round,pad=0.004,rounding_size=0.02", fc=CARD, ec=CARD_EDGE, lw=1, zorder=2))
    etiqueta = "NOTICIA DEL DÍA" if cu.get("is_news") else "DATO CURIOSO"
    ax.text(0.5, 0.788, etiqueta, ha="center", va="center", color=GOLD_DK, fontproperties=blk(20), zorder=5)
    # texto grande envuelto (ajusta tamaño según largo)
    card = cu.get("card", "") or ""
    lines = textwrap.wrap(card, width=18) or [""]
    fs = 40 if len(lines) <= 3 else (32 if len(lines) <= 4 else 26)
    y = 0.70; step = (fs + 14) / 1100.
    for ln in lines[:6]:
        ax.text(0.5, y, ln, ha="center", va="center", color=INK, fontproperties=blk(fs), zorder=5); y -= step
    if cu.get("is_news") and cu.get("source"):
        ax.text(0.5, 0.43, f"fuente: {cu['source']}", ha="center", va="center", color=SUB, fontproperties=hvy(15), zorder=5)
    else:
        ax.text(0.5, 0.43, "según mis 20.000 simulaciones", ha="center", va="center", color=SUB, fontproperties=hvy(15), zorder=5)

    # ===== mini carrera al título =====
    if champ:
        ax.text(0.5, 0.355, "CARRERA POR EL TÍTULO", ha="center", color=GOLD, fontproperties=blk(22), zorder=5)
        ax.add_patch(FancyBboxPatch((0.06, 0.16), 0.88, 0.165,
                     boxstyle="round,pad=0.004,rounding_size=0.02", fc=CARD, ec=CARD_EDGE, lw=1, zorder=2))
        cmax = max(v for _, v in champ); yy = 0.285
        for j, (t, v) in enumerate(champ):
            p = flags.flag_path(t)
            if p:
                try: ax.add_artist(AnnotationBbox(OffsetImage(plt.imread(p), zoom=0.26), (0.11, yy), frameon=False, zorder=6))
                except Exception: pass
            ax.text(0.16, yy, f"{j+1}. {dd.acc(t)}", ha="left", va="center", color=INK, fontproperties=hvy(17), zorder=5)
            ax.add_patch(plt.Rectangle((0.50, yy - 0.010), 0.30 * (v / cmax), 0.020, fc=GOLDBAR, ec="none", zorder=4))
            ax.text(0.50 + 0.30 * (v / cmax) + 0.012, yy, f"{v:.1f}%", ha="left", va="center", color=GOLD_DK, fontproperties=blk(15), zorder=5)
            yy -= 0.048

    # ===== pie =====
    ax.text(0.5, 0.10, f"Vuelve {'el 11 de junio' if days > 0 else 'cuando rueden los partidos'} · análisis gratis en mi Substack",
            ha="center", va="center", color=WHITE, fontproperties=hvy(16), zorder=5)
    ax.text(0.5, 0.040, "Modelo propio · 20.000 simulaciones · contenido informativo y de entretenimiento",
            ha="center", va="center", color=MUTE, fontproperties=reg(11), zorder=5)
    fig.savefig("matchday.png", facecolor=BG)
    print(f"→ matchday.png (tarjeta de dato curioso) guardado")

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    render(target)
