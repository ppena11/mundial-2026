"""
contexto.py — CONTEXTO DEL TORNEO "hasta hoy" para que el guion diario suene AL DÍA.

Eficiente por diseño: se arma de DATOS QUE YA TENEMOS (predictions_log calificado + track_record
+ champ_today), CERO llamadas extra a APIs de pago. Opcional: 1 titular de noticia REAL del Mundial
(Google News RSS, gratis, con fuente). Claude teje esto en el guion; los datos siguen siendo exactos.

USO:  python contexto.py [--date YYYYMMDD]
"""
import os, json, urllib.parse
try:
    import requests
except ImportError:
    requests = None
try:
    from env_loader import load_env; load_env()
except Exception:
    pass

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PROXY = "https://api.codetabs.com/v1/proxy/?quest="
NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl=es-419&gl=US&ceid=US:es-419"
NEWS_QUERY = ('("Mundial 2026" OR "Copa del Mundo 2026") '
              '(resultado OR gol OR sorpresa OR clasificado OR eliminado OR lesión)')

def _log():
    try:
        return [json.loads(l) for l in open("predictions_log.jsonl", encoding="utf-8") if l.strip()]
    except Exception:
        return []

def noticia_mundial():
    """Top titular REAL del Mundial (Google News RSS). None si no hay nada relevante."""
    if requests is None:
        return None
    import xml.etree.ElementTree as ET
    url = NEWS_RSS.format(q=urllib.parse.quote(NEWS_QUERY))
    raw = None
    for u in (url, PROXY + urllib.parse.quote(url, safe="")):
        try:
            r = requests.get(u, headers=HEAD, timeout=20)
            if r.status_code == 200 and "<item" in r.text:
                raw = r.text; break
        except Exception:
            pass
    if not raw:
        return None
    try:
        root = ET.fromstring(raw)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            src = item.find("source")
            source = (src.text.strip() if src is not None and src.text else "Google News")
            low = title.lower()
            if any(k in low for k in ("mundial", "world cup", "fifa", "2026")):
                if " - " in title:
                    title, source = title.rsplit(" - ", 1)
                return {"title": title.strip(), "source": source.strip()}
    except Exception:
        pass
    return None

def resumen_torneo(target, con_noticia=True):
    """String compacto con lo que ha pasado en el torneo hasta `target` (exclusive)."""
    import daily_digest as dd
    log = [r for r in _log() if r.get("actual") is not None]
    iso = f"{target[0:4]}-{target[4:6]}-{target[6:8]}"
    jugados = [r for r in log if r.get("fecha", "") < iso]
    L = []
    if jugados:
        L.append("CONTEXTO DEL TORNEO HASTA HOY (téjelo para que el guion suene al día; menciona algún "
                 "resultado o sorpresa reciente, SIN inventar nada):")
        recientes = sorted(jugados, key=lambda r: r.get("fecha", ""))[-6:]
        L.append("Resultados recientes: " + " · ".join(
            f"{dd.acc(r['a'])} {r.get('marcador_real','')} {dd.acc(r['b'])}" for r in recientes))
        sorp = [r for r in jugados if not r.get("acierto_1x2") and max(r.get("p1", 0), r.get("p2", 0)) >= 0.6]
        if sorp:
            s = sorp[-1]; fav = s["a"] if s.get("p1", 0) >= s.get("p2", 0) else s["b"]
            L.append(f"Sorpresa reciente: {dd.acc(fav)} era favorito y no ganó "
                     f"({dd.acc(s['a'])} {s.get('marcador_real','')} {dd.acc(s['b'])}).")
        try:
            tr = json.load(open("track_record.json", encoding="utf-8"))
            if tr.get("n", 0) > 0:
                L.append(f"Récord del modelo hasta ahora: {tr['aciertos_1x2']} de {tr['n']} ({tr['tasa_1x2']} por ciento).")
        except Exception:
            pass
    if con_noticia:
        n = noticia_mundial()
        if n:
            L.append(f"Titular real de hoy (fuente {n['source']}): {n['title']}")
    return "\n".join(L)

def dato_curioso(target):
    """Un 'dato curioso' del torneo hasta `target` (incluido), calculado de datos reales. Rota por día. '' si no hay."""
    import daily_digest as dd
    from datetime import date
    iso = f"{target[0:4]}-{target[4:6]}-{target[6:8]}"
    jug = [r for r in _log() if r.get("actual") is not None and r.get("marcador_real") and r.get("fecha", "") <= iso]
    def _gol(r):
        try:
            x, y = r["marcador_real"].split("-"); return int(x), int(y)
        except Exception:
            return None
    cands = []
    if jug:
        tot = nm = 0
        for r in jug:
            g = _gol(r)
            if g: tot += g[0] + g[1]; nm += 1
        if nm:
            cands.append(f"En el Mundial ya se han marcado {tot} goles en {nm} partidos, un promedio de "
                         f"{tot/nm:.1f} por partido.")
        gole = max(jug, key=lambda r: (abs(_gol(r)[0]-_gol(r)[1]) if _gol(r) else -1))
        g = _gol(gole)
        if g and abs(g[0]-g[1]) >= 3:
            cands.append(f"La goleada del torneo hasta ahora: {dd.acc(gole['a'])} {gole['marcador_real']} {dd.acc(gole['b'])}.")
        ups = []
        for r in jug:
            o = r.get("actual")
            if o == "1" and r.get("p1", 1) < 0.40: ups.append((r.get("p1", 1), r["a"]))
            elif o == "2" and r.get("p2", 1) < 0.40: ups.append((r.get("p2", 1), r["b"]))
        if ups:
            p, w = min(ups, key=lambda x: x[0])
            cands.append(f"La mayor sorpresa del Mundial: {dd.acc(w)} ganó cuando la IA le daba solo "
                         f"{round(100*p)} por ciento.")
    try:
        champ = list(json.load(open("champ_today.json", encoding="utf-8"))["campeon"].items())
        dh = [(t, v) for t, v in champ[5:11] if v >= 1.0]
        if dh:
            cands.append(f"El tapado del Mundial: {dd.acc(dh[0][0])} sale campeón en {round(dh[0][1])} de cada 100 "
                         "simulaciones, y casi nadie habla de él.")
    except Exception:
        pass
    if not cands:
        return ""
    try:
        n = (date.fromisoformat(iso) - date(2026, 6, 11)).days
    except Exception:
        n = 0
    return cands[n % len(cands)]

if __name__ == "__main__":
    import sys
    from datetime import date
    t = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    out = resumen_torneo(t)
    print(out or "(sin contexto aún: el torneo no ha empezado o no hay resultados calificados)")
    print("\nDATO CURIOSO:", dato_curioso(t) or "(aún no hay)")
