import React from 'react';
import {AbsoluteFill, Audio, Sequence, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, Easing} from 'remotion';
import {flagColors} from './flags';

// ---------- paleta MUNDIAL 2026 ----------
const MAGENTA = '#FF2D78', BLUE = '#2563EB', TEAL = '#06D6C8', GREEN = '#22C55E', RED = '#EF4444', GOLD = '#FCD34D';
const INK = '#0A0A1F', WHITE = '#FFFFFF', FONT = '"Segoe UI", system-ui, Arial, sans-serif';

type Word = {w: string; t: number; e: number};
const norm = (s: string) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]/g, '');

// primer tiempo en que la voz nombra a un equipo (para anclar las tarjetas al audio)
const anchorOf = (words: Word[], team: string, fromT = 0): number | null => {
  const key = norm(team.split(' ')[0]);
  for (const w of words) if (w.t >= fromT && norm(w.w).startsWith(key) && key.length >= 3) return w.t;
  return null;
};

const usePunch = (delay = 0, bounce = 9) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  return spring({frame: f - delay, fps, config: {damping: bounce, mass: 0.6, stiffness: 150}});
};
const shakeAt = (f: number, at: number, dur = 12, mag = 18) => {
  const t = f - at; if (t < 0 || t > dur) return {x: 0, y: 0};
  const d = 1 - t / dur; return {x: Math.sin(t * 3.1) * mag * d, y: Math.cos(t * 4.3) * mag * d};
};
const countUp = (f: number, delay: number, dur: number, target: number) =>
  Math.round(interpolate(f, [delay, delay + dur], [0, target], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)}));

// ---------- fondo Mundial + líneas de campo ----------
const Bg: React.FC = () => {
  const f = useCurrentFrame();
  const blob = (x: number, y: number, c: string, sp: number, r: number) => (
    <div style={{position: 'absolute', width: r, height: r, left: x + Math.sin(f / sp) * 110, top: y + Math.cos(f / (sp * 1.2)) * 110, background: c, filter: 'blur(120px)', borderRadius: '50%', opacity: 0.5}} />
  );
  return (
    <AbsoluteFill style={{background: 'linear-gradient(160deg,#360E5E 0%,#2A0E66 30%,#0E2A78 62%,#06304F 100%)'}}>
      {blob(40, 200, MAGENTA, 52, 560)}{blob(560, 980, BLUE, 66, 640)}{blob(220, 1560, TEAL, 80, 520)}
      <div style={{position: 'absolute', left: '50%', top: '40%', width: 560, height: 560, marginLeft: -280, marginTop: -280, border: '3px solid rgba(255,255,255,0.05)', borderRadius: '50%'}} />
      <div style={{position: 'absolute', left: 0, right: 0, top: '40%', height: 3, background: 'rgba(255,255,255,0.05)'}} />
      <AbsoluteFill style={{boxShadow: 'inset 0 0 460px rgba(0,0,0,0.7)'}} />
    </AbsoluteFill>
  );
};

const TopBar: React.FC<{fecha?: string}> = ({fecha}) => {
  const f = useCurrentFrame(); const {durationInFrames} = useVideoConfig();
  return (
    <>
      <div style={{position: 'absolute', top: 0, left: 0, height: 10, width: `${(f / durationInFrames) * 100}%`, background: `linear-gradient(90deg,${MAGENTA},${GOLD},${TEAL})`}} />
      <div style={{position: 'absolute', top: 58, left: 54, fontSize: 38, fontWeight: 800, color: WHITE, fontFamily: FONT}}>@aiwithpedro</div>
      <div style={{position: 'absolute', top: 58, right: 54, background: `linear-gradient(90deg,${MAGENTA},${BLUE})`, color: WHITE, fontFamily: FONT, fontSize: 28, fontWeight: 900, letterSpacing: 1, padding: '8px 16px', borderRadius: 999}}>MUNDIAL 2026{fecha ? ` · ${fecha}` : ''}</div>
    </>
  );
};

// ---------- tu CLON (HeyGen) en círculo abajo-centro (mudo: la voz la pone el video) ----------
const Avatar: React.FC<{src?: string}> = ({src}) => {
  if (!src) return null;
  const f = useCurrentFrame();
  const float = Math.sin(f / 22) * 6;
  return (
    <div style={{position: 'absolute', bottom: 250, left: '50%', marginLeft: -235, width: 470, height: 470,
      borderRadius: '50%', overflow: 'hidden', border: `7px solid ${GOLD}`,
      boxShadow: `0 0 60px rgba(0,0,0,0.55), 0 0 36px ${GOLD}44`, background: 'rgba(8,8,30,0.35)', transform: `translateY(${float}px)`}}>
      <OffthreadVideo src={staticFile(src)} muted style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center 30%', transform: 'scale(2.2)'}} />
    </div>
  );
};

// ---------- captions kinéticas sincronizadas a las palabras ----------
const Captions: React.FC<{words: Word[]; bottom?: number}> = ({words, bottom = 250}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig(); const t = frame / fps;
  const lines: {toks: Word[]; start: number; end: number}[] = React.useMemo(() => {
    const out: any[] = []; let cur: Word[] = [];
    for (const w of words) {
      cur.push(w);
      if (cur.length >= 3 || /[.!?]$/.test(w.w)) {out.push({toks: cur, start: cur[0].t, end: cur[cur.length - 1].e}); cur = [];}
    }
    if (cur.length) out.push({toks: cur, start: cur[0].t, end: cur[cur.length - 1].e});
    return out;
  }, [words]);
  if (!lines.length) return null;
  const line = lines.find((l) => t >= l.start - 0.1 && t <= l.end + 0.18) || (t < lines[0].start ? lines[0] : null);
  if (!line) return null;
  const lf = frame - Math.round(line.start * fps);
  const lin = spring({frame: lf, fps, config: {damping: 11, mass: 0.5, stiffness: 160}});
  return (
    <div style={{position: 'absolute', bottom, left: 40, right: 40, textAlign: 'center', transform: `scale(${0.85 + lin * 0.15})`}}>
      <div style={{display: 'inline-flex', flexWrap: 'wrap', gap: '10px 14px', justifyContent: 'center'}}>
        {line.toks.map((tok, i) => {
          const active = t >= tok.t - 0.03 && t <= tok.e + 0.08;
          const pop = spring({frame: frame - Math.round(tok.t * fps), fps, config: {damping: 8, mass: 0.5, stiffness: 170}});
          return (
            <span key={i} style={{
              fontFamily: FONT, fontWeight: 900, textTransform: 'uppercase', letterSpacing: -1,
              fontSize: active ? 104 : 84, lineHeight: 1.0, color: active ? INK : WHITE,
              background: active ? `linear-gradient(180deg,${GOLD},#F59E0B)` : 'transparent',
              padding: active ? '0 16px' : '0 4px', borderRadius: 14,
              textShadow: active ? 'none' : '0 6px 22px rgba(0,0,0,0.7)',
              transform: `scale(${(active ? 1.05 : 1) * (0.4 + pop * 0.6)})`, display: 'inline-block',
              boxShadow: active ? `0 12px 40px ${GOLD}66` : 'none',
            }}>{tok.w}</span>
          );
        })}
      </div>
    </div>
  );
};

const Flag: React.FC<{team: string; w?: number}> = ({team, w = 96}) => (
  <div style={{display: 'flex', width: w, height: w * 0.66, borderRadius: 8, overflow: 'hidden', border: '2px solid rgba(255,255,255,0.5)', boxShadow: '0 4px 16px rgba(0,0,0,0.45)'}}>
    {flagColors(team).map((c, i) => <div key={i} style={{flex: 1, background: c}} />)}
  </div>
);

const Scene: React.FC<{children: React.ReactNode; dur: number; shake?: {x: number; y: number}}> = ({children, dur, shake}) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [0, 7], [0, 1], {extrapolateRight: 'clamp'});
  const zoom = 1 + (f / Math.max(dur, 1)) * 0.08;
  return <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', paddingTop: 300, paddingLeft: 56, paddingRight: 56, opacity: op, transform: `scale(${zoom}) translate(${shake?.x ?? 0}px,${shake?.y ?? 0}px)`}}>{children}</AbsoluteFill>;
};

// tarjeta VS de un partido con reveal de marcador + % de confianza
const MatchCard: React.FC<{p: any; dur: number}> = ({p, dur}) => {
  const f = useCurrentFrame();
  const e = usePunch(2, 8);
  const score = usePunch(12, 7);
  const sedeE = usePunch(24);
  const prob = countUp(f, 18, 20, p.fp || 0);
  const sh = shakeAt(f, 30, 10, 9);
  const Team = ({name, fav}: {name: string; fav: boolean}) => (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, width: 300}}>
      <Flag team={name} w={104} />
      <div style={{fontFamily: FONT, fontSize: name.length > 11 ? 38 : 46, fontWeight: 900, color: fav ? GOLD : WHITE, textAlign: 'center', lineHeight: 1.05}}>{name}</div>
    </div>
  );
  return (
    <Scene dur={dur} shake={sh}>
      <div style={{display: 'flex', gap: 12, marginBottom: 22, transform: `scale(${e})`, justifyContent: 'center'}}>
        {p.destacado ? <div style={{background: `linear-gradient(90deg,${MAGENTA},${BLUE})`, color: WHITE, fontFamily: FONT, fontSize: 32, fontWeight: 900, letterSpacing: 2, padding: '10px 24px', borderRadius: 999}}>PICK DEL DÍA</div> : null}
        {p.ronda ? <div style={{background: `linear-gradient(90deg,${GOLD},#F59E0B)`, color: INK, fontFamily: FONT, fontSize: 32, fontWeight: 900, letterSpacing: 2, padding: '10px 24px', borderRadius: 999, boxShadow: `0 0 32px ${GOLD}66`}}>🏆 {p.ronda}</div> : null}
        {p.hora_corta ? <div style={{background: 'rgba(255,255,255,0.12)', border: `2px solid ${TEAL}`, color: WHITE, fontFamily: FONT, fontSize: 32, fontWeight: 800, padding: '8px 22px', borderRadius: 999}}>🕐 {p.hora_corta}</div> : null}
      </div>
      <div style={{transform: `scale(${0.7 + e * 0.3})`, opacity: Math.min(1, e * 1.6), background: 'rgba(10,10,40,0.55)', border: '3px solid rgba(255,255,255,0.18)', borderRadius: 34, padding: '40px 36px', boxShadow: '0 24px 70px rgba(0,0,0,0.5)'}}>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8}}>
          <Team name={p.a} fav={p.fav === p.a} />
          <div style={{transform: `scale(${score})`, fontFamily: FONT, fontSize: 124, fontWeight: 900, color: WHITE, padding: '0 12px'}}>{p.sx}<span style={{color: MAGENTA}}>-</span>{p.sy}</div>
          <Team name={p.b} fav={p.fav === p.b} />
        </div>
      </div>
      <div style={{marginTop: 30, transform: `scale(${score})`, display: 'flex', alignItems: 'center', gap: 16, background: `linear-gradient(90deg,${GREEN},${TEAL})`, color: INK, fontFamily: FONT, fontWeight: 900, padding: '14px 36px', borderRadius: 999, boxShadow: `0 0 50px ${GREEN}55`}}>
        <span style={{fontSize: 84}}>{prob}%</span><span style={{fontSize: 36}}>{p.fav}</span>
      </div>
      {(p.destacado || p.is_ko) && p.sede ? <div style={{marginTop: 22, opacity: Math.min(1, sedeE * 1.5), fontFamily: FONT, fontSize: 34, fontWeight: 700, color: '#C9D4F0', textAlign: 'center'}}>{p.sede.split(',')[0]}</div> : null}
    </Scene>
  );
};

// ===================== PRONÓSTICO VIRAL =====================
export const PronosticoViral: React.FC<{words: Word[]; data: any; audio: string; avatar?: string}> = ({words = [], data = {}, audio = 'voz.mp3', avatar = ''}) => {
  const {fps, durationInFrames} = useVideoConfig();
  const partidos = data.partidos || [];
  const brandStart = durationInFrames - Math.round(fps * 2.2);
  const champStart = brandStart - Math.round(fps * 4);        // carrera al título (4s)
  const resumenStart = champStart - Math.round(fps * 4.8);    // tarjeta-resumen capturable (4.8s)
  // Anclar cada tarjeta a la 1ª MENCIÓN real de su equipo en la voz (independiente), y ORDENAR las tarjetas
  // por ese tiempo: así aparecen en el ORDEN en que el narrador las nombra y quedan SINCRONIZADAS. (El orden de
  // 'partidos' va por hora del partido, que NO coincide con el de la narración —el narrador abre por el estrella—
  // por eso el anclado secuencial anterior desincronizaba y dejaba fuera las últimas tarjetas.)
  const hookMin = Math.round(fps * Math.min(6, (durationInFrames / fps) * 0.10));  // intro CORTA (IA+fecha+récord); las tarjetas entran ~6-7s
  const minGap = Math.round(fps * 1.4);
  const tagged = partidos.map((p: any, i: number) => {
    const aT = anchorOf(words, p.a, hookMin / fps);
    const bT = anchorOf(words, p.b, hookMin / fps);
    const cand = [aT, bT].filter((x): x is number => x != null);
    return {p, i, t: cand.length ? Math.min(...cand) : null};
  });
  const ordered = tagged.slice().sort((x, y) => {
    if (x.t == null && y.t == null) return x.i - y.i;   // sin mención: al final, orden original
    if (x.t == null) return 1;
    if (y.t == null) return -1;
    return x.t - y.t;
  });
  const starts: number[] = [];
  let prev = hookMin - minGap;
  for (const it of ordered) {                            // starts monótonos sin solape (respeta minGap)
    let s = it.t != null ? Math.round(it.t * fps) : prev + minGap;
    if (s < prev + minGap) s = prev + minGap;
    starts.push(s); prev = s;
  }
  const firstCard = starts.length ? starts[0] : hookMin;

  return (
    <AbsoluteFill style={{background: '#0A0A1F'}}>
      <Audio src={staticFile(audio)} />
      <Audio src={staticFile('musica.mp3')} volume={0.12} loop />
      <Bg />

      {/* INTRO: la tarjeta con TODOS los pronósticos (fecha + IA) mientras la voz dice la intro, hasta la 1ª tarjeta */}
      <Sequence from={0} durationInFrames={firstCard}><ResumenCard data={data} intro /></Sequence>

      {/* tarjetas de partido, en ORDEN de narración y ancladas a la voz */}
      {ordered.map((it: any, k: number) => {
        const start = starts[k];
        const next = k + 1 < starts.length ? starts[k + 1] : resumenStart;
        const cdur = Math.max(Math.round(fps * 1.5), next - start);
        if (start >= resumenStart) return null;
        return <Sequence key={it.i} from={start} durationInFrames={Math.min(cdur, resumenStart - start)}><MatchCard p={it.p} dur={cdur} /></Sequence>;
      })}

      {/* tarjeta-resumen capturable (todos los pronósticos) */}
      <Sequence from={resumenStart} durationInFrames={champStart - resumenStart}><ResumenCard data={data} /></Sequence>
      {/* carrera al título */}
      <Sequence from={champStart} durationInFrames={brandStart - champStart}><ChampRace campeon={data.campeon || []} /></Sequence>
      {/* cierre */}
      <Sequence from={brandStart} durationInFrames={durationInFrames - brandStart}><Brand /></Sequence>

      <Avatar src={avatar} />
      <TopBar fecha={data.fecha} />
      <Captions words={words} bottom={avatar ? 760 : 250} />
    </AbsoluteFill>
  );
};

const HookPron: React.FC<{data: any}> = ({data}) => {
  const e = usePunch(2, 7); const b = usePunch(22, 8);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 64, textAlign: 'center'}}>
      <div style={{transform: `scale(${0.4 + e * 0.6})`, opacity: Math.min(1, e * 2)}}>
        <div style={{fontFamily: FONT, fontSize: 60, fontWeight: 800, color: GOLD, letterSpacing: 3}}>MUNDIAL 2026 · HOY</div>
        <div style={{fontFamily: FONT, fontSize: 150, fontWeight: 900, lineHeight: 0.95, letterSpacing: -3, background: `linear-gradient(120deg,${MAGENTA},${GOLD},${TEAL})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent'}}>{(data.partidos || []).length} PRONÓSTICOS</div>
      </div>
      <div style={{marginTop: 50, transform: `scale(${0.3 + b * 0.7})`, opacity: Math.min(1, b * 2), fontFamily: FONT, fontSize: 56, fontWeight: 800, color: WHITE}}>en 60 segundos ⚽</div>
    </AbsoluteFill>
  );
};

const IntroPron: React.FC<{data: any}> = ({data}) => {
  const f = useCurrentFrame();
  const e = usePunch(2, 8); const big = usePunch(22, 8);
  const rec = data.record || {};
  const hits = countUp(f, 24, 22, rec.aciertos || 0);
  const intro = (data.intro || 'mi inteligencia artificial ya jugó la jornada');
  return (
    <Scene dur={200}>
      <div style={{transform: `scale(${0.72 + e * 0.28})`, textAlign: 'center', marginBottom: rec.n ? 40 : 0}}>
        <div style={{fontFamily: FONT, fontSize: 66, fontWeight: 900, color: WHITE, lineHeight: 1.12, textTransform: 'uppercase', letterSpacing: -1}}>{intro}</div>
      </div>
      {rec.n ? (
        <div style={{transform: `scale(${0.6 + big * 0.4})`, textAlign: 'center'}}>
          <div style={{fontFamily: FONT, fontSize: 48, fontWeight: 700, color: '#9FB3D1'}}>récord del modelo</div>
          <div style={{fontFamily: FONT, fontSize: 152, fontWeight: 900, lineHeight: 1, background: `linear-gradient(120deg,${TEAL},${GREEN})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent'}}>{hits}/{rec.n}</div>
          <div style={{fontFamily: FONT, fontSize: 46, fontWeight: 900, color: WHITE, letterSpacing: 5}}>ACIERTOS</div>
        </div>
      ) : null}
    </Scene>
  );
};

// tarjeta-resumen CAPTURABLE: todos los pronósticos del día (para screenshot + compartir)
const ResumenCard: React.FC<{data: any; intro?: boolean}> = ({data, intro = false}) => {
  const e = usePunch(2, 8);
  const partidos = data.partidos || [];
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', paddingTop: 250, paddingLeft: 46, paddingRight: 46}}>
      <div style={{transform: `scale(${0.86 + e * 0.14})`, width: 960, background: 'rgba(8,8,32,0.78)', border: `4px solid ${GOLD}`, borderRadius: 38, padding: '38px 34px', boxShadow: '0 24px 90px rgba(0,0,0,0.65)'}}>
        <div style={{textAlign: 'center', marginBottom: 22}}>
          <div style={{fontFamily: FONT, fontSize: 42, fontWeight: 900, color: GOLD, letterSpacing: 2}}>PRONÓSTICOS DE HOY</div>
          <div style={{fontFamily: FONT, fontSize: 34, fontWeight: 800, color: WHITE}}>Mundial 2026 · {data.fecha}</div>
          <div style={{fontFamily: FONT, fontSize: 28, fontWeight: 800, color: TEAL, marginTop: 4}}>🤖 mi inteligencia artificial</div>
        </div>
        {partidos.map((p: any, i: number) => (
          <div key={i} style={{display: 'flex', alignItems: 'center', gap: 12, padding: '13px 4px', borderBottom: i < partidos.length - 1 ? '2px solid rgba(255,255,255,0.09)' : 'none'}}>
            <Flag team={p.a} w={54} />
            <div style={{flex: 1, textAlign: 'right', fontFamily: FONT, fontSize: 33, fontWeight: 800, color: p.fav === p.a ? GOLD : WHITE, whiteSpace: 'nowrap', overflow: 'hidden'}}>{p.a}</div>
            <div style={{fontFamily: FONT, fontSize: 46, fontWeight: 900, color: WHITE, minWidth: 118, textAlign: 'center', background: `linear-gradient(180deg,${MAGENTA}33,${BLUE}33)`, borderRadius: 12, padding: '2px 0'}}>{p.sx}<span style={{color: MAGENTA}}>-</span>{p.sy}</div>
            <div style={{flex: 1, textAlign: 'left', fontFamily: FONT, fontSize: 33, fontWeight: 800, color: p.fav === p.b ? GOLD : WHITE, whiteSpace: 'nowrap', overflow: 'hidden'}}>{p.b}</div>
            <Flag team={p.b} w={54} />
          </div>
        ))}
        <div style={{textAlign: 'center', marginTop: 22, fontFamily: FONT, fontSize: 32, fontWeight: 800, color: TEAL}}>{intro ? '@aiwithpedro · el Mundial en 60 segundos' : '@aiwithpedro · captura y comparte 📸'}</div>
      </div>
    </AbsoluteFill>
  );
};

const ChampRace: React.FC<{campeon: [string, number][]}> = ({campeon}) => {
  const top = (campeon || []).slice(0, 5);
  const maxv = Math.max(1, ...top.map((x) => x[1]));
  const title = usePunch(2, 8);
  return (
    <Scene dur={200}>
      <div style={{transform: `scale(${0.7 + title * 0.3})`, fontFamily: FONT, fontSize: 64, fontWeight: 900, color: WHITE, marginBottom: 34}}>🏆 CARRERA AL TÍTULO</div>
      <div style={{width: 880, display: 'flex', flexDirection: 'column', gap: 18}}>
        {top.map((row, i) => <ChampRow key={i} row={row} maxv={maxv} delay={10 + i * 8} />)}
      </div>
    </Scene>
  );
};

const ChampRow: React.FC<{row: [string, number]; maxv: number; delay: number}> = ({row, maxv, delay}) => {
  const e = usePunch(delay, 10);
  const w = (row[1] / maxv) * 100 * e;
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
      <Flag team={row[0]} w={72} />
      <div style={{flex: 1, height: 56, background: 'rgba(255,255,255,0.08)', borderRadius: 12, overflow: 'hidden', position: 'relative'}}>
        <div style={{height: '100%', width: `${w}%`, background: `linear-gradient(90deg,${MAGENTA},${TEAL})`, borderRadius: 12}} />
        <div style={{position: 'absolute', left: 16, top: 8, fontFamily: FONT, fontSize: 34, fontWeight: 900, color: WHITE}}>{row[0]}</div>
      </div>
      <div style={{width: 110, textAlign: 'right', fontFamily: FONT, fontSize: 40, fontWeight: 900, color: GOLD}}>{row[1].toFixed(1)}%</div>
    </div>
  );
};

const Brand: React.FC = () => {
  const e = usePunch(2, 8);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 64}}>
      <div style={{transform: `scale(${0.6 + e * 0.4})`, opacity: Math.min(1, e * 1.6), textAlign: 'center'}}>
        <div style={{width: 140, height: 140, borderRadius: '50%', background: `linear-gradient(135deg,${MAGENTA},${GOLD},${TEAL})`, margin: '0 auto 30px', boxShadow: `0 0 70px ${MAGENTA}`}} />
        <div style={{fontFamily: FONT, fontSize: 96, fontWeight: 900, color: WHITE}}>@aiwithpedro</div>
        <div style={{fontFamily: FONT, fontSize: 44, fontWeight: 800, color: GOLD, marginTop: 12}}>el Mundial en 60 segundos al día</div>
        <div style={{marginTop: 34, display: 'inline-block', background: WHITE, color: INK, fontFamily: FONT, fontSize: 46, fontWeight: 900, padding: '18px 44px', borderRadius: 999}}>SÍGUELO 👆</div>
      </div>
    </AbsoluteFill>
  );
};

// ===================== RECAP VIRAL =====================
export const RecapViral: React.FC<{words: Word[]; data: any; audio: string; avatar?: string}> = ({words = [], data = {}, audio = 'recap_voz.mp3', avatar = ''}) => {
  const {fps, durationInFrames} = useVideoConfig();
  const partidos = data.partidos || [];
  const firstCard = Math.round(fps * 2.6);
  const recordStart = durationInFrames - Math.round(fps * 6);
  const brandStart = durationInFrames - Math.round(fps * 2.0);
  return (
    <AbsoluteFill style={{background: '#0A0A1F'}}>
      <Audio src={staticFile(audio)} />
      <Bg />
      <Sequence from={0} durationInFrames={firstCard}><HookRecap data={data} /></Sequence>
      {partidos.slice(0, 2).map((p: any, i: number) => {
        const span = Math.max(1, recordStart - firstCard);
        const start = firstCard + Math.round((span / Math.min(2, partidos.length)) * i);
        const dur = Math.round(span / Math.min(2, partidos.length));
        return <Sequence key={i} from={start} durationInFrames={dur}><ResultCard p={p} /></Sequence>;
      })}
      <Sequence from={recordStart} durationInFrames={brandStart - recordStart}><RecordScene data={data} /></Sequence>
      <Sequence from={brandStart} durationInFrames={durationInFrames - brandStart}><Brand /></Sequence>
      <Avatar src={avatar} />
      <TopBar fecha={data.fecha} />
      <Captions words={words} bottom={avatar ? 760 : 250} />
    </AbsoluteFill>
  );
};

const HookRecap: React.FC<{data: any}> = ({data}) => {
  const e = usePunch(2, 7);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 64, textAlign: 'center'}}>
      <div style={{transform: `scale(${0.4 + e * 0.6})`, opacity: Math.min(1, e * 2)}}>
        <div style={{fontFamily: FONT, fontSize: 64, fontWeight: 800, color: GOLD}}>ANOCHE EN EL MUNDIAL</div>
        <div style={{fontFamily: FONT, fontSize: 150, fontWeight: 900, letterSpacing: -3, background: `linear-gradient(120deg,${GREEN},${TEAL})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent'}}>¿LE ATINÉ?</div>
      </div>
    </AbsoluteFill>
  );
};

const ResultCard: React.FC<{p: any}> = ({p}) => {
  const f = useCurrentFrame(); const e = usePunch(2, 8); const stamp = usePunch(16, 7);
  const ok = !!p.acierto;
  const sh = shakeAt(f, 16, 10, 10);
  return (
    <Scene dur={120} shake={sh}>
      <div style={{transform: `scale(${0.7 + e * 0.3})`, opacity: Math.min(1, e * 1.6), background: 'rgba(10,10,40,0.55)', border: `3px solid ${ok ? GREEN : RED}`, borderRadius: 34, padding: '40px 40px', textAlign: 'center', boxShadow: `0 0 50px ${(ok ? GREEN : RED)}44`}}>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18}}>
          <Flag team={p.a} w={92} />
          <div style={{fontFamily: FONT, fontSize: 96, fontWeight: 900, color: WHITE}}>{p.real_sx ?? p.sx}<span style={{color: MAGENTA}}>-</span>{p.real_sy ?? p.sy}</div>
          <Flag team={p.b} w={92} />
        </div>
        <div style={{marginTop: 14, fontFamily: FONT, fontSize: 34, fontWeight: 700, color: '#9FB3D1'}}>{p.a} vs {p.b}</div>
        {p.pred ? <div style={{marginTop: 6, fontFamily: FONT, fontSize: 30, color: '#9FB3D1'}}>pronóstico: {p.pred}</div> : null}
      </div>
      <div style={{marginTop: 30, transform: `scale(${stamp})`, background: ok ? GREEN : RED, color: WHITE, fontFamily: FONT, fontSize: 60, fontWeight: 900, padding: '14px 40px', borderRadius: 20}}>{ok ? '✓ ACERTÉ' : '✗ FALLÉ'}</div>
    </Scene>
  );
};

const RecordScene: React.FC<{data: any}> = ({data}) => {
  const f = useCurrentFrame(); const hits = data.aciertos ?? data.hits ?? 0; const n = data.n ?? 0;
  const big = usePunch(2, 8); const cnt = countUp(f, 6, 22, hits);
  return (
    <Scene dur={180}>
      <div style={{transform: `scale(${0.6 + big * 0.4})`, textAlign: 'center'}}>
        <div style={{fontFamily: FONT, fontSize: 56, fontWeight: 800, color: '#9FB3D1'}}>el récord del modelo</div>
        <div style={{fontFamily: FONT, fontSize: 180, fontWeight: 900, color: GREEN, lineHeight: 1, textShadow: `0 0 50px ${GREEN}66`}}>{cnt}/{n}</div>
        <div style={{fontFamily: FONT, fontSize: 50, fontWeight: 900, color: WHITE, letterSpacing: 4}}>ACIERTOS</div>
      </div>
    </Scene>
  );
};
