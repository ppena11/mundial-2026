"""
make_tiktok.py — gráfico VERTICAL 9:16 (1080x1920) estilo TikTok/Reels.
Usa el ENSEMBLE (modelo+mercado, ya con lesiones) y ANOTA las bajas por selección.

Entrada:  champ_ensemble.json (de make_ensemble.py) + injuries.json (de fetch_injuries.py)
Salida:   champ_tiktok.png   (listo para subir a TikTok/Instagram/YouTube Shorts)

USO:  python make_tiktok.py
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

N_TOP = 10
# paleta
BG_DARK = "#050a16"   # casi negro azulado (fondo y facecolor)
GOLD = "#FFD23F"; CYAN = "#27E1C1"; RED = "#FF5C7A"; WHITE = "#F5F7FF"; MUTE = "#8AA0C8"

_FONTDIRS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
             "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/dejavu"]
def _fp(*candidates, size=20):
    """Carga una fuente por ruta (Windows o Linux); si no, bold por defecto."""
    for d in _FONTDIRS:
        for fn in candidates:
            path = os.path.join(d, fn)
            if os.path.exists(path):
                return font_manager.FontProperties(fname=path, size=size)
    return font_manager.FontProperties(weight="bold", size=size)

# titulares: Arial Black (Win) / Liberation Sans Bold (Linux) / DejaVu Bold
def black(size):  return _fp("ariblk.ttf", "impact.ttf", "arialbd.ttf",
                             "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", size=size)
def heavy(size):  return _fp("arialbd.ttf", "segoeuib.ttf",
                             "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", size=size)

def main():
    ens = json.load(open("champ_ensemble.json", encoding="utf-8"))["ensemble"]  # {equipo: %}
    try:
        inj = json.load(open("injuries.json", encoding="utf-8"))
    except FileNotFoundError:
        inj = {}
    def bajas(team):
        out = [p["player"] for p in inj.get(team, []) if p["status"] == "out"]
        return out

    teams = list(ens.keys())[:N_TOP]
    vals = [ens[t] for t in teams]
    vmax = max(vals)

    fig = plt.figure(figsize=(9, 16), dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # --- fondo degradado vertical ---
    grad = np.linspace(0, 1, 256).reshape(-1, 1)
    c_top = np.array([11, 20, 55]) / 255.0
    c_bot = np.array([3, 6, 18]) / 255.0
    grad_rgb = c_bot + (c_top - c_bot) * grad  # abajo oscuro, arriba azul
    ax.imshow(grad_rgb.reshape(256, 1, 3), extent=[0, 1, 0, 1], aspect="auto", zorder=0)

    # --- cabecera ---
    ax.text(0.5, 0.967, "@aiwithpedro", ha="center", va="center", color=CYAN,
            fontproperties=black(22), zorder=5)
    ax.text(0.5, 0.933, "MUNDIAL 2026", ha="center", va="center", color=GOLD,
            fontproperties=black(46), zorder=5)
    ax.text(0.5, 0.902, "¿QUIÉN SERÁ CAMPEÓN?", ha="center", va="center", color=WHITE,
            fontproperties=black(29), zorder=5)
    ax.text(0.5, 0.879, "Modelo + mercado · 20.000 simulaciones · con lesiones",
            ha="center", va="center", color=MUTE, fontproperties=heavy(15), zorder=5)
    ax.plot([0.1, 0.9], [0.863, 0.863], color=CYAN, lw=2.5, alpha=0.8, zorder=5)

    # --- barras ---
    top_y, bot_y = 0.848, 0.090
    row_h = (top_y - bot_y) / N_TOP
    x0 = 0.30                      # inicio de las barras
    x_full = 0.80                  # fin máximo (deja sitio al % a la derecha)
    medals = {0: GOLD, 1: "#C9D2E3", 2: "#E0925A"}
    for i, (t, v) in enumerate(zip(teams, vals)):
        yc = top_y - (i + 0.5) * row_h
        bar_w = max(0.02, (x_full - x0) * (v / vmax))
        color = medals.get(i, CYAN)
        # barra (centrada en yc, fina para dejar aire arriba/abajo)
        ax.add_patch(plt.Rectangle((x0, yc - row_h*0.21), bar_w, row_h*0.42,
                     color=color, zorder=4, alpha=0.96))
        # ranking
        ax.text(0.075, yc, f"{i+1}", ha="center", va="center", color=color,
                fontproperties=black(34), zorder=6)
        # nombre selección (encima de la barra)
        ax.text(0.140, yc + row_h*0.30, t.upper(), ha="left", va="center", color=WHITE,
                fontproperties=black(21), zorder=6)
        # porcentaje al final de la barra
        ax.text(x0 + bar_w + 0.015, yc, f"{v:.1f}%", ha="left", va="center", color=WHITE,
                fontproperties=black(21), zorder=6)
        # bajas (lesiones) debajo de la barra, en el hueco entre filas
        outs = bajas(t)
        if outs:
            txt = "BAJAS: " + ", ".join(outs[:3]) + ("…" if len(outs) > 3 else "")
            ax.text(0.140, yc - row_h*0.34, txt, ha="left", va="center", color=RED,
                    fontproperties=heavy(12), zorder=6)

    # --- pie ---
    ax.text(0.5, 0.054, "Dixon-Coles + Poisson + Montecarlo", ha="center", color=MUTE,
            fontproperties=heavy(14))
    ax.text(0.5, 0.032, "Contenido informativo · no es consejo de apuestas", ha="center",
            color=MUTE, fontproperties=heavy(12), alpha=0.85)

    fig.savefig("champ_tiktok.png", facecolor=BG_DARK)
    print("→ champ_tiktok.png guardado (1080x1920, listo para TikTok)")
    n_inj = sum(1 for t in teams if bajas(t))
    print(f"   {n_inj}/{len(teams)} selecciones del top con bajas anotadas")

if __name__ == "__main__":
    main()
