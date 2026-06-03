"""
make_ensemble.py — combina el MODELO en vivo (champ_today.json, ya con lesiones)
con el MERCADO en vivo (odds_live.json, cuotas de-vigueadas) y genera:
  - champ_ensemble.json : porcentajes del ensemble + comparativa modelo/mercado
  - champ_ensemble.png  : gráfico del ensemble (lo que corrige el sesgo longshot del modelo)

Ensemble = (1-W)*modelo + W*mercado, renormalizado sobre las 48 selecciones del Mundial.
W=0.5 por defecto (50/50). Sube W para confiar más en el mercado.

USO:  python make_ensemble.py [W]      (ej: python make_ensemble.py 0.5)
"""
import sys, json

W = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].replace(".","",1).isdigit() else 0.5

# alias de nombres del feed (inglés) que no coinciden con namemap.json
FEED_ALIASES = {"USA":"United States", "Bosnia & Herzegovina":"Bosnia and Herzegovina"}

def market_to_spanish(clean, namemap):
    en2es = {en: es for es, en in namemap.items()}
    out = {}
    for name_en, prob in clean.items():
        name_en = FEED_ALIASES.get(name_en, name_en)
        es = en2es.get(name_en)
        if es is not None:
            out[es] = prob
    return out

def main():
    namemap = json.load(open("namemap.json", encoding="utf-8"))
    model = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]  # en %
    model = {t: v/100.0 for t, v in model.items()}                             # -> fracción
    feed = json.load(open("odds_live.json", encoding="utf-8"))["clean_probs"]
    market = market_to_spanish(feed, namemap)

    # ensemble solo sobre las selecciones del modelo (48 del Mundial)
    ens = {}
    for t, pm in model.items():
        pc = market.get(t, pm)              # si el mercado no la cotiza, usa el modelo
        ens[t] = (1 - W) * pm + W * pc
    s = sum(ens.values())
    ens = {t: ens[t] / s for t in ens}      # renormalizar a 100%

    rows = sorted(ens, key=lambda t: ens[t], reverse=True)
    out = {"W_mercado": W,
           "ensemble": {t: round(100*ens[t], 2) for t in rows},
           "modelo":   {t: round(100*model[t], 2) for t in rows},
           "mercado":  {t: round(100*market.get(t, float("nan")), 2) for t in rows}}
    json.dump(out, open("champ_ensemble.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"ENSEMBLE modelo+mercado (W mercado={W:.0%}):\n")
    print(f"{'Selección':<14}{'Modelo':>8}{'Mercado':>9}{'Ensemble':>10}")
    for t in rows[:12]:
        pcm = market.get(t)
        print(f"{t:<14}{100*model[t]:>7.1f}%{(f'{100*pcm:>8.1f}%' if pcm is not None else '       —')}{100*ens[t]:>9.1f}%")
    print("\n→ champ_ensemble.json guardado")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        top = rows[:12][::-1]
        labels = top
        model_v = [100*model[t] for t in top]
        ens_v   = [100*ens[t] for t in top]
        import numpy as np
        y = np.arange(len(labels)); h = 0.4
        plt.figure(figsize=(9, 6.5))
        plt.barh(y+h/2, ens_v,   height=h, color="#d62728", label=f"Ensemble (modelo+{W:.0%} mercado)")
        plt.barh(y-h/2, model_v, height=h, color="#1f77b4", label="Modelo solo (con lesiones)")
        plt.yticks(y, labels)
        plt.xlabel("Probabilidad de ser campeón (%)")
        plt.title("Mundial 2026 — Modelo vs Ensemble con corrección de mercado")
        plt.legend(loc="lower right")
        for yi, v in zip(y+h/2, ens_v):   plt.text(v+0.1, yi, f"{v:.1f}%", va="center", fontsize=8)
        plt.tight_layout()
        plt.savefig("champ_ensemble.png", dpi=130)
        print("→ champ_ensemble.png guardado")
    except Exception as e:
        print(f"(gráfico omitido: {e})")

if __name__ == "__main__":
    main()
