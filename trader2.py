import json,math
mkts=json.load(open("markets.json",encoding="utf-8"))
champ={t:mkts[t]["champ"] for t in mkts}

# ---- CUOTAS DE MERCADO (campeón, varias casas, jun 2026) en formato decimal ----
# (cuotas ilustrativas de mercado actual; el método es lo que importa)
odds={"Espana":6.5,"Francia":7.0,"Inglaterra":8.0,"Argentina":11.0,"Brasil":12.0,"Portugal":13.0,
"Alemania":17.0,"Paises Bajos":21.0,"Belgica":34.0,"Uruguay":67.0,"Colombia":67.0,"Croacia":81.0,
"Marruecos":81.0,"Mexico":51.0,"Estados Unidos":67.0,"Japon":101.0,"Senegal":81.0,"Suiza":81.0,
"Ecuador":151.0,"Noruega":67.0,"Dinamarca":126.0,"Austria":151.0,"Corea del Sur":201.0}

# ---- (4) DE-VIG: quitar el margen para obtener la prob. IMPLÍCITA LIMPIA ----
# Método multiplicativo (estándar de la industria): prob_limpia = (1/cuota) / overround
raw={t:1/o for t,o in odds.items()}
overround=sum(raw.values())
clean={t:raw[t]/overround for t in raw}
print(f"=== (4) DE-VIG ===")
print(f"Overround del mercado (margen): {100*(overround-1):.1f}%  (suma cruda {100*overround:.1f}%)")
print(f"-> Las cuotas crudas suman >100%: esa diferencia es la comisión de la casa, no probabilidad.\n")

# ---- (2) SESGO FAVORITO-LONGSHOT: ¿el mercado limpio infla longshots vs el modelo? ----
print("=== (2) SESGO FAVORITO-LONGSHOT (modelo vs mercado limpio) ===")
print(f"{'Equipo':<13}{'Modelo':>8}{'Mkt limpio':>12}{'Cuota':>8}   lectura")
fav=sorted(odds,key=lambda t:odds[t])
for t in fav[:12]:
    if t not in champ:continue
    m=champ[t]*100;cl=clean[t]*100
    if m>cl*1.25: rd="modelo MÁS alto (posible value)"
    elif cl>m*1.25: rd="mercado más alto (longshot inflado/sabe algo)"
    else: rd="≈ alineados"
    print(f"{t:<13}{m:>7.1f}%{cl:>11.1f}%{odds[t]:>8.0f}   {rd}")

# ---- (1+5) VALUE REAL: EV con de-vig, NO contra cuota cruda ----
print("\n=== (1) VALUE REAL (EV) — comparando con MERCADO LIMPIO, no con cuota cruda ===")
print("EV = prob_modelo × cuota − 1.  Pero ajustamos: solo es value si supera el margen.")
print(f"{'Equipo':<13}{'p_mod':>7}{'cuota':>7}{'EV_bruto':>10}{'¿value real?':>16}")
rows=[]
for t in fav:
    if t not in champ:continue
    p=champ[t];o=odds[t];ev=p*o-1
    # value real: la prob del modelo debe superar la prob limpia (no la cruda) con margen de seguridad
    real = p > clean[t]*1.10
    rows.append((t,p,o,ev,real))
for t,p,o,ev,real in sorted(rows,key=lambda x:-x[3])[:10]:
    print(f"{t:<13}{100*p:>6.1f}%{o:>7.0f}{ev:>+9.2f}{'★ SÍ' if real else 'no':>16}")

# ---- sesgo favorito-longshot agregado ----
print("\n=== Diagnóstico agregado del sesgo ===")
longshots=[t for t in odds if odds[t]>=50 and t in champ]
favs=[t for t in odds if odds[t]<15 and t in champ]
lm=sum(champ[t] for t in longshots);lc=sum(clean[t] for t in longshots)
fm=sum(champ[t] for t in favs);fc=sum(clean[t] for t in favs)
print(f"Longshots (cuota≥50): modelo {100*lm:.1f}% vs mkt limpio {100*lc:.1f}%  -> mercado los {'INFLA' if lc>lm else 'acorta'}")
print(f"Favoritos (cuota<15): modelo {100*fm:.1f}% vs mkt limpio {100*fc:.1f}%  -> mercado los {'acorta' if fc<fm else 'infla'}")
