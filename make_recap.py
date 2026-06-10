"""
make_recap.py — TARJETA VERTICAL del CIERRE DEL DÍA (1080x1920), estilo "Veredicto".
Espejo visual de la infografía de la mañana, pero el marcador central es el REAL, con sello
✓/✗ por partido y el pronóstico debajo. Sección inferior: "Lo que viene". Sale recap.png.

USO: python make_recap.py [--date YYYYMMDD]   (por defecto: AYER en ET)
"""
import sys, os, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import recap, flags, daily_digest as dd
from make_matchday import blk, hvy, reg, GOLD, WHITE, MUTE, BG, CARD, CARD_EDGE, INK, SUB, GREEN, GOLD_DK

RED = "#DC2626"

def flag(ax, team, x, y, zoom=0.24):
    p = flags.flag_path(team)
    if not p: return
    try:
        ax.add_artist(AnnotationBbox(OffsetImage(plt.imread(p), zoom=zoom), (x, y),
                      frameon=False, zorder=6, box_alignment=(0.5, 0.5)))
    except Exception:
        pass

def stamp(ax, x, y, ok, R=34):
    """Sello circular ✓/✗ dibujado como vector (redondo en píxeles pese al aspecto 9:16)."""
    col = GREEN if ok else RED
    ax.add_patch(Ellipse((x, y), 2*R/1080, 2*R/1920, fc=col, ec="white", lw=2, zorder=7))
    if ok:
        ax.plot([x-14/1080, x-4/1080, x+15/1080], [y+1/1920, y-11/1920, y+14/1920],
                color="white", lw=3.5, solid_capstyle="round", solid_joinstyle="round", zorder=8)
    else:
        ax.plot([x-11/1080, x+11/1080], [y-11/1920, y+11/1920], color="white", lw=3.5, solid_capstyle="round", zorder=8)
        ax.plot([x-11/1080, x+11/1080], [y+11/1920, y-11/1920], color="white", lw=3.5, solid_capstyle="round", zorder=8)

def render(target):
    cu = recap.ensure(target)
    if cu.get("empty"):
        print(f"Sin partidos para recapitular el {target}; no se genera recap.png."); return False
    matches = cu["matches"]; rec = cu.get("record", {}); prox = cu.get("proximo")

    fig = plt.figure(figsize=(10.8, 19.2), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ct = np.array([12, 122, 82]) / 255.; cb = np.array([4, 35, 26]) / 255.
    grad = cb + (ct - cb) * np.linspace(0, 1, 256).reshape(-1, 1)
    ax.imshow(grad.reshape(256, 1, 3), extent=[0, 1, 0, 1], aspect="auto", zorder=0)

    # ===== cabecera =====
    ax.add_patch(FancyBboxPatch((0.325, 0.949), 0.35, 0.035, boxstyle="round,pad=0.003,rounding_size=0.017", fc=GOLD, ec="none", zorder=4))
    ax.text(0.5, 0.9665, "@aiwithpedro", ha="center", va="center", color="#0b3b29", fontproperties=blk(23), zorder=6)
    ax.text(0.5, 0.927, "MUNDIAL 2026", ha="center", va="center", color=GOLD, fontproperties=blk(52), zorder=5)
    ax.text(0.5, 0.898, f"¿LE ATINAMOS?  ·  {cu['fecha_h']}  ·  hora ET", ha="center", va="center",
            color=WHITE, fontproperties=blk(19), zorder=5)

    # ===== tarjetas de partido (marcador REAL + sello + pronóstico) =====
    ytop, ybot = 0.878, 0.455; n = max(1, len(matches)); rh = (ytop - ybot) / n
    for i, d in enumerate(matches):
        yc = ytop - (i + 0.5) * rh
        ax.add_patch(FancyBboxPatch((0.055, yc-rh*0.40), 0.89, rh*0.80,
                     boxstyle="round,pad=0.004,rounding_size=0.018", fc=CARD, ec=CARD_EDGE, lw=1, zorder=2))
        a, b = d["a"], d["b"]
        ax.text(0.085, yc+rh*0.30, f"{d['hora']}   ·   {d['label']}", ha="left", va="center",
                color=SUB, fontproperties=hvy(13), zorder=5)
        stamp(ax, 0.915, yc+rh*0.30, d["ok1x2"])
        ax.text(0.5, yc+rh*0.30, "resultado", ha="center", va="center", color=SUB, fontproperties=hvy(10), zorder=5)
        # color del equipo que pronosticamos (verde si acertó, rojo si falló); el rival en tinta
        col_a = (GREEN if d["ok1x2"] else RED) if d["pick_code"] == "1" else INK
        col_b = (GREEN if d["ok1x2"] else RED) if d["pick_code"] == "2" else INK
        flag(ax, a, 0.095, yc+rh*0.08, zoom=0.25)
        ax.text(0.135, yc+rh*0.08, dd.acc(a).upper(), ha="left", va="center", color=col_a, fontproperties=blk(17), zorder=5)
        flag(ax, b, 0.905, yc+rh*0.08, zoom=0.25)
        ax.text(0.865, yc+rh*0.08, dd.acc(b).upper(), ha="right", va="center", color=col_b, fontproperties=blk(17), zorder=5)
        # marcador REAL grande al centro
        real = d["marcador_real"].replace("-", " - ")
        ax.text(0.5, yc+rh*0.06, real, ha="center", va="center", color=INK, fontproperties=blk(24), zorder=5)
        # pronóstico
        pickcol = GREEN if d["ok1x2"] else RED
        dijimos = "empate" if d["pick_code"] == "X" else dd.acc(d["pick_team"])
        ax.text(0.5, yc-rh*0.16, f"dijimos: {dijimos} ({d['ppick']:.0%})", ha="center", va="center",
                color=pickcol, fontproperties=blk(15), zorder=5)
        ax.text(0.5, yc-rh*0.32, f"previsto {d['marcador_pred']}  ·  real {d['marcador_real']}"
                + ("  ·  marcador exacto" if d["okexact"] else ""),
                ha="center", va="center", color=SUB, fontproperties=hvy(11), zorder=5)

    # ===== resumen del día =====
    ax.text(0.5, 0.418, f"HOY: {cu['hits']} DE {cu['n']} ACIERTOS", ha="center", va="center",
            color=GOLD, fontproperties=blk(30), zorder=5)
    if rec.get("n", 0) > 0:
        ax.text(0.5, 0.388, f"Racha {rec['aciertos_1x2']}/{rec['n']} ({rec['tasa_1x2']:.0f}%)  ·  Brier {rec['brier']}",
                ha="center", va="center", color=MUTE, fontproperties=hvy(16), zorder=5)
    else:
        ax.text(0.5, 0.388, "Primer cierre del Mundial", ha="center", va="center", color=MUTE, fontproperties=hvy(16), zorder=5)

    # ===== lo que viene =====
    ax.text(0.5, 0.350, "LO QUE VIENE", ha="center", color=GOLD, fontproperties=blk(22), zorder=5)
    ax.add_patch(FancyBboxPatch((0.055, 0.135), 0.89, 0.185,
                 boxstyle="round,pad=0.004,rounding_size=0.018", fc=CARD, ec=CARD_EDGE, lw=1, zorder=2))
    if prox:
        ax.text(0.5, 0.295, f"{prox['fecha_h']}  ·  {prox['hora']}", ha="center", va="center",
                color=SUB, fontproperties=hvy(14), zorder=5)
        flag(ax, prox["a"], 0.16, 0.232, zoom=0.26)
        ax.text(0.22, 0.232, dd.acc(prox["a"]).upper(), ha="left", va="center", color=INK, fontproperties=blk(17), zorder=5)
        ax.text(0.5, 0.232, "vs", ha="center", va="center", color=SUB, fontproperties=hvy(14), zorder=5)
        ax.text(0.78, 0.232, dd.acc(prox["b"]).upper(), ha="right", va="center", color=INK, fontproperties=blk(17), zorder=5)
        flag(ax, prox["b"], 0.84, 0.232, zoom=0.26)
        ax.text(0.5, 0.168, f"favorito: {dd.acc(prox['fav'])} ({prox['fp']:.0%})", ha="center", va="center",
                color=GOLD_DK, fontproperties=blk(16), zorder=5)
    else:
        ax.text(0.5, 0.227, "El calendario se actualiza pronto", ha="center", va="center",
                color=SUB, fontproperties=hvy(15), zorder=5)

    # ===== pie =====
    ax.text(0.5, 0.082, "Mostramos aciertos y fallos · análisis gratis en mi Substack",
            ha="center", va="center", color=MUTE, fontproperties=hvy(15), zorder=5)
    ax.text(0.5, 0.040, "Modelo propio · 20.000 simulaciones · contenido informativo y de entretenimiento",
            ha="center", va="center", color=MUTE, fontproperties=reg(11), zorder=5)
    fig.savefig("recap.png", facecolor=BG)
    print("→ recap.png (cierre del día) guardado (1080x1920)")
    return True

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else recap.yesterday_et()
    render(target)
