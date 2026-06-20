"""
make_weekly.py — bloque RESUMEN SEMANAL del Mundial para tu email de Substack.
Lo pegas dentro del correo semanal (junto a tu contenido de IA). Tono familiar, sin apuestas.

Incluye:
  - Cómo nos fue (aciertos de la semana, del track_record)
  - Mejores aciertos de la semana (incluida alguna sorpresa bien clavada)
  - La carrera por el título hoy
  - Los partidos clave de la próxima semana (con el favorito del modelo)

USO: python make_weekly.py [--date YYYYMMDD]   (por defecto: hoy; el --date fija "el lunes")
Genera: weekly.md y weekly.html
"""
import sys, os, json
from datetime import datetime, timedelta, date
import daily_digest as dd
import predict_match as pm
import track_record as tr
try:
    import requests
except ImportError:
    requests = None

BRAND = "aiwithpedro"

AI_WEEKLY_SYS = (
    "Eres el editor de @aiwithpedro, un creador que enseña inteligencia artificial. Con los datos de la SEMANA "
    "del Mundial 2026, devuelve EXCLUSIVAMENTE un objeto JSON (sin ``` ni texto extra) con estas claves:\n"
    '"titulo": título viral para el resumen semanal (máx ~70 caracteres, con gancho, máximo 1 emoji).\n'
    '"intro": 1 o 2 frases de apertura que resuman la semana y enganchen (cómo le fue al modelo, el dato más jugoso).\n'
    '"cierre": 1 frase motivadora que invite a seguir el pronóstico diario en el canal de YouTube @aiwithpedro y el Substack.\n'
    "Español, cercano y enérgico, apto para todo público, nada de apuestas. Usa SOLO los datos dados; NO inventes números. "
    "ESCRIBE EN ESPAÑOL CON TODAS LAS TILDES Y SIGNOS CORRECTOS (á, é, í, ó, ú, ñ, ¿, ¡).")

def ai_weekly(summary):
    """Claude redacta titulo + intro + cierre virales del semanal. {} si no hay key."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return {}
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")  # texto corto: Haiku = barato
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 500, "system": AI_WEEKLY_SYS,
                  "messages": [{"role": "user", "content": "Datos de la semana:\n" + summary}]}, timeout=45)
        if r.status_code != 200:
            print(f"(IA semanal no disponible: {r.status_code})"); return {}
        txt = r.json()["content"][0]["text"]
        return json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    except Exception as e:
        print(f"(IA semanal falló: {e})"); return {}

def build(today_str):
    today = datetime.strptime(today_str, "%Y%m%d").date()
    wk_start = today - timedelta(days=7)
    nxt_end = today + timedelta(days=7)

    # --- récord de la semana (del log calificado) ---
    log = [r for r in tr.load_log()
           if r.get("actual") is not None and wk_start.isoformat() <= r["fecha"] < today.isoformat()]
    n = len(log); hits = sum(1 for r in log if r.get("acierto_1x2"))
    correct = [r for r in log if r.get("acierto_1x2")]
    def conf(r): return max(r["p1"], r["p2"])
    # "sorpresa bien clavada": acertó y el favorito del modelo no era claro (<55%)
    surprises = sorted([r for r in correct if conf(r) < 0.55], key=lambda r: conf(r))
    confident = sorted(correct, key=conf, reverse=True)

    # --- campeón ---
    try:
        champ = list(json.load(open("champ_today.json", encoding="utf-8"))["campeon"].items())[:5]
    except Exception:
        champ = []

    # --- próximos partidos clave (7 días) ---
    atk, dfn, c, g, rho = pm.fit_model(); pm.apply_adjustments(atk, dfn)
    topnames = {t for t, _ in champ[:8]}
    upcoming = []
    for m in dd.fetch_all():
        ed = dd.et_date(m["utc"])
        if not (today.isoformat() <= ed < nxt_end.isoformat()): continue
        a, b = m["a"], m["b"]
        if a not in pm.MAP or b not in pm.MAP: continue
        pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=True)
        fav, fp = (a, pw) if pw >= pl else (b, pl)
        key = (a in topnames or b in topnames) or m["is_ko"]
        upcoming.append({"ed": ed, "m": m, "a": a, "b": b, "fav": fav, "fp": fp, "key": key})
    upcoming.sort(key=lambda x: x["m"]["utc"])
    claves = [u for u in upcoming if u["key"]][:6] or upcoming[:6]

    # ---------- texto ----------
    rng = f"{wk_start.strftime('%d/%m')} al {(today-timedelta(days=1)).strftime('%d/%m')}"

    # ---- resumen de datos para Claude ----
    destac = (surprises[:1] + confident[:2]) if surprises else confident[:2]
    sm = [f"Semana del {rng}."]
    if n > 0:
        sm.append(f"Récord: {hits} de {n} aciertos ({round(100*hits/n)} por ciento).")
        for r in destac:
            sm.append(f"Acertó {r['a']} contra {r['b']} ({r.get('marcador_real','')}).")
    if champ:
        sm.append("Campeón: " + ", ".join(f"{t} {v} por ciento" for t, v in champ[:3]) + ".")
    for u in claves[:4]:
        sm.append(f"Próximo clave: {u['a']} contra {u['b']}, favorito {u['fav']} {round(100*u['fp'])} por ciento.")
    aw = ai_weekly("\n".join(sm))
    titulo = (aw.get("titulo") or "").strip()

    # ---- armado (Claude pone lo viral; los datos van exactos) ----
    head = titulo or "⚽ El Mundial con IA — resumen de la semana"
    md = [f"## {head}", f"_Semana {rng}_\n"]
    if aw.get("intro"):
        md.append(aw["intro"].strip()); md.append("")

    if n > 0:
        md.append("### 📈 ¿Cómo nos fue?")
        md.append(f"El modelo acertó **{hits} de {n}** partidos esta semana (**{100*hits/n:.0f}%**).")
        seen = set()
        for r in destac:
            if r["key"] in seen: continue
            seen.add(r["key"])
            md.append(f"- ✅ Le acertamos a **{r['a']} vs {r['b']}** ({r.get('marcador_real','')}).")
        md.append("")

    if champ:
        medals = ["🥇","🥈","🥉"]
        parts = [f"{medals[i] if i<3 else '•'} {t} {v:.1f}%" for i,(t,v) in enumerate(champ)]
        md.append("### 🏆 La carrera por el título")
        md.append("- " + "  ".join(parts))
        md.append("")

    if claves:
        md.append("### 🔮 Lo que viene (partidos clave)")
        for u in claves:
            md.append(f"- **{u['ed'][8:10]}/{u['ed'][5:7]} · {dd.hora_et(u['m']['utc'])}** · "
                      f"{u['a']} vs {u['b']} — favorita **{u['fav']} ({u['fp']:.0%})**")
        md.append("")

    if aw.get("cierre"):
        md.append(f"_{aw['cierre'].strip()}_")
    else:
        md.append(f"_Sigue el pronóstico **diario** en mi **canal de YouTube @{BRAND}** y en el archivo del Substack._")
    md.append(f"_Contenido informativo y de entretenimiento. Predicciones de un modelo, no certezas._")
    text = "\n".join(md)

    import re
    def b(s): return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s).replace("_","")
    html = []
    for ln in md:
        if ln.startswith("### "): html.append(f"<h3>{b(ln[4:])}</h3>")
        elif ln.startswith("## "): html.append(f"<h2>{b(ln[3:])}</h2>")
        elif ln.startswith("- "): html.append(f"<p style='margin:3px 0'>{b(ln[2:])}</p>")
        elif ln.strip(): html.append(f"<p style='margin:4px 0'>{b(ln)}</p>")
    html_doc = "<div style='font-family:Arial,sans-serif;max-width:640px;color:#0b1437'>" + "".join(html) + "</div>"
    return text, html_doc, n, len(claves), titulo

if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    text, html, n, k, titulo = build(target)
    open("weekly.md","w",encoding="utf-8").write(text)
    open("weekly.html","w",encoding="utf-8").write(html)
    print(text)
    if titulo:
        print(f"\n📌 Título sugerido: {titulo}")
    print(f"\n→ weekly.md y weekly.html guardados ({n} partidos calificados, {k} clave próximos)")
