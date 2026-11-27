import { useEffect, useRef, useState } from 'react';

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose?: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => d?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose?.();
      }}
      className="m-auto max-h-[90vh] w-[min(660px,calc(100vw-32px))] overflow-auto rounded-2xl border p-0 text-[var(--aura-text)] backdrop:bg-black/60"
      style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      aria-label={title}
    >
      <div className="p-6">
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </dialog>
  );
}

/** Accessible button-based scale (>=36x36px hit targets, full keyboard focus). */
export function Scale({ label, min, max, value, onChange, low, high }: {
  label: string; min: number; max: number; value: number | null;
  onChange: (v: number) => void; low: string; high: string;
}) {
  return (
    <fieldset className="mb-5">
      <legend className="mb-2 text-sm font-medium">{label}</legend>
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
        <span className="text-xs sm:w-24 sm:text-right" style={{ color: 'var(--aura-muted)' }}>{low}</span>
        <div className="flex flex-1 gap-1.5" role="radiogroup" aria-label={label}>
          {Array.from({ length: max - min + 1 }, (_, i) => min + i).map((n) => {
            const active = value === n;
            return (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => onChange(n)}
                className="flex min-h-9 flex-1 items-center justify-center rounded-lg border text-sm font-medium tabular-nums transition-colors"
                style={{
                  borderColor: active ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
                  background: active ? 'var(--aura-calm)' : 'var(--aura-surface-elev)',
                  color: active ? 'var(--aura-bg)' : 'var(--aura-text)',
                }}
              >
                {n}
              </button>
            );
          })}
        </div>
        <span className="text-xs sm:w-24" style={{ color: 'var(--aura-muted)' }}>{high}</span>
      </div>
    </fieldset>
  );
}

const TASK_ITEMS: { id: string; label: string; min: number; max: number; low: string; high: string }[] = [
  { id: 'success', label: 'How well did you complete the task?', min: 1, max: 5, low: 'Not at all', high: 'Fully' },
  { id: 'sam_valence', label: 'How did you feel? (pleasure)', min: 1, max: 9, low: 'Unhappy', high: 'Happy' },
  { id: 'sam_arousal', label: 'How did you feel? (arousal)', min: 1, max: 9, low: 'Calm', high: 'Excited' },
  { id: 'sam_dominance', label: 'How did you feel? (control)', min: 1, max: 9, low: 'Controlled', high: 'In control' },
  { id: 'tlx_mental', label: 'How mentally demanding was the task?', min: 1, max: 7, low: 'Very low', high: 'Very high' },
  { id: 'tlx_frustration', label: 'How frustrated were you?', min: 1, max: 7, low: 'Very low', high: 'Very high' },
  { id: 'tlx_effort', label: 'How hard did you have to work?', min: 1, max: 7, low: 'Very low', high: 'Very high' },
  { id: 'personalization', label: 'The results were presented in a way that suited me.', min: 1, max: 7, low: 'Disagree', high: 'Agree' },
  { id: 'control', label: 'I felt in control of how the results were shown.', min: 1, max: 7, low: 'Disagree', high: 'Agree' },
  { id: 'trust', label: 'I trusted the information shown.', min: 1, max: 7, low: 'Disagree', high: 'Agree' },
];

export function TaskSurvey({ task, onSubmit, onCancel, busy }: {
  task: string;
  busy: boolean;
  onSubmit: (answers: Record<string, number | boolean>, answerText: string) => void;
  onCancel?: () => void;
}) {
  const [a, setA] = useState<Record<string, number | null>>(() =>
    Object.fromEntries(TASK_ITEMS.map((i) => [i.id, null])));
  const [completed, setCompleted] = useState(true);
  const [text, setText] = useState('');
  const missing = TASK_ITEMS.filter((i) => a[i.id] === null).length;
  return (
    <Modal title="About that task" onClose={onCancel}>
      <p className="mb-4 text-sm" style={{ color: 'var(--aura-muted)' }}>{task}</p>
      <label className="mb-5 flex cursor-pointer items-center gap-2.5 text-sm">
        <input
          type="checkbox"
          checked={completed}
          onChange={(e) => setCompleted(e.target.checked)}
          className="h-4 w-4 accent-[var(--aura-calm)]"
        />
        I finished the task
      </label>
      {TASK_ITEMS.map((i) => (
        <Scale
          key={i.id}
          label={i.label}
          min={i.min}
          max={i.max}
          low={i.low}
          high={i.high}
          value={a[i.id]}
          onChange={(v) => setA((s) => ({ ...s, [i.id]: v }))}
        />
      ))}
      <label className="mb-4 block text-sm">
        <span className="mb-1 block font-medium">Your answer to the task (optional)</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          rows={3}
          className="w-full rounded-lg border bg-transparent p-2.5 text-sm"
          style={{ borderColor: 'var(--aura-border-interactive)' }}
        />
        <span className="text-xs" style={{ color: 'var(--aura-muted)' }}>
          Stored with this session. Do not include personal information.
        </span>
      </label>
      <div className="flex gap-2">
        {onCancel && (
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="aura-target rounded-lg border px-4 text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          disabled={missing > 0 || busy}
          onClick={() => onSubmit({ ...(a as Record<string, number>), completed }, text)}
          className="aura-target flex-1 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
        >
          {missing > 0 ? `${missing} question${missing > 1 ? 's' : ''} left` : 'Submit'}
        </button>
      </div>
    </Modal>
  );
}

export function SusSurvey({ items, onSubmit, onClose, busy }: {
  items: string[];
  busy: boolean;
  onSubmit: (sus: number[]) => void;
  onClose: () => void;
}) {
  const [v, setV] = useState<(number | null)[]>(() => items.map(() => null));
  const missing = v.filter((x) => x === null).length;
  return (
    <Modal title="Usability questionnaire (SUS)" onClose={onClose}>
      <p className="mb-4 text-sm" style={{ color: 'var(--aura-muted)' }}>
        About Aura overall, in this part of the session.
      </p>
      {items.map((label, i) => (
        <Scale
          key={i}
          label={`${i + 1}. ${label}`}
          min={1}
          max={5}
          low="Strongly disagree"
          high="Strongly agree"
          value={v[i]}
          onChange={(n) => setV((s) => s.map((x, j) => (j === i ? n : x)))}
        />
      ))}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onClose}
          className="aura-target flex-1 rounded-lg border text-sm"
          style={{ borderColor: 'var(--aura-border-interactive)' }}
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={missing > 0 || busy}
          onClick={() => onSubmit(v as number[])}
          className="aura-target flex-1 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
        >
          {missing > 0 ? `${missing} left` : 'Submit'}
        </button>
      </div>
    </Modal>
  );
}
