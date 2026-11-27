import { ExternalLink, Pause, Play, Volume2 } from 'lucide-react';
import { createContext, useContext, useEffect, useState } from 'react';
import type { Claim, SourceItem, StageA } from '../../types';

/* Facts reach widgets only by reference (claim ids, step indices, source ids)
   and are rendered from Stage A's own wording -- the layout can change, the
   facts cannot (backend/search/validator.py). */

export interface GenCtx {
  stageA: StageA;
  claims: Record<string, Claim>;
  sources: Record<string, SourceItem>;
  sourceOrder: string[];
  focusSource: string | null;
  onCite: (sourceId: string) => void;
  onQuery: (q: string) => void;
  answerText: string;
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

/** Citation chips: claim ids -> the sources those claims cite, numbered like the source list. */
export function Cites({ claimIds = [], sourceIds = [] }: { claimIds?: string[]; sourceIds?: string[] }) {
  const g = useGen();
  const ids = Array.from(new Set([...sourceIds, ...claimIds.flatMap((c) => g.claims[c]?.source_ids ?? [])]))
    .filter((s) => g.sources[s])
    .sort((a, b) => g.sourceOrder.indexOf(a) - g.sourceOrder.indexOf(b));
  if (!ids.length) return null;
  return (
    <span className="ml-1 inline-flex gap-1 align-baseline">
      {ids.map((id) => (
        <button
          key={id}
          type="button"
          onClick={() => g.onCite(id)}
          className="rounded px-1.5 text-[11px] font-medium tabular-nums hover:brightness-125"
          style={{ background: 'var(--aura-faint)', color: 'var(--aura-text)' }}
          aria-label={`Show source ${id.slice(1)}`}
        >
          {id.slice(1)}
        </button>
      ))}
    </span>
  );
}

export function AnswerCard({ text, claim_ids, source_ids }: { text: string; claim_ids: string[]; source_ids: string[] }) {
  return (
    <section aria-label="Answer" className="rounded-xl border p-5" style={card}>
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
      <ul className="aura-readable space-y-2">
        {claim_ids.map((id) => {
          const c = g.claims[id];
          if (!c) return null;
          return (
            <li key={id} className="flex gap-3">
              <span
                className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: c.importance === 3 ? 'var(--aura-calm)' : 'var(--aura-faint)' }}
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
  const [done, setDone] = useState<Set<number>>(new Set());
  if (kind === 'facts') {
    // not a how-to query: these are the key facts, so nothing to tick off
    return (
      <section aria-label={title || 'Key points'}>
        <Heading>{title || 'Key points'}</Heading>
        <ol className="aura-readable space-y-2">
          {steps.map((s, i) => (
            <li key={i} className="flex items-start gap-3 rounded-lg border px-3 py-2" style={card}>
              <span className="tabular-nums" style={muted}>{i + 1}.</span>
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
  const toggle = (i: number) =>
    setDone((d) => {
      const n = new Set(d);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });
  return (
    <section aria-label={title || 'Steps'}>
      <Heading>{title || 'Steps'}</Heading>
      <ol className="aura-readable space-y-2">
        {steps.map((s, i) => (
          <li key={i}>
            <label className="aura-target flex cursor-pointer items-start gap-3 rounded-lg border" style={card}>
              <input
                type="checkbox"
                checked={done.has(i)}
                onChange={() => toggle(i)}
                className="mt-[0.45em] h-4 w-4 shrink-0 accent-[var(--aura-calm)]"
              />
              <span className="py-1.5" style={done.has(i) ? { ...muted, textDecoration: 'line-through' } : undefined}>
                <span className="mr-1 tabular-nums" style={muted}>{i + 1}.</span>
                {s.text}
                <Cites claimIds={s.claim_ids} />
              </span>
            </label>
          </li>
        ))}
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
          <thead style={{ background: 'var(--aura-surface)' }}>
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

function Chips({ items, onPick, label }: { items: string[]; onPick?: (s: string) => void; label: string }) {
  return (
    <div className="flex flex-wrap gap-2" role="list" aria-label={label}>
      {items.map((f) => (
        <button
          key={f}
          type="button"
          role="listitem"
          onClick={() => onPick?.(f)}
          className="aura-target rounded-full border text-sm hover:border-[var(--aura-calm)]"
          style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-text)' }}
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
      <Chips items={facets} label="Facets" onPick={(f) => g.onQuery(`${g.stageA.key_entities[0] ?? ''} ${f}`.trim())} />
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
    <nav aria-label="Your recent searches" className="text-sm">
      <span style={muted}>Where you are: </span>
      {queries.map((q, i) => (
        <span key={i}>
          {i > 0 && <span style={muted}> › </span>}
          {i === queries.length - 1 ? (
            <span className="font-medium">{q}</span>
          ) : (
            <button type="button" className="underline-offset-2 hover:underline" style={muted} onClick={() => g.onQuery(q)}>
              {q}
            </button>
          )}
        </span>
      ))}
    </nav>
  );
}

/** One physiological sigh (inhale, top-up, long exhale), offered, never forced. */
export function BreathingNudge() {
  const [phase, setPhase] = useState<'idle' | 'in' | 'top' | 'out'>('idle');
  useEffect(() => {
    if (phase === 'idle') return;
    const next = { in: ['top', 1500], top: ['out', 500], out: ['idle', 6000] } as const;
    const [to, ms] = next[phase];
    const t = window.setTimeout(() => setPhase(to), ms);
    return () => window.clearTimeout(t);
  }, [phase]);
  const scale = phase === 'in' ? 1 : phase === 'top' ? 1.12 : 0.55;
  const dur = phase === 'in' ? 1500 : phase === 'top' ? 500 : 6000;
  return (
    <section aria-label="Breathing pause" className="flex items-center gap-4 rounded-xl border p-4" style={card}>
      <div className="flex h-12 w-12 shrink-0 items-center justify-center" aria-hidden>
        <div
          className="h-12 w-12 rounded-full"
          style={{
            background: 'var(--aura-calm)',
            opacity: 0.35,
            transform: `scale(${phase === 'idle' ? 0.55 : scale})`,
            transition: `transform ${dur}ms ease-in-out`,
          }}
        />
      </div>
      <div className="flex-1 text-sm">
        <p>{phase === 'idle' ? 'One slow breath before you decide?' : phase === 'out' ? 'Long breath out…' : 'Breathe in…'}</p>
      </div>
      {phase === 'idle' && (
        <button type="button" onClick={() => setPhase('in')} className="aura-target rounded-lg border text-sm" style={{ borderColor: 'var(--aura-border)' }}>
          Start
        </button>
      )}
    </section>
  );
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
  return (
    <button
      type="button"
      onClick={toggle}
      className="aura-target flex w-fit items-center gap-2 rounded-lg border text-sm"
      style={{ borderColor: 'var(--aura-border)' }}
    >
      {speaking ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}
      <Volume2 size={16} aria-hidden />
      {speaking ? 'Stop reading' : 'Read the answer aloud'}
    </button>
  );
}
