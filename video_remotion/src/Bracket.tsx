import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Easing} from 'remotion';
import {flagColors} from './flags';

// ===== INFOGRAFÍA DEL CUADRO — "RUMBO A NUEVA YORK" (estilo FIFA oficial, data-driven de viral_bracket.json)
// Estados: QF_PENDIENTES / QF_EN_CURSO / SF_LISTAS / SF_EN_CURSO / FINAL_LISTA / CAMPEON
// Coreografía: título golpea -> banderas en cascada POP (zigzag) -> líneas se dibujan -> óvalo FINAL con glow;
// ganadores destellan dorado y VIAJAN por la línea a su llave; eliminados se desaturan en vivo.

const FONT = '"Segoe UI", system-ui, Arial, sans-serif';
const GOLDF = '#C9A45C';           // dorado FIFA (distinto del GOLD de marca, más bronce)
const LINE = '#3A3A40';
const WHITE = '#FFFFFF';

const usePunch = (delay = 0, bounce = 9) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  return spring({frame: f - delay, fps, config: {damping: bounce, mass: 0.6, stiffness: 150}});
};
const shakeAt = (f: number, at: number, dur = 12, mag = 18) => {
  const t = f - at; if (t < 0 || t > dur) return {x: 0, y: 0};
  const d = 1 - t / dur; return {x: Math.sin(t * 3.1) * mag * d, y: Math.cos(t * 4.3) * mag * d};
};
const grow = (f: number, from: number, dur: number) =>
  interpolate(f, [from, from + dur], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
const countUp = (f: number, delay: number, dur: number, target: number) =>
  Math.round(interpolate(f, [delay, delay + dur], [0, target], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)}));

// bandera CIRCULAR con aro (normal / ganadora dorada / eliminada gris)
export const CircleFlag: React.FC<{team?: string | null; d?: number; delay?: number; winner?: boolean; out?: boolean; outAt?: number}> =
  ({team, d = 124, delay = 0, winner = false, out = false, outAt = 0}) => {
  const f = useCurrentFrame();
  const e = usePunch(delay, 8);
  const halo = interpolate(f, [delay, delay + 22], [46, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const gray = out ? grow(f, outAt, 20) : 0;                          // eliminado: se desatura EN VIVO
  const flash = winner ? 14 + 10 * Math.sin(f / 7) : 0;               // ganador: aro dorado que late
  const rot = interpolate(e, [0, 1], [-14, 0]);
  if (!team) return (                                                  // llave vacía: círculo punteado "?"
    <div style={{width: d, height: d, borderRadius: '50%', border: `3px dashed rgba(255,255,255,${0.25 * Math.min(1, e * 1.4)})`,
      display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${0.4 + e * 0.6})`,
      color: 'rgba(255,255,255,0.35)', fontFamily: FONT, fontSize: d * 0.42, fontWeight: 800}}>?</div>);
  return (
    <div style={{width: d, height: d, borderRadius: '50%', overflow: 'hidden', display: 'flex',
      transform: `scale(${0.2 + e * (out ? 0.75 : 0.8) + (winner ? 0.06 : 0)}) rotate(${rot}deg)`,
      border: winner ? `5px solid ${GOLDF}` : '3px solid rgba(255,255,255,0.28)',
      outline: '3px solid rgba(0,0,0,0.55)',
      filter: `grayscale(${gray}) brightness(${1 - gray * 0.45})`, opacity: 1 - gray * 0.55,
      boxShadow: winner ? `0 0 ${flash + halo}px ${GOLDF}CC` : `0 0 ${halo}px rgba(255,255,255,0.5), 0 10px 30px rgba(0,0,0,0.6)`}}>
      {flagColors(team).map((c, i) => <div key={i} style={{flex: 1, background: c}} />)}
    </div>);
};

const Lbl: React.FC<{x: number; y: number; children: React.ReactNode; size?: number; color?: string; w?: number; ls?: number; weight?: number; nowrap?: boolean}> =
  ({x, y, children, size = 24, color = 'rgba(255,255,255,0.55)', w = 300, ls = 2, weight = 700, nowrap = false}) => (
  <div style={{position: 'absolute', left: x - w / 2, top: y - size * 0.7, width: w, textAlign: 'center',
    fontFamily: FONT, fontSize: size, fontWeight: weight, letterSpacing: ls, color,
    ...(nowrap ? {whiteSpace: 'nowrap' as const, overflow: 'visible' as const} : {})}}>{children}</div>);
// nombres de equipo: SIN salto de línea; los largos ('Estados Unidos', 'R.D. Congo'...) bajan de tamaño
const nameSize = (n?: string | null) => ((n || '').length > 13 ? 15 : 21);

// línea que SE DIBUJA (h/v) desde un extremo
const Seg: React.FC<{x: number; y: number; len: number; vert?: boolean; from: number; dur?: number; gold?: boolean; rev?: boolean}> =
  ({x, y, len, vert = false, from, dur = 12, gold = false, rev = false}) => {
  const f = useCurrentFrame(); const g = grow(f, from, dur);
  const l = len * g;
  return <div style={{position: 'absolute', background: gold ? GOLDF : LINE,
    left: vert ? x - 1.5 : (rev ? x - l : x), top: vert ? (rev ? y - l : y) : y - 1.5,
    width: vert ? 3 : l, height: vert ? l : 3, boxShadow: gold ? `0 0 8px ${GOLDF}88` : 'none'}} />;
};

// mini-bandera del ganador que VIAJA por la línea hasta su llave
const Traveler: React.FC<{team: string; x0: number; y0: number; x1: number; y1: number; from: number; d?: number}> =
  ({team, x0, y0, x1, y1, from, d = 96}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [from, from + 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  if (f < from) return null;
  const x = x0 + (x1 - x0) * t, y = y0 + (y1 - y0) * t;
  return <div style={{position: 'absolute', left: x - d / 2, top: y - d / 2}}>
    <CircleFlag team={team} d={d} delay={from} winner /></div>;
};

// confetti dorado determinista (estado CAMPEÓN; sin Math.random — reproducible frame a frame)
const Confetti: React.FC<{from: number}> = ({from}) => {
  const f = useCurrentFrame(); if (f < from) return null;
  const t = f - from;
  return <AbsoluteFill style={{pointerEvents: 'none'}}>
    {Array.from({length: 42}, (_, i) => {
      const x = ((i * 199) % 1040) + 20 + Math.sin((t + i * 7) / 13) * 46;
      const y = ((t * (3.2 + (i % 5))) + i * 173) % 1500;
      const s = 8 + (i % 4) * 4;
      return <div key={i} style={{position: 'absolute', left: x, top: y, width: s, height: s * 1.7,
        background: i % 3 ? GOLDF : WHITE, opacity: 0.85, transform: `rotate(${(t * 6 + i * 40) % 360}deg)`, borderRadius: 2}} />;
    })}
  </AbsoluteFill>;
};

// ===================== CARRERA AL TÍTULO (simulación de MI IA sobre el cuadro) =====================
// Muestra lo que el MODELO ve HOY: % de avanzar en cada llave pendiente, avances "FANTASMA" (translúcidos,
// aro dorado punteado — NUNCA se confunden con un resultado real), la final más probable en el óvalo y el
// campeón más probable con su % en grande. Los cruces YA JUGADOS se ven sólidos (realidad) — el contraste
// realidad vs simulación es el gancho. Cubre todas las fases: cuartos, semis y final definida.
const Pill: React.FC<{x: number; y: number; txt: string; hot?: boolean; delay?: number; w?: number}> = ({x, y, txt, hot = false, delay = 0, w = 112}) => {
  const e = usePunch(delay, 8);
  return <div style={{position: 'absolute', left: x - w / 2, top: y - 21, width: w, textAlign: 'center',
    transform: `scale(${0.3 + e * 0.7})`, opacity: Math.min(1, e * 1.5),
    background: hot ? GOLDF : 'rgba(255,255,255,0.13)', color: hot ? '#0B0B10' : 'rgba(255,255,255,0.75)',
    fontFamily: FONT, fontSize: 26, fontWeight: 900, padding: '7px 0', borderRadius: 999,
    boxShadow: hot ? `0 0 22px ${GOLDF}88` : 'none'}}>{txt}</div>;
};

const Ghost: React.FC<{team: string; x: number; y: number; d?: number; delay?: number}> = ({team, x, y, d = 96, delay = 0}) => {
  const f = useCurrentFrame();
  const e = usePunch(delay, 8);
  if (f < delay) return null;
  return (
    <div style={{position: 'absolute', left: x - d / 2, top: y - d / 2, width: d, height: d, borderRadius: '50%',
      overflow: 'hidden', display: 'flex', opacity: 0.8 * Math.min(1, e * 1.4), transform: `scale(${0.3 + e * 0.7})`,
      border: `4px dashed ${GOLDF}`, boxShadow: `0 0 ${14 + 8 * Math.sin(f / 8)}px ${GOLDF}66`}}>
      {flagColors(team).map((c, i) => <div key={i} style={{flex: 1, background: c, opacity: 0.85}} />)}
    </div>);
};

export const BracketRace: React.FC<{bracket: any; dur?: number; y?: number; s?: number}> = ({bracket = {}, dur = 150, y = 0, s = 1}) => {
  const f = useCurrentFrame();
  const P = bracket.probs || {};
  const qf = bracket.qf || [], sf = bracket.sf || [], fin = bracket.final || {};
  const pOf = (t: string | null, k: string) => (t && P[t] ? (P[t][k] || 0) : 0);
  const favQF = (q: any) => q?.ganador || (!q?.a || !q?.b ? null : (pOf(q.a, 'semis') >= pOf(q.b, 'semis') ? q.a : q.b));
  const T = (x: number) => Math.round(dur * x);
  const sh = shakeAt(f, 5, 12, 14);
  const tE = usePunch(0, 8);
  const float = Math.sin(f / 24) * 4;

  // misma geometría que BracketScene
  const D = 116, cxL = 150, cxR = 930, rows = [386, 534, 762, 910];
  const midT = (rows[0] + rows[1]) / 2, midB = (rows[2] + rows[3]) / 2, midC = (midT + midB) / 2;
  const jxL = 272, jxR = 808, sxL = 350, sxR = 730;
  const OV = {cx: 540, cy: midC, w: 300, h: 142};
  const pairs = [
    {L: true,  r: [0, 1], q: qf[0], sx: sxL, sy: midT}, {L: true,  r: [2, 3], q: qf[1], sx: sxL, sy: midB},
    {L: false, r: [0, 1], q: qf[2], sx: sxR, sy: midT}, {L: false, r: [2, 3], q: qf[3], sx: sxR, sy: midB},
  ];
  // semifinalistas por nodo (REAL si el cuarto ya se jugó; si no, favorito del modelo)
  const nodo = pairs.map(p => ({...p, team: favQF(p.q), real: !!(p.q && p.q.ganador)}));
  // finalista más probable por lado (real si la semi ya se jugó)
  const finalista = (i: number) => {
    if (i === 0 && fin.a) return {t: fin.a, real: true};
    if (i === 1 && fin.b) return {t: fin.b, real: true};
    const [n1, n2] = i === 0 ? [nodo[0], nodo[1]] : [nodo[2], nodo[3]];
    const c = [n1.team, n2.team].filter(Boolean) as string[];
    if (!c.length) return {t: null, real: false};
    return {t: c.sort((a, b) => pOf(b, 'final') - pOf(a, 'final'))[0], real: false};
  };
  const fA = finalista(0), fB = finalista(1);
  const vivos = Object.keys(P);
  const champPred = vivos.sort((a, b) => pOf(b, 'campeon') - pOf(a, 'campeon'))[0] || null;
  const champE = usePunch(T(0.72), 7);
  const champPct = countUp(f, T(0.74), 18, Math.round(pOf(champPred, 'campeon')));
  const ovalE = usePunch(T(0.58), 7);

  return (
    <AbsoluteFill style={{background: '#0B0B10', overflow: 'hidden'}}>
      <AbsoluteFill style={{background: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.016) 0 44px, transparent 44px 88px)'}} />
      <div style={{position: 'absolute', inset: 0, transform: `translateY(${y + float}px) scale(${s})`, transformOrigin: '540px 520px'}}>

        {/* título */}
        <div style={{position: 'absolute', top: 118, width: '100%', textAlign: 'center', transform: `translate(${sh.x}px,${sh.y}px) scale(${0.6 + tE * 0.4})`, opacity: Math.min(1, tE * 1.5)}}>
          <div style={{fontFamily: FONT, fontSize: 27, fontWeight: 800, letterSpacing: 9, color: 'rgba(255,255,255,0.55)'}}>MI IA SIMULÓ LO QUE VIENE</div>
          <div style={{fontFamily: FONT, fontSize: 84, fontWeight: 900, letterSpacing: -2, color: WHITE, lineHeight: 1.02, transform: 'scaleY(1.08)', textShadow: '0 8px 40px rgba(0,0,0,0.8)'}}>LA CARRERA AL TÍTULO</div>
          <div style={{fontFamily: FONT, fontSize: 30, fontWeight: 800, letterSpacing: 5, color: GOLDF, marginTop: 8}}>ASÍ LA VE HOY · SIMULACIÓN</div>
        </div>

        {/* llaves con banderas + duelo de % en los cruces pendientes */}
        {pairs.map((Pr, pi) => {
          const cx = Pr.L ? cxL : cxR, jx = Pr.L ? jxL : jxR;
          const q = Pr.q || {}; const gan = q.ganador;
          const yA = rows[Pr.r[0]], yB = rows[Pr.r[1]], mid = (yA + yB) / 2;
          const edge = cx + (Pr.L ? D / 2 : -D / 2);
          const dA = 8 + pi * 4, lf = T(0.08) + pi * 4;
          const fav = favQF(q);
          const pend = !gan && q.a && q.b;
          return (
            <React.Fragment key={pi}>
              <div style={{position: 'absolute', left: cx - D / 2, top: yA - D / 2}}>
                <CircleFlag team={q.a} d={D} delay={dA} winner={gan === q.a} out={!!gan && gan !== q.a} outAt={lf} /></div>
              <div style={{position: 'absolute', left: cx - D / 2, top: yB - D / 2}}>
                <CircleFlag team={q.b} d={D} delay={dA + 3} winner={gan === q.b} out={!!gan && gan !== q.b} outAt={lf} /></div>
              <Lbl x={cx} y={yA - D / 2 - 20} size={nameSize(q.a)} w={230} nowrap>{(q.a || '').toUpperCase()}</Lbl>
              <Lbl x={cx} y={yB + D / 2 + 26} size={nameSize(q.b)} w={230} nowrap>{(q.b || '').toUpperCase()}</Lbl>
              <Seg x={edge} y={yA} len={Math.abs(jx - edge)} from={lf} rev={!Pr.L} />
              <Seg x={edge} y={yB} len={Math.abs(jx - edge)} from={lf} rev={!Pr.L} />
              <Seg x={jx} y={yA} len={yB - yA} vert from={lf + 4} />
              <Seg x={Pr.L ? jx : Pr.sx} y={mid} len={Math.abs(Pr.sx - jx)} from={lf + 8} gold={!!gan || !!fav} />
              {/* duelo de %: UN pill por llave en la unión (arriba-abajo), dorado = va el favorito */}
              {pend ? <Pill x={jx} y={mid - 64} w={150}
                txt={`${Math.round(pOf(q.a, 'semis'))}–${100 - Math.round(pOf(q.a, 'semis'))}%`} hot
                delay={T(0.12) + pi * 4} /> : null}
              {/* nodo SF: REAL sólido si ya se jugó (APAGADO si luego perdió la semi); FANTASMA si es predicción */}
              {(() => {
                const sfGan = (pi < 2 ? sf[0] : sf[1])?.ganador;      // ganador REAL de la semi de este lado
                if (gan && sfGan && gan !== sfGan)                    // clasificó al QF pero cayó en semis
                  return <div style={{position: 'absolute', left: Pr.sx - 48, top: Pr.sy - 48}}>
                    <CircleFlag team={gan} d={96} delay={lf + 10} out outAt={lf + 24} /></div>;
                if (gan) return <Traveler team={gan} x0={cx} y0={gan === q.a ? yA : yB} x1={Pr.sx} y1={Pr.sy} from={lf + 10} />;
                return fav ? <Ghost team={fav} x={Pr.sx} y={Pr.sy} delay={T(0.3) + pi * 5} /> : null;
              })()}
              {fav && !(pi < 2 ? sf[0] : sf[1])?.ganador
                ? <Pill x={Pr.sx} y={Pr.sy + 84} w={150} txt={`FINAL ${Math.round(pOf(fav, 'final'))}%`} hot={false} delay={T(0.46) + pi * 4} /> : null}
            </React.Fragment>);
        })}

        {/* uniones SF -> centro */}
        <Seg x={sxL} y={midT} len={midB - midT} vert from={T(0.5)} gold />
        <Seg x={sxR} y={midT} len={midB - midT} vert from={T(0.5)} gold />
        <Seg x={sxL} y={midC} len={OV.cx - OV.w / 2 - sxL} from={T(0.55)} gold />
        <Seg x={OV.cx + OV.w / 2} y={midC} len={sxR - (OV.cx + OV.w / 2)} from={T(0.55)} gold />

        {/* óvalo: la FINAL más probable */}
        <div style={{position: 'absolute', left: OV.cx - OV.w / 2, top: OV.cy - OV.h / 2, width: OV.w, height: OV.h,
          borderRadius: '50%', border: `2.5px solid ${GOLDF}`, background: 'rgba(0,0,0,0.6)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          transform: `scale(${0.3 + ovalE * 0.7})`, boxShadow: `0 0 ${16 + 9 * Math.sin(f / 9)}px ${GOLDF}55`}}>
          {fA.t && fB.t ? (
            <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
              <CircleFlag team={fA.t} d={60} delay={T(0.6)} /><span style={{fontFamily: FONT, fontSize: 28, fontWeight: 900, color: WHITE}}>VS</span><CircleFlag team={fB.t} d={60} delay={T(0.62)} /></div>
          ) : <div style={{fontFamily: FONT, fontSize: 40, fontWeight: 900, letterSpacing: 3, color: WHITE}}>FINAL</div>}
          <div style={{fontFamily: FONT, fontSize: 22, fontWeight: 800, letterSpacing: 2, color: GOLDF, marginTop: 5}}>
            {(fA.real && fB.real) ? bracket.final_fecha || '' : 'FINAL MÁS PROBABLE'}</div>
        </div>

        {/* remate: CAMPEÓN MÁS PROBABLE — bandera centrada con el % como chip dorado en su base */}
        {champPred ? (<>
          <Lbl x={540} y={OV.cy - 318} size={30} color={GOLDF} w={800} ls={4} weight={900}>CAMPEÓN MÁS PROBABLE</Lbl>
          <div style={{position: 'absolute', left: 540 - 86, top: OV.cy - 282, transform: `scale(${0.3 + champE * 0.7})`}}>
            <CircleFlag team={champPred} d={172} delay={T(0.72)} winner /></div>
          <div style={{position: 'absolute', left: 540 - 78, top: OV.cy - 134, width: 156, textAlign: 'center',
            opacity: Math.min(1, champE * 1.4), transform: `scale(${0.4 + champE * 0.6})`,
            background: '#0B0B10', border: `3px solid ${GOLDF}`, borderRadius: 999, padding: '6px 0',
            fontFamily: FONT, fontSize: 42, fontWeight: 900, color: GOLDF, boxShadow: `0 0 26px ${GOLDF}66`}}>{champPct}%</div>
        </>) : null}
      </div>
    </AbsoluteFill>
  );
};

// ===================== ESCENA PRINCIPAL =====================
export const BracketScene: React.FC<{bracket: any; y?: number; s?: number}> = ({bracket = {}, y = 0, s = 1}) => {
  const f = useCurrentFrame();
  const qf = bracket.qf || [], sf = bracket.sf || [], fin = bracket.final || {};
  const estado = bracket.estado || 'QF_PENDIENTES';
  const champ = estado === 'CAMPEON' ? fin.ganador : null;
  const sh = shakeAt(f, 5, 12, 14);
  const tE = usePunch(0, 8);
  const ovalE = usePunch(84, 7);
  const champE = usePunch(96, 6);
  const subLS = interpolate(f, [8, 30], [14, 5], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const float = Math.sin(f / 24) * 4;                                  // loop sutil: nunca congelado
  const pulse = 16 + 9 * Math.sin(f / 9);                              // glow del óvalo FINAL

  // geometría (espacio 1080 x ~980, cabe sobre el avatar): filas de banderas y llaves
  const D = 124, cxL = 150, cxR = 930, rows = [386, 534, 762, 910];
  const midT = (rows[0] + rows[1]) / 2, midB = (rows[2] + rows[3]) / 2, midC = (midT + midB) / 2; // 474 / 822 / 648
  const jxL = 272, jxR = 808, sxL = 350, sxR = 730;                    // x de llaves y de nodos SF
  const OV = {cx: 540, cy: midC, w: 300, h: 142};
  const flagDelay = (side: number, row: number) => 10 + (row * 2 + side) * 6;   // cascada POP en zigzag
  // llaves: [ladoIzq?, filas(par de índices), cruce QF, nodo SF (x,y)]
  const pairs = [
    {L: true,  r: [0, 1], q: qf[0], sx: sxL, sy: midT}, {L: true,  r: [2, 3], q: qf[1], sx: sxL, sy: midB},
    {L: false, r: [0, 1], q: qf[2], sx: sxR, sy: midT}, {L: false, r: [2, 3], q: qf[3], sx: sxR, sy: midB},
  ];
  const finListo = estado === 'FINAL_LISTA' || estado === 'CAMPEON';

  return (
    <AbsoluteFill style={{background: '#0B0B10', overflow: 'hidden'}}>
      {/* textura diagonal sutil (look FIFA) */}
      <AbsoluteFill style={{background: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.016) 0 44px, transparent 44px 88px)'}} />
      <div style={{position: 'absolute', inset: 0, transform: `translateY(${y + float}px) scale(${s})`, transformOrigin: '540px 520px'}}>

        {/* título: golpea como sello + subtítulo dorado que respira */}
        <div style={{position: 'absolute', top: 118, width: '100%', textAlign: 'center', transform: `translate(${sh.x}px,${sh.y}px) scale(${0.6 + tE * 0.4})`, opacity: Math.min(1, tE * 1.5)}}>
          <div style={{fontFamily: FONT, fontSize: 27, fontWeight: 800, letterSpacing: 9, color: 'rgba(255,255,255,0.55)'}}>MUNDIAL 2026</div>
          <div style={{fontFamily: FONT, fontSize: bracket.ronda && bracket.ronda.length > 16 ? 76 : 92, fontWeight: 900, letterSpacing: -2, color: WHITE, lineHeight: 1.02, transform: 'scaleY(1.08)', textShadow: '0 8px 40px rgba(0,0,0,0.8)'}}>{bracket.ronda || 'CUARTOS DE FINAL'}</div>
          <div style={{fontFamily: FONT, fontSize: champ ? 40 : 30, fontWeight: 900, letterSpacing: subLS, color: GOLDF, marginTop: 8}}>{champ ? `🏆 ${String(champ).toUpperCase()} 🏆` : 'RUMBO A NUEVA YORK'}</div>
        </div>

        {/* llaves: banderas POP -> líneas que se dibujan -> nodo SF -> centro */}
        {pairs.map((P, pi) => {
          const cx = P.L ? cxL : cxR, jx = P.L ? jxL : jxR;
          const q = P.q || {}; const gan = q.ganador;
          const yA = rows[P.r[0]], yB = rows[P.r[1]], mid = (yA + yB) / 2;
          const dA = flagDelay(P.L ? 0 : 1, P.r[0]), dB = flagDelay(P.L ? 0 : 1, P.r[1]);
          const edge = cx + (P.L ? D / 2 : -D / 2);
          const lf = 48 + pi * 5;                                       // cuándo se dibuja esta llave
          return (
            <React.Fragment key={pi}>
              <div style={{position: 'absolute', left: cx - D / 2, top: yA - D / 2}}>
                <CircleFlag team={q.a} d={D} delay={dA} winner={gan === q.a} out={!!gan && gan !== q.a} outAt={lf + 40} /></div>
              <div style={{position: 'absolute', left: cx - D / 2, top: yB - D / 2}}>
                <CircleFlag team={q.b} d={D} delay={dB} winner={gan === q.b} out={!!gan && gan !== q.b} outAt={lf + 40} /></div>
              {/* nombres: ARRIBA del par y ABAJO del par (no chocan con la otra bandera) */}
              <Lbl x={cx} y={yA - D / 2 - 20} size={nameSize(q.a)} w={230} nowrap>{(q.a || '').toUpperCase()}</Lbl>
              <Lbl x={cx} y={yB + D / 2 + 26} size={nameSize(q.b)} w={230} nowrap>{(q.b || '').toUpperCase()}</Lbl>
              {/* líneas: bandera->llave, unión vertical, llave->nodo SF */}
              <Seg x={edge} y={yA} len={Math.abs(jx - edge)} from={lf} rev={!P.L} />
              <Seg x={edge} y={yB} len={Math.abs(jx - edge)} from={lf} rev={!P.L} />
              <Seg x={jx} y={yA} len={yB - yA} vert from={lf + 8} />
              <Seg x={P.L ? jx : P.sx} y={mid} len={Math.abs(P.sx - jx)} from={lf + 16} gold={!!gan} rev={false} />
              {/* fecha del cruce (sube si hay ganador para no chocar con la bandera que viaja) */}
              <Lbl x={jx} y={mid - (gan ? 72 : 22)} size={23} color={GOLDF} ls={3}>{q.fecha || ''}</Lbl>
              {/* nodo SF: ganador viaja hasta su llave; si no, punteado */}
              {gan
                ? <Traveler team={gan} x0={cx} y0={gan === q.a ? yA : yB} x1={P.sx} y1={P.sy} from={lf + 26} />
                : <div style={{position: 'absolute', left: P.sx - 46, top: P.sy - 46}}><CircleFlag d={92} delay={lf + 20} /></div>}
            </React.Fragment>);
        })}

        {/* uniones SF -> centro */}
        <Seg x={sxL} y={midT} len={midB - midT} vert from={70} gold={!!(sf[0] && sf[0].ganador)} />
        <Seg x={sxR} y={midT} len={midB - midT} vert from={70} gold={!!(sf[1] && sf[1].ganador)} />
        <Seg x={sxL} y={midC} len={OV.cx - OV.w / 2 - sxL} from={78} gold={!!(sf[0] && sf[0].ganador)} />
        <Seg x={OV.cx + OV.w / 2} y={midC} len={sxR - (OV.cx + OV.w / 2)} from={78} gold={!!(sf[1] && sf[1].ganador)} />

        {/* óvalo FINAL: el ojo termina en la meta */}
        <div style={{position: 'absolute', left: OV.cx - OV.w / 2, top: OV.cy - OV.h / 2, width: OV.w, height: OV.h,
          borderRadius: '50%', border: `2.5px solid ${champ ? GOLDF : 'rgba(255,255,255,0.4)'}`,
          background: 'rgba(0,0,0,0.55)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          transform: `scale(${0.3 + ovalE * 0.7})`, boxShadow: `0 0 ${pulse}px ${champ ? GOLDF : 'rgba(255,255,255,0.25)'}`}}>
          {finListo && fin.a && fin.b && !champ ? (
            <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
              <CircleFlag team={fin.a} d={62} delay={92} /><span style={{fontFamily: FONT, fontSize: 30, fontWeight: 900, color: WHITE}}>VS</span><CircleFlag team={fin.b} d={62} delay={96} /></div>
          ) : <div style={{fontFamily: FONT, fontSize: 44, fontWeight: 900, letterSpacing: 4, color: WHITE}}>FINAL</div>}
          <div style={{fontFamily: FONT, fontSize: 27, fontWeight: 800, letterSpacing: 3, color: GOLDF, marginTop: 4}}>{bracket.final_fecha || '19 DE JULIO'}</div>
        </div>

        {/* CAMPEÓN: la bandera al centro (entre el título y el óvalo) + confetti */}
        {champ ? (<>
          <div style={{position: 'absolute', left: 540 - 100, top: OV.cy - 300, transform: `scale(${0.3 + champE * 0.7})`}}>
            <CircleFlag team={champ} d={200} delay={96} winner /></div>
          <Confetti from={100} />
        </>) : null}

        {/* sede de la final, pequeñito bajo el óvalo */}
        <Lbl x={540} y={OV.cy + OV.h / 2 + 30} size={22} w={500}>{(bracket.final_sede || '').toUpperCase()}</Lbl>
      </div>
    </AbsoluteFill>
  );
};
