import { useEffect, useRef, useState } from 'react';
import type { ViewPolicyName } from '../types';

export type SoundscapeId = 'off' | 'rain' | 'brown' | 'drone';

export interface AmbientSoundController {
  sound: SoundscapeId;
  preferredSound: Exclude<SoundscapeId, 'off'>;
  volume: number;
  autoOnStress: boolean;
  playing: boolean;
  setSound: (id: SoundscapeId) => void;
  setPreferredSound: (id: Exclude<SoundscapeId, 'off'>) => void;
  setVolume: (v: number) => void;
  setAutoOnStress: (v: boolean) => void;
  mute: () => void;
}

function createNoiseBuffer(ctx: AudioContext, mode: 'pink' | 'brown', seconds = 4): AudioBuffer {
  const len = Math.floor(ctx.sampleRate * seconds);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const data = buf.getChannelData(0);
  if (mode === 'brown') {
    let last = 0;
    for (let i = 0; i < len; i++) {
      const white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      data[i] = Math.max(-1, Math.min(1, last * 3.2));
    }
  } else {
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < len; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + white * 0.0555179;
      b1 = 0.99332 * b1 + white * 0.0750759;
      b2 = 0.96900 * b2 + white * 0.1538520;
      b3 = 0.86650 * b3 + white * 0.3104856;
      b4 = 0.55000 * b4 + white * 0.5329522;
      b5 = -0.7616 * b5 - white * 0.0168980;
      const pink = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362;
      b6 = white * 0.115926;
      data[i] = Math.max(-1, Math.min(1, pink * 0.11));
    }
  }
  return buf;
}

/**
 * Pure Web Audio procedural ambient soundscapes (zero external files or API keys).
 * Smoothly fades in/out over 500ms and can optionally auto-fade in under Overwhelmed/Fatigued.
 */
export function useAmbientSound(effectiveMood: ViewPolicyName): AmbientSoundController {
  const [sound, setSoundState] = useState<SoundscapeId>('off');
  const [preferredSound, setPreferredSound] = useState<Exclude<SoundscapeId, 'off'>>('brown');
  const [volume, setVolume] = useState(0.35);
  const [autoOnStress, setAutoOnStress] = useState(false);
  const [manualMuted, setManualMuted] = useState(false);

  const ctxRef = useRef<AudioContext | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const stopNodesRef = useRef<(() => void) | null>(null);

  const setSound = (id: SoundscapeId) => {
    setSoundState(id);
    if (id === 'off') {
      setManualMuted(true);
    } else {
      setManualMuted(false);
      setPreferredSound(id);
    }
  };

  const mute = () => {
    setSoundState('off');
    setManualMuted(true);
  };

  // Optional auto-fade-in during Overwhelmed / Fatigued moods
  useEffect(() => {
    if (!autoOnStress) return;
    const calmingMood = effectiveMood === 'overwhelmed' || effectiveMood === 'fatigued';
    if (calmingMood && sound === 'off' && !manualMuted) {
      setSoundState(preferredSound);
    } else if (!calmingMood && sound !== 'off') {
      setSoundState('off');
    }
    if (!calmingMood) setManualMuted(false);
  }, [autoOnStress, effectiveMood, preferredSound, sound, manualMuted]);

  // Build / teardown audio graph when active sound changes
  useEffect(() => {
    stopNodesRef.current?.();
    stopNodesRef.current = null;
    if (sound === 'off') return;

    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      if (!ctxRef.current) ctxRef.current = new AudioCtx();
      const ctx = ctxRef.current;
      if (ctx.state === 'suspended') void ctx.resume();

      const master = ctx.createGain();
      master.gain.setValueAtTime(0.0001, ctx.currentTime);
      master.gain.linearRampToValueAtTime(Math.max(0.01, volume * 0.45), ctx.currentTime + 0.5);
      master.connect(ctx.destination);
      gainRef.current = master;

      const cleanups: (() => void)[] = [];

      if (sound === 'rain') {
        const src = ctx.createBufferSource();
        src.buffer = createNoiseBuffer(ctx, 'pink', 4);
        src.loop = true;
        const bp = ctx.createBiquadFilter();
        bp.type = 'bandpass';
        bp.frequency.value = 900;
        bp.Q.value = 0.65;
        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = 1800;
        const lfo = ctx.createOscillator();
        const lfoGain = ctx.createGain();
        lfo.frequency.value = 0.15;
        lfoGain.gain.value = 0.12;
        lfo.connect(lfoGain);
        lfoGain.connect(master.gain);
        src.connect(bp);
        bp.connect(lp);
        lp.connect(master);
        src.start();
        lfo.start();
        cleanups.push(() => {
          try { src.stop(); lfo.stop(); src.disconnect(); lfo.disconnect(); } catch { /* ignore */ }
        });
      } else if (sound === 'brown') {
        const src = ctx.createBufferSource();
        src.buffer = createNoiseBuffer(ctx, 'brown', 4);
        src.loop = true;
        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = 320;
        src.connect(lp);
        lp.connect(master);
        src.start();
        cleanups.push(() => {
          try { src.stop(); src.disconnect(); } catch { /* ignore */ }
        });
      } else if (sound === 'drone') {
        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = 420;
        lp.connect(master);
        const freqs = [110, 164.81, 220, 329.63];
        const oscs = freqs.map((f, i) => {
          const osc = ctx.createOscillator();
          const g = ctx.createGain();
          osc.type = i % 2 === 0 ? 'sine' : 'triangle';
          osc.frequency.value = f;
          g.gain.value = i < 2 ? 0.28 : 0.12;
          osc.connect(g);
          g.connect(lp);
          osc.start();
          return osc;
        });
        const lfo = ctx.createOscillator();
        const lfoGain = ctx.createGain();
        lfo.frequency.value = 0.08;
        lfoGain.gain.value = 0.06;
        lfo.connect(lfoGain);
        lfoGain.connect(master.gain);
        lfo.start();
        cleanups.push(() => {
          for (const o of oscs) {
            try { o.stop(); o.disconnect(); } catch { /* ignore */ }
          }
          try { lfo.stop(); lfo.disconnect(); } catch { /* ignore */ }
        });
      }

      stopNodesRef.current = () => {
        try {
          master.gain.setValueAtTime(master.gain.value, ctx.currentTime);
          master.gain.linearRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
          window.setTimeout(() => {
            cleanups.forEach((fn) => fn());
            try { master.disconnect(); } catch { /* ignore */ }
          }, 380);
        } catch {
          cleanups.forEach((fn) => fn());
        }
      };
    } catch {
      /* ignore Web Audio restrictions */
    }

    return () => {
      stopNodesRef.current?.();
      stopNodesRef.current = null;
    };
  }, [sound]); // eslint-disable-line react-hooks/exhaustive-deps

  // Smooth live volume changes without restarting nodes
  useEffect(() => {
    const ctx = ctxRef.current;
    const g = gainRef.current;
    if (ctx && g && sound !== 'off') {
      try {
        g.gain.setTargetAtTime(Math.max(0.01, volume * 0.45), ctx.currentTime, 0.15);
      } catch { /* ignore */ }
    }
  }, [volume, sound]);

  return {
    sound,
    preferredSound,
    volume,
    autoOnStress,
    playing: sound !== 'off',
    setSound,
    setPreferredSound,
    setVolume,
    setAutoOnStress,
    mute,
  };
}
