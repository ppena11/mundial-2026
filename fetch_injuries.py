"""
fetch_injuries.py — scraper GRATIS de lesiones del Mundial 2026 (sin API key).
Fuente: tracker de ESPN (renderizado en servidor, reputado). NO necesita clave ni pago.

QUÉ HACE:
  - Descarga el tracker de lesiones de ESPN.
  - Lo parsea por secciones: "Will miss" (FUERA), "Concerning" (DUDA), "Should play" (juega).
  - Extrae jugador + selección + estado y los traduce a los nombres del modelo (español).
  - Guarda injuries.json en el formato que consume player_layer.py.

USO:
  python fetch_injuries.py            # imprime y guarda injuries.json
  python fetch_injuries.py --print    # solo imprime, no guarda

FRAGILIDAD (honestidad): depende del HTML de ESPN. Si ESPN cambia la maqueta,
hay que reajustar los patrones de abajo (busca 'PATRONES'). El modelo NO se rompe
si esto falla: player_layer usa injuries.json solo si existe.
"""
import sys, json, re
try:
    import requests
except ImportError:
    print("Falta requests:  pip install requests"); sys.exit(1)

URL = ("https://www.espn.com/soccer/story/_/id/48572979/"
       "2026-fifa-world-cup-injuries-tracker-which-stars-miss-latest-info")
HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# alias de nombres de ESPN (inglés) -> inglés del namemap
ESPN_ALIASES = {
    "United States": "United States", "USA": "United States",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    "South Korea": "South Korea", "Czech Republic": "Czech Republic",
}

def _strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).strip()

def scrape():
    html = requests.get(URL, headers=HEAD, timeout=25).text
    # --- PATRONES (ajustar aquí si ESPN cambia la maqueta) ---
    # 3 secciones por estado
    i_out  = html.find("Will miss the World Cup")
    i_doubt= html.find("Concerning")
    i_play = html.find("Should play")
    if min(i_out, i_doubt, i_play) < 0:
        raise RuntimeError("No se hallaron las secciones de ESPN (cambió la maqueta).")

    def status_at(pos):
        if i_out <= pos < i_doubt: return "out"
        if i_doubt <= pos < i_play: return "doubtful"
        return None  # "should play" -> disponible, no nos interesa

    # cada lesionado vive en un <h3> que termina con el enlace del equipo
    nm = json.load(open("namemap.json", encoding="utf-8"))
    en2es = {en: es for es, en in nm.items()}
    en2es["United States"] = "Estados Unidos"

    out = {}
    for m in re.finditer(r"<h3>(.*?)</h3>", html, re.DOTALL):
        block, pos = m.group(1), m.start()
        st = status_at(pos)
        if st is None:
            continue
        # el texto del <h3> es "Jugador, Equipo": separamos por la última coma
        text = _strip_tags(block)
        if "," not in text:
            continue
        player, team_en_raw = (s.strip() for s in text.rsplit(",", 1))
        team_en = ESPN_ALIASES.get(team_en_raw, team_en_raw)
        team_es = en2es.get(team_en)
        if team_es is None or not player:
            continue
        out.setdefault(team_es, [])
        if not any(p["player"] == player for p in out[team_es]):
            out[team_es].append({"player": player, "status": st})
    return out

if __name__ == "__main__":
    import os
    # Si el scraping falla o devuelve vacío, NO rompemos nada ni borramos lo bueno:
    # conservamos el injuries.json anterior (las lesiones de selecciones cambian poco).
    try:
        data = scrape()
    except Exception as e:
        print(f"⚠️  No se pudo leer ESPN ({e}).")
        if os.path.exists("injuries.json"):
            print("   Conservo el injuries.json anterior. El pipeline sigue normal.")
        else:
            print("   No hay injuries.json previo; el modelo correrá sin ajuste por lesiones.")
        sys.exit(0)

    n_players = sum(len(v) for v in data.values())
    if n_players == 0 and os.path.exists("injuries.json"):
        print("⚠️  ESPN devolvió 0 lesiones; conservo el injuries.json anterior."); sys.exit(0)

    print(f"Lesiones halladas: {n_players} jugadores en {len(data)} selecciones (fuente: ESPN, gratis)\n")
    for team in sorted(data):
        fuera = [p["player"] for p in data[team] if p["status"] == "out"]
        duda  = [p["player"] for p in data[team] if p["status"] == "doubtful"]
        print(f"  {team}: FUERA={fuera or '—'}  DUDA={duda or '—'}")
    if "--print" not in sys.argv:
        json.dump(data, open("injuries.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("\n→ injuries.json guardado")
