"""
backtest_tournament.py — valida la SIMULACIÓN COMPLETA (todas las herramientas) contra los
resultados reales de los Mundiales 2010/2014/2018/2022, en TODAS las etapas incluido el campeón.

Para cada Mundial: entrena el modelo Dixon-Coles SOLO con partidos previos, y corre la misma
maquinaria que el pipeline diario —desempates FIFA (head-to-head), binomial negativa (colas),
nivel de goles mundialista (WC_GOAL_LEVEL), ventaja del anfitrión— sobre el formato real de 32
equipos (8 grupos, bracket estándar). Luego compara las probabilidades por etapa y de campeón
contra lo que ocurrió REALMENTE.

Notas honestas:
  - Es una predicción PRE-torneo (no condiciona a resultados reales; mide la calidad del pronóstico).
  - Las capas de sede (altura/calor/viaje) van apagadas aquí: no hay datos de sede de Mundiales
    pasados. Se valida el motor + DC + NB + nivel de goles + desempates + anfitrión.
  - Grupos/bracket/etapas reales salen de openfootball (no se inventan); los campeones son hechos.

Métricas (menor = mejor salvo donde se indique):
  - Campeón: −log P(campeón real)  y  ranking del campeón real en P(campeón).
  - Por etapa (R16/QF/SF/Final): Brier y log-loss de P(llegar) sobre los 32 participantes.

Uso:  python backtest_tournament.py [K]      (K = nº de simulaciones, def. 20000)
"""
import json, math, random, sys, urllib.request
import fit_dc, format_engine as fe, context_factors as cf

WC_START = {2010: "2010-06-11", 2014: "2014-06-12", 2018: "2018-06-14", 2022: "2022-11-20"}
HOST = {2010: "South Africa", 2014: "Brazil", 2018: "Russia", 2022: "Qatar"}
CHAMPION = {2010: "Spain", 2014: "Germany", 2018: "France", 2022: "Argentina"}  # hechos
# bracket estándar de 32 equipos (posición, grupo) — fijo en todos los Mundiales 1998-2022
R16 = [("1", "A", "2", "B"), ("1", "C", "2", "D"), ("1", "E", "2", "F"), ("1", "G", "2", "H"),
       ("1", "B", "2", "A"), ("1", "D", "2", "C"), ("1", "F", "2", "E"), ("1", "H", "2", "G")]
# alias openfootball -> nombres del dataset martj42 (results.csv)
ALIAS = {"China PR": "China", "Korea Republic": "South Korea", "IR Iran": "Iran",
         "USA": "United States", "Czech Republic": "Czechia",
         "Côte d'Ivoire": "Ivory Coast", "Bosnia-Herzegovina": "Bosnia and Herzegovina"}


def load_wc(year):
    d = json.load(urllib.request.urlopen(
        f"https://raw.githubusercontent.com/openfootball/worldcup.json/master/{year}/worldcup.json", timeout=30))
    ms = d["matches"]
    def nm(t): return ALIAS.get(t, t)
    groups = {}
    for m in ms:
        gp = m.get("group")
        if gp and gp.startswith("Group"):
            groups.setdefault(gp.split()[1], set()).update([nm(m["team1"]), nm(m["team2"])])
    def teams_in(rounds):
        s = set()
        for m in ms:
            if m.get("round") in rounds:
                s.update([nm(m["team1"]), nm(m["team2"])])
        return s
    actual = {"R16": teams_in({"Round of 16"}),
              "QF": teams_in({"Quarter-final", "Quarter-finals"}),
              "SF": teams_in({"Semi-final", "Semi-finals"}),
              "Final": teams_in({"Final"})}
    return {L: sorted(ts) for L, ts in groups.items()}, actual


def fit_pre(year):
    rows = fit_dc.load("1990-01-01", f"{year}-12-31", with_tournament=True)
    return fit_dc.fit(fit_dc.build([r for r in rows if r[0] < WC_START[year]], WC_START[year]))


def simulate(groups, M, host, K):
    ti = {t: i for i, t in enumerate(M["teams"])}; O = M["OTH"]
    c, g, rho = M["c"], M["g"], M["rho"]; atk, dfn = M["atk"], M["dfn"]
    MU = cf.WC_GOAL_LEVEL
    def gm(a, b):
        ia, ib = ti.get(a, O), ti.get(b, O)
        lh = math.exp(c + atk[ia] - dfn[ib] + (g if a == host else 0)) * MU
        la = math.exp(c + atk[ib] - dfn[ia] + (g if b == host else 0)) * MU
        ga, gb = fe.sample_score(lh, la, rho, dispersion_r=cf.DISPERSION_R)
        if ga == gb:
            return a if random.random() < lh / (lh + la) else b
        return a if ga > gb else b
    teams = [t for L in groups for t in groups[L]]
    champ = {t: 0 for t in teams}
    reach = {s: {t: 0 for t in teams} for s in ("R16", "QF", "SF", "Final")}
    for _ in range(K):
        pos = {}
        for L, T in groups.items():
            gms = []
            for i in range(4):
                for j in range(i + 1, 4):
                    a, b = T[i], T[j]
                    ia, ib = ti.get(a, O), ti.get(b, O)
                    lh = math.exp(c + atk[ia] - dfn[ib] + (g if a == host else 0)) * MU
                    la = math.exp(c + atk[ib] - dfn[ia] + (g if b == host else 0)) * MU
                    ga, gb = fe.sample_score(lh, la, 0.0, dispersion_r=cf.DISPERSION_R)
                    gms.append((a, b, ga, gb))
            order = fe.rank_group(T, gms)
            pos[L] = (order[0], order[1])
        r16t = [pos[L][0] for L in groups] + [pos[L][1] for L in groups]
        for t in r16t: reach["R16"][t] += 1
        r16w = [gm(pos[L1][0 if p1 == "1" else 1], pos[L2][0 if p2 == "1" else 1]) for p1, L1, p2, L2 in R16]
        for t in r16w: reach["QF"][t] += 1
        qfw = [gm(r16w[i], r16w[i + 1]) for i in range(0, 8, 2)]
        for t in qfw: reach["SF"][t] += 1
        sfw = [gm(qfw[i], qfw[i + 1]) for i in range(0, 4, 2)]
        for t in sfw: reach["Final"][t] += 1
        champ[gm(sfw[0], sfw[1])] += 1
    P = lambda d: {t: d[t] / K for t in d}
    return P(champ), {s: P(reach[s]) for s in reach}, teams


def metrics(year, K):
    groups, actual = load_wc(year)
    M = fit_pre(year)
    pchamp, preach, teams = simulate(groups, M, HOST[year], K)
    res = {"year": year, "champion_real": CHAMPION[year]}
    pc = pchamp.get(CHAMPION[year], 0.0)
    res["champ_logloss"] = -math.log(max(pc, 1e-9))
    res["champ_prob"] = pc
    res["champ_rank"] = 1 + sum(1 for t in pchamp if pchamp[t] > pc)
    for s in ("R16", "QF", "SF", "Final"):
        ys = {t: (1.0 if t in actual[s] else 0.0) for t in teams}
        n = len(teams)
        res[f"{s}_brier"] = sum((preach[s][t] - ys[t]) ** 2 for t in teams) / n
        res[f"{s}_logloss"] = -sum(ys[t] * math.log(max(preach[s][t], 1e-9)) +
                                   (1 - ys[t]) * math.log(max(1 - preach[s][t], 1e-9)) for t in teams) / n
    # top-5 favoritos al título (para inspección)
    res["top5"] = sorted(pchamp.items(), key=lambda x: -x[1])[:5]
    return res


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20000
    print(f"Backtest de torneo COMPLETO (todas las herramientas), K={K} sims por Mundial\n")
    allr = []
    for y in (2010, 2014, 2018, 2022):
        r = metrics(y, K); allr.append(r)
        print(f"=== {y}  (campeón real: {r['champion_real']}) ===")
        print(f"  Campeón: P(real)={r['champ_prob']:.1%}  ranking del real={r['champ_rank']}/32  −logP={r['champ_logloss']:.3f}")
        print(f"  Top-5 modelo: " + ", ".join(f"{t} {p:.0%}" for t, p in r["top5"]))
        print(f"  Brier por etapa:  R16={r['R16_brier']:.3f}  QF={r['QF_brier']:.3f}  SF={r['SF_brier']:.3f}  Final={r['Final_brier']:.3f}")
        print()
    n = len(allr)
    print("PROMEDIO sobre los 4 Mundiales:")
    print(f"  Campeón: −logP(real)={sum(r['champ_logloss'] for r in allr)/n:.3f}  "
          f"(baseline uniforme 1/32 = {math.log(32):.3f})  | ranking medio del campeón real = "
          f"{sum(r['champ_rank'] for r in allr)/n:.1f}/32")
    for s in ("R16", "QF", "SF", "Final"):
        print(f"  {s:<6} Brier={sum(r[f'{s}_brier'] for r in allr)/n:.3f}  logloss={sum(r[f'{s}_logloss'] for r in allr)/n:.3f}")
    json.dump([{k: v for k, v in r.items() if k != "top5"} for r in allr],
              open("backtest_tournament.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n→ backtest_tournament.json guardado")
