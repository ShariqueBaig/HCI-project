import { Check, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { ViewPolicyName } from '../types';

export type SearchLoadingStage = 'retrieving' | 'synthesizing' | 'composing';

const STEPS: { id: SearchLoadingStage; label: string; defaultMsg: string; pct: number }[] = [
  { id: 'retrieving', label: 'Search sources', defaultMsg: 'Searching sources…', pct: 30 },
  { id: 'synthesizing', label: 'Extract cited facts', defaultMsg: 'Extracting cited facts…', pct: 66 },
  { id: 'composing', label: 'Tailor layout', defaultMsg: 'Tailoring layout…', pct: 90 },
];

const SUB_CUES: Record<SearchLoadingStage, string[]> = {
  retrieving: [
    'Scanning authoritative sources…',
    'Cross-checking snippets for relevance…',
    'Gathering citations…',
  ],
  synthesizing: [
    'Verifying claims against sources…',
    'Distilling key facts & comparisons…',
    'Linking inline citations…',
  ],
  composing: [
    'Arranging widgets for your current view…',
    'Tuning density & readability…',
    'Polishing final layout…',
  ],
};

function ShimmerBar({ className = '', width }: { className?: string; width: string }) {
  return <div className={`aura-shimmer rounded-md ${className}`} style={{ width }} aria-hidden />;
}

function WireframeCards({ mood }: { mood: ViewPolicyName }) {
  if (mood === 'overwhelmed') {
    return (
      <div className="mx-auto flex w-full max-w-xl flex-col gap-5">
        <div
          className="flex flex-col gap-3 rounded-xl border p-5"
          style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
        >
          <ShimmerBar className="h-3" width="28%" />
          <ShimmerBar className="h-4" width="94%" />
          <ShimmerBar className="h-4" width="84%" />
        </div>
        <div
          className="flex flex-col gap-3.5 rounded-xl border p-5"
          style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
        >
          <ShimmerBar className="h-3" width="34%" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="aura-shimmer h-6 w-6 shrink-0 rounded-full" aria-hidden />
              <ShimmerBar className="h-3.5" width={`${82 - i * 11}%`} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (mood === 'focused' || mood === 'energized') {
    return (
      <div className="grid grid-cols-1 gap-5 md:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="flex flex-col gap-5">
          <div
            className="flex flex-col gap-3 rounded-xl border p-5"
            style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
          >
            <ShimmerBar className="h-3" width="26%" />
            <ShimmerBar className="h-4" width="95%" />
            <ShimmerBar className="h-4" width="88%" />
            <ShimmerBar className="h-4" width="70%" />
          </div>
          <div
            className="flex flex-col gap-3 rounded-xl border p-5"
            style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
          >
            <ShimmerBar className="h-3" width="32%" />
            <div className="grid grid-cols-2 gap-3 pt-1">
              <ShimmerBar className="h-3" width="90%" />
              <ShimmerBar className="h-3" width="86%" />
              <ShimmerBar className="h-3" width="80%" />
              <ShimmerBar className="h-3" width="76%" />
            </div>
          </div>
        </div>
        <aside className="flex flex-col gap-4">
          <div
            className="flex flex-col gap-2.5 rounded-xl border p-4"
            style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
          >
            <ShimmerBar className="h-2.5" width="48%" />
            <div className="flex flex-wrap gap-1.5 pt-1">
              <div className="aura-shimmer h-6 w-20 rounded-full" aria-hidden />
              <div className="aura-shimmer h-6 w-24 rounded-full" aria-hidden />
              <div className="aura-shimmer h-6 w-16 rounded-full" aria-hidden />
            </div>
          </div>
          <div
            className="flex flex-col gap-2.5 rounded-xl border p-4"
            style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
          >
            <ShimmerBar className="h-2.5" width="42%" />
            <ShimmerBar className="h-3" width="92%" />
            <ShimmerBar className="h-3" width="78%" />
            <ShimmerBar className="h-3" width="85%" />
          </div>
        </aside>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div
        className="flex flex-col gap-3 rounded-xl border p-5"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      >
        <div className="flex items-center justify-between gap-3">
          <ShimmerBar className="h-3" width="24%" />
          <div className="flex gap-1.5">
            <div className="aura-shimmer h-5 w-6 rounded" aria-hidden />
            <div className="aura-shimmer h-5 w-6 rounded" aria-hidden />
          </div>
        </div>
        <ShimmerBar className="h-4" width="94%" />
        <ShimmerBar className="h-4" width="87%" />
        <ShimmerBar className="h-4" width="66%" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {[0, 1].map((cardIdx) => (
          <div
            key={cardIdx}
            className="flex flex-col gap-2.5 rounded-xl border p-4"
            style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
          >
            <ShimmerBar className="h-3" width="38%" />
            <ShimmerBar className="h-3.5" width={`${90 - cardIdx * 6}%`} />
            <ShimmerBar className="h-3.5" width={`${76 - cardIdx * 4}%`} />
            <ShimmerBar className="h-3.5" width="58%" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Animated search loading placeholder shown while retrieval + Stage A + Stage B run. */
export function ResultsSkeleton({
  stage = 'retrieving',
  message,
  mood = 'neutral',
  query,
  sourceCount,
  compact = false,
}: {
  stage?: SearchLoadingStage | null;
  message?: string | null;
  mood?: ViewPolicyName;
  query?: string;
  sourceCount?: number | null;
  compact?: boolean;
}) {
  const activeStage: SearchLoadingStage = stage ?? 'retrieving';
  const [cueIdx, setCueIdx] = useState(0);

  useEffect(() => {
    setCueIdx(0);
    const id = window.setInterval(() => {
      setCueIdx((i) => i + 1);
    }, 2200);
    return () => window.clearInterval(id);
  }, [activeStage]);

  const cues = SUB_CUES[activeStage];
  const subCue = cues[cueIdx % cues.length];
  const activeIdx = Math.max(0, STEPS.findIndex((s) => s.id === activeStage));
  const activeMeta = STEPS[activeIdx];
  const headline = message?.trim() || activeMeta.defaultMsg;

  if (compact) {
    return (
      <div className="aura-fade-up flex flex-col gap-4" aria-busy="true" aria-label={headline}>
        <div
          className="flex flex-col gap-2.5 rounded-xl border px-4 py-3"
          style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
        >
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="flex items-center gap-2 font-medium" style={{ color: 'var(--aura-calm)' }}>
              <Loader2 size={14} className="aura-spin" aria-hidden />
              {headline}
            </span>
            <span style={{ color: 'var(--aura-subtle)' }}>{subCue}</span>
          </div>
          <div className="relative h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--aura-track)' }}>
            <div
              className="aura-progress-sweep h-full w-2/5 rounded-full"
              style={{ background: 'var(--aura-calm)' }}
            />
          </div>
        </div>
        <WireframeCards mood={mood} />
      </div>
    );
  }

  return (
    <div className="aura-fade-up flex flex-col gap-5" aria-busy="true" aria-label={headline}>
      <section
        className="flex flex-col gap-3.5 rounded-2xl border p-5"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3 items-center justify-center" aria-hidden>
              <span
                className="aura-orb-ping absolute inset-0 rounded-full"
                style={{ background: 'var(--aura-calm)' }}
              />
              <span className="relative h-2.5 w-2.5 rounded-full" style={{ background: 'var(--aura-calm)' }} />
            </span>
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--aura-text)' }}>
                {headline}
              </p>
              <p className="aura-fade-in text-xs" key={`${activeStage}-${cueIdx % cues.length}`} style={{ color: 'var(--aura-muted)' }}>
                {subCue}
                {query ? ` · “${query}”` : ''}
              </p>
            </div>
          </div>
          {typeof sourceCount === 'number' && sourceCount > 0 && (
            <span
              className="aura-fade-in rounded-full border px-2.5 py-0.5 text-xs font-medium tabular-nums"
              style={{
                borderColor: 'var(--aura-calm)',
                background: 'var(--aura-accent-soft)',
                color: 'var(--aura-calm)',
              }}
            >
              {sourceCount} source{sourceCount === 1 ? '' : 's'} found
            </span>
          )}
        </div>

        {/* Determinate stage track with continuous indeterminate shimmer sweep */}
        <div className="relative h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--aura-track)' }}>
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{ width: `${activeMeta.pct}%`, background: 'var(--aura-calm)' }}
          />
          <div
            className="aura-progress-sweep pointer-events-none absolute inset-y-0 left-0 w-1/3 rounded-full opacity-55"
            style={{ background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.65), transparent)' }}
          />
        </div>

        {/* 3-step pipeline tracker */}
        <ol className="grid grid-cols-1 gap-2 sm:grid-cols-3" aria-label="Search pipeline progress">
          {STEPS.map((s, idx) => {
            const done = idx < activeIdx;
            const current = idx === activeIdx;
            return (
              <li
                key={s.id}
                className="flex items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors duration-200"
                style={{
                  borderColor: current ? 'var(--aura-calm)' : 'var(--aura-border)',
                  background: current ? 'var(--aura-accent-soft)' : 'var(--aura-surface-elev)',
                  color: done || current ? 'var(--aura-text)' : 'var(--aura-subtle)',
                }}
              >
                <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                  {done ? (
                    <Check size={13} style={{ color: 'var(--aura-calm)' }} aria-hidden />
                  ) : current ? (
                    <Loader2 size={13} className="aura-spin" style={{ color: 'var(--aura-calm)' }} aria-hidden />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: 'var(--aura-subtle)' }} aria-hidden />
                  )}
                </span>
                <span className={current ? 'font-semibold' : 'font-medium'}>
                  {idx + 1}. {s.label}
                </span>
              </li>
            );
          })}
        </ol>
      </section>

      <WireframeCards mood={mood} />
    </div>
  );
}
