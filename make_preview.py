"""
make_preview.py — GUÍA COMPLETA DEL MUNDIAL 2026 según la IA (post premium pre-torneo, Substack).
Informativo/educativo. Incorpora los 3 ajustes del sistema:
  - LESIONES (player layer / apply_adjustments)
  - FORMA y LOCALÍA (modelo Dixon-Coles)
  - MERCADO (ensemble modelo+mercado que genera la nube: champ_ensemble.json)

Contenido:
  1) Intro educativa (Claude) — qué es el modelo y sus ajustes.
  2) ¿Quién gana el Mundial? — tabla modelo vs mercado vs ensemble.
  3) Grupo por grupo (los 72 partidos reales): 1X2, marcador más probable, goles esperados y bajas,
     + proyección de quién avanza (puntos esperados). Cada grupo con un análisis corto (Claude).
  4) Disclaimer informativo.

USO: python make_preview.py     (usa los .json más recientes; haz git pull antes para traer el mercado de la nube)
Genera: preview.md y preview.html
"""
import sys, os, json, math, re
import daily_digest as dd
import predict_match as pm
try:
    import requests
except ImportError:
    requests = None
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

BRAND = "aiwithpedro"
DISCLAIMER = ("Contenido informativo y educativo. Son predicciones de un modelo estadístico, no certezas, "
              "y no constituyen consejo de apuestas. El fútbol es hermoso justamente porque sorprende.")

# nombres del modelo (ASCII) -> nombre con acentos para mostrar
DISP = {"Mexico": "México", "Sudafrica": "Sudáfrica", "Canada": "Canadá", "Haiti": "Haití", "Turquia": "Turquía",
        "Paises Bajos": "Países Bajos", "Japon": "Japón", "Tunez": "Túnez", "Belgica": "Bélgica", "Iran": "Irán",
        "Espana": "España", "Arabia Saudi": "Arabia Saudí", "Uzbekistan": "Uzbekistán", "Panama": "Panamá"}
def disp(t): return DISP.get(t, t)

MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
def fecha_corta(utc):
    try:
        d = dd._et(utc); return f"{d.day} {MESES[d.month]}"
    except Exception:
        return ""

AI_PREVIEW_SYS = (
    "Eres el editor de @aiwithpedro, un creador que enseña inteligencia artificial. Escribe la narrativa de una "
    "GUÍA PRE-MUNDIAL 2026 educativa, basada en un modelo estadístico (Dixon-Coles + Montecarlo, 20.000 "
    "simulaciones) ajustado por lesiones y por el mercado. Te doy datos EXACTOS. Devuelve EXCLUSIVAMENTE un objeto "
    "JSON (sin ``` ni texto extra) con estas claves:\n"
    '"titulo": título viral para el post de Substack (máx ~70 caracteres, con gancho, máximo 1 emoji).\n'
    '"intro": 2 o 3 frases que expliquen, simple y enganchador, qué es el modelo y sus tres ajustes (lesiones, '
    "forma y localía, mercado).\n"
    '"grupos": un objeto con una clave por grupo ("A".."L"); cada valor es 1 o 2 frases sobre ese grupo (quién '
    "avanza según el modelo y el duelo clave), educativo y usando los números dados.\n"
    '"cierre": 1 o 2 frases que inviten a seguir el pronóstico diario en TikTok @aiwithpedro y el Substack.\n'
    "Español cercano y educativo, apto para todo público, nada de apuestas. Usa SOLO los datos dados; NO inventes "
    "números. ESCRIBE EN ESPAÑOL CON TODAS LAS TILDES Y SIGNOS CORRECTOS (á, é, í, ó, ú, ñ, ¿, ¡).")

def ai_preview(summary):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return {}
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 2600, "system": AI_PREVIEW_SYS,
                  "messages": [{"role": "user", "content": "Datos del torneo:\n" + summary}]}, timeout=120)
        if r.status_code != 200:
            print(f"(IA preview no disponible: {r.status_code} {r.text[:150]})"); return {}
        txt = r.json()["content"][0]["text"]
        return json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    except Exception as e:
        print(f"(IA preview falló: {e})"); return {}

def _load(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None

def build():
    atk, dfn, c, g, rho = pm.fit_model(); sq = pm.apply_adjustments(atk, dfn)
    def bajas(t): return [n for n, w, av in sq.get(t, {}).get("key_players", []) if not av]

    # mercado por partido (suele estar escaso antes del torneo)
    mkt = {}
    try:
        import fetch_odds
        for ev in fetch_odds.h2h():
            pe = {dd.EN2ES.get(k, k): v for k, v in ev["clean_probs"].items()}
            ts = [t for t in pe if t != "Draw"]
            if len(ts) == 2: mkt[frozenset(ts)] = pe
    except Exception as e:
        print(f"(sin cuotas de partido: {e})")

    champ_model = (_load("champ_today.json") or {}).get("campeon", {})
    ens = _load("champ_ensemble.json") or {}

    # agrupar los partidos de fase de grupos (equipos reales)
    groups = {}
    for m in dd.fetch_all():
        a, b = m["a"], m["b"]
        ga, gb = dd.TEAM2GROUP.get(a), dd.TEAM2GROUP.get(b)
        if ga and ga == gb and a in pm.MAP and b in pm.MAP:
            groups.setdefault(ga, []).append(m)

    GD = {}
    for gname in sorted(groups):
        ms = sorted(groups[gname], key=lambda x: x["utc"])
        pts = {t: 0.0 for t in dd.GROUPS.get(gname, [])}
        rows = []
        for m in ms:
            a, b = m["a"], m["b"]
            pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=True)
            pts[a] = pts.get(a, 0) + 3*pw + pdr
            pts[b] = pts.get(b, 0) + 3*pl + pdr
            mp = mkt.get(frozenset((a, b)))
            rows.append({"m": m, "a": a, "b": b, "pw": pw, "pdr": pdr, "pl": pl, "lh": lh, "la": la,
                         "sx": sx, "sy": sy, "ba": bajas(a), "bb": bajas(b), "mp": mp})
        rank = sorted(pts, key=lambda t: pts[t], reverse=True)
        GD[gname] = {"rows": rows, "rank": rank, "pts": pts}
    return champ_model, ens, GD

def render():
    champ_model, ens, GD = build()
    ens_top = list(ens.get("ensemble", {}).items())[:8]

    # ---- resumen exacto para Claude ----
    sm = ["Guía pre-Mundial 2026. Modelo Dixon-Coles + Montecarlo (20.000 sims).",
          "Los TRES ajustes son: 1) LESIONES (bajas de jugadores clave que debilitan a su selección); "
          "2) FORMA reciente y ventaja de LOCALÍA (lo calcula el propio modelo); "
          "3) MERCADO: las CUOTAS de las casas de apuestas, combinadas con el modelo en un 'ensemble' (50/50). "
          "OJO: el ajuste de mercado son CUOTAS, NO valores de fichaje de jugadores."]
    if ens_top:
        sm.append("Campeón (ensemble modelo+mercado): " + ", ".join(f"{t} {v} por ciento" for t, v in ens_top[:5]) + ".")
    elif champ_model:
        sm.append("Campeón (modelo): " + ", ".join(f"{t} {v} por ciento" for t, v in list(champ_model.items())[:5]) + ".")
    for gname in sorted(GD):
        r = GD[gname]["rank"]
        eq = ", ".join(dd.GROUPS.get(gname, []))
        sm.append(f"Grupo {gname}: {eq}. Avanzan (proyección por puntos esperados): {r[0]} y {r[1]}.")
    ai = ai_preview("\n".join(sm))
    grp_txt = ai.get("grupos", {}) if isinstance(ai.get("grupos"), dict) else {}

    # ---------- MARKDOWN ----------
    md = ["# 🏆 Guía completa del Mundial 2026 — según la IA",
          f"#### Pronóstico informativo de @{BRAND} · modelo + lesiones + mercado · todos los partidos de grupos\n"]
    if ai.get("intro"):
        md.append(ai["intro"].strip()); md.append("")
    md.append("> 🤖 **Cómo se hace:** un modelo estadístico (Dixon-Coles + Poisson) aprende la fuerza de cada "
              "selección con ~49.000 partidos, corre **20.000 simulaciones** del torneo y ajusta por **lesiones**, "
              "**forma/localía** y el **mercado**. Aquí están sus mejores predicciones. _Solo información y educación._")
    md.append("")

    # ---- cómo leer (para quien no sabe de probabilidades) ----
    md.append("## 📖 Cómo leer estas predicciones (en 30 segundos)")
    md.append("- **El % de un equipo** = de cada 100 mundiales simulados, en cuántos gana. Ej.: 84% = gana 84 de cada 100… pero pierde 16. **Nada está garantizado.**")
    md.append("- **Empate %** = probabilidad de que terminen iguales (en grupos sí hay empates).")
    md.append("- **🎯 Marcador probable** = el resultado que más se repite en las simulaciones (no el único posible).")
    md.append("- **Goles esperados** = cuántos goles, en promedio, se espera que marque cada equipo.")
    md.append("- **Ensemble (modelo + mercado)** = mezclamos nuestro modelo con las casas de apuestas; suele ser más preciso que cualquiera por separado.")
    md.append("- **Avanzan** = los **2 primeros** de cada grupo pasan directo; el 3º puede colarse como **mejor tercero**.")
    md.append("- ⚠️ **Son probabilidades, no certezas.** Si el favorito al 84% pierde, el modelo no \"falló\": ese 16% también existía. Por eso publicamos los aciertos **y** los fallos cada día.")
    md.append("")

    # ---- campeón: modelo vs mercado vs ensemble ----
    md.append("## 🥇 ¿Quién gana el Mundial? (modelo vs mercado)")
    if ens_top:
        md.append("El **ensemble** combina nuestro modelo con las casas (corrige el sesgo del modelo hacia los outsiders):\n")
        rowshtml = ["<table style='border-collapse:collapse;width:100%;font-size:14px'>"
                    "<tr style='background:#0e8a5f;color:#fff'><th style='padding:6px;text-align:left'>Selección</th>"
                    "<th style='padding:6px'>Modelo</th><th style='padding:6px'>Mercado</th><th style='padding:6px'>Ensemble</th></tr>"]
        modd, merd = ens.get("modelo", {}), ens.get("mercado", {})
        for i, (t, v) in enumerate(ens_top):
            mk = merd.get(t)
            mk = "—" if (mk is None or (isinstance(mk, float) and math.isnan(mk))) else f"{mk:.1f}%"
            bg = "#f3f7f4" if i % 2 else "#ffffff"
            rowshtml.append(f"<tr style='background:{bg}'><td style='padding:6px'><b>{i+1}. {disp(t)}</b></td>"
                            f"<td style='padding:6px;text-align:center'>{modd.get(t,'—')}%</td>"
                            f"<td style='padding:6px;text-align:center'>{mk}</td>"
                            f"<td style='padding:6px;text-align:center'><b>{v}%</b></td></tr>")
        rowshtml.append("</table>")
        md.append("".join(rowshtml))
        # versión texto (para el .md)
        md.append("")
        for i, (t, v) in enumerate(ens_top):
            md.append(f"- {i+1}. **{disp(t)}** — ensemble **{v}%** (modelo {ens.get('modelo',{}).get(t,'—')}%)")
    elif champ_model:
        md.append("_(El ensemble con mercado no está disponible ahora; mostramos el modelo.)_\n")
        for i, (t, v) in enumerate(list(champ_model.items())[:8]):
            md.append(f"- {i+1}. **{disp(t)}** — {v}%")
    md.append("")

    # ---- grupo por grupo ----
    md.append("## ⚽ Grupo por grupo — los 72 partidos")
    md.append("_El % es probabilidad de ganar según el modelo. 🎯 = marcador más probable. Goles esp. = goles esperados._\n")
    for gname in sorted(GD):
        d = GD[gname]; r = d["rank"]; pts = d["pts"]
        md.append(f"### Grupo {gname}")
        if grp_txt.get(gname):
            md.append(grp_txt[gname].strip())
        # proyección de tabla
        proj = "  ·  ".join(f"{i+1}. {disp(t)} ({pts[t]:.1f})" for i, t in enumerate(r))
        md.append(f"**Proyección** (puntos esperados en 3 partidos): {proj}")
        md.append(f"➡️ **Avanzan según el modelo: {disp(r[0])} y {disp(r[1])}** _(el 3º pelea un cupo de mejores terceros)._\n")
        for x in d["rows"]:
            m = x["m"]; a, b = x["a"], x["b"]; da, db = disp(a), disp(b)
            fav, fp = (da, x["pw"]) if x["pw"] >= x["pl"] else (db, x["pl"])
            md.append(f"- **{fecha_corta(m['utc'])} · {dd.hora_et(m['utc'])} · {da} vs {db}**")
            md.append(f"  - 1X2: {da} **{x['pw']:.0%}** · empate {x['pdr']:.0%} · {db} **{x['pl']:.0%}**")
            md.append(f"  - 🎯 Marcador probable: **{x['sx']}-{x['sy']}** · goles esp. {x['lh']:.1f}–{x['la']:.1f}")
            bj = []
            if x["ba"]: bj.append(f"{da}: {', '.join(x['ba'][:3])}")
            if x["bb"]: bj.append(f"{db}: {', '.join(x['bb'][:3])}")
            if bj: md.append(f"  - ⚠️ Bajas: " + " · ".join(bj))
            if x["mp"]:
                ma, mb = x["mp"].get(a), x["mp"].get(b)
                if ma and x["pw"] > ma * 1.2 and x["pw"] >= 0.2:
                    md.append(f"  - 💎 Valor: el modelo ve a **{da}** más fuerte que el mercado ({x['pw']:.0%} vs {ma:.0%})")
                elif mb and x["pl"] > mb * 1.2 and x["pl"] >= 0.2:
                    md.append(f"  - 💎 Valor: el modelo ve a **{db}** más fuerte que el mercado ({x['pl']:.0%} vs {mb:.0%})")
        md.append("")

    if ai.get("cierre"):
        md.append("---")
        md.append(ai["cierre"].strip())
    md.append("---")
    md.append(f"🎬 Pronóstico **diario** en mi TikTok **@{BRAND}** · 📩 resumen semanal por correo.")
    md.append(f"_{DISCLAIMER}_")
    text = "\n".join(md)

    # ---------- HTML ----------
    def b(s): return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s).replace("_", "")
    html = []
    for ln in md:
        s = ln.rstrip()
        if s.startswith("<table") or s.startswith("</table") or s.startswith("<tr") or s.startswith("<td") or s.startswith("<th"):
            html.append(ln); continue
        if s.startswith("#### "): html.append(f"<p style='color:#5566aa;margin:0 0 12px;font-size:14px'>{b(s[5:])}</p>")
        elif s.startswith("### "): html.append(f"<h3 style='color:#0e8a5f;margin:18px 0 4px'>{b(s[4:])}</h3>")
        elif s.startswith("## "): html.append(f"<h2 style='color:#1f3b8b;margin:22px 0 6px'>{b(s[3:])}</h2>")
        elif s.startswith("# "): html.append(f"<h1 style='margin:0'>{b(s[2:])}</h1>")
        elif s.startswith("> "): html.append(f"<blockquote style='background:#eef6f1;border-left:4px solid #0e8a5f;margin:8px 0;padding:8px 12px;border-radius:6px'>{b(s[2:])}</blockquote>")
        elif s.startswith("  - "): html.append(f"<p style='margin:1px 0 1px 18px;color:#22324a'>{b(s[4:])}</p>")
        elif s.startswith("- "): html.append(f"<p style='margin:6px 0 1px'>{b(s[2:])}</p>")
        elif s.strip() == "---": html.append("<hr style='border:none;border-top:1px solid #d9deec;margin:14px 0'>")
        elif s.strip(): html.append(f"<p style='margin:6px 0'>{b(s)}</p>")
    html_doc = ("<div style='font-family:Arial,Helvetica,sans-serif;max-width:680px;margin:auto;"
                "color:#0b1437;padding:8px 14px;line-height:1.5'>" + "".join(html) + "</div>")

    titulo = (ai.get("titulo") or "").strip() or "Guía del Mundial 2026 según la IA: predicciones de toda la fase de grupos"
    n_matches = sum(len(GD[g]["rows"]) for g in GD)
    return text, html_doc, n_matches, (disp(ens_top[0][0]) if ens_top else disp(next(iter(champ_model), "—"))), titulo

if __name__ == "__main__":
    text, html, n, fav, titulo = render()
    open("preview.md", "w", encoding="utf-8").write(text)
    open("preview.html", "w", encoding="utf-8").write(html)
    print(text[:1200])
    print(f"\n... [recortado] ...")
    print(f"\n📌 Título sugerido para Substack: {titulo}")
    print(f"\n→ preview.md y preview.html guardados ({n} partidos de grupos · favorito: {fav})")
