"""
make_script.py — GUION HABLADO del día para ElevenLabs (tu voz) + caption para TikTok.
Texto natural en español (sin símbolos ni emojis, para que ElevenLabs lo lea limpio):
  hook + lo más importante de la infografía + CTA.

USO: python make_script.py [--date YYYYMMDD]
Genera: voiceover.txt (para pegar en ElevenLabs) y caption.txt (descripción + hashtags TikTok).
Flujo: voiceover.txt -> ElevenLabs (tu voz) -> voice.mp3 -> make_reel.py -> matchday.mp4
"""
import sys, json
from datetime import date
import daily_digest as dd
import predict_match as pm

BRAND = "aiwithpedro"
VAL_MARGIN, VAL_FLOOR = 1.20, 0.20

def pct(x): return f"{round(100*x)} por ciento"

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
    voiceover=" ".join(S)

    # ---------- CAPTION TikTok ----------
    cap_pick = f" Pick del día: {pick[1][0]}." if pick else ""
    caption=(f"Mi IA predice el Mundial 2026 ⚽🤖{cap_pick} Análisis completo gratis en mi Substack (link en bio). "
             f"#Mundial2026 #WorldCup2026 #IA #inteligenciaartificial #futbol #{BRAND} #datos #predicciones")
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
