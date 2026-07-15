"""
make_music.py — genera una CAMA MUSICAL ORIGINAL y libre de derechos para los videos virales.
100% sintetizada aquí (osciladores propios, SIN samples de terceros), así que NUNCA puede recibir un
reclamo de Content ID en YouTube. Progresión pop alegre I-V-vi-IV (Do–Sol–Lam–Fa): pad + bajo + bombo
suave + un arpegio que da chispa. A 12% de volumen bajo la voz suena como un fondo profesional.

USO:  python make_music.py            ->  musica.mp3  (~32 s, loopeable)
"""
import os, subprocess, struct, math, wave, tempfile

SR = 44100

def _ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

# frecuencias (Hz) de las notas que usamos
N = {'C2':65.41,'E2':82.41,'F2':87.31,'G2':98.00,'A2':110.00,
     'C3':130.81,'D3':146.83,'E3':164.81,'F3':174.61,'G3':196.00,'A3':220.00,'B3':246.94,
     'C4':261.63,'D4':293.66,'E4':329.63,'F4':349.23,'G4':392.00,'A4':440.00,'B4':493.88,
     'C5':523.25,'D5':587.33,'E5':659.25,'F5':698.46,'G5':783.99,'A5':880.00}

def _osc(freq, n, detune=0.004):
    """Oscilador cálido: dos dientes ligeramente desafinados + un poco del 2º armónico."""
    out = [0.0]*n
    w1 = 2*math.pi*freq/SR
    w2 = 2*math.pi*freq*(1+detune)/SR
    w3 = 2*math.pi*freq*2/SR
    for i in range(n):
        out[i] = math.sin(w1*i) + 0.6*math.sin(w2*i) + 0.25*math.sin(w3*i)
    return out

def _env(n, a=0.02, r=0.3):
    e = [1.0]*n
    na, nr = int(SR*a), int(SR*r)
    for i in range(min(na, n)): e[i] = i/max(1, na)
    for i in range(min(nr, n)): e[n-1-i] = i/max(1, nr)
    return e

def _add(buf, seg, at, gain=1.0):
    a = int(at*SR)
    for i, v in enumerate(seg):
        j = a+i
        if 0 <= j < len(buf): buf[j] += v*gain

def _pad(notes, dur):
    n = int(SR*dur); mix = [0.0]*n
    for nm in notes:
        o = _osc(N[nm], n, detune=0.005)
        for i in range(n): mix[i] += o[i]
    e = _env(n, a=0.10, r=0.5)
    return [mix[i]*e[i]*0.22 for i in range(n)]

def _bass(nm, dur):
    n = int(SR*dur); o = _osc(N[nm], n, detune=0.0)
    e = _env(n, a=0.01, r=0.25)
    return [o[i]*e[i]*0.5 for i in range(n)]

def _kick(dur=0.5):
    n = int(SR*dur); out = [0.0]*n; ph = 0.0
    for i in range(n):
        t = i/SR
        f = 120*math.exp(-t*32) + 45      # caída de tono (cuerpo del bombo)
        ph += 2*math.pi*f/SR
        out[i] = math.sin(ph)*math.exp(-t*9)*0.55
    return out

def _arp(notes, dur, steps=8):
    n = int(SR*dur); out = [0.0]*n; step = dur/steps
    for s in range(steps):
        nm = notes[s % len(notes)]
        sn = int(SR*step); o = _osc(N[nm], sn, detune=0.002); e = _env(sn, a=0.004, r=step*0.7)
        _add(out, [o[i]*e[i]*0.10 for i in range(sn)], s*step)
    return out

def build(out="musica.mp3"):
    # progresión I-V-vi-IV en Do mayor (la más alegre/universal del pop)
    prog = [
        (['C4','E4','G4'], 'C3', ['C5','E5','G5','E5','C5','E5','G5','C5']),
        (['G3','B3','D4'], 'G2', ['B4','D5','G5','D5','B4','D5','G5','B4']),
        (['A3','C4','E4'], 'A2', ['C5','E5','A5','E5','C5','E5','A5','C5']),
        (['F3','A3','C4'], 'F2', ['A4','C5','F5','C5','A4','C5','F5','A4']),
    ]
    bar = 2.0          # 2 s por acorde
    total = bar*len(prog)
    n = int(SR*total); buf = [0.0]*n
    for k, (ch, bs, ar) in enumerate(prog):
        at = k*bar
        _add(buf, _pad(ch, bar), at, 1.0)
        _add(buf, _bass(bs, bar), at, 0.9)
        _add(buf, _arp(ar, bar), at, 0.9)
        for b in range(4):                         # bombo suave en negras
            _add(buf, _kick(0.5), at + b*0.5, 0.8)
    # normalizar a ~0.9 de pico
    peak = max(1e-6, max(abs(v) for v in buf))
    g = 0.9/peak
    buf = [v*g for v in buf]
    # repetir la progresión (8 s) hasta ~32 s para loop largo
    loops = 4
    full = buf*loops
    # WAV temporal -> mp3
    tmp = tempfile.mktemp(suffix=".wav")
    with wave.open(tmp, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1,min(1,v))*32000)) for v in full))
    ff = _ff()
    subprocess.run([ff, "-y", "-i", tmp, "-af", "lowpass=f=6000,highpass=f=80,afade=t=in:d=1",
                    "-c:a", "libmp3lame", "-q:a", "4", out], capture_output=True)
    try: os.remove(tmp)
    except Exception: pass
    dur = len(full)/SR
    print(f"→ {out} generado: cama original (I-V-vi-IV), {dur:.0f}s, libre de derechos (sintetizada).")
    return os.path.exists(out)

def build_suave(out="musica_suave.mp3"):
    """Cama SUAVE y emotiva (piezas personales): solo pads + bajo tenue, tempo lento, sin bombo ni arpegio."""
    prog = [(['C4','E4','G4'], 'C3'), (['G3','B3','D4'], 'G2'),
            (['A3','C4','E4'], 'A2'), (['F3','A3','C4'], 'F2')]
    bar = 3.6
    total = bar * len(prog)
    n = int(SR * total); buf = [0.0] * n
    for k, (ch, bs) in enumerate(prog):
        at = k * bar
        _add(buf, _pad(ch, bar), at, 1.0)
        _add(buf, _bass(bs, bar), at, 0.45)
    peak = max(1e-6, max(abs(v) for v in buf)); g = 0.85 / peak
    buf = [v * g for v in buf]
    full = buf * 3
    tmp = tempfile.mktemp(suffix=".wav")
    with wave.open(tmp, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32000)) for v in full))
    subprocess.run([_ff(), "-y", "-i", tmp, "-af", "lowpass=f=4200,highpass=f=90,afade=t=in:d=2",
                    "-c:a", "libmp3lame", "-q:a", "4", out], capture_output=True)
    try: os.remove(tmp)
    except Exception: pass
    print(f"→ {out}: cama SUAVE original ({len(full)/SR:.0f}s, libre de derechos).")
    return os.path.exists(out)


if __name__ == "__main__":
    import sys
    if "suave" in sys.argv:
        build_suave()
    else:
        build()
