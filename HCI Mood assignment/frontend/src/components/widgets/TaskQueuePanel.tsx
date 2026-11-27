import { useState } from 'react';
import { CheckCircle2, Circle, ListTodo, Plus, Trash2 } from 'lucide-react';
import type { TaskItem } from '../../types/aura';

interface TaskQueuePanelProps {
  tasks: TaskItem[];
  viewMode?: 'compact' | 'kanban' | 'guided';
  maxVisible?: number;
  onAddTask: (title: string, priority: 'high' | 'medium' | 'low', minutes: number, category: string) => void;
  onToggleTask: (id: string, completed: boolean) => void;
  onDeleteTask: (id: string) => void;
}

export function TaskQueuePanel({
  tasks,
  viewMode = 'compact',
  maxVisible = 20,
  onAddTask,
  onToggleTask,
  onDeleteTask,
}: TaskQueuePanelProps) {
  const [newTitle, setNewTitle] = useState('');
  const [priority, setPriority] = useState<'high' | 'medium' | 'low'>('medium');
  const [minutes, setMinutes] = useState<number>(15);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    onAddTask(newTitle.trim(), priority, minutes, 'General');
    setNewTitle('');
  };

  const incomplete = tasks.filter((t) => !t.completed);
  const completed = tasks.filter((t) => t.completed);
  const visibleList = [...incomplete, ...completed].slice(0, maxVisible);

  const renderTaskRow = (task: TaskItem) => (
    <div
      key={task.id}
      className="group flex items-start justify-between gap-2.5 rounded-xl border p-3 transition-colors"
      style={{
        backgroundColor: task.completed ? 'var(--aura-panel-alt)' : 'var(--aura-panel)',
        borderColor: 'var(--aura-border)',
        opacity: task.completed ? 0.65 : 1,
      }}
    >
      <button
        type="button"
        onClick={() => onToggleTask(task.id, !task.completed)}
        className="flex flex-1 items-start gap-2.5 text-left cursor-pointer"
      >
        {task.completed ? (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--aura-accent)' }} />
        ) : (
          <Circle className="mt-0.5 h-4 w-4 shrink-0 opacity-60" />
        )}
        <div className="min-w-0 flex-1">
          <div className={`text-sm font-medium ${task.completed ? 'line-through' : ''}`}>{task.title}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px]" style={{ color: 'var(--aura-muted)' }}>
            <span
              className="rounded px-1.5 py-0.5 font-semibold uppercase"
              style={{
                backgroundColor:
                  task.priority === 'high'
                    ? '#FEE2E2'
                    : task.priority === 'medium'
                      ? 'var(--aura-accent-soft)'
                      : 'var(--aura-panel-alt)',
                color: task.priority === 'high' ? '#991B1B' : 'var(--aura-text)',
              }}
            >
              {task.priority}
            </span>
            <span>{task.estimatedMinutes}m</span>
            <span>{task.category}</span>
          </div>
        </div>
      </button>
      <button
        type="button"
        onClick={() => onDeleteTask(task.id)}
        className="rounded p-1 opacity-40 hover:opacity-100 cursor-pointer"
        title="Delete task"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );

  return (
    <section
      className="rounded-3xl border p-5 shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ListTodo className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
          <h2 className="text-sm font-bold">
            {viewMode === 'kanban'
              ? 'Momentum Kanban Board'
              : viewMode === 'guided'
                ? 'Top 3 Clear Priorities'
                : 'Task Queue'}
          </h2>
        </div>
        <span className="font-mono-code text-xs" style={{ color: 'var(--aura-muted)' }}>
          {incomplete.length} active
        </span>
      </div>

      {/* Add Task Form */}
      <form onSubmit={handleSubmit} className="mt-3 flex flex-wrap gap-2">
        <input
          type="text"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="Add a concrete task..."
          className="min-w-[160px] flex-1 rounded-xl border px-3 py-1.5 text-xs outline-none"
          style={{
            backgroundColor: 'var(--aura-panel-alt)',
            borderColor: 'var(--aura-border)',
            color: 'var(--aura-text)',
          }}
        />
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as 'high' | 'medium' | 'low')}
          className="rounded-xl border px-2 py-1.5 text-xs"
          style={{
            backgroundColor: 'var(--aura-panel-alt)',
            borderColor: 'var(--aura-border)',
            color: 'var(--aura-text)',
          }}
        >
          <option value="high">High</option>
          <option value="medium">Med</option>
          <option value="low">Low</option>
        </select>
        <input
          type="number"
          min={2}
          max={120}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value) || 15)}
          className="w-14 rounded-xl border px-2 py-1.5 text-xs"
          style={{
            backgroundColor: 'var(--aura-panel-alt)',
            borderColor: 'var(--aura-border)',
            color: 'var(--aura-text)',
          }}
          title="Estimated minutes"
        />
        <button
          type="submit"
          className="aura-target inline-flex items-center gap-1 rounded-xl text-xs font-semibold text-white cursor-pointer"
          style={{ backgroundColor: 'var(--aura-accent)' }}
        >
          <Plus className="h-3.5 w-3.5" /> Add
        </button>
      </form>

      {viewMode === 'kanban' ? (
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          {[
            { label: 'High Impact', items: incomplete.filter((t) => t.priority === 'high') },
            { label: 'In Flight', items: incomplete.filter((t) => t.priority !== 'high') },
            { label: 'Completed', items: completed },
          ].map((col) => (
            <div
              key={col.label}
              className="rounded-2xl border p-3"
              style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
            >
              <div className="mb-2 flex items-center justify-between text-xs font-bold">
                <span>{col.label}</span>
                <span className="font-mono-code" style={{ color: 'var(--aura-muted)' }}>
                  {col.items.length}
                </span>
              </div>
              <div className="space-y-2">{col.items.map(renderTaskRow)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 space-y-2">{visibleList.map(renderTaskRow)}</div>
      )}
    </section>
  );
}
