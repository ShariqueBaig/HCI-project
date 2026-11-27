import { useEffect, useState } from 'react';
import { Pause, Play, RotateCcw, Wind } from 'lucide-react';

type PatternKey = '4-7-8' | 'box';

const PATTERNS: Record<PatternKey, Array<{ label: string; seconds: number; scale: number }>> = {
  '4-7-8': [
    { label: 'Inhale gently', seconds: 4, scale: 1.28 },
    { label: 'Hold softly', seconds: 7, scale: 1.28 },
    { label: 'Exhale slowly', seconds: 8, scale: 0.88 },
  ],
  box: [
    { label: 'Inhale', seconds: 4, scale: 1.26 },
    { label: 'Hold', seconds: 4, scale: 1.26 },
    { label: 'Exhale', seconds: 4, scale: 0.88 },
    { label: 'Rest', seconds: 4, scale: 0.88 },
  ],
};

export function SomaticResetWidget() {
  const [pattern, setPattern] = useState<PatternKey>('4-7-8');
  const [running, setRunning] = useState<boolean>(false);
  const [phaseIdx, setPhaseIdx] = useState<number>(0);
  const [secLeft, setSecLeft] = useState<number>(PATTERNS['4-7-8'][0].seconds);
  const [cycles, setCycles] = useState<number>(0);

  const phases = PATTERNS[pattern];
  const currentPhase = phases[phaseIdx % phases.length];

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => {
      setSecLeft((prev) => {
        if (prev > 1) return prev - 1;
        setPhaseIdx((idx) => {
          const next = (idx + 1) % phases.length;
          if (next === 0) setCycles((c) => c + 1);
          setSecLeft(phases[next].seconds);
          return next;
        });
        return prev;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, phases]);

  const switchPattern = (nextPattern: PatternKey) => {
    setRunning(false);
    setPattern(nextPattern);
    setPhaseIdx(0);
    setSecLeft(PATTERNS[nextPattern][0].seconds);
  };

  return (
    <section
      className="rounded-3xl border p-5 shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Wind className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
          <h3 className="text-sm font-bold">Somatic Breathing Pacer</h3>
        </div>
        <div className="flex rounded-lg border p-0.5 text-[11px]" style={{ borderColor: 'var(--aura-border)' }}>
          {(['4-7-8', 'box'] as PatternKey[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => switchPattern(key)}
              className="rounded-md px-2 py-0.5 font-semibold cursor-pointer"
              style={{
                backgroundColor: pattern === key ? 'var(--aura-accent-soft)' : 'transparent',
                color: pattern === key ? 'var(--aura-accent)' : 'var(--aura-muted)',
              }}
            >
              {key === '4-7-8' ? '4-7-8' : 'Box 4x4'}
            </button>
          ))}
        </div>
      </div>

      <div className="my-5 flex flex-col items-center justify-center">
        <div
          className="flex h-28 w-28 flex-col items-center justify-center rounded-full border-4 transition-transform duration-1000 ease-in-out"
          style={{
            borderColor: 'var(--aura-accent)',
            backgroundColor: 'var(--aura-accent-soft)',
            transform: `scale(${running ? currentPhase.scale : 1})`,
          }}
        >
          <span className="text-2xl font-bold tabular-nums" style={{ color: 'var(--aura-accent)' }}>
            {secLeft}s
          </span>
          <span className="text-[11px] font-semibold" style={{ color: 'var(--aura-text)' }}>
            {running ? currentPhase.label : 'Ready'}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between gap-2">
        <span className="text-xs" style={{ color: 'var(--aura-muted)' }}>
          Completed cycles: <strong>{cycles}</strong>
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setRunning((r) => !r)}
            className="aura-target inline-flex items-center gap-1.5 rounded-xl text-xs font-semibold text-white cursor-pointer"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            {running ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            {running ? 'Pause' : 'Start Pacer'}
          </button>
          <button
            type="button"
            onClick={() => switchPattern(pattern)}
            className="aura-target inline-flex items-center rounded-xl border text-xs cursor-pointer"
            style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}
            title="Reset breathing cycle"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </section>
  );
}
