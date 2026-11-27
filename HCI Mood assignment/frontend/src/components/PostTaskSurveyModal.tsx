import { useMemo, useState } from 'react';
import { CheckCircle2, ClipboardCheck, X } from 'lucide-react';

interface PostTaskSurveyModalProps {
  open: boolean;
  trial: {
    sessionId: string;
    participantId: string;
    scenario: string;
    condition: string;
    taskPrompt: string;
    startedAtMs: number;
  } | null;
  counters: {
    clicks: number;
    rageClicks: number;
    hesitations: number;
    backtracks: number;
    errors: number;
  };
  visualType: string;
  navType: string;
  onClose: () => void;
  onSubmitted: () => void;
}

const SUS_ITEMS = [
  '1. I think that I would like to use this interface frequently.',
  '2. I found the interface unnecessarily complex.',
  '3. I thought the interface was easy to use.',
  '4. I think that I would need the support of a technical person to use this system.',
  '5. I found the various functions in this interface were well integrated.',
  '6. I thought there was too much inconsistency in this interface.',
  '7. I would imagine that most people would learn to use this interface very quickly.',
  '8. I found the interface very awkward to use.',
  '9. I felt very confident using the interface.',
  '10. I needed to learn a lot of things before I could get going with this interface.',
];

export function PostTaskSurveyModal({
  open,
  trial,
  counters,
  visualType,
  navType,
  onClose,
  onSubmitted,
}: PostTaskSurveyModalProps) {
  const [sus, setSus] = useState<number[]>([4, 2, 4, 1, 4, 2, 4, 2, 4, 1]);
  const [samValence, setSamValence] = useState(6);
  const [samArousal, setSamArousal] = useState(4);
  const [samDominance, setSamDominance] = useState(6);
  const [tlxMental, setTlxMental] = useState(3);
  const [tlxFrustration, setTlxFrustration] = useState(2);
  const [tlxEffort, setTlxEffort] = useState(3);
  const [completed, setCompleted] = useState(true);
  const [accuracy, setAccuracy] = useState(100);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const liveSus = useMemo(() => {
    let total = 0;
    sus.forEach((v, i) => {
      total += i % 2 === 0 ? v - 1 : 5 - v;
    });
    return (total * 2.5).toFixed(1);
  }, [sus]);

  if (!open || !trial) return null;

  const submitSurvey = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch('/api/research/session/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: trial.sessionId,
          completed,
          task_accuracy: accuracy,
          error_count: counters.errors,
          backtrack_count: counters.backtracks,
          click_count: counters.clicks,
          rage_click_count: counters.rageClicks,
          hesitation_count: counters.hesitations,
          sus_answers: sus,
          sam_valence: samValence,
          sam_arousal: samArousal,
          sam_dominance: samDominance,
          nasa_tlx_mental: tlxMental,
          nasa_tlx_frustration: tlxFrustration,
          nasa_tlx_effort: tlxEffort,
          visual_type: visualType,
          nav_type: navType,
          notes,
        }),
      });
      if (res.ok) {
        onSubmitted();
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4">
      <form
        onSubmit={submitSurvey}
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-3xl border p-6 shadow-2xl"
        style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      >
        <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: 'var(--aura-border)' }}>
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5" style={{ color: 'var(--aura-accent)' }} />
            <div>
              <h2 className="text-base font-bold">Post-Task HCI Evaluation (SUS + SAM + NASA-TLX)</h2>
              <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                Participant {trial.participantId} • {trial.condition === 'emotional_agent' ? 'Emotional AI Agent' : 'Prompt-Only Control'} • {counters.clicks} clicks
              </p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 cursor-pointer">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Task Outcome & Ground Truth SAM */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border p-4" style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}>
            <div className="text-xs font-bold uppercase" style={{ color: 'var(--aura-accent)' }}>
              Task Effectiveness Check
            </div>
            <label className="mt-2 flex items-center gap-2 text-xs font-semibold">
              <input type="checkbox" checked={completed} onChange={(e) => setCompleted(e.target.checked)} />
              Participant successfully completed goal
            </label>
            <label className="mt-3 block text-xs">
              Decision / Task Accuracy: <strong>{accuracy}%</strong>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={accuracy}
                onChange={(e) => setAccuracy(Number(e.target.value))}
                className="mt-1 w-full accent-blue-600"
              />
            </label>
          </div>

          <div className="rounded-2xl border p-4" style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}>
            <div className="text-xs font-bold uppercase" style={{ color: 'var(--aura-accent)' }}>
              SAM Ground-Truth Emotion (1–9)
            </div>
            <label className="mt-2 block text-xs">
              Valence (1 Unhappy → 9 Happy): <strong>{samValence}</strong>
              <input type="range" min={1} max={9} value={samValence} onChange={(e) => setSamValence(Number(e.target.value))} className="w-full accent-blue-600" />
            </label>
            <label className="mt-2 block text-xs">
              Arousal (1 Calm → 9 Excited/Tense): <strong>{samArousal}</strong>
              <input type="range" min={1} max={9} value={samArousal} onChange={(e) => setSamArousal(Number(e.target.value))} className="w-full accent-blue-600" />
            </label>
            <label className="mt-2 block text-xs">
              Control / Dominance (1 Overwhelmed → 9 In Control): <strong>{samDominance}</strong>
              <input type="range" min={1} max={9} value={samDominance} onChange={(e) => setSamDominance(Number(e.target.value))} className="w-full accent-blue-600" />
            </label>
          </div>
        </div>

        {/* Short NASA-TLX */}
        <div className="mt-4 rounded-2xl border p-4" style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}>
          <div className="mb-2 text-xs font-bold uppercase" style={{ color: 'var(--aura-accent)' }}>
            NASA-TLX Cognitive Workload (1 Low – 7 High)
          </div>
          <div className="grid gap-3 sm:grid-cols-3 text-xs">
            <label>
              Mental Demand: <strong>{tlxMental}</strong>
              <input type="range" min={1} max={7} value={tlxMental} onChange={(e) => setTlxMental(Number(e.target.value))} className="w-full accent-blue-600" />
            </label>
            <label>
              Frustration: <strong>{tlxFrustration}</strong>
              <input type="range" min={1} max={7} value={tlxFrustration} onChange={(e) => setTlxFrustration(Number(e.target.value))} className="w-full accent-blue-600" />
            </label>
            <label>
              Effort: <strong>{tlxEffort}</strong>
              <input type="range" min={1} max={7} value={tlxEffort} onChange={(e) => setTlxEffort(Number(e.target.value))} className="w-full accent-blue-600" />
            </label>
          </div>
        </div>

        {/* 10-Item System Usability Scale (SUS) */}
        <div className="mt-4 rounded-2xl border p-4" style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-bold uppercase" style={{ color: 'var(--aura-accent)' }}>
              System Usability Scale (SUS: 1 Strongly Disagree → 5 Strongly Agree)
            </span>
            <span className="font-mono-code rounded-full px-2.5 py-0.5 text-xs font-bold" style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}>
              Live SUS: {liveSus} / 100
            </span>
          </div>
          <div className="space-y-2 text-xs">
            {SUS_ITEMS.map((label, idx) => (
              <div key={idx} className="flex flex-col justify-between gap-2 rounded-xl border p-2.5 sm:flex-row sm:items-center" style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}>
                <span className="flex-1 font-medium">{label}</span>
                <div className="flex shrink-0 items-center gap-1.5">
                  {[1, 2, 3, 4, 5].map((val) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => setSus((prev) => prev.map((x, j) => (j === idx ? val : x)))}
                      className="h-7 w-7 rounded-lg text-xs font-bold cursor-pointer"
                      style={{
                        backgroundColor: sus[idx] === val ? 'var(--aura-accent)' : 'var(--aura-panel-alt)',
                        color: sus[idx] === val ? '#FFFFFF' : 'var(--aura-text)',
                      }}
                    >
                      {val}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <textarea
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional researcher observation notes..."
          className="mt-4 w-full rounded-xl border p-3 text-xs outline-none"
          style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
        />

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="aura-target rounded-xl border text-xs font-semibold cursor-pointer"
            style={{ borderColor: 'var(--aura-border)' }}
          >
            Resume Trial
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="aura-target inline-flex items-center gap-1.5 rounded-xl text-xs font-bold text-white cursor-pointer"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            <CheckCircle2 className="h-4 w-4" />
            {submitting ? 'Saving Trial...' : 'Save Trial to Research DB'}
          </button>
        </div>
      </form>
    </div>
  );
}
