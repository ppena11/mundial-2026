"""
produce_historico.py — reconstruye el GUION + datos del pronóstico de una fecha PASADA usando EXACTAMENTE lo
que se publicó (predictions_log.jsonl), SIN re-simular el modelo (que hoy daría otros resultados). Sirve para
regenerar videos antiguos (p. ej. tras un reclamo de música) sin cambiar ningún pronóstico.

Qué reproduce fiel: el marcador, el favorito y las probabilidades de cada partido (del log) y la sede/hora (del
calendario). El récord mostrado es el de ESA fecha. La narración (Claude) se vuelve a redactar, pero sobre los
mismos pronósticos. No mete noticias de HOY.

USO:  python produce_historico.py 2026-06-23   ->  voiceover.txt, viral_pronostico.json, caption.txt, youtube.txt
"""
import sys, os, json, shutil
try:
    from env_loader import load_env; load_env()
except Exception:
    pass
import make_script as ms, track_record as trk
try:                                  # histórico: NO mezclar noticias de hoy en la narración
    import contexto
    contexto.noticia_partido = lambda *a, **k: None
    contexto.noticia_mundial = lambda *a, **k: None
except Exception:
    pass

if __name__ == "__main__":
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").replace("-", "")
    if len(arg) != 8:
        print("USO: python produce_historico.py 2026-06-23"); sys.exit(1)
    target = arg
    iso = f"{target[:4]}-{target[4:6]}-{target[6:8]}"
    # récord ANTES de esta fecha (partidos ya jugados), para que el 'Vamos X de Y' sea el de ese día
    graded = [r for r in trk.load_log() if r.get("fecha", "") < iso and r.get("actual") is not None]
    nrec = len(graded); hits = sum(1 for r in graded if r.get("acierto_1x2"))
    rec = {"n": nrec, "aciertos_1x2": hits, "tasa_1x2": round(100 * hits / nrec, 1) if nrec else 0.0}
    bak = None
    if os.path.exists("track_record.json"):
        bak = "track_record.json.histbak"; shutil.copy("track_record.json", bak)
    json.dump(rec, open("track_record.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    try:
        played = ms.played_desde_log(target)
        if not played:
            print(f"(sin pronósticos en el log para {iso})"); sys.exit(1)
        print(f"=== {iso}: {len(played)} pronósticos (DEL LOG, sin re-simular) | récord previo {hits} de {nrec} ===")
        for d in played:
            print(f"   {d['a']} {d['sx']}-{d['sy']} {d['b']}  (fav={d['fav']})")
        vo, cap, ng = ms.build(target, played_override=played)
        open("voiceover.txt", "w", encoding="utf-8").write(vo)
        open("caption.txt", "w", encoding="utf-8").write(cap)
        print(f"→ voiceover.txt + caption.txt + viral_pronostico.json + youtube.txt listos ({ng} partidos)")
    finally:
        if bak:
            shutil.move(bak, "track_record.json")   # restaura el récord real
