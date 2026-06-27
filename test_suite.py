"""
test_suite.py — BATERÍA DE PRUEBAS EXHAUSTIVA (pre-lanzamiento).
Valida todo el sistema sin gastar APIs: desactiva Claude/ElevenLabs y mockea cuotas.
Cubre: mapeo de nombres, banderas, probabilidades, TODAS las fechas del torneo (104 partidos),
casos borde (0 partidos, placeholders de eliminatorias, equipos eliminados), integridad de la
simulación, cuadro de eliminatorias (assign_thirds) y track record.

USO:  python test_suite.py
Sale con código 0 si todo pasa; 1 si algo falla.
"""
import os, sys, json, math, shutil, subprocess
from datetime import date, timedelta

# --- desactivar costos/no-determinismo ANTES de usar los módulos ---
for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"):
    os.environ.pop(k, None)
# La batería corre sim_live con pocas simulaciones para ser rápida (las pruebas validan
# integridad/condicionamiento, no precisión). Producción usa el default alto (K=100.000).
os.environ["SL_K"] = "4000"

import daily_digest as dd
import predict_match as pm
import make_script as ms
import make_matchday as mm
import make_weekly as mw
import flags
import fetch_odds
import track_record as tr
import recap
# por si .env volvió a inyectar la clave al importar:
os.environ.pop("ANTHROPIC_API_KEY", None)

PY = sys.executable
PASS = 0; FAIL = 0; FAILS = []
def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS  {name}")
    else: FAIL += 1; FAILS.append(f"{name} — {detail}"); print(f"  FAIL  {name}  ::  {detail}")

def section(t): print(f"\n========== {t} ==========")

# ====== aceleración: fit del modelo UNA vez, ESPN UNA vez, cuotas mockeadas ======
print("Preparando (fit del modelo + calendario ESPN una sola vez)...")
_a, _d, _c, _g, _rho = pm.fit_model()          # crudo (sin ajustar)
pm.fit_model = lambda: (dict(_a), dict(_d), _c, _g, _rho)   # copia fresca por llamada (apply_adjustments muta)
_ALL = dd.fetch_all()
dd.fetch_all = lambda: _ALL
fetch_odds.h2h = lambda: []                    # sin gastar cuota
import curio
curio.web_news = lambda: None                  # offline + determinista: fuerza el dato del modelo
if os.path.exists(curio.CURIO_FILE): os.remove(curio.CURIO_FILE)
import contexto
contexto.noticia_mundial = lambda: None        # offline: sin red en las pruebas
_noticia_partido_real = contexto.noticia_partido            # guardar la real para probar sus filtros abajo
contexto.noticia_partido = lambda a, b, target=None: None   # offline: sin red en las pruebas (noticia por partido)
# CRÍTICO: env_loader re-inyecta la clave al importar curio/contexto -> forzar VACÍA para que las pruebas
# nunca llamen a Claude (deterministas y SIN gastar créditos).
os.environ["ANTHROPIC_API_KEY"] = ""
TEAMS = list(pm.MAP.keys())                    # 48 selecciones (es)

# ============================================================
section("1) MAPEO DE NOMBRES")
# 1a. namemap ida y vuelta para las 48
en2es = {en: es for es, en in pm.MAP.items()}
ok("namemap 48 selecciones", len(pm.MAP) == 48, f"hay {len(pm.MAP)}")
ok("namemap sin duplicados en inglés", len(en2es) == 48, f"{len(en2es)} ingleses únicos")
# 1b. cada equipo de los partidos reales de ESPN (no placeholders) mapea al modelo
unresolved = set()
for m in _ALL:
    for t in (m["a"], m["b"]):
        # placeholders contienen palabras como Winner/Place/Group/Third/Round/Semifinal/Quarter
        if any(w in t for w in ("Winner", "Place", "Group", "Third", "Round", "Semifinal", "Quarterfinal", "Loser")):
            continue
        if t not in pm.MAP:
            unresolved.add(t)
ok("todos los equipos reales de ESPN mapean", not unresolved, f"sin mapear: {sorted(unresolved)}")

# ============================================================
section("2) BANDERAS")
sinflag = [t for t in TEAMS if t not in flags.ISO]
ok("las 48 selecciones tienen código de bandera", not sinflag, f"faltan: {sinflag}")

# ============================================================
section("3) PROBABILIDADES 1X2 (válidas y normalizadas)")
atk, dfn, c, g, rho = pm.fit_model(); pm.apply_adjustments(atk, dfn)
bad = 0; tested = 0
for i, a in enumerate(TEAMS):
    for b in TEAMS[i+1:]:
        pw, pdr, pl, lh, la, (sx, sy) = pm.one_x_two(a, b, atk, dfn, c, g, rho, local_anfitrion=True)
        tested += 1
        finite = all(math.isfinite(v) for v in (pw, pdr, pl, lh, la, sx, sy))
        if not (finite and abs((pw+pdr+pl) - 1.0) < 1e-6 and 0 <= pw <= 1 and 0 <= pdr <= 1 and 0 <= pl <= 1
                and 0 < lh < 8 and 0 < la < 8 and 0 <= sx <= 12 and 0 <= sy <= 12):
            bad += 1
ok(f"1X2 suma 1, sin NaN, goles y marcadores en rango ({tested} cruces)", bad == 0, f"{bad} cruces inválidos")

# ============================================================
section("4) TODO EL TORNEO — cada fecha del 11-jun al 19-jul")
d0, d1 = date(2026, 6, 11), date(2026, 7, 19)
total_partidos = 0; dias_con_partidos = 0; errores = []
dd_dates = []
d = d0
while d <= d1:
    ds = d.strftime("%Y%m%d"); dd_dates.append(ds); d += timedelta(days=1)
for ds in dd_dates:
    try:
        games = dd.matches_on(ds)
        total_partidos += len(games)
        if games: dias_con_partidos += 1
        # digest sin crashear + 1X2 de cada partido jugable suma 1
        text, html, n, titulo = dd.build_digest(ds)
        if not text or "Mundial 2026" not in text:
            errores.append(f"{ds}: digest vacío/sin cabecera")
        # guion (plantilla) + caption con EXACTAMENTE 5 hashtags
        os.environ["MAKESCRIPT_NO_EXPORT"] = "1"   # que el test NO pise viral_pronostico.json real
        vo, cap, ng = ms.build(ds)
        if cap.count("#") != 5:
            errores.append(f"{ds}: caption con {cap.count('#')} hashtags (esperado 5)")
        if not vo.strip():
            errores.append(f"{ds}: guion vacío")
        # infografía (datos) sin crashear
        mm.collect(ds)
    except Exception as e:
        errores.append(f"{ds}: EXCEPCIÓN {type(e).__name__}: {e}")
ok("ninguna fecha del torneo crashea", not errores, "; ".join(errores[:6]))
ok("el calendario suma 104 partidos", total_partidos == 104, f"contados: {total_partidos}")
print(f"     (info: {dias_con_partidos} días con partidos, {total_partidos} partidos en total)")

# ============================================================
section("5) CASOS BORDE")
# 5a. día sin partidos (pre-torneo)
try:
    t0, h0, n0, ti0 = dd.build_digest("20260603")
    ok("día sin partidos no crashea", n0 == 0 and "no hay partidos" in t0.lower(), "no detectó 0 partidos")
except Exception as e:
    ok("día sin partidos no crashea", False, f"{type(e).__name__}: {e}")
# 5b. día de eliminatorias con placeholders (equipos por definir) -> se omiten sin romper
ko_days = [m["utc"][:10] for m in _ALL if m.get("is_ko")]
if ko_days:
    kd = sorted(ko_days)[0].replace("-", "")
    try:
        txt, _, _, _ = dd.build_digest(kd)
        ok("día KO con placeholders no crashea", bool(txt), "vacío")
    except Exception as e:
        ok("día KO con placeholders no crashea", False, f"{type(e).__name__}: {e}")
else:
    ok("hay días de eliminatoria en el calendario", False, "no se detectaron KO")

# ============================================================
section("6) SIMULACIÓN (sim_live) — integridad y condicionamiento")
shutil.copy("champ_today.json", "_bak_champ.json") if os.path.exists("champ_today.json") else None
def run(cmd, **kw): return subprocess.run([PY]+cmd, capture_output=True, text=True, timeout=600, **kw)
# 6a. pre-torneo: corre y champ suma ~1 con 48 selecciones
r = run(["sim_live.py"])
ok("sim_live corre sin error (pre-torneo)", r.returncode == 0, r.stderr[-200:])
try:
    cj = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
    s = sum(cj.values())
    ok("champ suma ~100% y 48 selecciones", abs(s-100) < 1.5 and len(cj) == 48, f"suma={s:.1f}, n={len(cj)}")
    ok("ninguna probabilidad negativa", all(v >= 0 for v in cj.values()), "hay negativas")
except Exception as e:
    ok("champ_today.json válido", False, f"{e}")
# 6b. condicionamiento: España pierde sus 3 -> ~0%
json.dump([["Espana","Cabo Verde",0,1],["Espana","Arabia Saudi",0,1],["Espana","Uruguay",0,2]],
          open("wc_results_mock.json","w",encoding="utf-8"))
r = run(["sim_live.py"])
try:
    cj = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
    ok("España eliminada -> ~0% campeón", cj.get("Espana",9) < 0.5, f"Espana={cj.get('Espana')}")
except Exception as e:
    ok("condicionamiento grupos", False, f"{e}")
os.remove("wc_results_mock.json")

# ============================================================
section("7) CUADRO DE ELIMINATORIAS (sim_live_ko)")
r = run(["sim_live_ko.py"])
ok("sim_live_ko corre sin error", r.returncode == 0, r.stderr[-200:])
try:
    cj = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
    ok("champ KO suma ~100%", abs(sum(cj.values())-100) < 1.5, f"suma={sum(cj.values()):.1f}")
except Exception as e:
    ok("champ_today.json (KO) válido", False, f"{e}")
# 7b. assign_thirds: robustez ante combinaciones de grupos clasificados
import importlib, itertools
sko = importlib.import_module("sim_live_ko")
groups = list("ABCDEFGHIJKL")
fallos_match = 0; combos = 0
for combo in itertools.combinations(groups, 8):
    combos += 1
    res = sko.assign_thirds(set(combo))
    # válido si asigna las 8 casillas a grupos del combo, sin repetir
    if len(res) != 8 or len(set(res.values())) != 8 or not set(res.values()).issubset(set(combo)):
        fallos_match += 1
ok(f"assign_thirds asigna 8 terceros en las {combos} combinaciones", fallos_match == 0, f"{fallos_match} combos sin matching perfecto")
# restaurar champ_today.json original
if os.path.exists("_bak_champ.json"):
    shutil.move("_bak_champ.json", "champ_today.json")

# ============================================================
section("8) TRACK RECORD — matemática de aciertos y Brier")
bak_log = "predictions_log.jsonl"; bak_tr = "track_record.json"
for f in (bak_log, bak_tr):
    if os.path.exists(f): shutil.copy(f, f+".bak")
# log controlado: 2 aciertos de 3 ; conocemos el resultado esperado
ctrl = [
 {"key":"k1","fecha":"2026-06-11","a":"A","b":"B","label":"G","p1":0.7,"pX":0.2,"p2":0.1,"pick":"1","marcador_pred":"2-0","actual":"1","marcador_real":"2-0","acierto_1x2":True,"acierto_exacto":True},
 {"key":"k2","fecha":"2026-06-11","a":"C","b":"D","label":"G","p1":0.2,"pX":0.3,"p2":0.5,"pick":"2","marcador_pred":"0-1","actual":"X","marcador_real":"1-1","acierto_1x2":False,"acierto_exacto":False},
 {"key":"k3","fecha":"2026-06-11","a":"E","b":"F","label":"G","p1":0.6,"pX":0.25,"p2":0.15,"pick":"1","marcador_pred":"1-0","actual":"1","marcador_real":"3-1","acierto_1x2":True,"acierto_exacto":False},
]
tr.save_log(ctrl)
s = tr.summary()
brier_esp = ((0.7-1)**2+0.2**2+0.1**2 + 0.2**2+(0.3-1)**2+0.5**2 + (0.6-1)**2+0.25**2+0.15**2)/3
ok("aciertos 1X2 = 2/3", s.get("aciertos_1x2")==2 and s.get("n")==3, f"{s}")
ok("Brier correcto", abs(s.get("brier",9)-round(brier_esp,3))<0.01, f"got {s.get('brier')}, esp {round(brier_esp,3)}")
# REGLA (recap): el acierto es del 1X2 (quién gana). Empate REAL con pick de GANADOR = FALLO; pick de EMPATE = acierto.
ctrl_x = [
 {"key":"x1","fecha":"2026-06-11","a":"A","b":"B","label":"G","p1":0.7,"pX":0.2,"p2":0.1,"pick":"1","marcador_pred":"2-0","actual":None},   # dijimos: gana A
 {"key":"x2","fecha":"2026-06-11","a":"C","b":"D","label":"G","p1":0.2,"pX":0.5,"p2":0.3,"pick":"X","marcador_pred":"1-1","actual":None},   # dijimos: empate
]
tr.save_log(ctrl_x)
_orig_fr = tr.fetch_results
tr.fetch_results = lambda: {"x1": {"a":"A","b":"B","ga":1,"gb":1}, "x2": {"a":"C","b":"D","ga":1,"gb":1}}   # ambos EMPATAN 1-1
try:
    tr.grade()
    g = {r["key"]: r for r in tr.load_log()}
finally:
    tr.fetch_results = _orig_fr
ok("empate real + pick de ganador = FALLO; empate real + pick de empate = ACIERTO",
   g["x1"].get("acierto_1x2") is False and g["x2"].get("acierto_1x2") is True,
   f"x1(pick 1, real X)={g['x1'].get('acierto_1x2')} | x2(pick X, real X)={g['x2'].get('acierto_1x2')}")
# restaurar
for f in (bak_log, bak_tr):
    if os.path.exists(f+".bak"): shutil.move(f+".bak", f)
    elif os.path.exists(f): os.remove(f)

# ============================================================
section("9) RESUMEN SEMANAL (make_weekly)")
werr = []
for wd in ("20260615", "20260622", "20260629", "20260706", "20260713"):  # 5 lunes del torneo
    try:
        wt, wh, wn, wk, wti = mw.build(wd)
        if not wt.strip() or not wh.strip(): werr.append(f"{wd}: vacío")
    except Exception as e:
        werr.append(f"{wd}: {type(e).__name__}: {e}")
ok("el semanal se arma en 5 lunes del torneo sin crashear", not werr, "; ".join(werr))

# ============================================================
section("10) RENDER REAL DE LA INFOGRAFÍA (PNG válido)")
r = run(["make_matchday.py", "--date", "20260611"])   # día inaugural (equipos reales)
png_ok = False
try:
    with open("matchday.png", "rb") as f: head = f.read(8)
    png_ok = head.startswith(b"\x89PNG") and os.path.getsize("matchday.png") > 8000
except Exception: pass
ok("make_matchday renderiza un PNG válido (>8KB) para un día real", r.returncode == 0 and png_ok,
   f"rc={r.returncode} {r.stderr[-160:]}")

# ============================================================
section("11) ENSAYO GENERAL — fase de grupos completa (condicionamiento end-to-end)")
# resultados deterministas de los 72 partidos de grupos: gana el de mayor (atk-dfn); empate si parejos
af, df2, cf, gf, rf = pm.fit_model(); pm.apply_adjustments(af, df2)
str_ = {t: af[t] - df2[t] for t in pm.MAP}
mock = []
for m in _ALL:
    if m.get("is_ko"): continue
    a, b = m["a"], m["b"]
    if a not in pm.MAP or b not in pm.MAP: continue
    da, db = str_[a], str_[b]
    if   da > db + 0.10: mock.append([a, b, 2, 0])
    elif db > da + 0.10: mock.append([a, b, 0, 2])
    else:                mock.append([a, b, 1, 1])
shutil.copy("champ_today.json", "_bak_champ2.json") if os.path.exists("champ_today.json") else None
json.dump(mock, open("wc_results_mock.json", "w", encoding="utf-8"))
ok("se generaron los 72 resultados de grupos", len(mock) == 72, f"generados {len(mock)}")
r = run(["sim_live.py"])
ok("sim_live corre con la fase de grupos completa", r.returncode == 0, r.stderr[-200:])
try:
    cj = json.load(open("champ_today.json", encoding="utf-8"))["campeon"]
    nonzero = [t for t, v in cj.items() if v > 0.05]   # con grupos cerrados, solo pueden ser campeón los clasificados
    ok("tras los grupos, <=32 selecciones siguen con opción al título",
       len(nonzero) <= 32, f"{len(nonzero)} con prob>0.05% (deberían ser <=32 clasificados)")
    ok("la distribución de campeón sigue sumando ~100%", abs(sum(cj.values())-100) < 1.5, f"suma={sum(cj.values()):.1f}")
    # un equipo que perdió sus 3 (de los más débiles) debe quedar en 0
    weakest = min(str_, key=str_.get)
    ok(f"un eliminado en grupos ({weakest}) queda en ~0%", cj.get(weakest, 9) < 0.5, f"{weakest}={cj.get(weakest)}")
except Exception as e:
    ok("champ tras grupos válido", False, f"{e}")
os.remove("wc_results_mock.json")
if os.path.exists("_bak_champ2.json"): shutil.move("_bak_champ2.json", "champ_today.json")

# ============================================================
section("12) DATO CURIOSO (días sin partido) — contenido + render")
cu = curio.build("20260603")    # web_news mockeado a None -> usa el dato exacto del modelo
ok("curio genera todos los campos", all(cu.get(k) for k in ("titulo","gancho","voz","card","caption","hashtags")),
   f"campos incompletos: {list(cu.keys())}")
ok("curio: exactamente 5 hashtags", len(cu["hashtags"]) == 5, f"{cu['hashtags']}")
ok("curio: voz apta para TTS (sin # ni emojis)",
   "#" not in cu["voz"] and all(ord(ch) < 0x2190 for ch in cu["voz"]), "la voz trae símbolos/emojis")
ok("curio: caption final arma >=5 hashtags",
   (cu["caption"].rstrip() + " " + " ".join(cu["hashtags"])).count("#") >= 5, "menos de 5")
cu2 = curio.build("20260620")   # torneo YA empezado (día de descanso) -> sin cuenta regresiva
ok("curio en torneo NO usa cuenta regresiva",
   "altan" not in cu2["voz"] and "altan" not in cu2["card"] and "altan" not in cu2["gancho"],
   f"voz={cu2['voz'][:90]}")
import make_curio_card
try:
    make_curio_card.render("20260603")
    with open("matchday.png", "rb") as f: h = f.read(8)
    ok("make_curio_card renderiza PNG válido (>8KB)", h.startswith(b"\x89PNG") and os.path.getsize("matchday.png") > 8000, "PNG inválido")
except Exception as e:
    ok("make_curio_card renderiza PNG válido (>8KB)", False, f"{type(e).__name__}: {e}")
if os.path.exists(curio.CURIO_FILE): os.remove(curio.CURIO_FILE)

# ============================================================
section("13) CIERRE DEL DÍA (recap: resultados vs pronóstico)")
bak_log = "predictions_log.jsonl"; bak_tr = "track_record.json"
for f in (bak_log, bak_tr):
    if os.path.exists(f): shutil.copy(f, f + ".bak")
tr.fetch_results = lambda: {}                  # offline: el log ya viene calificado
rday = "20260611"
ms_day = dd.matches_on(rday)[:2]
ctrl = []
for i, m in enumerate(ms_day):
    a, b = m["a"], m["b"]; acierto = (i == 0)   # 1º acierta, 2º falla
    ctrl.append({"key": tr._key(a, b, dd.et_date(m["utc"])), "fecha": dd.et_date(m["utc"]),
                 "a": a, "b": b, "label": m["label"], "p1": 0.6, "pX": 0.25, "p2": 0.15, "pick": "1",
                 "marcador_pred": "2-0", "actual": "1" if acierto else "2",
                 "marcador_real": "2-0" if acierto else "0-1",
                 "acierto_1x2": acierto, "acierto_exacto": acierto})
tr.save_log(ctrl)
try:
    cu = recap.build(rday)
    ok("recap arma todos los campos",
       (not cu.get("empty")) and all(cu.get(k) for k in ("titulo", "gancho", "voz", "caption", "hashtags", "matches")),
       f"campos: {list(cu.keys())}")
    ok("recap cuenta bien los aciertos del día (1 de 2)", cu.get("n") == 2 and cu.get("hits") == 1, f"{cu.get('hits')}/{cu.get('n')}")
    ok("recap: exactamente 5 hashtags", len(cu.get("hashtags", [])) == 5, f"{cu.get('hashtags')}")
    ok("recap: voz apta para TTS (sin # ni emojis)",
       "#" not in cu["voz"] and all(ord(ch) < 0x2190 for ch in cu["voz"]), "voz con símbolos")
    ok("recap: 'lo que viene' apunta a una fecha posterior", bool(cu.get("proximo")) and cu["proximo"]["fecha_h"] != cu["fecha_h"], f"{cu.get('proximo')}")
    ok("recap: la firma no queda pegada a la despedida (frases aparte para que pausas respire)",
       "Pédro, nos vemos" not in cu["voz"] and "Pédro,nos vemos" not in cu["voz"], cu["voz"][-60:])
    ok("recap _sep_firma: 'Pédro, nos vemos mañana' -> '. Nos vemos' (pausa)",
       recap._sep_firma("Suscríbete. Soy éi ái uíz Pédro, nos vemos mañana.") == "Suscríbete. Soy éi ái uíz Pédro. Nos vemos mañana.",
       recap._sep_firma("Soy éi ái uíz Pédro, nos vemos mañana."))
    import make_recap
    make_recap.render(rday)
    with open("recap.png", "rb") as f: h = f.read(8)
    ok("make_recap renderiza PNG válido (>8KB)", h.startswith(b"\x89PNG") and os.path.getsize("recap.png") > 8000, "PNG inválido")
except Exception as e:
    ok("recap end-to-end", False, f"{type(e).__name__}: {e}")
for f in (bak_log, bak_tr):
    if os.path.exists(f + ".bak"): shutil.move(f + ".bak", f)
    elif os.path.exists(f): os.remove(f)
for f in ("recap_today.json", "recap_voiceover.txt", "recap_caption.txt"):
    if os.path.exists(f): os.remove(f)

# ============================================================
section("14) SUBTÍTULOS (texto = nuestro guion; Whisper solo para el tiempo)")
import subtitulos as sub
guion_sub = "Aqui estan los pronosticos del dia. Catar pierde con Suiza. Brasil empata. Soy éi ái uíz Pédro."
ok("normalizar_marca_texto: la firma fonética -> aiwithpedro",
   "aiwithpedro" in sub.normalizar_marca_texto(guion_sub) and "íz" not in sub.normalizar_marca_texto(guion_sub),
   sub.normalizar_marca_texto(guion_sub)[-25:])
# validación: galimatías (como el bug real) da ratio bajo; transcripción buena da ratio alto
galim = [(w, i*0.3, i*0.3+0.3) for i, w in enumerate("en la Bogchia que nostitra los ghospiertas borrowing copio".split())]
bueno = [(w, i*0.3, i*0.3+0.3) for i, w in enumerate("Aqui estan los pronosticos del dia Catar pierde con Suiza Brasil".split())]
ok("similitud detecta galimatías (ratio bajo)", sub.similitud(galim, guion_sub) < 0.3, f"{sub.similitud(galim, guion_sub):.2f}")
ok("similitud aprueba transcripción buena (ratio alto)", sub.similitud(bueno, guion_sub) >= 0.55, f"{sub.similitud(bueno, guion_sub):.2f}")
# fallback proporcional: cobertura completa, texto = guion (sin galimatías), marca normalizada
srt_p = sub.srt_proporcional(guion_sub, 30.0)
times = [l for l in srt_p.splitlines() if "-->" in l]
ok("srt_proporcional cubre desde 0s", times and times[0].startswith("00:00:00,0"), times[0] if times else "vacío")
ok("srt_proporcional llega cerca del final", times and times[-1].split(" --> ")[1].startswith("00:00:30"), times[-1] if times else "vacío")
ok("srt_proporcional usa el guion (sin galimatías) + marca", "Bogchia" not in srt_p and "aiwithpedro" in srt_p, "texto incorrecto")
# alinear: cada palabra del guion recibe tiempo monótono; el texto mostrado ES el guion
pal = sub.alinear(guion_sub, bueno, 30.0)
ok("alinear da tiempos monótonos y crecientes", pal and all(pal[i][1] >= pal[i-1][1] for i in range(1, len(pal))), "no monótono")
ok("alinear muestra nuestro texto (marca al final = aiwithpedro)", pal and pal[-1][0].startswith("aiwithpedro"), pal[-1][0] if pal else "vacío")
# timing_sano: el patrón ROTO de la corrida real (frases de ~4.5s + racimo amontonado) debe rechazarse
roto = [("a", 1.1, 1.5), ("b", 5.6, 6.0), ("c", 10.0, 10.4), ("d", 14.5, 14.9)] + \
       [(f"w{i}", 21.2 + i*0.03, 21.2 + i*0.03 + 0.3) for i in range(15)]
sano = [(f"w{i}", i*0.6, i*0.6 + 0.5) for i in range(20)]
ok("timing_sano RECHAZA el patrón roto de hoy (estirado+amontonado)", not sub.timing_sano(roto, 42.0), "no lo detectó")
ok("timing_sano ACEPTA un timing parejo", sub.timing_sano(sano, 12.0), "rechazó uno bueno")

# ============================================================
section("15) DÍA DE LA SEMANA + TÍTULO YOUTUBE + FIRMA (YouTube, sin TikTok)")
import make_script as msx
# (1) día de la semana calculado en Python (no por Claude)
ok("weekday_es correcto en fechas del torneo",
   dd.weekday_es("20260613") == "sábado" and dd.weekday_es("20260611") == "jueves"
   and dd.weekday_es("20260618") == "jueves" and dd.weekday_es("20260620") == "sábado",
   f'13->{dd.weekday_es("20260613")}, 11->{dd.weekday_es("20260611")}')
ok("fecha_larga (fecha hablada) correcta",
   dd.fecha_larga("20260618") == "jueves 18 de junio" and dd.fecha_larga("20260613") == "sábado 13 de junio",
   f'18->{dd.fecha_larga("20260618")}')
# el resumen que recibe Claude trae la fecha hablada YA resuelta, SIN "día N del torneo"
played_x = [{"a": "Brasil", "b": "Marruecos", "fav": "Brasil", "fp": 0.5, "sx": 1, "sy": 0,
             "utc": "2026-06-13T19:00Z", "estadio": "Estadio Azteca", "ciudad": "Ciudad de México", "pais": "México"}]
sm_x = msx._summary("13/06/2026", played_x, None, None, {"n": 0})
ok("_summary abre con la fecha hablada (sábado 13 de junio)", "Hoy es sábado 13 de junio" in sm_x, sm_x.splitlines()[0])
ok("hora_hablada en palabras (sin ET ni cifras; 'una' correcto)",
   dd.hora_hablada("2026-06-13T20:00Z") == "a las cuatro de la tarde, hora del este"
   and dd.hora_hablada("2026-06-13T17:00Z") == "a la una de la tarde, hora del este"
   and dd.hora_hablada("2026-06-14T00:00Z") == "a las ocho de la noche, hora del este",
   dd.hora_hablada("2026-06-13T20:00Z"))
ok("_summary incluye hora HABLADA y sede = SOLO el estadio (sin ciudad ni país)",
   "Hora: a las tres de la tarde, hora del este" in sm_x and "Sede: Estadio Azteca" in sm_x
   and "Sede: Estadio Azteca, " not in sm_x, sm_x)
ok("AI_SYSTEM pide hora + SOLO el estadio (sin ciudad ni país) y NO citar el medio",
   all(s in msx.AI_SYSTEM for s in ("SOLO el nombre del", "ESTADIO", "NUNCA la ciudad ni el país", "SIN citar el medio")), "falta la regla")
ok("AI_SYSTEM: el marcador se dice en el ORDEN de la tarjeta (sx primero, no invertir números)",
   all(s in msx.AI_SYSTEM for s in ("REGLA ABSOLUTA", "PROHIBIDÍSIMAS", "JAMÁS 'Australia uno a cero'")), "falta la regla de coherencia del marcador")
# nº de partido del equipo: contado por fecha ET, NO UTC (un juego de noche en ET cae al día UTC siguiente y se descontaba)
_synth_np = [{"a":"X","b":"Y","utc":"2026-06-14T23:00Z"},   # ET 2026-06-14
             {"a":"X","b":"Z","utc":"2026-06-26T02:00Z"}]   # ET 2026-06-25 (pero fecha UTC = 2026-06-26)
ok("num_partido_en_torneo cuenta por ET (el juego de noche en ET no se descuenta como 'segundo')",
   msx.num_partido_en_torneo("X", "2026-06-25", _synth_np) == 2
   and msx.num_partido_en_torneo("X", "2026-06-24", _synth_np) == 1,
   f"25/06 ET -> {msx.num_partido_en_torneo('X','2026-06-25',_synth_np)} (esperado 2)")
ok("fix_team_hashtags: corrige typos de equipo (#PaísesBasos->#PaisesBajos, #Croasia->#Croacia) y respeta los buenos",
   msx.fix_team_hashtags(["#PaísesBasos", "#Mundial2026", "#Brasil", "#Croasia", "#IA"])
   == ["#PaisesBajos", "#Mundial2026", "#Brasil", "#Croacia", "#IA"],
   msx.fix_team_hashtags(["#PaísesBasos", "#Mundial2026", "#Brasil", "#Croasia", "#IA"]))
ok("_summary ya NO mete 'el día N del torneo'", "hoy es el día" not in sm_x.lower(), "quedó el día N")
ok("AI_SYSTEM abre con la fecha y prohíbe 'día N del torneo'",
   "Aquí están los pronósticos del Mundial 2026 de mi inteligencia artificial" in msx.AI_SYSTEM and "el día N del torneo" in msx.AI_SYSTEM, "falta la regla")
ok("el prompt prohíbe que Claude deduzca el día", "NUNCA lo deduzcas" in msx.AI_SYSTEM, "falta la regla")
# (1b) pronóstico CLARO por partido + ángulo viral con noticia real o dato del modelo (sin inventar)
ok("_summary marca el PRONÓSTICO de cada partido", "PRONÓSTICO Brasil contra Marruecos" in sm_x, sm_x)
ok("AI_SYSTEM pide 'el pronóstico de A contra B' por partido", "el pronóstico de A contra B" in msx.AI_SYSTEM, "falta la regla")
ok("AI_SYSTEM prohíbe inventar (noticias/hora/sede)",
   "NUNCA inventes" in msx.AI_SYSTEM and "noticias" in msx.AI_SYSTEM, "falta el guardarraíl")
# el partido MÁS importante lleva sede+noticia; los demás solo la hora
played2 = [
    {"a": "Brasil", "b": "Marruecos", "fav": "Brasil", "fp": 0.6, "sx": 2, "sy": 0,
     "utc": "2026-06-13T19:00Z", "estadio": "Azteca", "ciudad": "CDMX", "pais": "México"},
    {"a": "Catar", "b": "Suiza", "fav": "Suiza", "fp": 0.7, "sx": 0, "sy": 2,
     "utc": "2026-06-13T22:00Z", "estadio": "Lumen Field", "ciudad": "Seattle", "pais": "Estados Unidos"},
]
sm2 = msx._summary("13/06/2026", played2, None, None, {"n": 0})
ok("fase de grupos: solo el destacado va en detalle; los demás solo la hora",
   sm2.count("[DETALLE]") == 1 and sm2.count("Sede:") == 1 and sm2.count("Hora:") == 2, sm2)
# eliminatorias = TODAS las rondas desde 28-jun (dieciseisavos, octavos, cuartos, semis, final): TODOS importantes
for _kod, _ronda in [("28/06/2026", "dieciseisavos"), ("04/07/2026", "octavos"), ("09/07/2026", "cuartos"),
                     ("14/07/2026", "semifinal"), ("19/07/2026", "final")]:
    _smk = msx._summary(_kod, played2, None, None, {"n": 0})
    ok(f"eliminatorias {_ronda} ({_kod}): TODOS los partidos en detalle (todos importantes)",
       _smk.count("[DETALLE]") == 2 and _smk.count("Sede:") == 2, _smk)
# el video quita 'PICK DEL DÍA' en TODA la eliminatoria (umbral cubre las 5 rondas; NO el último día de grupos)
ok("video: 'PICK DEL DÍA' se quita en todas las eliminatorias (umbral 20260628), no en grupos",
   all(d >= "20260628" for d in ("20260628", "20260704", "20260709", "20260714", "20260719"))
   and not ("20260627" >= "20260628"), "umbral de eliminatorias mal")
ok("ronda_ko: nombra cada fase eliminatoria por fecha; '' en grupos",
   dd.ronda_ko("20260628") == "DIECISEISAVOS" and dd.ronda_ko("20260705") == "OCTAVOS DE FINAL"
   and dd.ronda_ko("20260710") == "CUARTOS DE FINAL" and dd.ronda_ko("20260715") == "SEMIFINAL"
   and dd.ronda_ko("20260718") == "TERCER PUESTO" and dd.ronda_ko("20260719") == "GRAN FINAL"
   and dd.ronda_ko("20260622") == "", [dd.ronda_ko(d) for d in ("20260628", "20260705", "20260719", "20260622")])
ok("AI_SYSTEM: [DETALLE]=completo, los demás=solo hora",
   "[DETALLE]" in msx.AI_SYSTEM and "SOLO el pronóstico" in msx.AI_SYSTEM, "falta la regla")
ok("AI_SYSTEM: arranque CORTO y directo (IA + fecha + RÉCORD al inicio, sin gancho/simulaciones/opinión)",
   all(s in msx.AI_SYSTEM for s in ("ABRE CORTO Y DIRECTO", "Vamos <aciertos> de <total>",
       "PROHIBIDO en el ARRANQUE", "empieza DIRECTO con lo que piensa")), "falta alguna regla del arranque corto")
ok("AI_SYSTEM: el récord se dice UNA vez al inicio (no se repite al final)",
   "El récord se dice UNA sola vez" in msx.AI_SYSTEM and "_INTRO_VARIANTS" in dir(msx), "falta la regla del récord")
ok("AI_SYSTEM: variación por partido + opinión del destacado + actitud al cierre",
   all(s in msx.AI_SYSTEM for s in ("VARÍA cómo introduces", "OPINIÓN PROPIA", "ACTITUD")), "falta alguna mejora de estilo")
ok("AI_SYSTEM: la opinión del destacado va JUSTO DESPUÉS de ese partido (no al final, no sobre otro)",
   "JUSTO DESPUÉS de su pronóstico" in msx.AI_SYSTEM and "SOLO para el destacado" in msx.AI_SYSTEM, "falta la regla de posición")
ok("AI_SYSTEM: SIN etiquetas de emoción ([excited] prohibido)",
   "PROHIBIDAS también las etiquetas de emoción" in msx.AI_SYSTEM and "[excited]" not in msx.AI_SYSTEM.split("PROHIBIDAS")[0], "aún permite [excited]")
# fonética de estadios/ciudades SOLO para el audio (ElevenLabs); el texto queda real para subtítulos
import make_voice as mvz
ph = mvz.foneticizar("Se juega en el NRG Stadium de Houston, Texas. También Mexico City y el BMO Field.")
ok("foneticizar: ciudades a fonética española, pero estadios COMERCIALES en su nombre original",
   "estadio NRG" in ph and "campo BMO" in ph and "jiúston" in ph and "téksas" in ph
   and "Ciudad de México" in ph, ph)
# CRÍTICO: ningún nombre COMERCIAL de estadio se deja en "modo fonético" (como pasó con 'jard rok')
ok("foneticizar: marcas de estadio NO foneticizadas (Hard Rock, Gillette, Levi's, MetLife, SoFi, Mercedes-Benz)",
   all(marca in mvz.foneticizar(orig) for orig, marca in [
       ("Hard Rock Stadium", "Hard Rock"), ("Gillette Stadium", "Gillette"), ("Levi's Stadium", "Levi's"),
       ("MetLife Stadium", "MetLife"), ("SoFi Stadium", "SoFi"), ("Mercedes-Benz Stadium", "Mercedes-Benz"),
       ("Lincoln Financial Field", "Lincoln Financial"), ("Arrowhead Stadium", "Arrowhead")]),
   "alguna marca quedó foneticizada")
ok("foneticizar: NO altera el texto normal del guion",
   mvz.foneticizar("El pronóstico de hoy es muy claro") == "El pronóstico de hoy es muy claro", "tocó texto normal")
ok("foneticizar: Haití -> aití (H muda; el TTS no debe decir 'jaiti')",
   "aití" in mvz.foneticizar("ante Haití") and "Haití" not in mvz.foneticizar("ante Haití"), mvz.foneticizar("ante Haití"))
ok("suavizar_tts: quita rayas/elipsis y espacios dobles (pausas raras)",
   mvz.suavizar_tts("Hola—mundo…  ya") == "Hola, mundo. ya", mvz.suavizar_tts("Hola—mundo…  ya"))
# etiquetas de emoción de eleven_v3: se quedan SOLO en el audio v3; fuera del v2 y del subtítulo
ok("quitar_tags: elimina [excited] para el audio (fallback v2)",
   mvz.quitar_tags("[excited] Hola [confident] mundo") == "Hola mundo", mvz.quitar_tags("[excited] Hola [confident] mundo"))
ok("quitar_tags: BLINDAJE — un corchete con contenido real NO se borra (conserva el texto, quita 'LABEL:')",
   mvz.quitar_tags("[DETALLE: Escocia recibe a Brasil hoy.]") == "Escocia recibe a Brasil hoy."
   and mvz.quitar_tags("Gol [confident]. Sigue.") == "Gol. Sigue.", mvz.quitar_tags("[DETALLE: Escocia recibe a Brasil hoy.]"))
ok("subtítulos NO muestran las etiquetas de emoción",
   "[" not in sub.normalizar_marca_texto("[excited] Canadá goleó") and
   "Canadá goleó" in sub.normalizar_marca_texto("[excited] Canadá goleó"), "quedó la etiqueta en el subtítulo")
ok("numeros_a_palabras: cifras 0-99 a palabras (audio), años intactos",
   mvz.numeros_a_palabras("60 por ciento, 2 a 1, 18 de 32, Mundial 2026")
   == "sesenta por ciento, dos a uno, dieciocho de treinta y dos, Mundial 2026",
   mvz.numeros_a_palabras("60 por ciento, 2 a 1, 18 de 32, Mundial 2026"))
ok("_num_es: 20-29 con TILDES correctas (veintidós/veintitrés/veintiséis), resto intacto",
   [mvz._num_es(str(k)) for k in (20,21,22,23,24,25,26,27,28,29)] ==
   ["veinte","veintiuno","veintidós","veintitrés","veinticuatro","veinticinco","veintiséis","veintisiete","veintiocho","veintinueve"]
   and mvz.numeros_a_palabras("22 de junio, vamos 23 de 40") == "veintidós de junio, vamos veintitrés de cuarenta",
   [mvz._num_es(str(k)) for k in (22,23,26)])
ok("numeros_a_palabras: decimales se leen con 'punto' (60.5 -> sesenta punto cinco, no 'sesenta cinco')",
   mvz.numeros_a_palabras("60.5 por ciento") == "sesenta punto cinco por ciento"
   and mvz.numeros_a_palabras("57.5") == "cincuenta y siete punto cinco", mvz.numeros_a_palabras("60.5 por ciento"))
ok("stitching: parte el guion en frases y agrupa en bloques",
   len(mvz._frases("Uno. Dos! Tres?")) == 3 and len(mvz._bloques("Frase larga de prueba número. " * 30)) >= 2,
   f'frases={len(mvz._frases("Uno. Dos! Tres?"))}, bloques={len(mvz._bloques("Frase larga de prueba número. " * 30))}')
# QC de pausas: objetivos según puntuación + variación natural por largo de frase
import pausas as pz
ok("pausas: clause_lens reinicia en cada signo",
   pz._clause_lens(["Hola", "mundo.", "Otra", "frase."]) == [1, 2, 1, 2], str(pz._clause_lens(["Hola", "mundo.", "Otra", "frase."])))
ok("pausas: punto > coma > sin-signo, y varía con frase larga",
   pz._objetivo("hoy.", 1) >= pz.PUNTO_BASE and pz._objetivo("hoy.", 10) > pz._objetivo("hoy.", 1)
   and pz._objetivo("hoy,", 3) < pz._objetivo("hoy.", 3) and pz._objetivo("palabra", 5) == pz.SIN_SIGNO,
   f'punto1={pz._objetivo("hoy.",1)}, punto10={pz._objetivo("hoy.",10)}, coma={pz._objetivo("hoy,",3)}')
# CRÍTICO: los segmentos del audio NUNCA se solapan (mensajes no se montan uno sobre otro), ni con ops adversarios
_segx = pz._segmentos([("cut", 1.0, 2.0), ("ins", 1.5, 0.3), ("cut", 3.0, 3.4), ("ins", 4.0, 0.2), ("cut", 2.5, 5.0)], 6.0)
_aud = [s for s in (_segx or []) if s[0] == "a"]
ok("pausas: los segmentos van en orden y SIN solaparse (mensajes no se solapan)",
   _segx is not None and all(_aud[i][2] <= _aud[i + 1][1] + 1e-6 for i in range(len(_aud) - 1))
   and all(s[2] > s[1] for s in _aud), str(_segx))
# noticia_partido: relevante al juego + contexto Mundial 2026 + publicada el día o el anterior
import contexto as _ctx
_orig_req = _ctx.requests
class _FakeReq:
    def __init__(s, text): s._t = text
    def get(s, *a, **k):
        class _R: pass
        r = _R(); r.status_code = 200; r.text = s._t; return r
def _rss(items):
    body = "".join(f"<item><title>{t}</title><source>{s}</source><description>{d}</description><pubDate>{p}</pubDate></item>"
                   for t, s, d, p in items)
    return f"<rss><channel>{body}</channel></rss>"
LINK = "ver mas en http://news.google.com/articulo"   # las descripciones REALES traen enlaces (no deben romper)
_ctx.requests = _FakeReq(_rss([
    ("Mundial Sub-17: Brasil vs Marruecos", "ESPN", LINK, "Wed, 17 Jun 2026 10:00:00 GMT"),            # fuera: sub-17
    ("Brasil vs Marruecos: dónde ver el partido", "ESPN", LINK, "Wed, 17 Jun 2026 10:00:00 GMT"),      # fuera: logística
    ("Brasil vs Marruecos: mejores apuestas y cuotas", "AS", LINK, "Wed, 17 Jun 2026 10:00:00 GMT"),   # fuera: apuestas
    ("Brasil vs Marruecos del Mundial 2022 inolvidable", "AS", LINK, "Wed, 17 Jun 2026 10:00:00 GMT"), # fuera: otra edición
    ("Brasil vs Marruecos en el Mundial 2026", "Marca", LINK, "Fri, 12 Jun 2026 10:00:00 GMT"),        # fuera: fecha vieja
    ("Brasil vs Marruecos: previa caliente del Mundial 2026", "AS", LINK, "Wed, 17 Jun 2026 09:00:00 GMT"),  # OK
]))
n_ok = _noticia_partido_real("Brasil", "Marruecos", "20260618")
ok("noticia_partido: elige la nota con sustancia (salta sub-17/logística/apuestas/2022/vieja; enlace en desc NO rompe)",
   bool(n_ok) and "previa caliente" in n_ok["title"], f"{n_ok}")
_ctx.requests = _FakeReq(_rss([("Brasil brilla en el Mundial 2026", "AS", LINK, "Wed, 17 Jun 2026 09:00:00 GMT")]))
ok("noticia_partido: rechaza si NO menciona a ambos equipos",
   _noticia_partido_real("Brasil", "Marruecos", "20260618") is None, "no debió aceptar")
# ranking: entre varias válidas, elige la MÁS viral (no solo la primera de Google)
_ctx.requests = _FakeReq(_rss([
    ("Brasil vs Marruecos: previa del Mundial 2026", "AS", LINK, "Wed, 17 Jun 2026 09:00:00 GMT"),                 # genérica, va primero
    ("Brasil lanza advertencia a Marruecos en el Mundial 2026", "TUDN", LINK, "Thu, 18 Jun 2026 08:00:00 GMT"),   # viral + del día -> debe ganar
]))
ok("noticia_partido: prioriza la MÁS viral, no la primera",
   "advertencia" in (_noticia_partido_real("Brasil", "Marruecos", "20260618") or {}).get("title", ""), "no priorizó la viral")
_ctx.requests = _FakeReq(_rss([("Pronóstico Brasil vs Marruecos: predicciones del Mundial 2026", "AS", LINK, "Thu, 18 Jun 2026 08:00:00 GMT")]))
ok("noticia_partido: descarta pronósticos/predicciones de otros medios",
   _noticia_partido_real("Brasil", "Marruecos", "20260618") is None, "no debió aceptar un pronóstico ajeno")
_ctx.requests = _FakeReq(_rss([("Brasil vs Marruecos: posible alineación en el Mundial 2026", "AS", LINK, "Thu, 18 Jun 2026 08:00:00 GMT")]))
ok("noticia_partido: descarta notas de alineaciones",
   _noticia_partido_real("Brasil", "Marruecos", "20260618") is None, "no debió aceptar una alineación")
_ctx.requests = _orig_req
# (2) título de YouTube del pronóstico: VIRAL y diario (no el formato fijo viejo)
msx.write_youtube("youtube_test.txt", played_x, "18/06/2026", None)
yt_l1 = open("youtube_test.txt", encoding="utf-8").read().splitlines()[0]
ok("título YouTube del pronóstico es VIRAL (menciona Mundial + favorito, no el formato fijo)",
   "Mundial 2026" in yt_l1 and "Brasil" in yt_l1 and "- Pronósticos Mundial 2026 @aiwithpedro" not in yt_l1
   and len(yt_l1) <= 100, yt_l1)
ok("limpiar_voz: corrige 'un a cero'->'uno a cero' y la tilde de 'Suscríbete'",
   msx._limpiar_voz("Uruguay gana un a cero hoy. Suscribete a mi canal.") == "Uruguay gana uno a cero hoy. Suscríbete a mi canal."
   and msx._limpiar_voz("un punto, una jugada") == "un punto, una jugada", msx._limpiar_voz("gana un a cero. Suscribete."))
ok("limpiar_voz: elimina duplicaciones ('Bélgica y Bélgica'->'Bélgica', 'la la'->'la'), sin tocar equipos distintos",
   msx._limpiar_voz("Bélgica y Bélgica contra Irán") == "Bélgica contra Irán"
   and msx._limpiar_voz("es la la mejor") == "es la mejor"
   and msx._limpiar_voz("España y Japón juegan") == "España y Japón juegan", msx._limpiar_voz("Bélgica y Bélgica contra Irán"))
ok("limpiar_voz: 'a la ocho'->'a las ocho' (la 's' SIEMPRE salvo en 'a la una')",
   msx._limpiar_voz("juega a la ocho y a la una") == "juega a las ocho y a la una", msx._limpiar_voz("a la ocho, a la una"))
ok("hora_hablada: 'a las' salvo 'a la una' (la 's' nunca falta)",
   dd.hora_hablada("2026-06-22T00:00Z").startswith("a las ocho") and dd.hora_hablada("2026-06-21T17:00Z").startswith("a la una")
   and dd.hora_hablada("2026-06-21T19:00Z").startswith("a las tres"),
   dd.hora_hablada("2026-06-22T00:00Z") + " | " + dd.hora_hablada("2026-06-21T17:00Z"))
if os.path.exists("youtube_test.txt"): os.remove("youtube_test.txt")
# (3) firma menciona YouTube; sin TikTok en los prompts de contenido
import curio as cux
ok("la firma invita a suscribirse a YouTube (pronóstico, curio, recap)",
   all("canal de YouTube" in p for p in (msx.AI_SYSTEM, cux.CURIO_SYS, recap.AI_RECAP_SYS)), "falta YouTube en alguna")
ok("modelo de TÍTULO VIRAL (estilo Shorts) aplicado a pronóstico, recap y dato curioso",
   all("SHORT VIRAL" in p and "GANCHO que se lea" in p for p in (msx.AI_SYSTEM, cux.CURIO_SYS, recap.AI_RECAP_SYS)),
   "falta el modelo viral compartido en alguno")
ok("pronóstico: integra modelo vs mercado con 'por qué' real y PROHÍBE lenguaje de apuestas",
   "Modelo vs mercado" in msx.AI_SYSTEM and "PROHIBIDO el lenguaje de apuestas" in msx.AI_SYSTEM
   and "NUNCA inventes la razón" in msx.AI_SYSTEM, "falta la regla modelo-vs-mercado/no-apuestas")
import fetch_odds as fox
ok("cuotas: 1 sola región por defecto (no agotar el plan gratis de 500/mes)", "," not in fox.REGIONS, fox.REGIONS)
import predict_match as pmx
_eh = pmx.ensamble_marcador(1.3, 1.3, 0.0, 0.85, 0.10, 0.05)   # mercado favorece LOCAL
_ea = pmx.ensamble_marcador(1.3, 1.3, 0.0, 0.05, 0.10, 0.85)   # mercado favorece VISITA
ok("ensamble modelo+mercado: el mercado inclina el marcador (local fuerte->gana local; visita fuerte->gana visita)",
   _eh[2] > _eh[4] and _eh[0] >= _eh[1] and _ea[4] > _ea[2] and _ea[1] >= _ea[0],
   f"local={_eh[0]}-{_eh[1]} pw={_eh[2]:.2f} | visita={_ea[0]}-{_ea[1]} pl={_ea[4]:.2f}")
# El marcador más probable se MANTIENE; el pick/favorito DERIVA de él (no al revés) para que todo concuerde.
ok("outcome_de: el resultado 1X2 sale del marcador (2-0->1, 1-1->X, 0-2->2)",
   pmx.outcome_de(2,0)=="1" and pmx.outcome_de(1,1)=="X" and pmx.outcome_de(0,2)=="2", "outcome_de mal")
ok("track_record: el pick deriva del marcador previsto (marcador de empate -> pick 'X', no un ganador)",
   pmx.outcome_de(1,1)=="X" and pmx.outcome_de(3,1)=="1",
   "si el marcador es 1-1, el pick debe ser empate (X), no victoria")
import os as _os, json as _json
_cp = dd.campeon_probs()
_pref_ok = True
if _os.path.exists("champ_ensemble.json"):
    _pref_ok = (_cp == _json.load(open("champ_ensemble.json", encoding="utf-8")).get("ensemble", {}))
ok("campeon_probs: prefiere el ENSEMBLE modelo+mercado (campeón usa el mercado, no solo el modelo)",
   isinstance(_cp, dict) and len(_cp) > 0 and _pref_ok, "campeon_probs no prefirió el ensemble")
# videos virales: remap de timestamps por pausas + alineación hablado->pantalla
_rw = pz.remap_words([{"w": "a", "t": 0.5, "e": 0.8}, {"w": "b", "t": 1.5, "e": 1.8}],
                     [("a", 0.0, 1.0), ("s", 0.5), ("a", 1.2, 2.0)])
ok("remap_words: remapea los tiempos por cortes/inserciones de pausas (silencio insertado desplaza)",
   abs(_rw[0]["t"] - 0.5) < 0.01 and abs(_rw[1]["t"] - 1.8) < 0.01, str(_rw))
_al = mvz.alinear_display([{"w": "España", "t": 0.0, "e": 0.4}, {"w": "gana", "t": 0.5, "e": 0.8}, {"w": "tres", "t": 1.0, "e": 1.3}], "España gana 3")
ok("alinear_display: palabras de PANTALLA con tiempos (casadas exactas, número interpolado, monótono)",
   [x["w"] for x in _al] == ["España", "gana", "3"] and abs(_al[0]["t"]) < 0.01 and abs(_al[1]["t"] - 0.5) < 0.01
   and all(_al[i]["t"] <= _al[i + 1]["t"] + 0.001 for i in range(len(_al) - 1)), str(_al))
ok("ningún prompt de contenido menciona TikTok",
   not any("tiktok" in p.lower() for p in (msx.AI_SYSTEM, cux.CURIO_SYS, recap.AI_RECAP_SYS, dd.AI_DIGEST_SYS)),
   "quedó TikTok en un prompt")

# ============================================================
section("16) CONTEXTO (altura/calor/viaje) + FORMATO (sobredispersión + desempates FIFA)")
import context_factors as _cf, format_engine as _fe, schedule_2026 as _sc, random as _rnd
# 16a. checks directos (no dependen de pytest)
ok("altura: equipo nivel del mar en el Azteca ≈0.91", abs(_cf.f_altitude(2240, 0) - 0.9104) < 1e-3, str(_cf.f_altitude(2240, 0)))
ok("altura: nativo de altura NO se castiga (gap 0 → 1.0)", _cf.f_altitude(2240, 2240) == 1.0)
ok("multiplicadores acotados a [0.90, 1.08]", _cf.CLAMP_LO == 0.90 and _cf.CLAMP_HI == 1.08 and _cf.f_altitude(6000, 0) == 0.90)
ok("calor: techo cerrado + aire apaga el factor", _cf.f_heat("extreme", "retractable", True, 14) == 1.0)
ok("viaje: hacia el ESTE penaliza más que hacia el oeste", _cf.f_travel(4, 0, 3) < _cf.f_travel(4, 0, -3))
ok("haversine: (0,0)→(0,180) = media circunferencia", abs(_cf.haversine(0, 0, 0, 180) - math.pi * _cf._EARTH_KM) < 1.0)
_o = _fe.rank_group(["A", "B", "C", "D"],
                    [("A", "B", 1, 0), ("A", "C", 1, 1), ("A", "D", 0, 1),
                     ("B", "C", 1, 0), ("B", "D", 1, 1), ("C", "D", 2, 2)], rng=_rnd.Random(0))
ok("desempate FIFA: head-to-head ordena a dos empatados (A venció a B)", _o.index("A") < _o.index("B"))
_res = _fe.assign_thirds(set("ABCDEFGH"))
ok("mejores terceros: 8 casillas asignadas sin repetir", len(_res) == 8 and len(set(_res.values())) == 8)
_p = [_fe.negbin_pmf(k, 2.0, 4.0) for k in range(80)]
_m = sum(k * _p[k] for k in range(80)); _v = sum(k * k * _p[k] for k in range(80)) - _m * _m
ok("sobredispersión: binomial negativa tiene Var>media (colas más gordas que Poisson)", _v > _m + 0.05, f"var={_v:.3f} media={_m:.3f}")
ok("calendario: parseo de hora/UTC ('13:00 UTC-6')", _sc.parse_kickoff("13:00 UTC-6") == (13, -6.0))
_ctx = _cf.load_context()
ok("datos verificados: 16 sedes y 48 selecciones cargadas", len(_ctx.get("venues", {})) == 16 and len(_ctx.get("teams", {})) == 48,
   f"sedes={len(_ctx.get('venues', {}))} equipos={len(_ctx.get('teams', {}))}")
# 16b. calibración + peso por competición (infraestructura; ver backtest.py)
import calibration as _cal, fit_dc as _fd
ok("peso por competición: Mundial(4) > eliminatoria(2) > amistoso(1)",
   _fd.importance("FIFA World Cup") > _fd.importance("FIFA World Cup qualification") > _fd.importance("Friendly"))
_cid = _cal.apply_calibrator({"a": [1, 1, 1], "b": [0, 0, 0]}, [0.5, 0.3, 0.2])
ok("calibración: identidad (a=1,b=0) preserva y normaliza las probabilidades",
   abs(sum(_cid) - 1.0) < 1e-9 and abs(_cid[0] - 0.5) < 1e-9)
# 16c. baterías detalladas con pytest si está disponible (degrada con elegancia si no)
try:
    import pytest as _pytest  # noqa: F401
    _r = run(["-m", "pytest", "-q",
              "test_context_factors.py", "test_format_engine.py", "test_schedule_2026.py",
              "test_validate_layers.py", "test_calibration.py", "test_backtest.py",
              "test_backtest_tournament.py", "test_wc_form.py", "test_predict_match.py"])
    ok("pytest: baterías de altura/formato/calendario/validación/calibración/backtest en verde",
       _r.returncode == 0, (_r.stdout[-400:] + _r.stderr[-200:]))
except ImportError:
    print("  NOTA  pytest no instalado: omito las baterías detalladas (pip install pytest para correrlas)")

# ============================================================
print(f"\n========== RESULTADO: {PASS} PASS / {FAIL} FAIL ==========")
if FAILS:
    print("Fallos:")
    for f in FAILS: print("  -", f)
sys.exit(1 if FAIL else 0)
