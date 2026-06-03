"""
make_script.py — GUION HABLADO del día para ElevenLabs (tu voz) + caption para TikTok.
Texto natural en español (sin símbolos ni emojis, para que ElevenLabs lo lea limpio):
  hook + lo más importante de la infografía + CTA.

USO: python make_script.py [--date YYYYMMDD]
Genera: voiceover.txt (para pegar en ElevenLabs) y caption.txt (descripción + hashtags TikTok).
Flujo: voiceover.txt -> ElevenLabs (tu voz) -> voice.mp3 -> make_reel.py -> matchday.mp4
"""
import sys, os, json
from datetime import date
import daily_digest as dd
import predict_match as pm
try:
    import requests
except ImportError:
    requests = None

BRAND = "aiwithpedro"
VAL_MARGIN, VAL_FLOOR = 1.20, 0.20

def pct(x): return f"{round(100*x)} por ciento"

# nombres con espacios/acentos -> hashtag limpio
_TAG = {"Estados Unidos":"USA","Corea del Sur":"Corea","Arabia Saudi":"ArabiaSaudita",
        "Paises Bajos":"PaisesBajos","Nueva Zelanda":"NuevaZelanda","Cabo Verde":"CaboVerde",
        "Costa de Marfil":"CostaDeMarfil","R.D. Congo":"Congo","Sudafrica":"Sudafrica"}
def _tag(team): return "#" + _TAG.get(team, team.replace(" ", ""))

def _summary(fh, played, pick, clearest, tr):
    """Resumen de datos del día que se le pasa a Claude para que redacte el guion."""
    L = [f"Fecha: {fh}."]
    if not played:
        L.append("Hoy no hay partidos del Mundial (el torneo arranca el 11 de junio).")
        return "\n".join(L)
    L.append("Partidos de hoy y favorito del modelo:")
    for d in played:
        L.append(f"- {d['a']} contra {d['b']}: favorito {d['fav']} con {round(100*d['fp'])} por ciento.")
    if pick:
        t, mpb, mkp, edge = pick[1]
        L.append(f"Jugada de valor del día: {t} (el modelo le da {round(100*mpb)} por ciento y el mercado solo {round(100*mkp)} por ciento; está infravalorada).")
    if clearest:
        L.append(f"Resultado más claro: {clearest['fav']} con {round(100*clearest['fp'])} por ciento en {clearest['a']} contra {clearest['b']}.")
    if tr.get("n", 0) > 0:
        L.append(f"Historial del modelo: {tr['aciertos_1x2']} aciertos de {tr['n']} ({tr['tasa_1x2']} por ciento).")
    return "\n".join(L)

AI_SYSTEM = (
    "Eres el guionista de @aiwithpedro, un creador que enseña inteligencia artificial. Escribes el GUION "
    "HABLADO de un video corto de TikTok (35 a 45 segundos, 90 a 120 palabras) sobre los pronósticos del "
    "Mundial 2026 que hace su propia IA. Estilo: cercano, enérgico, claro, español neutro, primera persona "
    "('mi IA', 'mi modelo'). REGLAS ESTRICTAS: sin emojis ni símbolos (lo lee un sintetizador de voz); escribe "
    "los números con dígitos y la palabra 'por ciento'; di 'contra' en vez de 'vs'; arranca con un GANCHO fuerte "
    "en la primera frase; destaca el dato más jugoso del día (la jugada de valor o una sorpresa); cierra "
    "invitando a ver el análisis completo gratis en el Substack (link en la bio) y firma diciendo que es "
    "aiwithpedro, inteligencia artificial aplicada al fútbol. Nada de apuestas; apto para todo público. "
    "Varía el arranque cada día para que no suene repetitivo. Devuelve SOLO el guion, sin comillas ni títulos.")

def ai_voiceover(summary):
    """Pide a Claude que redacte el guion del día. Devuelve None si no hay API key o falla."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or requests is None:
        return None
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 600, "system": AI_SYSTEM,
                  "messages": [{"role": "user", "content": "Datos de hoy:\n" + summary}]}, timeout=45)
        if r.status_code != 200:
            print(f"(guion IA no disponible: {r.status_code} {r.text[:150]})"); return None
        txt = r.json()["content"][0]["text"].strip().strip('"').strip()
        return txt or None
    except Exception as e:
        print(f"(guion IA falló: {e})"); return None

def day_hashtags(played):
    """Exactamente 5 hashtags virales, 2 según los equipos estrella del día."""
    teams = []
    try:
        champ = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]  # ordenado por prob desc
        playing = {d["a"] for d in played} | {d["b"] for d in played}
        teams = [t for t in champ if t in playing][:2]   # los 2 más "buscados" que juegan hoy
    except Exception:
        pass
    tags = ["#Mundial2026"] + [_tag(t) for t in teams] + ["#IA", "#parati"]
    for fill in ("#futbol", "#WorldCup2026"):            # relleno si hoy no hay equipos (raro)
        if len(tags) >= 5: break
        if fill not in tags: tags.append(fill)
    out = []
    for t in tags:
        if t not in out: out.append(t)
    return " ".join(out[:5])

def build(target):
    games = dd.matches_on(target)
    atk,dfn,c,g,rho = pm.fit_model(); pm.apply_adjustments(atk,dfn)
    mkt={}
    try:
        import fetch_odds
        for ev in fetch_odds.h2h():
            pe={dd.EN2ES.get(k,k):v for k,v in ev["clean_probs"].items()}
            ts=[t for t in pe if t!="Draw"]
            if len(ts)==2: mkt[frozenset(ts)]=pe
    except Exception: pass
    played=[]
    for m in sorted(games,key=lambda x:x["utc"]):
        a,b=m["a"],m["b"]
        if a not in pm.MAP or b not in pm.MAP: continue
        pw,pdr,pl,lh,la,(sx,sy)=pm.one_x_two(a,b,atk,dfn,c,g,rho,local_anfitrion=True)
        mp=mkt.get(frozenset((a,b))); vc=[]
        if mp:
            ma,mb=mp.get(a),mp.get(b)
            if ma and pw>=VAL_FLOOR and pw>ma*VAL_MARGIN: vc.append((a,pw,ma,pw/ma))
            if mb and pl>=VAL_FLOOR and pl>mb*VAL_MARGIN: vc.append((b,pl,mb,pl/mb))
        fav,fp=(a,pw) if pw>=pl else (b,pl)
        played.append({"a":a,"b":b,"fav":fav,"fp":fp,"vc":vc})
    pickall=[(d,v) for d in played for v in d["vc"]]
    pick=max(pickall,key=lambda x:x[1][3]) if pickall else None
    clearest=max(played,key=lambda d:d["fp"],default=None)
    try: tr=json.load(open("track_record.json",encoding="utf-8"))
    except Exception: tr={"n":0}

    # ---------- GUION (hablado, sin símbolos) ----------
    S=[]
    if not played:
        S.append("Hoy no hay partidos del Mundial, pero mi inteligencia artificial ya está lista para cuando ruede el balón.")
    else:
        S.append("Quién gana hoy en el Mundial. Mi inteligencia artificial corrió veinte mil simulaciones, y esto es lo que encontró.")
        if pick:
            d,(team,mpb,mkp,edge)=pick; riv=d["b"] if team==d["a"] else d["a"]
            S.append(f"La jugada del día es {team}, contra {riv}. Mi modelo le da {pct(mpb)} de ganar, "
                     f"pero las casas la pagan como si fuera mucho más difícil. Para mí, está infravalorada.")
        if clearest:
            S.append(f"El resultado más claro del día: en {clearest['a']} contra {clearest['b']}, "
                     f"el favorito es {clearest['fav']}, con {pct(clearest['fp'])}.")
        if tr.get("n",0)>0:
            S.append(f"Y para que confíes en el modelo: llevamos {tr['aciertos_1x2']} aciertos de {tr['n']} partidos.")
    S.append(f"El análisis completo de todos los partidos lo tienes gratis en mi Substack, el link está en mi perfil. "
             f"Soy {BRAND}, esto es inteligencia artificial aplicada al fútbol. Nos vemos mañana.")
    voiceover=" ".join(S)   # plantilla (respaldo)
    # guion fresco/viral con IA (Claude); si no hay ANTHROPIC_API_KEY, usa la plantilla
    ai = ai_voiceover(_summary(target[6:8]+"/"+target[4:6]+"/"+target[0:4], played, pick, clearest, tr))
    if ai:
        voiceover = ai

    # ---------- CAPTION TikTok ----------
    cap_pick = f" Pick del día: {pick[1][0]}." if pick else ""
    caption=(f"Mi IA predice el Mundial 2026 ⚽🤖{cap_pick} Análisis completo gratis en mi Substack (link en bio). "
             + day_hashtags(played))
    return voiceover, caption, len(played)

if __name__=="__main__":
    target = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else date.today().strftime("%Y%m%d")
    vo, cap, n = build(target)
    open("voiceover.txt","w",encoding="utf-8").write(vo)
    open("caption.txt","w",encoding="utf-8").write(cap)
    print("===== VOICEOVER (pégalo en ElevenLabs) =====\n")
    print(vo)
    print("\n===== CAPTION TikTok =====\n")
    print(cap)
    print(f"\n→ voiceover.txt y caption.txt guardados ({n} partidos)")
