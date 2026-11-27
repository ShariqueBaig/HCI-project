import { Sparkles } from 'lucide-react';
import { useState } from 'react';
import { apiPost } from '../api';
import type { AppStatus } from '../types';
import { Scale } from './study/Surveys';

/**
 * Explicit Post-Recording Wrap-Up modal.
 * Prevents accidental data loss (v1 silently discarded self-report if Journal was closed)
 * and keeps Journal notes cleanly separated from stopping an active recording.
 */
export function SessionWrapUpModal({
  app,
  onDone,
}: {
  app: AppStatus;
  onDone: () => void;
}) {
  const [stress, setStress] = useState<number | null>(4);
  const [mood, setMood] = useState<number | null>(6);
  const [note, setNote] = useState('');
  const [reflection, setReflection] = useState('');
  const [busy, setBusy] = useState(false);

  if (!app.recording.pending_finalize) return null;
  const s = app.recording.summary as {
    duration_s?: number;
    avg?: number;
    peak?: number;
    held?: number;
  };
  const durMin = Math.floor((s.duration_s ?? 0) / 60);
  const durSec = Math.round((s.duration_s ?? 0) % 60);

  const reflect = async () => {
    setBusy(true);
    try {
      const r = await apiPost<{ reflection: string }>('/api/app/journal/reflect', { note });
      setReflection(r.reflection);
    } finally {
      setBusy(false);
    }
  };

  const finalize = async (skipRatings = false) => {
    setBusy(true);
    try {
      await apiPost('/api/app/recording/finalize', {
        perceived_stress: skipRatings ? null : stress,
        mood: skipRatings ? null : mood,
        note,
        reflection,
        skip_ratings: skipRatings,
      });
      onDone();
    } finally {
      setBusy(false);
    }
  };

  const resume = async () => {
    setBusy(true);
    try {
      await apiPost('/api/app/recording/resume', {});
      onDone();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Finish recorded session"
      className="aura-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div
        className="aura-scale-in max-h-[90vh] w-full max-w-xl overflow-auto rounded-2xl border p-6 shadow-2xl"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      >
        <h2 className="text-xl font-semibold">Finish Recorded Session</h2>
        <p className="mt-1 text-sm" style={{ color: 'var(--aura-muted)' }}>
          Duration {durMin}m {String(durSec).padStart(2, '0')}s · avg stress {(s.avg ?? 0).toFixed(0)} · peak{' '}
          {(s.peak ?? 0).toFixed(0)} · held alerts {s.held ?? 0}
        </p>

        <div className="mt-5">
          <Scale
            label="Perceived stress during this block (0–10)"
            min={0}
            max={10}
            value={stress}
            onChange={setStress}
            low="Very calm"
            high="Very stressed"
          />
          <Scale
            label="Overall mood (0–10)"
            min={0}
            max={10}
            value={mood}
            onChange={setMood}
            low="Low"
            high="Great"
          />
        </div>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Reflection note (optional)</span>
          <textarea
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="How did this session feel? (Saved with this session)"
            className="w-full rounded-xl border bg-transparent p-3 text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)' }}
          />
        </label>

        {reflection && (
          <div className="mt-3 rounded-xl border p-3.5 text-sm" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
            <p className="mb-1 text-xs font-semibold" style={{ color: 'var(--aura-calm)' }}>Aura reflection</p>
            <p>{reflection}</p>
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={reflect}
            className="aura-target flex items-center gap-1.5 rounded-xl border px-3.5 text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-calm)' }}
          >
            <Sparkles size={14} aria-hidden /> Reflect with Aura
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={resume}
            className="aura-target rounded-xl border px-3.5 text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
          >
            Resume recording
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void finalize(true)}
            className="aura-target rounded-xl border px-3.5 text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
          >
            Skip ratings
          </button>
          <button
            type="button"
            disabled={busy || stress === null || mood === null}
            onClick={() => void finalize(false)}
            className="aura-target ml-auto rounded-xl px-5 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
          >
            Save &amp; Finalize
          </button>
        </div>
      </div>
    </div>
  );
}
