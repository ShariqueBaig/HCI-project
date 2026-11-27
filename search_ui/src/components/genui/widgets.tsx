import { Compass, ExternalLink, Pause, Play, Sparkles, Volume2 } from 'lucide-react';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { Claim, SourceItem, StageA, ViewPolicyName } from '../../types';
import { UnifiedBreathing } from '../UnifiedBreathing';

export interface GenCtx {
  searchId: string;
  policyName: ViewPolicyName;
  stageA: StageA;
  claims: Record<string, Claim>;
  sources: Record<string, SourceItem>;
  sourceOrder: string[];
  focusSource: string | null;
  onCite: (sourceId: string) => void;
  onQuery: (q: string) => void;
  answerText: string;
  checkedSteps: Set<number>;
  onToggleStep: (index: number) => void;
}

export const Ctx = createContext<GenCtx | null>(null);
const useGen = () => useContext(Ctx)!;

const muted = { color: 'var(--aura-muted)' };
const card = { borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' };

export function Heading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider" style={muted}>
      {children}
    </h2>
  );
}

function domain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

/** Accessible citation chips (>=24x24px) with inline hover/focus preview popover. */
export function Cites({ claimIds = [], sourceIds = [] }: { claimIds?: string[]; sourceIds?: string[] }) {
  const g = useGen();
  const ids = Array.from(new Set([...sourceIds, ...claimIds.flatMap((c) => g.claims[c]?.source_ids ?? [])]))
    .filter((s) => g.sources[s])
    .sort((a, b) => g.sourceOrder.indexOf(a) - g.sourceOrder.indexOf(b));
  if (!ids.length) return null;
  return (
    <span className="ml-1.5 inline-flex flex-wrap gap-1 align-middle">
      {ids.map((id) => (
        <CiteBadge key={id} id={id} source={g.sources[id]} onJump={() => g.onCite(id)} />
      ))}
    </span>
  );
}

function CiteBadge({ id, source, onJump }: { id: string; source: SourceItem; onJump: () => void }) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<number | undefined>(undefined);
  const wrapRef = useRef<HTMLSpanElement>(null);

  const show = () => {
    window.clearTimeout(closeTimer.current);
    setOpen(true);
  };
  const hideSoon = () => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };

  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <span
      ref={wrapRef}
      className="relative inline-block"
      onMouseEnter={show}
      onMouseLeave={hideSoon}
      onFocus={show}
      onBlur={(e) => {
        if (!wrapRef.current?.contains(e.relatedTarget as Node)) hideSoon();
      }}
    >
      <button
        type="button"
        onClick={onJump}
        aria-expanded={open}
        className="aura-cite-target inline-flex items-center justify-center rounded border text-xs font-semibold tabular-nums transition-colors duration-150 hover:border-[var(--aura-calm)]"
        style={{
          borderColor: open ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
          background: open ? 'var(--aura-accent-soft)' : 'var(--aura-surface-elev)',
          color: 'var(--aura-text)',
        }}
        aria-label={`Source ${id.slice(1)}: ${source.title}`}
      >
        {id.slice(1)}
      </button>

      {open && (
        <span
          role="dialog"
          aria-label={`Citation ${id.slice(1)} preview`}
          className="aura-scale-in origin-bottom-left absolute bottom-full left-0 z-30 mb-2 block w-72 rounded-xl border p-3 text-left text-xs shadow-2xl sm:w-80"
          style={{
            borderColor: 'var(--aura-border-interactive)',
            background: 'var(--aura-surface)',
            color: 'var(--aura-text)',
          }}
        >
          <span className="block font-semibold" style={{ color: 'var(--aura-calm)' }}>
            [{id.slice(1)}] {domain(source.url)}
          </span>
          <span className="mt-0.5 block font-semibold leading-snug">{source.title}</span>
          {source.snippet && (
            <span className="mt-1 line-clamp-3 block leading-relaxed" style={{ color: 'var(--aura-muted)' }}>
              {source.snippet}
            </span>
          )}
          <span className="mt-2.5 flex items-center justify-between gap-2 border-t pt-2" style={{ borderColor: 'var(--aura-border)' }}>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              data-source-link
              className="inline-flex items-center gap-1 font-medium underline underline-offset-2"
              style={{ color: 'var(--aura-calm)' }}
            >
              Open source <ExternalLink size={11} aria-hidden />
            </a>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onJump();
              }}
              className="rounded px-2 py-1 text-[11px] hover:bg-[var(--aura-surface-elev)]"
              style={{ color: 'var(--aura-muted)' }}
            >
              View in list ↓
            </button>
          </span>
        </span>
      )}
    </span>
  );
}

export function AnswerCard({ text, claim_ids, source_ids }: { text: string; claim_ids: string[]; source_ids: string[] }) {
  const g = useGen();
  const p = g.policyName;
  const isOverwhelmed = p === 'overwhelmed';
  const isFatigued = p === 'fatigued';
  const isEnergized = p === 'energized';
  const isDisoriented = p === 'disoriented';

  const eyebrow = isOverwhelmed
    ? 'Start here · 1 clear takeaway'
    : isFatigued
    ? 'Easy-read summary'
    : isEnergized
    ? 'Explore & compare'
    : isDisoriented
    ? 'Quick summary'
    : null;

  return (
    <section
      aria-label="Answer"
      className={`rounded-xl border transition-colors ${isOverwhelmed || isFatigued ? 'p-6' : 'p-5'} ${isOverwhelmed ? 'border-l-4' : ''}`}
      style={{
        borderColor: isOverwhelmed || isEnergized ? 'var(--aura-calm)' : 'var(--aura-border)',
        background: isOverwhelmed || isFatigued ? 'var(--aura-accent-soft)' : 'var(--aura-surface)',
        borderTopWidth: isEnergized ? '3px' : undefined,
      }}
    >
      {eyebrow && (
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-calm)' }}>
          {isEnergized && <Sparkles size={12} aria-hidden />}
          {eyebrow}
        </p>
      )}
      <p className="aura-readable text-[1.05rem]">
        {text}
        <Cites claimIds={claim_ids} sourceIds={source_ids} />
      </p>
    </section>
  );
}

export function KeyFactsList({ claim_ids, title }: { claim_ids: string[]; title?: string }) {
  const g = useGen();
  return (
    <section aria-label={title || 'Key facts'}>
      <Heading>{title || 'Key facts'}</Heading>
      <ul className="aura-readable space-y-2.5">
        {claim_ids.map((id) => {
          const c = g.claims[id];
          if (!c) return null;
          return (
            <li key={id} className="flex gap-3">
              <span
                className="mt-2.5 h-2 w-2 shrink-0 rounded-full"
                style={{ background: c.importance === 3 ? 'var(--aura-calm)' : 'var(--aura-subtle)' }}
                aria-hidden
              />
              <span>
                {c.text}
                <Cites claimIds={[id]} />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function GuidedSteps({ steps, title, kind }: {
  steps: { text: string; claim_ids: string[] }[];
  title?: string;
  kind?: 'steps' | 'facts';
}) {
  const g = useGen();
  if (kind === 'facts') {
    return (
      <section aria-label={title || 'Key points'}>
        <Heading>{title || 'Key points'}</Heading>
        <ol className="aura-readable space-y-2">
          {steps.map((s, i) => (
            <li key={i} className="flex items-start gap-3 rounded-lg border px-3 py-2.5" style={card}>
              <span className="tabular-nums font-medium" style={muted}>{i + 1}.</span>
              <span>
                {s.text}
                <Cites claimIds={s.claim_ids} />
              </span>
            </li>
          ))}
        </ol>
      </section>
    );
  }
  return (
    <section aria-label={title || 'Steps'}>
      <Heading>{title || 'Steps'}</Heading>
      <ol className="aura-readable space-y-2">
        {steps.map((s, i) => {
          const isDone = g.checkedSteps.has(i);
          return (
            <li key={i}>
              <label
                className="aura-target flex cursor-pointer items-start gap-3 rounded-lg border py-1.5"
                style={{ ...card, borderColor: 'var(--aura-border-interactive)' }}
              >
                <input
                  type="checkbox"
                  checked={isDone}
                  onChange={() => g.onToggleStep(i)}
                  className="mt-1 h-4 w-4 shrink-0 accent-[var(--aura-calm)]"
                />
                <span style={isDone ? { ...muted, textDecoration: 'line-through' } : undefined}>
                  <span className="mr-1 tabular-nums" style={muted}>{i + 1}.</span>
                  {s.text}
                  <Cites claimIds={s.claim_ids} />
                </span>
              </label>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function ComparisonTable({ columns, rows, claim_ids }: {
  columns: string[];
  rows: { axis: string; cells: string[] }[];
  claim_ids: string[];
}) {
  return (
    <section aria-label="Comparison">
      <Heading>
        Comparison <Cites claimIds={claim_ids} />
      </Heading>
      <div className="overflow-x-auto rounded-xl border" style={{ borderColor: 'var(--aura-border)' }}>
        <table className="aura-readable w-full text-left text-sm">
          <thead style={{ background: 'var(--aura-accent-soft)' }}>
            <tr>
              <th className="px-3 py-2 font-medium" style={muted} scope="col" />
              {columns.map((c) => (
                <th key={c} className="px-3 py-2 font-semibold" scope="col">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.axis} className="border-t" style={{ borderColor: 'var(--aura-border)' }}>
                <th className="px-3 py-2 font-medium" style={muted} scope="row">{r.axis}</th>
                {r.cells.map((c, i) => <td key={i} className="px-3 py-2">{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ProsCons({ subject, pros, cons }: { subject?: string; pros: string[]; cons: string[] }) {
  const g = useGen();
  const col = (title: string, ids: string[], color: string) => (
    <div className="flex-1 rounded-xl border p-4" style={card}>
      <h3 className="mb-2 text-sm font-semibold" style={{ color }}>{title}</h3>
      <ul className="aura-readable space-y-1.5 text-sm">
        {ids.map((id) => g.claims[id] && (
          <li key={id}>{g.claims[id].text}<Cites claimIds={[id]} /></li>
        ))}
      </ul>
    </div>
  );
  return (
    <section aria-label="Pros and cons">
      <Heading>{subject ? `${subject}: pros and cons` : 'Pros and cons'}</Heading>
      <div className="flex flex-col gap-3 sm:flex-row">
        {pros.length > 0 && col('Pros', pros, 'var(--aura-calm)')}
        {cons.length > 0 && col('Cons', cons, 'var(--aura-elev)')}
      </div>
    </section>
  );
}

export function Timeline({ items }: { items: { label: string; claim_id: string }[] }) {
  const g = useGen();
  return (
    <section aria-label="Timeline">
      <Heading>Timeline</Heading>
      <ol className="aura-readable space-y-3 border-l pl-4" style={{ borderColor: 'var(--aura-border)' }}>
        {items.map((it) => g.claims[it.claim_id] && (
          <li key={it.claim_id}>
            {it.label && <div className="text-xs font-semibold" style={{ color: 'var(--aura-calm)' }}>{it.label}</div>}
            {g.claims[it.claim_id].text}
            <Cites claimIds={[it.claim_id]} />
          </li>
        ))}
      </ol>
    </section>
  );
}

export function SourceList({ source_ids, compact }: { source_ids: string[]; compact?: boolean }) {
  const g = useGen();
  return (
    <section aria-label="Sources">
      <Heading>Sources</Heading>
      <ol className="space-y-2">
        {source_ids.map((id) => {
          const s = g.sources[id];
          if (!s) return null;
          return (
            <li
              key={id}
              id={`src-${id}`}
              className={`rounded-lg border transition-colors ${compact ? 'px-3 py-2' : 'p-3'}`}
              style={{ ...card, borderColor: g.focusSource === id ? 'var(--aura-calm)' : 'var(--aura-border)' }}
            >
              <a href={s.url} target="_blank" rel="noopener noreferrer" data-source-link className="flex items-baseline gap-2 font-medium hover:underline">
                <span className="text-xs tabular-nums" style={muted}>{id.slice(1)}</span>
                <span className={compact ? 'text-sm' : ''}>{s.title}</span>
                <ExternalLink size={12} className="shrink-0 self-center" style={muted} aria-hidden />
              </a>
              <div className="mt-0.5 text-xs" style={{ color: 'var(--aura-calm)' }}>{domain(s.url)}</div>
              {!compact && <p className="mt-1 line-clamp-2 text-sm" style={muted}>{s.snippet}</p>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Chips({ items, onPick, label, accent = false }: { items: string[]; onPick?: (s: string) => void; label: string; accent?: boolean }) {
  return (
    <div className="flex flex-wrap gap-2" role="list" aria-label={label}>
      {items.map((f) => (
        <button
          key={f}
          type="button"
          role="listitem"
          onClick={() => onPick?.(f)}
          className="aura-target rounded-full border text-sm transition-colors duration-150 hover:border-[var(--aura-calm)]"
          style={{
            borderColor: accent ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
            color: 'var(--aura-text)',
            background: accent ? 'var(--aura-accent-soft)' : 'var(--aura-surface)',
          }}
        >
          {f}
        </button>
      ))}
    </div>
  );
}

export function FacetChips({ facets }: { facets: string[] }) {
  const g = useGen();
  return (
    <section aria-label="Explore by">
      <Heading>Explore by</Heading>
      <Chips items={facets} label="Facets" accent onPick={(f) => g.onQuery(`${g.stageA.key_entities[0] ?? ''} ${f}`.trim())} />
    </section>
  );
}

export function FollowUpChips({ queries }: { queries: string[] }) {
  const g = useGen();
  return (
    <section aria-label="Search next">
      <Heading>Search next</Heading>
      <Chips items={queries} label="Follow-up searches" onPick={g.onQuery} />
    </section>
  );
}

export function ClarifierChips({ question, options }: { question: string; options: string[] }) {
  const g = useGen();
  return (
    <section aria-label="Narrow it down" className="rounded-xl border p-4" style={card}>
      <p className="aura-readable mb-3 font-medium">{question}</p>
      <Chips items={options} label="Options" onPick={(o) => g.onQuery(`${g.stageA.key_entities[0] ?? ''} ${o}`.trim())} />
    </section>
  );
}

export function QueryTrail({ queries }: { queries: string[] }) {
  const g = useGen();
  if (!queries.length) return null;
  return (
    <nav
      aria-label="Your recent searches"
      className="flex flex-wrap items-center gap-1.5 rounded-xl border px-4 py-3 text-sm"
      style={{ borderColor: 'var(--aura-calm)', background: 'var(--aura-accent-soft)' }}
    >
      <Compass size={15} style={{ color: 'var(--aura-calm)' }} aria-hidden />
      <span className="font-medium" style={{ color: 'var(--aura-calm)' }}>Where you left off:</span>
      {queries.map((q, i) => (
        <span key={i}>
          {i > 0 && <span style={muted}> › </span>}
          {i === queries.length - 1 ? (
            <span className="font-semibold">{q}</span>
          ) : (
            <button type="button" className="underline underline-offset-2 hover:opacity-80" style={muted} onClick={() => g.onQuery(q)}>
              {q}
            </button>
          )}
        </span>
      ))}
    </nav>
  );
}

export function BreathingNudge() {
  return <UnifiedBreathing inline defaultCycles={1} />;
}

export function ReadAloud() {
  const g = useGen();
  const [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  if (!supported) return null;
  const toggle = () => {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const u = new SpeechSynthesisUtterance(g.answerText);
    u.rate = 0.95;
    u.onend = () => setSpeaking(false);
    window.speechSynthesis.speak(u);
    setSpeaking(true);
  };
  const isFatigued = g.policyName === 'fatigued';
  return (
    <button
      type="button"
      onClick={toggle}
      className={`aura-target flex items-center gap-2.5 rounded-xl border text-sm font-medium hover:brightness-110 ${isFatigued ? 'w-full justify-center py-3' : 'w-fit'}`}
      style={{
        borderColor: 'var(--aura-calm)',
        background: isFatigued ? 'var(--aura-accent-soft)' : 'var(--aura-surface)',
        color: isFatigued ? 'var(--aura-text)' : 'var(--aura-calm)',
      }}
    >
      {speaking ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}
      <Volume2 size={16} aria-hidden />
      {speaking ? 'Stop reading' : 'Listen to the answer (Read aloud)'}
    </button>
  );
}
