import { Info } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { HciState, StateSnapshot } from '../types';

export const STATE_LABEL: Record<HciState, string> = {
  focused: 'Focused',
  overwhelmed: 'Overwhelmed',
  fatigued: 'Fatigued',
  energized: 'Energized',
  disoriented: 'Disoriented',
};

const SIGNAL_LABEL: Record<string, string> = {
  aura_stress: 'Aura stress (whole desktop)',
  camera_valence: 'Mood from camera (-1 to 1)',
  camera_arousal: 'Energy from camera (-1 to 1)',
  query_typing_stress: 'Typing stress (this search box)',
  typing_tempo_kps: 'Typing tempo (keys/s)',
  friction_events: 'Rapid clicks / quick back-outs',
  hesitations: 'Long pauses before clicking',
  reformulations: 'Reworded searches',
};

/** Inferred state + a "Why?" popover showing evidence, signals and the policy in force. */
export function StatePill({ snap }: { snap: StateSnapshot | null }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);

  if (!snap) return null;
  const f = snap.fused;
  const label = snap.adaptive ? STATE_LABEL[f.committed_state] : 'Not adapting';

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm hover:border-[var(--aura-calm)]"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
        title="Why this state?"
      >
        <span>{label}</span>
        {snap.adaptive && (
          <span className="text-xs tabular-nums" style={{ color: 'var(--aura-muted)' }}>
            {Math.round(f.confidence * 100)}%
          </span>
        )}
        {snap.adaptive && f.candidate_state && (
          <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--aura-mild)' }}>
            → {STATE_LABEL[f.candidate_state]}
            <span className="h-1 w-8 overflow-hidden rounded-full" style={{ background: 'var(--aura-track)' }}>
              <span className="block h-full" style={{ width: `${f.dwell_progress * 100}%`, background: 'var(--aura-mild)' }} />
            </span>
          </span>
        )}
        <Info size={14} style={{ color: 'var(--aura-muted)' }} aria-hidden />
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Why this state"
          className="absolute right-0 z-20 mt-2 w-[min(360px,calc(100vw-32px))] rounded-xl border p-4 text-sm shadow-xl"
          style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
        >
          {!snap.adaptive && (
            <p className="mb-3" style={{ color: 'var(--aura-mild)' }}>
              Aura is in Control (A) mode, so results use the standard layout. The state below is
              recorded for the study but not acted on.
            </p>
          )}
          <p className="font-medium">
            {STATE_LABEL[f.committed_state]} · {Math.round(f.confidence * 100)}% confidence
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5" style={{ color: 'var(--aura-muted)' }}>
            {f.evidence.map((e) => <li key={e}>{e}</li>)}
          </ul>

          {Object.keys(f.contributions).length > 0 && (
            <>
              <h3 className="mt-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>Signals</h3>
              <dl className="mt-1 space-y-0.5">
                {Object.entries(f.contributions).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt style={{ color: 'var(--aura-muted)' }}>{SIGNAL_LABEL[k] ?? k}</dt>
                    <dd className="tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}

          <h3 className="mt-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>Layout rules in use</h3>
          <p className="mt-1">
            <span className="font-medium">{snap.policy.label}:</span>{' '}
            <span style={{ color: 'var(--aura-muted)' }}>{snap.policy.summary}</span>
          </p>
          <p className="mt-3 text-xs" style={{ color: 'var(--aura-muted)' }}>
            A new state must hold for 3 s before the layout changes ({f.flickers_prevented} brief changes ignored so far).
          </p>
        </div>
      )}
    </div>
  );
}
