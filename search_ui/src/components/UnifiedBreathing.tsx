import { Pause, Play, Wind, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiPost } from '../api';

type Phase = 'idle' | 'in' | 'top' | 'out';

const PHASE_COPY: Record<Phase, { label: string; hint: string; durMs: number; radius: number }> = {
  idle: { label: 'Ready', hint: 'Double inhale through the nose, then one long slow exhale.', durMs: 300, radius: 24 },
  in: { label: 'Inhale', hint: 'Fill your lungs comfortably…', durMs: 1500, radius: 44 },
  top: { label: 'Inhale again', hint: 'One quick top-up sip of air…', durMs: 500, radius: 52 },
  out: { label: 'Exhale slowly', hint: 'Let it all out slowly…', durMs: 6000, radius: 22 },
};

/**
 * Single unified physiological-sigh component used both inline (GenUI BreathingNudge)
 * and in the Wellness / Corner-Nudge breathing modal.
 * Fixes v1's duplicate text bug and React widget's missing "Inhale again" cue.
 */
export function UnifiedBreathing({
  inline = false,
  defaultCycles = 3,
  onClose,
}: {
  inline?: boolean;
  defaultCycles?: 1 | 3;
  onClose?: () => void;
}) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [cyclesTotal, setCyclesTotal] = useState<1 | 3>(defaultCycles);
  const [cycleIdx, setCycleIdx] = useState(0);
  const [secLeft, setSecLeft] = useState(0);

  useEffect(() => {
    if (!inline) {
      void apiPost('/api/app/breathing', { active: true }).catch(() => undefined);
      return () => {
        void apiPost('/api/app/breathing', { active: false }).catch(() => undefined);
      };
    }
    return undefined;
  }, [inline]);

  useEffect(() => {
    if (inline || !onClose) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [inline, onClose]);

  useEffect(() => {
    if (phase === 'idle') return;
    const dur = PHASE_COPY[phase].durMs;
    setSecLeft(Math.ceil(dur / 1000));
    const started = performance.now();
    const tick = window.setInterval(() => {
      const left = Math.max(0, Math.ceil((dur - (performance.now() - started)) / 1000));
      setSecLeft(left);
    }, 200);
    const timer = window.setTimeout(() => {
      if (phase === 'in') setPhase('top');
      else if (phase === 'top') setPhase('out');
      else if (phase === 'out') {
        if (cycleIdx + 1 < cyclesTotal) {
          setCycleIdx((c) => c + 1);
          setPhase('in');
        } else {
          setPhase('idle');
          setCycleIdx(0);
        }
      }
    }, dur);
    return () => {
      window.clearInterval(tick);
      window.clearTimeout(timer);
    };
  }, [phase, cycleIdx, cyclesTotal]);

  const start = () => {
    setCycleIdx(0);
    setPhase('in');
  };
  const stop = () => {
    setPhase('idle');
    setCycleIdx(0);
  };

  const info = PHASE_COPY[phase];

  if (inline) {
    return (
      <section
        aria-label="Breathing pause"
        className="flex flex-wrap items-center gap-4 rounded-xl border p-4"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      >
        <svg width="64" height="64" viewBox="0 0 120 120" className="shrink-0" aria-hidden>
          <circle cx="60" cy="60" r="54" fill="none" stroke="var(--aura-track)" strokeWidth="2" />
          <circle
            cx="60"
            cy="60"
            r={info.radius}
            fill="var(--aura-calm)"
            opacity={phase === 'idle' ? 0.35 : 0.72}
            style={{ transition: `r ${info.durMs}ms ease-in-out` }}
          />
        </svg>
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            {phase === 'idle' ? 'Take one slow physiological sigh?' : `${info.label}${secLeft > 0 ? ` · ${secLeft}s` : ''}`}
          </p>
          <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
            {info.hint}
          </p>
        </div>
        {phase === 'idle' ? (
          <button
            type="button"
            onClick={() => {
              setCyclesTotal(1);
              start();
            }}
            className="aura-target flex items-center gap-1.5 rounded-lg border text-sm font-medium hover:border-[var(--aura-calm)]"
            style={{ borderColor: 'var(--aura-border-interactive)' }}
          >
            <Play size={14} aria-hidden /> Start 1 sigh
          </button>
        ) : (
          <button
            type="button"
            onClick={stop}
            className="aura-target flex items-center gap-1.5 rounded-lg border text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
          >
            <Pause size={14} aria-hidden /> Stop
          </button>
        )}
      </section>
    );
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Physiological sigh breathing guide"
      className="aura-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div
        className="aura-scale-in w-full max-w-md rounded-2xl border p-6 shadow-2xl"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Wind size={18} style={{ color: 'var(--aura-calm)' }} aria-hidden />
            <h2 className="text-lg font-semibold">Physiological Sigh</h2>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close breathing guide"
              className="aura-target rounded-lg p-1.5 hover:bg-[var(--aura-surface-elev)]"
            >
              <X size={18} aria-hidden />
            </button>
          )}
        </div>
        <p className="mt-1 text-sm" style={{ color: 'var(--aura-muted)' }}>
          Double inhale through your nose, followed by a long slow exhale.
        </p>

        <div className="my-5 flex flex-col items-center">
          <svg width="200" height="200" viewBox="0 0 120 120" aria-hidden>
            <circle cx="60" cy="60" r="56" fill="none" stroke="var(--aura-track)" strokeWidth="1.5" />
            <circle
              cx="60"
              cy="60"
              r={info.radius}
              fill="var(--aura-calm)"
              opacity={phase === 'idle' ? 0.25 : 0.78}
              style={{ transition: `r ${info.durMs}ms ease-in-out` }}
            />
          </svg>
          <p className="mt-2 text-xl font-semibold" style={{ color: phase === 'out' ? 'var(--aura-muted)' : 'var(--aura-calm)' }}>
            {phase === 'idle' ? 'Ready when you are' : info.label}
          </p>
          <p className="mt-1 text-sm" style={{ color: 'var(--aura-muted)' }}>
            {phase === 'idle'
              ? `${cyclesTotal} ${cyclesTotal === 1 ? 'cycle' : 'cycles'} · ~${cyclesTotal * 8}s`
              : `Cycle ${cycleIdx + 1} of ${cyclesTotal} · ${secLeft}s`}
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2" role="group" aria-label="Breath cycles">
            {([1, 3] as const).map((n) => (
              <button
                key={n}
                type="button"
                disabled={phase !== 'idle'}
                onClick={() => setCyclesTotal(n)}
                aria-pressed={cyclesTotal === n}
                className="aura-target rounded-lg border text-sm disabled:opacity-50"
                style={{
                  borderColor: cyclesTotal === n ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
                  color: cyclesTotal === n ? 'var(--aura-calm)' : 'var(--aura-muted)',
                }}
              >
                {n} {n === 1 ? 'cycle' : 'cycles'}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {phase === 'idle' ? (
              <button
                type="button"
                onClick={start}
                className="aura-target rounded-lg px-5 text-sm font-medium"
                style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
              >
                Begin
              </button>
            ) : (
              <button
                type="button"
                onClick={stop}
                className="aura-target rounded-lg border px-4 text-sm"
                style={{ borderColor: 'var(--aura-border-interactive)' }}
              >
                Stop
              </button>
            )}
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="aura-target rounded-lg border px-4 text-sm"
                style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
              >
                Done
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
