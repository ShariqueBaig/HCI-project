import { ClipboardList, Flag, Play } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { apiGet, apiPost } from '../../api';
import type { StudyStatus, StudyTask } from '../../types';
import { SusSurvey, TaskSurvey } from './Surveys';

const DEV = new URLSearchParams(window.location.search).get('dev') === '1';

/**
 * Study controls inside the search window. Recording itself is owned by Aura
 * (Privacy -> consent, then "Record session" in the desktop window); this panel
 * only runs tasks and questionnaires, which are written into that recording.
 */
export function StudyPanel({ recording, onTaskStart }: { recording: boolean; onTaskStart: () => void }) {
  const [st, setSt] = useState<StudyStatus | null>(null);
  const [ended, setEnded] = useState<StudyTask & { duration_s: number } | null>(null);
  const [sus, setSus] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  const refresh = useCallback(() => {
    apiGet<StudyStatus>('/api/study').then(setSt).catch(() => setSt(null));
  }, []);
  useEffect(refresh, [refresh, recording]);
  useEffect(() => {
    if (!st?.task) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [st?.task]);

  if (!st || (!recording && !DEV) || !st.tasks.length) return null;

  const start = async (id: string) => {
    setBusy(true);
    try {
      await apiPost('/api/study/task/start', { task_id: id });
      refresh();
      onTaskStart();
    } finally {
      setBusy(false);
    }
  };
  const finish = async () => {
    setBusy(true);
    try {
      const r = await apiPost<{ task: StudyTask & { duration_s: number } }>('/api/study/task/end', {});
      setEnded(r.task);
      refresh();
    } finally {
      setBusy(false);
    }
  };
  const submit = async (kind: 'task' | 'sus', answers: Record<string, unknown>, answerText = '', taskId = '') => {
    setBusy(true);
    try {
      const r = await apiPost<{ recorded: boolean; scores: Record<string, number> }>('/api/study/survey', {
        kind, task_id: taskId, answers, answer_text: answerText,
      });
      setNote(r.recorded ? 'Saved to this session.' : 'Not saved: Aura is not recording.');
      setEnded(null);
      setSus(false);
    } finally {
      setBusy(false);
    }
  };

  const t = st.task;
  const elapsed = t ? Math.max(0, Math.floor(now / 1000 - t.started)) : 0;
  return (
    <section
      aria-label="Study"
      className="rounded-xl border p-4 text-sm"
      style={{ borderColor: recording ? 'var(--aura-mild)' : 'var(--aura-border)', background: 'var(--aura-surface)' }}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold">
          <ClipboardList size={16} aria-hidden /> Study
          <span className="text-xs font-normal" style={{ color: recording ? 'var(--aura-mild)' : 'var(--aura-muted)' }}>
            {recording ? '● recording in Aura' : 'not recording (dev)'}
          </span>
        </h2>
        {!t && (
          <button type="button" onClick={() => setSus(true)} className="aura-target rounded-lg border text-xs"
            style={{ borderColor: 'var(--aura-border)' }}>
            Usability questionnaire (SUS)
          </button>
        )}
      </div>

      {t ? (
        <div className="flex flex-wrap items-center gap-3">
          <p className="min-w-0 flex-1"><span className="font-medium">Your task:</span> {t.task}</p>
          <span className="tabular-nums" style={{ color: 'var(--aura-muted)' }} aria-label="Time on task">
            {String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}
          </span>
          <button type="button" disabled={busy} onClick={finish}
            className="aura-target flex items-center gap-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}>
            <Flag size={14} aria-hidden /> I'm done
          </button>
        </div>
      ) : (
        <ul className="space-y-2">
          {st.tasks.map((f) => (
            <li key={f.id} className="flex items-center gap-3">
              <span className="min-w-0 flex-1">{f.task}</span>
              <button type="button" disabled={busy} onClick={() => start(f.id)}
                className="aura-target flex items-center gap-1.5 rounded-lg border text-xs disabled:opacity-50"
                style={{ borderColor: 'var(--aura-border)' }}>
                <Play size={12} aria-hidden /> Start
              </button>
            </li>
          ))}
        </ul>
      )}
      {note && <p role="status" className="mt-2 text-xs" style={{ color: 'var(--aura-muted)' }}>{note}</p>}

      {ended && (
        <TaskSurvey task={ended.task} busy={busy}
          onSubmit={(answers, text) => submit('task', answers, text, ended.id)} />
      )}
      {sus && (
        <SusSurvey items={st.sus_items} busy={busy} onClose={() => setSus(false)}
          onSubmit={(items) => submit('sus', { sus_items: items })} />
      )}
    </section>
  );
}
