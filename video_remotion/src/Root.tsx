import React from 'react';
import {Composition} from 'remotion';
import {PronosticoViral, RecapViral} from './Viral';

const FPS = 30;

// duración = la del audio (durationSec en props) o, si no, último word + cola
const calcDur = ({props}: any) => {
  const ds = props && props.durationSec;
  const words = (props && props.words) || [];
  const last = words.length ? words[words.length - 1].e : 60;
  const secs = ds && ds > 0 ? ds + 0.3 : last + 0.8;
  return {durationInFrames: Math.max(FPS * 5, Math.ceil(secs * FPS))};
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="PronosticoViral" component={PronosticoViral as any}
      fps={FPS} width={1080} height={1920} durationInFrames={1800}
      defaultProps={{words: [] as any, data: {} as any, audio: 'voz.mp3', durationSec: 0, avatar: ''}}
      calculateMetadata={calcDur as any}
    />
    <Composition
      id="RecapViral" component={RecapViral as any}
      fps={FPS} width={1080} height={1920} durationInFrames={1200}
      defaultProps={{words: [] as any, data: {} as any, audio: 'recap_voz.mp3', durationSec: 0, avatar: ''}}
      calculateMetadata={calcDur as any}
    />
  </>
);
