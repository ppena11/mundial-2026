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

if __name__ == "__main__":
    import sys
    from datetime import date
    t = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    out = resumen_torneo(t)
    print(out or "(sin contexto aún: el torneo no ha empezado o no hay resultados calificados)")
