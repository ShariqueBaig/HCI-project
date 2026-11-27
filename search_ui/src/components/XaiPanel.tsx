import { Brain, Camera, Check, ChevronDown, FlaskConical, Square, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { apiGet, apiPost } from '../api';
import { LAB_STATE_LABEL } from '../modes';
import type { CameraExplain, HciState, StateSnapshot, XaiCondition, XaiMood } from '../types';

const MOODS: HciState[] = ['focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented'];

const MOOD_HINT: Record<HciState, string> = {
  focused: 'Moderate stress, no friction: full detail and sources',
  overwhelmed: 'Stress 82/100: Simple View (one answer + next step)',
  fatigued: 'Slow, heavy typing: Easy-Read View',
  energized: 'Fast, accurate typing: Explore View',
  disoriented: 'Reworded searches + friction: Guided View',
};

const SOURCE_LABEL: Record<string, string> = {
  aura: 'Aura desktop stress',
  query_typing: 'Search-box typing stress',
};

export function XaiPanel({ snap, onClose, embedded = false }: {
  snap: StateSnapshot | null;
  onClose?: () => void;
  embedded?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!embedded) ref.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [embedded]);
  const [err, setErr] = useState<string | null>(null);
  const [openMood, setOpenMood] = useState<HciState | null>(null);

  if (!snap) return null;
  const f = snap.fused;
  const xai = f.xai;
  const sim = snap.simulation ?? null;

  const simulate = async (state: HciState | null) => {
    setBusy(true);
    setErr(null);
    try {
      await apiPost('/api/simulate', { state, duration_s: 45 });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      id="xai-panel"
      ref={ref}
      aria-label="Explainable AI state model"
      className={embedded ? 'text-sm' : 'rounded-xl border px-5 py-3 text-sm'}
      style={embedded ? undefined : { borderColor: 'var(--aura-border)' }}
    >
      {!embedded && (
        <header className="flex items-center gap-2" style={{ color: 'var(--aura-muted)' }}>
          <Brain size={15} aria-hidden />
          <span>Explainable AI (Researcher View)</span>
          {sim && (
            <span className="rounded-full px-2 py-0.5 text-xs uppercase tracking-wide"
              style={{ background: 'var(--aura-mild)', color: 'var(--aura-bg)' }}>
              simulating {LAB_STATE_LABEL[sim.state]}
            </span>
          )}
          {onClose && (
            <button type="button" onClick={onClose} aria-label="Close explanation"
              className="ml-auto rounded-md p-1 hover:bg-[var(--aura-surface)]">
              <X size={16} aria-hidden />
            </button>
          )}
        </header>
      )}

      <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <p>
          <span style={{ color: 'var(--aura-muted)' }}>Model predicts now: </span>
          <span className="font-medium">{LAB_STATE_LABEL[f.state]}</span>
          <span className="tabular-nums" style={{ color: 'var(--aura-muted)' }}> · {Math.round(f.confidence * 100)}% confidence</span>
        </p>
        <p>
          <span style={{ color: 'var(--aura-muted)' }}>Committed state: </span>
          <span className="font-medium">{LAB_STATE_LABEL[f.committed_state]}</span>
          {f.candidate_state && (
            <span style={{ color: 'var(--aura-mild)' }}>
              {' '}(switching to {LAB_STATE_LABEL[f.candidate_state]} in {Math.max(0, 3 * (1 - f.dwell_progress)).toFixed(1)} s)
            </span>
          )}
        </p>
      </div>

      <section className="mt-4" aria-label="Simulate a mood">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
          <FlaskConical size={13} aria-hidden /> Simulate a state (45 s)
        </h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {MOODS.map((m) => {
            const active = sim?.state === m;
            return (
              <button
                key={m}
                type="button"
                disabled={busy}
                title={MOOD_HINT[m]}
                aria-pressed={active}
                onClick={() => void simulate(active ? null : m)}
                className="aura-target rounded-lg border text-xs font-medium disabled:opacity-50 hover:border-[var(--aura-calm)]"
                style={{
                  borderColor: active ? 'var(--aura-mild)' : 'var(--aura-border-interactive)',
                  background: active ? 'color-mix(in srgb, var(--aura-mild) 18%, transparent)' : 'var(--aura-surface)',
                  color: active ? 'var(--aura-mild)' : 'var(--aura-text)',
                }}
              >
                {LAB_STATE_LABEL[m]}
              </button>
            );
          })}
          {sim && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void simulate(null)}
              className="aura-target flex items-center gap-1.5 rounded-lg border text-xs disabled:opacity-50"
              style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
            >
              <Square size={12} aria-hidden /> Stop ({Math.ceil(sim.remaining_s)} s)
            </button>
          )}
        </div>
        {err && <p role="alert" className="mt-2 text-xs" style={{ color: 'var(--aura-elev)' }}>{err}</p>}
      </section>

      <CameraSection />

      {xai && (
        <>
          <section className="mt-5" aria-label="Stress fusion">
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
              Step 1 · Fused stress {xai.stress_fusion.fused !== null && <span className="tabular-nums normal-case">= {xai.stress_fusion.fused}/100</span>}
            </h3>
            {xai.stress_fusion.parts.length === 0 ? (
              <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>No stress signals yet.</p>
            ) : (
              <ul className="mt-2 space-y-1.5">
                {xai.stress_fusion.parts.map((p) => (
                  <li key={p.source} className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3">
                    <span className="truncate text-xs" style={{ color: 'var(--aura-muted)' }}>{SOURCE_LABEL[p.source] ?? p.source}</span>
                    <Bar value={p.value / 100} color="var(--aura-calm)" />
                    <span className="tabular-nums text-xs" style={{ color: 'var(--aura-muted)' }}>
                      {p.value.toFixed(0)} × {p.weight} ({Math.round(p.share * 100)}%)
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-1 text-xs" style={{ color: 'var(--aura-subtle)' }}>{xai.stress_fusion.formula}</p>
          </section>

          <section className="mt-5" aria-label="Decision rules">
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
              Step 2 · Priority rules (first match wins)
            </h3>
            <ul className="mt-2 space-y-1">
              {xai.moods.map((m) => (
                <MoodRow
                  key={m.state}
                  mood={m}
                  open={openMood === m.state}
                  onToggle={() => setOpenMood((o) => (o === m.state ? null : m.state))}
                />
              ))}
            </ul>
            <p className="mt-2 text-xs" style={{ color: 'var(--aura-subtle)' }}>
              3 s dwell hysteresis ({f.flickers_prevented} brief flickers prevented).
            </p>
          </section>
        </>
      )}
    </section>
  );
}

function MoodRow({ mood, open, onToggle }: { mood: XaiMood; open: boolean; onToggle: () => void }) {
  const status = mood.chosen ? 'chosen' : mood.matched ? 'matched, lower priority' : 'not met';
  const color = mood.chosen ? 'var(--aura-calm)' : mood.matched ? 'var(--aura-mild)' : 'var(--aura-subtle)';
  return (
    <li className="rounded-lg" style={{ background: mood.chosen ? 'color-mix(in srgb, var(--aura-calm) 10%, transparent)' : undefined }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-[1.25rem_minmax(0,6.5rem)_1fr_minmax(0,8rem)_1rem] items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-[var(--aura-surface-elev)]"
      >
        <span className="tabular-nums text-xs" style={{ color: 'var(--aura-muted)' }}>{mood.priority}</span>
        <span className={mood.chosen ? 'font-medium' : ''}>{LAB_STATE_LABEL[mood.state]}</span>
        <Bar value={mood.closeness} color={color} />
        <span className="truncate text-xs" style={{ color }}>
          {Math.round(mood.closeness * 100)}% · {status}
        </span>
        <ChevronDown size={14} aria-hidden style={{ color: 'var(--aura-muted)', transform: open ? 'rotate(180deg)' : undefined }} />
      </button>
      {open && (
        <div className="space-y-2 px-2 pb-2 pl-8">
          {mood.clauses.map((c, i) => (
            <div key={c.name}>
              <p className="text-xs" style={{ color: c.met ? 'var(--aura-calm)' : 'var(--aura-muted)' }}>
                {i > 0 && <span style={{ color: 'var(--aura-subtle)' }}>or </span>}
                <span className="font-medium">{c.name}</span> {c.met ? '(fires)' : `(${Math.round(c.closeness * 100)}%)`}
              </p>
              <ul className="mt-0.5 space-y-0.5">
                {c.conditions.map((k) => <ConditionLine key={k.label} c={k} />)}
              </ul>
            </div>
          ))}
        </div>
      )}
    </li>
  );
}

function ConditionLine({ c }: { c: XaiCondition }) {
  return (
    <li className="flex items-center gap-2 text-xs">
      {c.met
        ? <Check size={12} aria-label="met" style={{ color: 'var(--aura-calm)' }} />
        : <X size={12} aria-label="not met" style={{ color: 'var(--aura-elev)' }} />}
      <span style={{ color: 'var(--aura-muted)' }}>{c.label}</span>
      <span className="ml-auto tabular-nums">
        {fmt(c.value)} <span style={{ color: 'var(--aura-muted)' }}>{c.op === 'is' ? 'should be' : c.op} {fmt(c.threshold)}{c.unit && ` ${c.unit}`}</span>
      </span>
    </li>
  );
}

function fmt(v: number | boolean | null) {
  if (v === null) return 'n/a';
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function Bar({ value, color }: { value: number; color: string }) {
  return (
    <span className="block h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--aura-track)' }}>
      <span className="block h-full rounded-full transition-all duration-300"
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: color }} />
    </span>
  );
}

const EMOTION_LABEL: Record<string, string> = {
  anger: 'Anger', contempt: 'Contempt', disgust: 'Disgust', fear: 'Fear',
  happiness: 'Happiness', neutral: 'Neutral', sadness: 'Sadness', surprise: 'Surprise',
};

function CameraSection() {
  const [cam, setCam] = useState<CameraExplain | null>(null);
  useEffect(() => {
    let alive = true;
    const poll = () =>
      apiGet<CameraExplain>('/api/camera/explain')
        .then((r) => { if (alive) setCam(r); })
        .catch(() => { if (alive) setCam(null); });
    void poll();
    const id = window.setInterval(poll, 400);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  const d = cam?.detail;
  return (
    <section className="mt-5" aria-label="Camera">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
        <Camera size={13} aria-hidden /> Step 0 · Camera affect
        {cam?.active && (
          <span className="font-normal normal-case" style={{ color: cam.used_by_fusion ? 'var(--aura-calm)' : 'var(--aura-muted)' }}>
            · {cam.used_by_fusion ? 'feeding rules' : 'not used right now'}
          </span>
        )}
      </h3>
      {!cam?.active ? (
        <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>
          Camera is off. Reading keyboard, mouse, and search interactions locally.
        </p>
      ) : !d ? (
        <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>Starting camera preview…</p>
      ) : (
        <div className="mt-2 grid gap-4 md:grid-cols-[minmax(0,220px)_1fr]">
          <div>
            {d.frame_jpeg_b64 ? (
              <img
                src={`data:image/jpeg;base64,${d.frame_jpeg_b64}`}
                alt={d.face ? 'Detected face landmarks' : 'Camera view, no face detected'}
                className="w-full rounded-lg border"
                style={{ borderColor: 'var(--aura-border)' }}
              />
            ) : (
              <div className="grid aspect-[4/3] place-items-center rounded-lg border text-xs" style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}>
                Waiting for frame…
              </div>
            )}
            <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>
              {d.face ? `Face detected · ${d.latency_ms ?? '--'} ms/frame` : 'No face in view.'}
            </p>
          </div>
          {d.face && (
            <div className="space-y-3">
              <div>
                <h4 className="text-xs" style={{ color: 'var(--aura-muted)' }}>Emotion model</h4>
                <ul className="mt-1 space-y-1">
                  {Object.entries(d.emotions).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k, v]) => (
                    <li key={k} className="grid grid-cols-[5rem_1fr_2.5rem] items-center gap-2 text-xs">
                      <span>{EMOTION_LABEL[k] ?? k}</span>
                      <Bar value={v} color={k === d.dominant ? 'var(--aura-calm)' : 'var(--aura-muted)'} />
                      <span className="text-right tabular-nums" style={{ color: 'var(--aura-muted)' }}>{Math.round(v * 100)}%</span>
                    </li>
                  ))}
                </ul>
              </div>
              <Circumplex valence={d.valence} arousal={d.arousal} anchors={d.anchors} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Circumplex({ valence, arousal, anchors }: { valence: number; arousal: number; anchors: Record<string, [number, number]> }) {
  const S = 130;
  const px = (v: number) => ((v + 1) / 2) * S;
  const py = (a: number) => ((1 - a) / 2) * S;
  return (
    <svg viewBox={`-6 -6 ${S + 12} ${S + 14}`} className="w-full max-w-[170px]" role="img"
      aria-label={`Mood ${valence.toFixed(2)}, energy ${arousal.toFixed(2)}`}>
      <rect x={0} y={0} width={S} height={S} rx={8} fill="none" stroke="var(--aura-border)" />
      <line x1={S / 2} y1={0} x2={S / 2} y2={S} stroke="var(--aura-track)" />
      <line x1={0} y1={S / 2} x2={S} y2={S / 2} stroke="var(--aura-track)" />
      {Object.entries(anchors).map(([k, [v, a]]) => (
        <g key={k}>
          <circle cx={px(v)} cy={py(a)} r={2} fill="var(--aura-muted)" />
          <text x={px(v) + 3} y={py(a) - 3} fontSize={7} fill="var(--aura-muted)">{EMOTION_LABEL[k] ?? k}</text>
        </g>
      ))}
      <circle cx={px(valence)} cy={py(arousal)} r={5} fill="var(--aura-calm)" stroke="var(--aura-bg)" strokeWidth={1.5} />
      <text x={2} y={S + 7} fontSize={7} fill="var(--aura-subtle)">low mood</text>
      <text x={S - 36} y={S + 7} fontSize={7} fill="var(--aura-subtle)">good mood</text>
    </svg>
  );
}
