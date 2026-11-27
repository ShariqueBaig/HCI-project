import { CheckCircle2, Clock, Feather, Volume2 } from 'lucide-react';
import type { TaskItem } from '../../types/aura';

interface QuickWinDeckWidgetProps {
  tasks: TaskItem[];
  onCompleteTask: (id: string) => void;
}

export function QuickWinDeckWidget({ tasks, onCompleteTask }: QuickWinDeckWidgetProps) {
  const speakTask = (text: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 0.94;
    window.speechSynthesis.speak(utter);
  };

  return (
    <section
      className="rounded-3xl border p-6 shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Feather className="h-5 w-5" style={{ color: 'var(--aura-accent)' }} />
          <div>
            <h2 className="text-base font-bold">Low-Friction Quick Wins (&le;15m)</h2>
            <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
              Heavy tasks are deferred until your energy recovers.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {tasks.length === 0 ? (
          <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: 'var(--aura-panel-alt)', color: 'var(--aura-muted)' }}>
            No pending quick wins right now. Enjoy a brief break!
          </p>
        ) : (
          tasks.map((task) => (
            <div
              key={task.id}
              className="flex flex-col justify-between gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center"
              style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
            >
              <div className="space-y-1">
                <div className="aura-readable font-semibold">{task.title}</div>
                <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--aura-muted)' }}>
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" /> {task.estimatedMinutes} min
                  </span>
                  <span>{task.category}</span>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={() => speakTask(`Quick win: ${task.title}. Estimated ${task.estimatedMinutes} minutes.`)}
                  className="aura-target inline-flex items-center gap-1 rounded-xl border text-xs font-medium cursor-pointer"
                  style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel)' }}
                  title="Read task aloud (Voice Assist)"
                >
                  <Volume2 className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
                </button>
                <button
                  type="button"
                  onClick={() => onCompleteTask(task.id)}
                  className="aura-target inline-flex items-center gap-1.5 rounded-xl text-xs font-semibold text-white cursor-pointer"
                  style={{ backgroundColor: 'var(--aura-accent)' }}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Done
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
