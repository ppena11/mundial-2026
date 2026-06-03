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

import daily_digest as dd
import predict_match as pm
import make_script as ms
import make_matchday as mm
import make_weekly as mw
import flags
import fetch_odds
import track_record as tr
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
print(f"\n========== RESULTADO: {PASS} PASS / {FAIL} FAIL ==========")
if FAILS:
    print("Fallos:")
    for f in FAILS: print("  -", f)
sys.exit(1 if FAIL else 0)
