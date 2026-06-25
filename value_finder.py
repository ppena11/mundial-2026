"""
value_finder.py — convierte (probabilidad del modelo + cuota de la casa) en una decisión de apuesta
de VALOR, con stake por Kelly fraccionado. Para el grind disciplinado en Mise-o-jeu+ (Quebec).

Idea: una apuesta tiene VALOR solo si  p_modelo × cuota_decimal > 1  (EV positivo). Con el margen
ALTO de Mise-o-jeu, hay que exigir un colchón (min_edge) porque el modelo no es perfecto y la casa
ya te cobra el vig. Stake = Kelly fraccionado (conservador) con tope por apuesta.

  EV%   = (p × cuota − 1) × 100         (ventaja esperada de la apuesta)
  Kelly = (p × cuota − 1) / (cuota − 1) (fracción óptima de banca; usamos una FRACCIÓN de esto)

Uso (interactivo o importable):
  python value_finder.py 1000   # banca; luego pegas mercado/selección/p_modelo/cuota
Funciones puras con pruebas en test_value_finder.py.
"""
import sys

KELLY_FRACTION = 0.25   # cuarto de Kelly: conservador (grind, baja varianza)
STAKE_CAP = 0.02        # nunca más del 2% de la banca por apuesta
MIN_EDGE = 0.10         # exigir ≥10% de EV para cubrir vig + imperfección del modelo


def ev(p_model, odds):
    """Ventaja esperada (fracción): p×cuota − 1. >0 = apuesta con valor."""
    return p_model * odds - 1.0

def implied_prob(odds):
    """Probabilidad implícita (con vig) de una cuota decimal."""
    return 1.0 / odds if odds > 0 else 0.0

def kelly_fraction(p_model, odds):
    """Fracción de banca de Kelly COMPLETO (0 si no hay valor)."""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    f = (p_model * odds - 1.0) / b
    return max(0.0, f)

def stake(bankroll, p_model, odds, frac=KELLY_FRACTION, cap=STAKE_CAP, min_edge=MIN_EDGE):
    """Stake recomendado ($). 0 si la apuesta no supera el umbral de valor (min_edge)."""
    if ev(p_model, odds) < min_edge:
        return 0.0
    f = min(cap, frac * kelly_fraction(p_model, odds))
    return round(f * bankroll, 2)

def analyze(bankroll, lines, **kw):
    """lines: [{'market','sel','p_model','odds'}, ...] -> añade EV%, implícita, stake, value."""
    out = []
    for L in lines:
        p, o = L["p_model"], L["odds"]
        s = stake(bankroll, p, o, **kw)
        out.append({**L, "implicita": round(100 * implied_prob(o), 1),
                    "EV%": round(100 * ev(p, o), 1), "stake": s, "value": s > 0})
    return sorted(out, key=lambda r: -r["EV%"])


if __name__ == "__main__":
    bankroll = float(sys.argv[1]) if len(sys.argv) > 1 else 1000.0
    print(f"Banca: ${bankroll:.0f} · Kelly×{KELLY_FRACTION} · tope {STAKE_CAP:.0%} · min EV {MIN_EDGE:.0%}\n")
    print("Pega líneas:  mercado,seleccion,p_modelo(0-1),cuota_decimal   (línea vacía para terminar)")
    lines = []
    try:
        while True:
            raw = input("> ").strip()
            if not raw:
                break
            mk, sel, p, o = [x.strip() for x in raw.split(",")]
            lines.append({"market": mk, "sel": sel, "p_model": float(p), "odds": float(o)})
    except (EOFError, KeyboardInterrupt):
        pass
    print(f"\n{'mercado':<14}{'sel':<16}{'p_mod':>7}{'implic':>8}{'cuota':>7}{'EV%':>7}{'stake$':>9}")
    for r in analyze(bankroll, lines):
        flag = "  ✅ VALOR" if r["value"] else "  —"
        print(f"{r['market']:<14}{r['sel']:<16}{100*r['p_model']:>6.0f}%{r['implicita']:>7.0f}%{r['odds']:>7.2f}{r['EV%']:>7.1f}{r['stake']:>9.2f}{flag}")
