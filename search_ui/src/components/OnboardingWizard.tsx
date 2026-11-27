import { CheckCircle2, Keyboard, ShieldCheck, Sliders, Volume2, VolumeX, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { apiPost } from '../api';
import type { AppStatus, ThemeId } from '../types';
import { ThemeCards } from './ThemePicker';

const PASSAGE =
  'Calm technology works quietly in the background without demanding your constant attention. ' +
  'As you type at a comfortable and steady pace, Aura measures only the natural rhythm between ' +
  'keystrokes to build your personal resting baseline. Keep your shoulders relaxed, breathe evenly, ' +
  'and simply follow the highlighted words until the thirty-second timer completes.';

function playKeyHapticSound(ctxRef: React.MutableRefObject<AudioContext | null>, isError: boolean) {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    if (!ctxRef.current) ctxRef.current = new AudioCtx();
    const ctx = ctxRef.current;
    if (ctx.state === 'suspended') void ctx.resume();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = isError ? 'triangle' : 'sine';
    osc.frequency.setValueAtTime(isError ? 165 : 540, ctx.currentTime);
    gain.gain.setValueAtTime(isError ? 0.05 : 0.025, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + (isError ? 0.055 : 0.024));
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + (isError ? 0.06 : 0.028));
  } catch {
    /* ignore audio errors in restricted environments */
  }
}

export function OnboardingWizard({
  app,
  initialStep = 0,
  onClose,
  onRefresh,
}: {
  app: AppStatus | null;
  initialStep?: 0 | 1 | 2;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [step, setStep] = useState<0 | 1 | 2>(initialStep);
  const [code, setCode] = useState(app?.consent.participant_code || '');
  const [storeQueries, setStoreQueries] = useState(app?.consent.store_queries ?? true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [typed, setTyped] = useState('');
  const [soundOn, setSoundOn] = useState(true);
  const [shakeTick, setShakeTick] = useState(0);
  const [pulseTick, setPulseTick] = useState(0);
  const [calibStartedAt, setCalibStartedAt] = useState<number | null>(null);

  const calib = app?.calibration;
  const keyTimes = useRef<{ down: number; up: number; isDel: boolean }[]>([]);
  const downMap = useRef(new Map<string, number>());
  const audioCtxRef = useRef<AudioContext | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    if (calib?.active) {
      const t = window.setTimeout(() => inputRef.current?.focus(), 20);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [calib?.active]);

  // Periodically ship calibration typing samples while active
  useEffect(() => {
    if (!calib?.active) return;
    const id = window.setInterval(() => {
      const now = performance.now();
      const recent = keyTimes.current.filter((k) => now - k.up < 5000);
      keyTimes.current = recent;
      if (recent.length < 3) return;
      const dwells = recent.map((k) => (k.up - k.down) / 1000).filter((d) => d > 0 && d < 2);
      const flights: number[] = [];
      for (let i = 1; i < recent.length; i++) {
        const f = (recent[i].down - recent[i - 1].up) / 1000;
        if (f > 0 && f < 2) flights.push(f);
      }
      const mean = (arr: number[]) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);
      const mf = mean(flights);
      const sf = flights.length > 1
        ? Math.sqrt(flights.reduce((s, v) => s + (v - mf) ** 2, 0) / (flights.length - 1))
        : 0;
      const errRate = recent.filter((k) => k.isDel).length / recent.length;
      void apiPost('/api/app/calibration/sample', {
        keys_per_second: recent.length / 5.0,
        error_rate: errRate,
        mean_dwell: mean(dwells),
        mean_flight: mf,
        std_flight: sf,
        flight_count: flights.length,
      }).catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(id);
  }, [calib?.active]);

  const saveConsent = async () => {
    setErr(null);
    if (!code.trim()) {
      setErr('Please enter your participant code (or a nickname such as P01).');
      return;
    }
    setBusy(true);
    try {
      await apiPost('/api/app/consent/grant', { participant_code: code.trim(), store_queries: storeQueries });
      onRefresh();
      setStep(1);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const startCalib = async () => {
    setErr(null);
    setTyped('');
    setCalibStartedAt(performance.now());
    keyTimes.current = [];
    await apiPost('/api/app/calibration/start', { duration_s: 30 }).catch(() => undefined);
    onRefresh();
    window.setTimeout(() => inputRef.current?.focus(), 30);
  };

  const handleTypedChange = (next: string) => {
    if (next.length > typed.length) {
      const idx = next.length - 1;
      const expected = PASSAGE[idx];
      const actual = next[idx];
      const isMistake = expected !== undefined && actual !== expected;
      setPulseTick((p) => p + 1);
      if (isMistake) setShakeTick((s) => s + 1);
      if (soundOn) playKeyHapticSound(audioCtxRef, isMistake);
    }
    setTyped(next);
  };

  const finishOnboarding = async () => {
    await apiPost('/api/app/comfort', { onboarding_complete: true }).catch(() => undefined);
    onRefresh();
    onClose();
  };

  // Live typing-game stats
  let correctChars = 0;
  for (let i = 0; i < Math.min(typed.length, PASSAGE.length); i++) {
    if (typed[i] === PASSAGE[i]) correctChars++;
  }
  const accuracy = typed.length > 0 ? Math.round((correctChars / Math.min(typed.length, PASSAGE.length)) * 100) : 100;
  const elapsedMin = calibStartedAt ? Math.max(0.05, (performance.now() - calibStartedAt) / 60000) : 0.05;
  const liveWpm = typed.length > 0 ? Math.round((correctChars / 5) / elapsedMin) : 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Aura setup"
      className="aura-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div
        className="aura-scale-in max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl border p-6 shadow-2xl"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-calm)' }}>
            <span>Setup · Step {step + 1} of 3</span>
          </div>
          <button
            type="button"
            onClick={finishOnboarding}
            aria-label="Skip setup for now"
            className="rounded-lg p-1.5 hover:bg-[var(--aura-surface-elev)]"
            style={{ color: 'var(--aura-muted)' }}
          >
            <X size={18} aria-hidden />
          </button>
        </div>

        {/* Stepper pills */}
        <div className="mt-3 mb-5 grid grid-cols-3 gap-2">
          {[
            { label: 'Privacy', icon: ShieldCheck },
            { label: 'Rhythm', icon: Keyboard },
            { label: 'Comfort', icon: Sliders },
          ].map((item, idx) => {
            const Icon = item.icon;
            const active = step === idx;
            return (
              <button
                key={item.label}
                type="button"
                onClick={() => setStep(idx as 0 | 1 | 2)}
                className="aura-target flex items-center justify-center gap-1.5 rounded-xl border text-xs font-medium"
                style={{
                  borderColor: active ? 'var(--aura-calm)' : 'var(--aura-border)',
                  background: active ? 'var(--aura-surface-elev)' : 'transparent',
                  color: active ? 'var(--aura-calm)' : 'var(--aura-muted)',
                }}
              >
                <Icon size={14} aria-hidden /> {item.label}
              </button>
            );
          })}
        </div>

        <div key={step} className="aura-fade-up">
        {step === 0 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Privacy &amp; Data Consent</h2>
            <p className="text-sm" style={{ color: 'var(--aura-muted)' }}>
              {app?.consent.storage_summary || 'Pseudonymous research logging, gated on your consent.'}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border p-3.5 text-xs" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <p className="mb-1.5 font-semibold" style={{ color: 'var(--aura-calm)' }}>What is recorded (only while recording)</p>
                <ul className="list-disc space-y-1 pl-4" style={{ color: 'var(--aura-muted)' }}>
                  <li>Numeric typing speed, timing variance, and mouse movement</li>
                  <li>Search queries (or hashed codes), layouts shown, survey answers</li>
                  <li>Any journal note you explicitly save</li>
                </ul>
              </div>
              <div className="rounded-xl border p-3.5 text-xs" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <p className="mb-1.5 font-semibold" style={{ color: 'var(--aura-mild)' }}>Never recorded</p>
                <ul className="list-disc space-y-1 pl-4" style={{ color: 'var(--aura-muted)' }}>
                  <li>Characters you type outside Search, passwords, or key codes</li>
                  <li>Window titles, app names, or webcam video frames</li>
                  <li>Your participant code (stored only as a salted hash)</li>
                </ul>
              </div>
            </div>

            <div>
              <label htmlFor="onb-code" className="mb-1 block text-sm font-medium">
                Participant code
              </label>
              <input
                id="onb-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="e.g. P01"
                className="w-full rounded-xl border px-3.5 py-2.5 text-sm"
                style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-bg)' }}
              />
            </div>

            <label className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input
                type="checkbox"
                checked={storeQueries}
                onChange={(e) => setStoreQueries(e.target.checked)}
                className="mt-1 h-4 w-4 accent-[var(--aura-calm)]"
              />
              <span>
                Keep the words of my Aura searches in local study logs
                <span className="block text-xs" style={{ color: 'var(--aura-muted)' }}>
                  Uncheck to store only a salted scrambled code instead.
                </span>
              </span>
            </label>

            {err && <p role="alert" className="text-xs" style={{ color: 'var(--aura-elev)' }}>{err}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="aura-target rounded-xl border px-4 text-sm"
                style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
              >
                Skip for now
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={saveConsent}
                className="aura-target rounded-xl px-5 text-sm font-medium disabled:opacity-50"
                style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
              >
                {app?.consent.granted ? 'Update & Continue' : 'I Consent · Continue'}
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-xl font-semibold">30-Second Rhythm Calibration</h2>
                <p className="text-sm" style={{ color: 'var(--aura-muted)' }}>
                  Follow the highlighted words at your natural pace — errors and rhythm highlight live as you type.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSoundOn((s) => !s)}
                aria-pressed={soundOn}
                className="aura-target flex items-center gap-1.5 rounded-lg border text-xs"
                style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
                title="Toggle soft keystroke feedback sounds"
              >
                {soundOn ? <Volume2 size={13} aria-hidden /> : <VolumeX size={13} aria-hidden />}
                Key sounds: {soundOn ? 'On' : 'Off'}
              </button>
            </div>

            {/* Live typing-game HUD */}
            <div className="flex items-center justify-between rounded-xl border px-3.5 py-2 text-xs" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
              <div className="flex items-center gap-2">
                <span
                  key={pulseTick}
                  className={`inline-block h-2.5 w-2.5 rounded-full ${pulseTick > 0 ? 'aura-pulse' : ''}`}
                  style={{ background: calib?.active ? 'var(--aura-calm)' : 'var(--aura-subtle)' }}
                  aria-hidden
                />
                <span style={{ color: 'var(--aura-muted)' }}>
                  {calib?.active ? 'Tracking rhythm live' : 'Click Start below to begin'}
                </span>
              </div>
              <div className="flex items-center gap-4 tabular-nums">
                <span><strong style={{ color: 'var(--aura-text)' }}>{liveWpm}</strong> <span style={{ color: 'var(--aura-muted)' }}>WPM</span></span>
                <span>
                  <strong style={{ color: accuracy >= 92 ? 'var(--aura-calm)' : 'var(--aura-mild)' }}>{accuracy}%</strong>{' '}
                  <span style={{ color: 'var(--aura-muted)' }}>accuracy</span>
                </span>
              </div>
            </div>

            {/* Monkeytype-style interactive upper passage */}
            <div
              key={shakeTick}
              onClick={() => inputRef.current?.focus()}
              className={`cursor-text select-none rounded-xl border p-4 font-mono text-[15px] leading-7 tracking-wide ${shakeTick > 0 ? 'aura-shake' : ''}`}
              style={{
                borderColor: calib?.active ? 'var(--aura-calm)' : 'var(--aura-border)',
                background: 'var(--aura-bg)',
              }}
            >
              {PASSAGE.split('').map((ch, idx) => {
                const isTyped = idx < typed.length;
                const isCurrent = calib?.active && idx === typed.length;
                const match = isTyped && typed[idx] === ch;
                const wrong = isTyped && typed[idx] !== ch;
                return (
                  <span key={idx} className="relative">
                    {isCurrent && (
                      <span
                        className="aura-caret absolute top-0.5 -left-[1px] inline-block h-[1.25em] w-[2px] rounded-full"
                        style={{ background: 'var(--aura-calm)' }}
                        aria-hidden
                      />
                    )}
                    <span
                      style={{
                        color: match
                          ? 'var(--aura-calm)'
                          : wrong
                          ? 'var(--aura-elev)'
                          : isCurrent
                          ? 'var(--aura-text)'
                          : 'var(--aura-subtle)',
                        background: wrong ? 'color-mix(in srgb, var(--aura-elev) 22%, transparent)' : undefined,
                        borderRadius: wrong ? '3px' : undefined,
                        textDecoration: wrong ? 'underline wavy var(--aura-elev)' : undefined,
                      }}
                    >
                      {wrong && ch === ' ' ? '·' : ch}
                    </span>
                  </span>
                );
              })}
            </div>

            <label className="block">
              <span className="mb-1 block text-xs font-medium" style={{ color: 'var(--aura-muted)' }}>
                Your input (type here — the passage above mirrors every keystroke)
              </span>
              <textarea
                ref={inputRef}
                rows={2}
                value={typed}
                onChange={(e) => handleTypedChange(e.target.value)}
                onKeyDown={(e) => {
                  if (!e.repeat) downMap.current.set(e.code, performance.now());
                }}
                onKeyUp={(e) => {
                  const d = downMap.current.get(e.code);
                  if (d !== undefined) {
                    downMap.current.delete(e.code);
                    keyTimes.current.push({ down: d, up: performance.now(), isDel: e.key === 'Backspace' || e.key === 'Delete' });
                  }
                }}
                disabled={!calib?.active}
                placeholder={calib?.active ? 'Start typing the passage above…' : 'Click Start 30s Calibration below…'}
                className="w-full rounded-xl border p-3 font-mono text-sm disabled:opacity-60"
                style={{ borderColor: calib?.active ? 'var(--aura-calm)' : 'var(--aura-border-interactive)', background: 'var(--aura-bg)' }}
              />
            </label>

            <div className="space-y-1.5">
              <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: 'var(--aura-track)' }}>
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{ width: `${(calib?.progress ?? 0) * 100}%`, background: calib?.status === 'insufficient' ? 'var(--aura-elev)' : 'var(--aura-calm)' }}
                />
              </div>
              <div className="flex justify-between text-xs" style={{ color: 'var(--aura-muted)' }}>
                <span>
                  {calib?.active
                    ? `${Math.ceil(calib.remaining_s)}s remaining · ${calib.samples} samples captured`
                    : calib?.status === 'done'
                    ? `Calibrated (${calib.baselines.kps.toFixed(1)} keys/s baseline)`
                    : calib?.message || 'Ready when you are'}
                </span>
                {calib?.calibrated && (
                  <span className="flex items-center gap-1" style={{ color: 'var(--aura-calm)' }}>
                    <CheckCircle2 size={13} aria-hidden /> Saved
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-wrap justify-between gap-2 pt-2">
              <div className="flex gap-2">
                {!calib?.active ? (
                  <button
                    type="button"
                    onClick={startCalib}
                    className="aura-target rounded-xl px-4 text-sm font-medium"
                    style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
                  >
                    {calib?.status === 'insufficient' ? 'Retry Calibration' : calib?.calibrated ? 'Recalibrate (30s)' : 'Start 30s Calibration'}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => void apiPost('/api/app/calibration/cancel', {}).then(onRefresh)}
                    className="aura-target rounded-xl border px-4 text-sm"
                    style={{ borderColor: 'var(--aura-border-interactive)' }}
                  >
                    Cancel
                  </button>
                )}
              </div>
              <button
                type="button"
                onClick={() => setStep(2)}
                className="aura-target rounded-xl border px-4 text-sm"
                style={{ borderColor: 'var(--aura-border-interactive)' }}
              >
                Next: Comfort →
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Ambient Comfort Preferences</h2>
            <p className="text-sm" style={{ color: 'var(--aura-muted)' }}>
              All sensory adjustments are opt-in and smoothly reversible anytime in Wellness.
            </p>
            <div className="space-y-2.5">
              {[
                {
                  key: 'auto_bright',
                  title: 'Screen Comfort (Brightness + Warmth)',
                  desc: 'Gently dims display and shifts warmth toward 3500K during prolonged tension.',
                  val: Boolean(app?.comfort.auto_bright),
                },
                {
                  key: 'focus_mode',
                  title: 'Focus Mode (Silent Notification Shield)',
                  desc: 'Holds notifications silently when tension spikes and delivers one summary afterward.',
                  val: Boolean(app?.comfort.focus_mode),
                },
                {
                  key: 'auto_music',
                  title: 'Audio Easing',
                  desc: 'Smoothly softens playback or Windows system volume when overloaded.',
                  val: Boolean(app?.comfort.auto_music),
                },
              ].map((item) => (
                <div
                  key={item.key}
                  className="flex items-center justify-between gap-3 rounded-xl border p-3.5"
                  style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}
                >
                  <div>
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>{item.desc}</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={item.val}
                    onClick={() => void apiPost('/api/app/comfort', { [item.key]: !item.val }).then(onRefresh)}
                    className="aura-target shrink-0 rounded-full border px-3.5 text-xs font-medium"
                    style={{
                      borderColor: item.val ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
                      background: item.val ? 'var(--aura-calm)' : 'var(--aura-surface)',
                      color: item.val ? 'var(--aura-bg)' : 'var(--aura-text)',
                    }}
                  >
                    {item.val ? 'On' : 'Off'}
                  </button>
                </div>
              ))}
              <div className="rounded-xl border p-3.5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <p className="mb-2 text-sm font-medium">Color Theme</p>
                <ThemeCards
                  theme={(app?.comfort.theme ?? 'dark') as ThemeId}
                  onSelect={(id) => void apiPost('/api/app/comfort', { theme: id }).then(onRefresh)}
                />
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={finishOnboarding}
                className="aura-target rounded-xl px-6 text-sm font-medium"
                style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
              >
                Finish &amp; Open Aura
              </button>
            </div>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
