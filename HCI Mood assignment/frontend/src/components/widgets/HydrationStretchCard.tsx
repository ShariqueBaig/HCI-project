import { useState } from 'react';
import { Check, Coffee, Droplets } from 'lucide-react';

export function HydrationStretchCard() {
  const [waterDone, setWaterDone] = useState(false);
  const [stretchDone, setStretchDone] = useState(false);

  return (
    <section
      className="rounded-3xl border p-5 shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div className="flex items-center gap-2">
        <Coffee className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
        <h3 className="text-sm font-bold">Fatigue Micro-Recovery</h3>
      </div>
      <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>
        Low arousal &amp; head-droop detected. Two 30-second resets restore visual comfort:
      </p>

      <div className="mt-3 space-y-2">
        <button
          type="button"
          onClick={() => setWaterDone((v) => !v)}
          className="aura-target flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-xs font-medium cursor-pointer"
          style={{
            backgroundColor: waterDone ? 'var(--aura-accent-soft)' : 'var(--aura-panel-alt)',
            borderColor: 'var(--aura-border)',
          }}
        >
          <span className="flex items-center gap-2">
            <Droplets className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
            Drink a glass of water &amp; blink 10x (20-20-20 eye rule)
          </span>
          {waterDone && <Check className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />}
        </button>

        <button
          type="button"
          onClick={() => setStretchDone((v) => !v)}
          className="aura-target flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-xs font-medium cursor-pointer"
          style={{
            backgroundColor: stretchDone ? 'var(--aura-accent-soft)' : 'var(--aura-panel-alt)',
            borderColor: 'var(--aura-border)',
          }}
        >
          <span>Roll shoulders back &amp; lift gaze level with screen</span>
          {stretchDone && <Check className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />}
        </button>
      </div>
    </section>
  );
}
