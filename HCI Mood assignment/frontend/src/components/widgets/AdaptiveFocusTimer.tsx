import { useEffect, useState } from 'react';
import { Pause, Play, RotateCcw, Timer } from 'lucide-react';

interface TimerPreset {
  label: string;
  focusMinutes: number;
  breakMinutes: number;
  description: string;
}

interface AdaptiveFocusTimerProps {
  preset: TimerPreset;
}

export function AdaptiveFocusTimer({ preset }: AdaptiveFocusTimerProps) {
  const [secondsLeft, setSecondsLeft] = useState(preset.focusMinutes * 60);
  const [running, setRunning] = useState(false);

  // Gracefully sync preset duration when user isn't mid-countdown
  useEffect(() => {
    if (!running) {
      setSecondsLeft(preset.focusMinutes * 60);
    }
  }, [preset.focusMinutes, preset.label, running]);

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          setRunning(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [running]);

  const mins = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const totalSecs = Math.max(1, preset.focusMinutes * 60);
  const progressPct = Math.min(100, Math.round(((totalSecs - secondsLeft) / totalSecs) * 100));

  const applyPresetNow = () => {
    setRunning(false);
    setSecondsLeft(preset.focusMinutes * 60);
  };

  return (
    <section
      className="rounded-3xl border p-5 shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Timer className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
          <h3 className="text-sm font-bold">{preset.label}</h3>
        </div>
        <span
          className="rounded-full px-2 py-0.5 font-mono-code text-[11px] font-semibold"
          style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
        >
          {preset.focusMinutes}m / {preset.breakMinutes}m
        </span>
      </div>

      <p className="mt-1.5 text-xs" style={{ color: 'var(--aura-muted)' }}>
        {preset.description}
      </p>

      <div className="my-4 flex items-baseline justify-between">
        <div className="font-mono-code text-4xl font-bold tracking-tight tabular-nums">
          {String(mins).padStart(2, '0')}:{String(secs).padStart(2, '0')}
        </div>
        <span className="font-mono-code text-xs" style={{ color: 'var(--aura-muted)' }}>
          {progressPct}%
        </span>
      </div>

      <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: 'var(--aura-panel-alt)' }}>
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${progressPct}%`, backgroundColor: 'var(--aura-accent)' }}
        />
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setRunning((r) => !r)}
          className="aura-target inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl text-xs font-semibold text-white cursor-pointer"
          style={{ backgroundColor: 'var(--aura-accent)' }}
        >
          {running ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          {running ? 'Pause' : 'Start Focus'}
        </button>
        <button
          type="button"
          onClick={applyPresetNow}
          className="aura-target inline-flex items-center rounded-xl border text-xs cursor-pointer"
          style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}
          title="Reset to adaptive preset"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  );
}
