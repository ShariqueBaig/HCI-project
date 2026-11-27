import { Brain, Camera, Check, ChevronDown, FlaskConical, Square, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { apiGet, apiPost } from '../api';
import type { CameraExplain, HciState, StateSnapshot, XaiCondition, XaiMood } from '../types';
import { STATE_LABEL } from './StatePill';

const MOODS: HciState[] = ['focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented'];

const MOOD_HINT: Record<HciState, string> = {
  focused: 'Moderate stress, no friction: full detail and sources',
  overwhelmed: 'Stress 82/100: one clear answer and a next step',
  fatigued: 'Slow, heavy typing: shorter, easier text',
  energized: 'Fast, accurate typing: compare-and-explore view',
  disoriented: 'Reworded searches + pauses: where you are, narrow it down',
};

const SOURCE_LABEL: Record<string, string> = {
  aura: 'Aura desktop stress',
  query_typing: 'Search-box typing stress',
};

/** Explainable-AI view of the state model, plus a mood simulator that drives it. */
export function XaiPanel({ snap, onClose }: { snap: StateSnapshot | null; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, []);
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
    <section id="xai-panel" ref={ref} aria-label="How Aura reads your mood"
      className="rounded-xl border px-5 py-3 text-sm" style={{ borderColor: 'var(--aura-border)' }}>
      <header className="flex items-center gap-2" style={{ color: 'var(--aura-muted)' }}>
        <Brain size={15} aria-hidden />
        <span>How Aura reads your mood (explainable AI)</span>
        {sim && (
          <span className="rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide"
            style={{ background: 'var(--aura-mild)', color: 'var(--aura-bg)' }}>
            simulating {STATE_LABEL[sim.state]}
          </span>
        )}
        <button type="button" onClick={onClose} aria-label="Close explanation"
          className="ml-auto rounded-md p-1 hover:bg-[var(--aura-surface)]">
          <X size={16} aria-hidden />
        </button>
      </header>

      {/* ---- verdict ---- */}
      <div className="mt-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <p>
          <span style={{ color: 'var(--aura-muted)' }}>Model predicts now: </span>
          <span className="font-medium">{STATE_LABEL[f.state]}</span>
          <span className="tabular-nums" style={{ color: 'var(--aura-muted)' }}> · {Math.round(f.confidence * 100)}% confidence</span>
        </p>
        <p>
          <span style={{ color: 'var(--aura-muted)' }}>Layout follows: </span>
          <span className="font-medium">{STATE_LABEL[f.committed_state]}</span>
          {f.candidate_state && (
            <span style={{ color: 'var(--aura-mild)' }}>
              {' '}(switching to {STATE_LABEL[f.candidate_state]} in {Math.max(0, 3 * (1 - f.dwell_progress)).toFixed(1)} s)
            </span>
          )}
        </p>
      </div>

      {/* ---- simulator ---- */}
      <section className="mt-4" aria-label="Simulate a mood">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
          <FlaskConical size={13} aria-hidden /> Simulate a mood
        </h3>
        <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>
          Feeds the model that mood's typical signals for 45 s, so you can watch the rules below fire and the
          layout adapt. Also available from Aura's <span className="font-medium">Simulate Stress</span> button.
        </p>
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
                className="aura-target rounded-lg border text-sm disabled:opacity-50 hover:border-[var(--aura-calm)]"
                style={{
                  borderColor: active ? 'var(--aura-mild)' : 'var(--aura-border)',
                  background: active ? 'color-mix(in srgb, var(--aura-mild) 18%, transparent)' : 'var(--aura-surface)',
                  color: active ? 'var(--aura-mild)' : 'var(--aura-text)',
                }}
              >
                {STATE_LABEL[m]}
              </button>
            );
          })}
          {sim && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void simulate(null)}
              className="aura-target flex items-center gap-1.5 rounded-lg border text-sm disabled:opacity-50"
              style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}
            >
              <Square size={12} aria-hidden /> Stop ({Math.ceil(sim.remaining_s)} s)
            </button>
          )}
        </div>
        {err && <p role="alert" className="mt-2 text-xs" style={{ color: 'var(--aura-elev)' }}>Could not simulate: {err}</p>}
      </section>

      <CameraSection />

      {xai && (
        <>
          {/* ---- stress fusion ---- */}
          <section className="mt-5" aria-label="Stress fusion">
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
              Step 1 · Fused stress {xai.stress_fusion.fused !== null && <span className="tabular-nums normal-case">= {xai.stress_fusion.fused}/100</span>}
            </h3>
            {xai.stress_fusion.parts.length === 0 ? (
              <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>No stress signals yet.</p>
            ) : (
              <ul className="mt-2 space-y-1.5">
                {xai.stress_fusion.parts.map((p) => (
                  <li key={p.source} className="grid grid-cols-[minmax(0,12rem)_1fr_auto] items-center gap-3">
                    <span className="truncate" style={{ color: 'var(--aura-muted)' }}>{SOURCE_LABEL[p.source] ?? p.source}</span>
                    <Bar value={p.value / 100} color="var(--aura-calm)" />
                    <span className="tabular-nums text-xs" style={{ color: 'var(--aura-muted)' }}>
                      {p.value.toFixed(0)} × weight {p.weight} ({Math.round(p.share * 100)}%)
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-1 text-xs" style={{ color: 'var(--aura-faint)' }}>{xai.stress_fusion.formula}</p>
          </section>

          {/* ---- rule trace ---- */}
          <section className="mt-5" aria-label="Decision rules">
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
              Step 2 · Rules, checked in priority order (first match wins)
            </h3>
            <ul className="mt-2 space-y-1">
              {xai.moods.map((m) => (
                <MoodRow key={m.state} mood={m} open={openMood === m.state}
                  onToggle={() => setOpenMood((o) => (o === m.state ? null : m.state))} />
              ))}
            </ul>
            <p className="mt-2 text-xs" style={{ color: 'var(--aura-faint)' }}>
              Bar = how close each mood's best rule is to firing (its weakest condition). A new mood must hold
              3 s before the layout changes; {f.flickers_prevented} brief changes ignored so far.
            </p>
          </section>
        </>
      )}
    </section>
  );
}

function MoodRow({ mood, open, onToggle }: { mood: XaiMood; open: boolean; onToggle: () => void }) {
  const status = mood.chosen ? 'chosen' : mood.matched ? 'matched, lower priority' : 'not met';
  const color = mood.chosen ? 'var(--aura-calm)' : mood.matched ? 'var(--aura-mild)' : 'var(--aura-faint)';
  return (
    <li className="rounded-lg" style={{ background: mood.chosen ? 'color-mix(in srgb, var(--aura-calm) 10%, transparent)' : undefined }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-[1.25rem_minmax(0,7rem)_1fr_minmax(0,9rem)_1rem] items-center gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-[var(--aura-surface)]"
      >
        <span className="tabular-nums text-xs" style={{ color: 'var(--aura-muted)' }}>{mood.priority}</span>
        <span className={mood.chosen ? 'font-medium' : ''}>{STATE_LABEL[mood.state]}</span>
        <Bar value={mood.closeness} color={color} />
        <span className="truncate text-xs" style={{ color }}>
          {Math.round(mood.closeness * 100)}% · {status}
        </span>
        <ChevronDown size={14} aria-hidden style={{ color: 'var(--aura-muted)', transform: open ? 'rotate(180deg)' : undefined }} />
      </button>
      {open && (
        <div className="space-y-2 px-2 pb-2 pl-9">
          {mood.clauses.map((c, i) => (
            <div key={c.name}>
              <p className="text-xs" style={{ color: c.met ? 'var(--aura-calm)' : 'var(--aura-muted)' }}>
                {i > 0 && <span style={{ color: 'var(--aura-faint)' }}>or </span>}
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
    <span className="block h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--aura-faint)' }}>
      <span className="block h-full rounded-full transition-all duration-300"
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: color }} />
    </span>
  );
}

const EMOTION_LABEL: Record<string, string> = {
  anger: 'Anger', contempt: 'Contempt', disgust: 'Disgust', fear: 'Fear',
  happiness: 'Happiness', neutral: 'Neutral', sadness: 'Sadness', surprise: 'Surprise',
};

/** Step 0: what the webcam sees and how it turns a face into mood numbers. */
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
        <Camera size={13} aria-hidden /> Step 0 · Your face (camera)
        {cam?.active && (
          <span className="font-normal normal-case" style={{ color: cam.used_by_fusion ? 'var(--aura-calm)' : 'var(--aura-muted)' }}>
            · {cam.used_by_fusion ? 'feeding the rules below' : 'not used right now'}
          </span>
        )}
      </h3>
      {!cam?.active ? (
        <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>
          The camera is off, so the model reads typing and clicks only. Turn on <span className="font-medium">Camera</span> at
          the top to see your face and what the emotion model decides from it. Video stays on this computer and is never saved.
        </p>
      ) : !d ? (
        <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>Starting the preview…</p>
      ) : (
        <div className="mt-2 grid gap-4 md:grid-cols-[minmax(0,260px)_1fr]">
          <div>
            {d.frame_jpeg_b64 ? (
              <img
                src={`data:image/jpeg;base64,${d.frame_jpeg_b64}`}
                alt={d.face ? 'Your face with the detected box and landmarks' : 'Camera view, no face found'}
                className="w-full rounded-lg border"
                style={{ borderColor: 'var(--aura-border)' }}
              />
            ) : (
              <div className="grid aspect-[4/3] place-items-center rounded-lg border text-xs" style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}>
                Waiting for a frame…
              </div>
            )}
            <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>
              {d.face
                ? `Face found${d.face_count > 1 ? ` (${d.face_count}, using the first)` : ''} · ${d.latency_ms ?? '--'} ms per frame`
                : 'No face in view: the camera is ignored until one appears.'}
            </p>
            {d.face && d.camera_state && (
              <p className="mt-2 text-xs">
                <span style={{ color: 'var(--aura-muted)' }}>Camera alone would say: </span>
                <span className="font-medium">{STATE_LABEL[d.camera_state]}</span>
                <span style={{ color: 'var(--aura-muted)' }}> ({Math.round(d.camera_state_confidence * 100)}%)</span>
              </p>
            )}
          </div>

          {d.face && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <h4 className="text-xs" style={{ color: 'var(--aura-muted)' }}>1 · Emotion model (smoothed)</h4>
                <ul className="mt-1 space-y-1">
                  {Object.entries(d.emotions).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                    <li key={k} className="grid grid-cols-[5rem_1fr_2.5rem] items-center gap-2 text-xs">
                      <span className={k === d.dominant ? 'font-medium' : ''} style={k === d.dominant ? undefined : { color: 'var(--aura-muted)' }}>
                        {EMOTION_LABEL[k] ?? k}
                      </span>
                      <Bar value={v} color={k === d.dominant ? 'var(--aura-calm)' : 'var(--aura-muted)'} />
                      <span className="text-right tabular-nums" style={{ color: 'var(--aura-muted)' }}>{Math.round(v * 100)}%</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-xs" style={{ color: 'var(--aura-muted)' }}>2 · Mood map (mood × energy)</h4>
                <Circumplex valence={d.valence} arousal={d.arousal} anchors={d.anchors} />
                <p className="mt-1 text-xs tabular-nums" style={{ color: 'var(--aura-muted)' }}>
                  mood {d.valence.toFixed(2)} · energy {d.arousal.toFixed(2)} · attention {Math.round(d.attention * 100)}%
                </p>
              </div>
              <div className="sm:col-span-2">
                <h4 className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                  3 · Cognitive load = {Math.round(d.cognitive_load * 100)}%
                  <span style={{ color: 'var(--aura-faint)' }}> (72% or more counts toward overwhelmed)</span>
                </h4>
                <ul className="mt-1 space-y-1">
                  {d.load_parts.map((p) => (
                    <li key={p.label} className="grid grid-cols-[minmax(0,1fr)_6rem_auto] items-center gap-2 text-xs">
                      <span className="truncate" style={{ color: 'var(--aura-muted)' }}>{p.label}</span>
                      <Bar value={p.contribution / 0.45} color="var(--aura-mild)" />
                      <span className="tabular-nums" style={{ color: 'var(--aura-muted)' }}>
                        {p.value.toFixed(2)} × {p.weight} = {p.contribution.toFixed(2)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/** Russell circumplex: each emotion sits at a fixed (mood, energy); you are the weighted mix. */
function Circumplex({ valence, arousal, anchors }: { valence: number; arousal: number; anchors: Record<string, [number, number]> }) {
  const S = 140;
  const px = (v: number) => ((v + 1) / 2) * S;
  const py = (a: number) => ((1 - a) / 2) * S;
  return (
    <svg viewBox={`-6 -6 ${S + 12} ${S + 14}`} className="mt-1 w-full max-w-[200px]" role="img"
      aria-label={`Mood ${valence.toFixed(2)}, energy ${arousal.toFixed(2)}`}>
      <rect x={0} y={0} width={S} height={S} rx={8} fill="none" stroke="var(--aura-border)" />
      <line x1={S / 2} y1={0} x2={S / 2} y2={S} stroke="var(--aura-faint)" />
      <line x1={0} y1={S / 2} x2={S} y2={S / 2} stroke="var(--aura-faint)" />
      {Object.entries(anchors).map(([k, [v, a]]) => (
        <g key={k}>
          <circle cx={px(v)} cy={py(a)} r={2} fill="var(--aura-muted)" />
          <text x={px(v) + 3} y={py(a) - 3} fontSize={7} fill="var(--aura-muted)">{EMOTION_LABEL[k] ?? k}</text>
        </g>
      ))}
      <circle cx={px(valence)} cy={py(arousal)} r={5} fill="var(--aura-calm)" stroke="var(--aura-bg)" strokeWidth={1.5} />
      <text x={2} y={S + 7} fontSize={7} fill="var(--aura-faint)">low mood</text>
      <text x={S - 34} y={S + 7} fontSize={7} fill="var(--aura-faint)">good mood</text>
    </svg>
  );
}
