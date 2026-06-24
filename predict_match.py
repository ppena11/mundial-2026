"""
predict_match.py — predicción 1X2 de UN partido con el XI confirmado.
El flujo de "1 hora antes" del README, ya automatizado salvo teclear el XI.

QUÉ HACE:
  1. Ajusta los ratings v7 del modelo (Dixon-Coles) por LESIONES (injuries.json)
     y por el XI CONFIRMADO (lineups.json) — este último manda.
  2. Calcula la probabilidad de victoria local / empate / visitante de ESE partido,
     los goles esperados y el marcador más probable.

USO:
  python predict_match.py "Espana" "Francia"
  python predict_match.py "Mexico" "Brasil" --local-anfitrion   # si el local juega en casa (Méx/EEUU/Can)

ANTES de correrlo (opcional): edita lineups.json con quién NO está en el XI.
"""
import sys, os, math, json
import fit_dc, engine
import context_factors as cf

engine.setconf(["Rep. Checa","Serbia y Montenegro"],"UEFA"); engine.setconf(["Cabo Verde"],"CAF")
MAP = json.load(open("namemap.json", encoding="utf-8"))
HOSTS = {"Mexico","Estados Unidos","Canada"}

def fit_model():
    rows = fit_dc.load("2019-01-01","2026-06-01")
    data = fit_dc.build(rows, "2026-06-01")
    M = fit_dc.fit(data, separate=True)
    ti = {t:i for i,t in enumerate(M['teams'])}
    atk = {es:M['atk'][ti[dn]] for es,dn in MAP.items()}
    dfn = {es:M['dfn'][ti[dn]] for es,dn in MAP.items()}
    return atk, dfn, M['c'], M['g'], M['rho']

def apply_adjustments(atk, dfn):
    """Resta a atk/dfn el efecto de lesiones + XI (player_layer)."""
    try:
        import player_layer
        sq = player_layer.load_squad_data()
        for t, d in sq.items():
            if t in atk:
                da, dd = player_layer.player_adjustment(0.0, 0.0, d["starters_available"], d["key_players"])
                atk[t] += da; dfn[t] += dd
        return sq
    except Exception as e:
        print(f"(sin ajuste por lesiones/XI: {e})"); return {}

def outcome_de(sx, sy):
    """Resultado 1X2 que IMPLICA un marcador (la predicción es el marcador más probable; el favorito/pick
    se DERIVA de él para que todo concuerde): sx>sy -> '1', empate -> 'X', sx<sy -> '2'."""
    return "1" if sx > sy else ("X" if sx == sy else "2")

def one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=False, sede=None, kickoff_hour=None):
    ga_host = g if (a in HOSTS and local_anfitrion) else 0
    gb_host = g if (b in HOSTS and local_anfitrion) else 0
    lh = math.exp(c + atk[a] - dfn[b] + ga_host)
    la = math.exp(c + atk[b] - dfn[a] + gb_host)
    # Factores de contexto si se da la sede (altura + calor; el viaje no es derivable de un
    # partido suelto sin calendario, así que queda apagado aquí).
    if sede:
        fh, fa = cf.match_factors(a, b, sede, kickoff_hour, enable_travel=False,
                                  enable_alt=cf.USE_ALTITUDE, enable_heat=cf.USE_HEAT)
        lh *= fh; la *= fa
    K = 11
    ph = [math.exp(-lh)*lh**k/math.factorial(k) for k in range(K)]
    pa = [math.exp(-la)*la**k/math.factorial(k) for k in range(K)]
    pw = pd = pl = 0.0
    grid = {}
    for x in range(K):
        for y in range(K):
            p = ph[x]*pa[y]
            if x<=1 and y<=1:   # corrección Dixon-Coles para marcadores bajos
                if   x==0 and y==0: p *= (1 - lh*la*rho)
                elif x==0 and y==1: p *= (1 + lh*rho)
                elif x==1 and y==0: p *= (1 + la*rho)
                else:               p *= (1 - rho)
            p = max(p, 0.0); grid[(x,y)] = p
            if x>y: pw += p
            elif x==y: pd += p
            else: pl += p
    s = pw+pd+pl
    top = max(grid, key=grid.get)   # marcador MÁS PROBABLE (el favorito/pick se deriva de él, no al revés)
    return pw/s, pd/s, pl/s, lh, la, top

def _grid_probs(lh, la, rho, K=11):
    """1X2 + grilla de marcadores para unos goles esperados (mismo cálculo Dixon-Coles que one_x_two)."""
    ph = [math.exp(-lh)*lh**k/math.factorial(k) for k in range(K)]
    pa = [math.exp(-la)*la**k/math.factorial(k) for k in range(K)]
    pw = pd = pl = 0.0; grid = {}
    for x in range(K):
        for y in range(K):
            p = ph[x]*pa[y]
            if x <= 1 and y <= 1:
                if   x == 0 and y == 0: p *= (1 - lh*la*rho)
                elif x == 0 and y == 1: p *= (1 + lh*rho)
                elif x == 1 and y == 0: p *= (1 + la*rho)
                else:                   p *= (1 - rho)
            p = max(p, 0.0); grid[(x, y)] = p
            if x > y: pw += p
            elif x == y: pd += p
            else: pl += p
    s = pw+pd+pl or 1.0
    return pw/s, pd/s, pl/s, {k: v/s for k, v in grid.items()}

def ensamble_marcador(lh, la, rho, m_w, m_d, m_l, w_modelo=0.6):
    """Mezcla MODELO + MERCADO y devuelve el marcador y probabilidades AJUSTADOS, usando TODOS los datos.
    m_w/m_d/m_l = probabilidad del mercado de que gane el local / empate / gane el visitante (de-vigueadas).
    Mantiene los goles esperados totales (lh*la) y desplaza la 'supremacía' hacia el consenso modelo+mercado.
    Devuelve (sx, sy, pw, pd, pl, lh', la'). Si el mercado no es válido, no cambia nada."""
    pw, pd, pl, _ = _grid_probs(lh, la, rho)
    if not (m_w and m_l) or (m_w + (m_d or 0) + m_l) <= 0:
        g = _grid_probs(lh, la, rho)[3]; top = max(g, key=g.get)
        return top[0], top[1], pw, pd, pl, lh, la
    s = m_w + (m_d or 0) + m_l; m_w, m_d, m_l = m_w/s, (m_d or 0)/s, m_l/s
    bw = w_modelo*pw + (1-w_modelo)*m_w
    bl = w_modelo*pl + (1-w_modelo)*m_l
    objetivo = bw - bl                         # supremacía local objetivo (blend modelo+mercado)
    lo, hi = -1.6, 1.6                          # δ: lh·e^δ, la·e^-δ (preserva lh·la); supremacía crece con δ
    for _ in range(44):
        mid = (lo + hi) / 2
        pw2, _, pl2, _ = _grid_probs(lh*math.exp(mid), la*math.exp(-mid), rho)
        if (pw2 - pl2) < objetivo: lo = mid
        else: hi = mid
    d = (lo + hi) / 2
    lh2, la2 = lh*math.exp(d), la*math.exp(-d)
    pw2, pd2, pl2, grid = _grid_probs(lh2, la2, rho)
    top = max(grid, key=grid.get)   # marcador MÁS PROBABLE del ensamble (el favorito/pick se deriva de él)
    return top[0], top[1], pw2, pd2, pl2, lh2, la2

def make_match_png(res, path="champ_match.png"):
    """Gráfico vertical 9:16 del partido (1X2 + goles + bajas), estilo TikTok."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    fdirs = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
             "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/dejavu"]
    def fp(size, *names):
        for d in fdirs:
            for n in names:
                p = os.path.join(d, n)
                if os.path.exists(p): return font_manager.FontProperties(fname=p, size=size)
        return font_manager.FontProperties(weight="bold", size=size)
    def black(s): return fp(s, "ariblk.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf")
    def heavy(s): return fp(s, "arialbd.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf")
    BG="#050a16"; GOLD="#FFD23F"; CYAN="#27E1C1"; GREY="#9AA8C2"; RED="#FF5C7A"; WHITE="#F5F7FF"; MUTE="#8AA0C8"

    fig=plt.figure(figsize=(9,16),dpi=120); ax=fig.add_axes([0,0,1,1]); ax.axis("off")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    import numpy as np
    grad=(np.array([3,6,18])/255.0)+((np.array([11,20,55])-np.array([3,6,18]))/255.0)*np.linspace(0,1,256).reshape(-1,1)
    ax.imshow(grad.reshape(256,1,3),extent=[0,1,0,1],aspect="auto",zorder=0)

    ax.text(0.5,0.95,"MUNDIAL 2026",ha="center",color=GOLD,fontproperties=black(40),zorder=5)
    ax.text(0.5,0.905,f"{res['local'].upper()}  vs  {res['visitante'].upper()}",
            ha="center",color=WHITE,fontproperties=black(30),zorder=5)
    ax.text(0.5,0.872,"Pronóstico del partido · modelo + lesiones + XI",ha="center",
            color=MUTE,fontproperties=heavy(15),zorder=5)
    ax.plot([0.1,0.9],[0.852,0.852],color=CYAN,lw=2.5,alpha=0.8,zorder=5)

    # tres barras 1 / X / 2
    items=[("1 — "+res["local"], res["p1"], CYAN),
           ("X — Empate",        res["pX"], GREY),
           ("2 — "+res["visitante"], res["p2"], GOLD)]
    vmax=max(v for _,v,_ in items)
    y0=[0.74,0.62,0.50]
    for (lab,val,col),yc in zip(items,y0):
        ax.text(0.1,yc+0.045,lab,ha="left",color=WHITE,fontproperties=black(24),zorder=6)
        ax.add_patch(plt.Rectangle((0.1,yc),(0.8)*(val/vmax)*1.0,0.035,color=col,zorder=4))
        ax.text(0.1+0.8*(val/vmax)+0.015,yc+0.017,f"{val:.0f}%",ha="left",va="center",
                color=WHITE,fontproperties=black(22),zorder=6)

    ax.text(0.5,0.40,f"Goles esperados:  {res['xg_local']}  -  {res['xg_visitante']}",
            ha="center",color=WHITE,fontproperties=heavy(20),zorder=6)
    ax.text(0.5,0.365,f"Marcador más probable:  {res['marcador']}",
            ha="center",color=MUTE,fontproperties=heavy(17),zorder=6)

    yb=0.30
    for team,key in [(res["local"],"bajas_local"),(res["visitante"],"bajas_visitante")]:
        bj=res.get(key,[])
        if bj:
            ax.text(0.1,yb,f"BAJAS {team}:",ha="left",color=RED,fontproperties=black(15),zorder=6)
            ax.text(0.1,yb-0.025,", ".join(bj[:4]),ha="left",color=WHITE,fontproperties=heavy(13),zorder=6)
            yb-=0.065
    ax.text(0.5,0.04,"Contenido informativo · no es consejo de apuestas",ha="center",
            color=MUTE,fontproperties=heavy(12),alpha=0.85)
    fig.savefig(path,facecolor=BG)

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print('Uso: python predict_match.py "Local" "Visitante" [--local-anfitrion]'); sys.exit(1)
    a, b = args[0], args[1]
    local_anf = "--local-anfitrion" in sys.argv
    if a not in MAP or b not in MAP:
        print(f"Selección desconocida. Usa los nombres de namemap.json. Recibido: {a!r}, {b!r}"); sys.exit(1)

    # sede + hora opcionales para activar altura/calor (claves de wc2026_context.json / calendario)
    sede = None; hora = None
    if "--sede" in sys.argv:
        sede = sys.argv[sys.argv.index("--sede") + 1]
    if "--hora" in sys.argv:
        try: hora = int(sys.argv[sys.argv.index("--hora") + 1])
        except (ValueError, IndexError): hora = None

    atk, dfn, c, g, rho = fit_model()
    sq = apply_adjustments(atk, dfn)
    pw, pd, pl, lh, la, (sx, sy) = one_x_two(a, b, atk, dfn, c, g, rho, local_anf, sede=sede, kickoff_hour=hora)

    def bajas(t):
        return [n for n,w,av in sq.get(t,{}).get("key_players",[]) if not av]

    print(f"\n=== {a}  vs  {b} ===")
    if sede:
        v = cf.venue(sede)
        det = f"sede {sede}" + (f" ({v['elevation_m']:.0f} m, techo {v.get('roof')})" if v else "")
        det += f" · saque {hora}h" if hora is not None else ""
        print(f"({det}{' · local juega en casa' if local_anf else ''})\n")
    else:
        print(f"(sede neutral{' · local juega en casa' if local_anf else ''})\n")
    print(f"  1  {a:<16} {100*pw:>5.1f}%")
    print(f"  X  {'Empate':<16} {100*pd:>5.1f}%")
    print(f"  2  {b:<16} {100*pl:>5.1f}%")
    print(f"\n  Goles esperados:  {a} {lh:.2f} - {la:.2f} {b}")
    print(f"  Marcador más probable:  {a} {sx}-{sy} {b}")
    if bajas(a): print(f"\n  Bajas/ausentes {a}: {', '.join(bajas(a))}")
    if bajas(b): print(f"  Bajas/ausentes {b}: {', '.join(bajas(b))}")
    print()

    # --- guardar JSON + gráfico del partido ---
    res = {"local": a, "visitante": b, "p1": round(100*pw,1), "pX": round(100*pd,1),
           "p2": round(100*pl,1), "xg_local": round(lh,2), "xg_visitante": round(la,2),
           "marcador": f"{sx}-{sy}", "bajas_local": bajas(a), "bajas_visitante": bajas(b)}
    json.dump(res, open("champ_match.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    if "--no-png" not in sys.argv:
        try:
            make_match_png(res)
            print("→ champ_match.png guardado")
        except Exception as e:
            print(f"(gráfico omitido: {e})")
