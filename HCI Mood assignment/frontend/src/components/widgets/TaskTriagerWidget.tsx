import { CheckCircle2, Circle, Layers, Sparkles } from 'lucide-react';
import type { TaskItem } from '../../types/aura';

interface TaskTriagerWidgetProps {
  task: TaskItem | null;
  hiddenTaskCount: number;
  onCompleteTask: (id: string) => void;
  onToggleMicroStep: (taskId: string, stepId: string) => void;
}

export function TaskTriagerWidget({
  task,
  hiddenTaskCount,
  onCompleteTask,
  onToggleMicroStep,
}: TaskTriagerWidgetProps) {
  if (!task) {
    return (
      <div
        className="rounded-2xl border p-8 text-center shadow-sm"
        style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      >
        <CheckCircle2 className="mx-auto mb-3 h-10 w-10" style={{ color: 'var(--aura-accent)' }} />
        <h2 className="text-xl font-bold">Everything is clear</h2>
        <p className="mt-1 text-sm" style={{ color: 'var(--aura-muted)' }}>
          All tasks are completed. Take a quiet breath before adding anything new.
        </p>
      </div>
    );
  }

  const nextStep = task.microSteps.find((s) => !s.done) ?? task.microSteps[0];

  return (
    <section
      className="rounded-3xl border p-6 shadow-sm sm:p-8"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
          style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Hick's Law Single-Task Triage
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--aura-muted)' }}>
          <Layers className="h-3.5 w-3.5" />
          {hiddenTaskCount} lower-priority items tucked away
        </span>
      </div>

      <h2 className="mt-4 text-xl font-bold tracking-tight sm:text-2xl">{task.title}</h2>
      <p className="mt-1 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
        {task.category} • ~{task.estimatedMinutes} min total • Priority: {task.priority}
      </p>

      {nextStep && (
        <div
          className="mt-6 rounded-2xl border p-5"
          style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
        >
          <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--aura-accent)' }}>
            Only do this 2-minute micro-step right now:
          </div>
          <button
            type="button"
            onClick={() => onToggleMicroStep(task.id, nextStep.id)}
            className="aura-target mt-3 flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left font-medium cursor-pointer"
            style={{
              backgroundColor: 'var(--aura-panel)',
              borderColor: 'var(--aura-border)',
            }}
          >
            {nextStep.done ? (
              <CheckCircle2 className="h-6 w-6 shrink-0" style={{ color: 'var(--aura-accent)' }} />
            ) : (
              <Circle className="h-6 w-6 shrink-0" style={{ color: 'var(--aura-accent)' }} />
            )}
            <span className={`aura-readable ${nextStep.done ? 'line-through opacity-60' : ''}`}>
              {nextStep.text}
            </span>
          </button>
        </div>
      )}

      {task.microSteps.length > 1 && (
        <div className="mt-4 space-y-2">
          {task.microSteps.map((step) => (
            <button
              key={step.id}
              type="button"
              onClick={() => onToggleMicroStep(task.id, step.id)}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors hover:opacity-80 cursor-pointer"
              style={{ color: step.done ? 'var(--aura-muted)' : 'var(--aura-text)' }}
            >
              {step.done ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: 'var(--aura-accent)' }} />
              ) : (
                <Circle className="h-4 w-4 shrink-0 opacity-60" />
              )}
              <span className={step.done ? 'line-through' : ''}>{step.text}</span>
            </button>
          ))}
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => onCompleteTask(task.id)}
          className="aura-target inline-flex flex-1 items-center justify-center gap-2 rounded-2xl text-sm font-bold text-white shadow-sm hover:opacity-95 cursor-pointer"
          style={{ backgroundColor: 'var(--aura-accent)' }}
        >
          <CheckCircle2 className="h-5 w-5" />
          Mark Primary Task Complete
        </button>
      </div>
    </section>
  );
}
