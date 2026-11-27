import { useEffect, useRef, useState } from 'react';

/* Post-task and SUS questionnaires. Answers go to /api/study/survey and into
   Aura's consented, hash-chained session file (consent v4). */

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
      className="m-auto max-h-[90vh] w-[min(640px,calc(100vw-32px))] overflow-auto rounded-2xl border p-0 text-[var(--aura-text)] backdrop:bg-black/60"
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

function Scale({ label, min, max, value, onChange, low, high }: {
  label: string; min: number; max: number; value: number | null;
  onChange: (v: number) => void; low: string; high: string;
}) {
  const name = label.replace(/\W+/g, '-').toLowerCase();
  return (
    <fieldset className="mb-4">
      <legend className="mb-1.5 text-sm font-medium">{label}</legend>
      <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--aura-muted)' }}>
        <span className="w-20 text-right">{low}</span>
        <div className="flex flex-1 justify-between gap-1" role="radiogroup" aria-label={label}>
          {Array.from({ length: max - min + 1 }, (_, i) => min + i).map((n) => (
            <label key={n} className="flex flex-1 cursor-pointer flex-col items-center gap-1">
              <input
                type="radio"
                name={name}
                value={n}
                checked={value === n}
                onChange={() => onChange(n)}
                className="h-4 w-4 accent-[var(--aura-calm)]"
              />
              <span className="tabular-nums">{n}</span>
            </label>
          ))}
        </div>
        <span className="w-20">{high}</span>
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

export function TaskSurvey({ task, onSubmit, busy }: {
  task: string;
  busy: boolean;
  onSubmit: (answers: Record<string, number | boolean>, answerText: string) => void;
}) {
  const [a, setA] = useState<Record<string, number | null>>(() =>
    Object.fromEntries(TASK_ITEMS.map((i) => [i.id, null])));
  const [completed, setCompleted] = useState(true);
  const [text, setText] = useState('');
  const missing = TASK_ITEMS.filter((i) => a[i.id] === null).length;
  return (
    <Modal title="About that task">
      <p className="mb-4 text-sm" style={{ color: 'var(--aura-muted)' }}>{task}</p>
      <label className="mb-4 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={completed} onChange={(e) => setCompleted(e.target.checked)}
          className="h-4 w-4 accent-[var(--aura-calm)]" />
        I finished the task
      </label>
      {TASK_ITEMS.map((i) => (
        <Scale key={i.id} label={i.label} min={i.min} max={i.max} low={i.low} high={i.high}
          value={a[i.id]} onChange={(v) => setA((s) => ({ ...s, [i.id]: v }))} />
      ))}
      <label className="mb-4 block text-sm">
        <span className="mb-1 block font-medium">Your answer to the task (optional)</span>
        <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={500} rows={3}
          className="w-full rounded-lg border bg-transparent p-2 text-sm"
          style={{ borderColor: 'var(--aura-border)' }} />
        <span className="text-xs" style={{ color: 'var(--aura-muted)' }}>Stored with this session. Don't include anything personal.</span>
      </label>
      <button
        type="button"
        disabled={missing > 0 || busy}
        onClick={() => onSubmit({ ...(a as Record<string, number>), completed }, text)}
        className="aura-target w-full rounded-lg text-sm font-medium disabled:opacity-50"
        style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
      >
        {missing > 0 ? `${missing} question${missing > 1 ? 's' : ''} left` : 'Submit'}
      </button>
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
        About Aura Search overall, in this part of the session.
      </p>
      {items.map((label, i) => (
        <Scale key={i} label={`${i + 1}. ${label}`} min={1} max={5} low="Strongly disagree" high="Strongly agree"
          value={v[i]} onChange={(n) => setV((s) => s.map((x, j) => (j === i ? n : x)))} />
      ))}
      <div className="flex gap-2">
        <button type="button" onClick={onClose} className="aura-target flex-1 rounded-lg border text-sm"
          style={{ borderColor: 'var(--aura-border)' }}>Cancel</button>
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
