import type { ConnectionStatus, LiveState } from '../types';

const TIER_VAR = ['var(--aura-calm)', 'var(--aura-mild)', 'var(--aura-elev)'];

export function StressChip({ live, status }: { live: LiveState | null; status: ConnectionStatus }) {
  const color = live ? TIER_VAR[live.tier] : 'var(--aura-subtle)';
  const pct = live ? Math.max(0, Math.min(100, live.score)) : 0;
  return (
    <div
      className="flex items-center gap-3 rounded-full border px-3 py-1.5"
      style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      title={status === 'live' ? 'Live stress from Aura UI' : `Connection: ${status}`}
    >
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} aria-hidden />
      <span className="text-sm font-medium" style={{ color }}>
        {live ? live.label : status === 'unauthorized' ? 'No access' : 'Waiting'}
      </span>
      <div className="h-1.5 w-24 overflow-hidden rounded-full" style={{ background: 'var(--aura-track)' }}>
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="w-8 text-right text-xs tabular-nums" style={{ color: 'var(--aura-muted)' }}>
        {live ? live.score.toFixed(0) : '--'}
      </span>
      {live?.simulated && <span className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--aura-mild)' }}>sim</span>}
      {live?.demo && <span className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--aura-calm)' }}>demo</span>}
    </div>
  );
}
