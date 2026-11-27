import { useState } from 'react';
import { ArrowUpRight, Lightbulb, Plus, Trash2 } from 'lucide-react';
import type { IdeaItem } from '../../types/aura';

interface DivergentIdeaCanvasProps {
  ideas: IdeaItem[];
  compact?: boolean;
  onAddIdea: (text: string, tag: string) => void;
  onDeleteIdea: (id: string) => void;
  onPromoteIdea: (id: string) => void;
}

export function DivergentIdeaCanvas({
  ideas,
  compact = false,
  onAddIdea,
  onDeleteIdea,
  onPromoteIdea,
}: DivergentIdeaCanvasProps) {
  const [text, setText] = useState('');
  const [tag, setTag] = useState('Experiment');

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onAddIdea(text.trim(), tag);
    setText('');
  };

  return (
    <section
      className="rounded-3xl border p-5 shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
          <h2 className="text-sm font-bold">
            {compact ? 'Quick Idea Inbox' : 'Divergent Idea Canvas'}
          </h2>
        </div>
        <span className="font-mono-code text-xs" style={{ color: 'var(--aura-muted)' }}>
          {ideas.length} sparks
        </span>
      </div>

      <form onSubmit={submit} className="mt-3 flex flex-wrap gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Capture a creative spark or hypothesis..."
          className="min-w-[180px] flex-1 rounded-xl border px-3 py-1.5 text-xs outline-none"
          style={{
            backgroundColor: 'var(--aura-panel-alt)',
            borderColor: 'var(--aura-border)',
            color: 'var(--aura-text)',
          }}
        />
        {!compact && (
          <input
            type="text"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            placeholder="Tag"
            className="w-28 rounded-xl border px-2.5 py-1.5 text-xs outline-none"
            style={{
              backgroundColor: 'var(--aura-panel-alt)',
              borderColor: 'var(--aura-border)',
              color: 'var(--aura-text)',
            }}
          />
        )}
        <button
          type="submit"
          className="aura-target inline-flex items-center gap-1 rounded-xl text-xs font-semibold text-white cursor-pointer"
          style={{ backgroundColor: 'var(--aura-accent)' }}
        >
          <Plus className="h-3.5 w-3.5" /> Capture
        </button>
      </form>

      <div className={`mt-4 grid gap-3 ${compact ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'}`}>
        {ideas.map((idea) => (
          <div
            key={idea.id}
            className="flex flex-col justify-between gap-3 rounded-2xl border p-3.5"
            style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
          >
            <div>
              <span
                className="inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase"
                style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
              >
                {idea.tag}
              </span>
              <p className="mt-2 text-sm font-medium leading-snug">{idea.text}</p>
            </div>
            <div className="flex items-center justify-between gap-2 pt-1">
              <button
                type="button"
                onClick={() => onPromoteIdea(idea.id)}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold hover:opacity-85 cursor-pointer"
                style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
              >
                Promote to Task <ArrowUpRight className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onDeleteIdea(idea.id)}
                className="rounded p-1 opacity-45 hover:opacity-100 cursor-pointer"
                title="Remove idea"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
