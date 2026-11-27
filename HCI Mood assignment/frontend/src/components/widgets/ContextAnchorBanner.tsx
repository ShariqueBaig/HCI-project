import { Compass, CheckCircle2, FileText, Target } from 'lucide-react';

interface ContextAnchorBannerProps {
  activeGoal: string;
  lastNoteTitle: string;
  lastNoteExcerpt: string;
  completedCount: number;
  totalCount: number;
}

export function ContextAnchorBanner({
  activeGoal,
  lastNoteTitle,
  lastNoteExcerpt,
  completedCount,
  totalCount,
}: ContextAnchorBannerProps) {
  return (
    <section
      className="rounded-3xl border p-6 shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-accent)' }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
          style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
        >
          <Compass className="h-3.5 w-3.5" />
          Where You Left Off (Context Re-Anchor)
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--aura-muted)' }}>
          <CheckCircle2 className="h-3.5 w-3.5" style={{ color: 'var(--aura-accent)' }} />
          {completedCount} of {totalCount} tasks completed
        </span>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div
          className="rounded-2xl border p-4"
          style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
        >
          <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--aura-accent)' }}>
            <Target className="h-3.5 w-3.5" /> Active Priority Goal
          </div>
          <p className="mt-1.5 text-base font-bold leading-snug">{activeGoal}</p>
        </div>

        <div
          className="rounded-2xl border p-4"
          style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
        >
          <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--aura-accent)' }}>
            <FileText className="h-3.5 w-3.5" /> Last Active Note: {lastNoteTitle}
          </div>
          <p className="mt-1.5 text-xs leading-relaxed" style={{ color: 'var(--aura-muted)' }}>
            {lastNoteExcerpt || 'Open Document Studio to continue writing.'}
          </p>
        </div>
      </div>
    </section>
  );
}
