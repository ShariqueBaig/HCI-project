import { Brain, Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { apiGet, apiPost, TOKEN } from './api';
import { ResultsView } from './components/ResultsView';
import { ResultsSkeleton } from './components/SearchResults';
import { CameraToggle } from './components/CameraToggle';
import { StatePill } from './components/StatePill';
import { StressChip } from './components/StressChip';
import { StudyPanel } from './components/study/StudyPanel';
import { XaiPanel } from './components/XaiPanel';
import { useBehaviourSignals } from './hooks/useBehaviourSignals';
import { useTypingDynamics } from './hooks/useTypingDynamics';
import { useAuraState } from './hooks/useAuraState';
import type { FixtureInfo, LiveState, RerenderResponse, SearchResponse, StateSnapshot } from './types';

export default function App() {
  const { live, snap, status } = useAuraState();
  const control = live?.condition === 'control';

  const [query, setQuery] = useState('');
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fixtures, setFixtures] = useState<FixtureInfo[]>([]);
  const [showXai, setShowXai] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const reqId = useRef(0);

  useTypingDynamics(inputRef, status !== 'unauthorized');
  useBehaviourSignals(status !== 'unauthorized');
  usePolicyTokens(snap);
  useSimulatedRelayout(snap, result, setResult);

  useEffect(() => {
    inputRef.current?.focus();
    if (TOKEN) {
      apiGet<{ fixtures: FixtureInfo[] }>('/api/fixtures')
        .then((r) => setFixtures(r.fixtures))
        .catch(() => setFixtures([]));
    }
  }, []);

  const run = async (q: string) => {
    const text = q.trim();
    if (!text || loading) return;
    const id = ++reqId.current;
    setQuery(text);
    setLoading(true);
    setError(null);
    try {
      const r = await apiPost<SearchResponse>('/api/search', { query: text });
      if (id === reqId.current) setResult(r);
    } catch (e) {
      if (id === reqId.current) setError((e as Error).message);
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header
        className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-6"
        style={{ borderColor: 'var(--aura-border)' }}
      >
        <div className="flex items-baseline gap-3">
          <h1 className="text-lg font-semibold tracking-tight">Aura Search</h1>
          <span className="text-xs" style={{ color: 'var(--aura-muted)' }}>
            {control ? 'Control (A): prompt-only' : 'Active (B): adapts to your state'}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {status !== 'unauthorized' && <CameraToggle face={snap?.camera?.face} />}
          {status !== 'unauthorized' && (
            <button
              type="button"
              onClick={() => setShowXai((v) => !v)}
              aria-pressed={showXai}
              aria-controls="xai-panel"
              title="Show how the model reads your mood, step by step"
              className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm hover:border-[var(--aura-calm)]"
              style={{
                borderColor: showXai ? 'var(--aura-calm)' : 'var(--aura-border)',
                background: 'var(--aura-surface)',
                color: showXai ? 'var(--aura-calm)' : undefined,
              }}
            >
              <Brain size={14} aria-hidden /> Explain{snap?.simulation ? ' · sim' : ''}
            </button>
          )}
          <StatePill snap={snap} />
          <StressChip live={live} status={status} />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-8">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void run(query);
          }}
        >
          <label className="sr-only" htmlFor="q">Search</label>
          <div
            className="flex flex-1 items-center gap-2 rounded-xl border px-4 focus-within:border-[var(--aura-calm)]"
            style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
          >
            <Search size={18} style={{ color: 'var(--aura-muted)' }} aria-hidden />
            <input
              id="q"
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={300}
              autoComplete="off"
              spellCheck
              className="h-12 flex-1 bg-transparent outline-none"
              placeholder="Ask anything"
              disabled={status === 'unauthorized'}
            />
          </div>
          <button
            type="submit"
            className="aura-target rounded-xl px-5 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
            disabled={loading || !query.trim() || status === 'unauthorized'}
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>

        {status !== 'unauthorized' && showXai && <XaiPanel snap={snap} onClose={() => setShowXai(false)} />}

        <StudyPanel
          recording={Boolean(live?.recording)}
          onTaskStart={() => {
            setResult(null);
            setQuery('');
            inputRef.current?.focus();
          }}
        />

        {status === 'unauthorized' && (
          <p className="rounded-lg border p-4 text-sm" style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}>
            This window needs to be opened from Aura UI (Search button, tray menu, or Ctrl+Shift+Space).
          </p>
        )}

        {!result && !loading && !live?.recording && fixtures.length > 0 && (
          <section aria-label="Study tasks" className="flex flex-wrap gap-2">
            {fixtures.map((f) => (
              <button
                key={f.query}
                type="button"
                title={f.task || 'Recorded results'}
                onClick={() => void run(f.query)}
                className="rounded-full border px-3 py-1 text-sm hover:border-[var(--aura-calm)]"
                style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}
              >
                {f.query}
              </button>
            ))}
          </section>
        )}

        {error && (
          <p role="alert" className="rounded-lg border p-4 text-sm" style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}>
            Search failed: {error}
          </p>
        )}

        {loading ? <ResultsSkeleton /> : result && <ResultsView data={result} snap={snap} onQuery={(q) => void run(q)} />}

        {live && <LiveSignals live={live} />}
      </main>
    </div>
  );
}

/** While a mood is simulated, re-lay out the results on screen for the mood the
 *  model commits to (same facts, Stage B only), so the effect is visible at once. */
function useSimulatedRelayout(
  snap: StateSnapshot | null,
  result: SearchResponse | null,
  setResult: (r: SearchResponse) => void,
) {
  const simState = snap?.simulation?.state;
  const committed = snap?.fused.committed_state;
  const asked = useRef('');
  useEffect(() => {
    if (!simState || !committed || !result || !result.adaptive || committed !== simState) return;
    if (result.policy.name === committed) return;
    const key = `${result.search_id}:${committed}`;
    if (asked.current === key) return;
    asked.current = key;
    apiPost<RerenderResponse>(`/api/search/${result.search_id}/rerender`, { policy: committed })
      .then((r) => setResult({ ...result, policy: r.policy, spec: r.spec }))
      .catch(() => undefined);
  }, [simState, committed, result, setResult]);
}

/** Apply the active policy's Fitts's-law / readability tokens as CSS variables. */
function usePolicyTokens(snap: StateSnapshot | null) {
  const tokens = snap?.adaptive ? snap.policy.tokens : null;
  const key = tokens ? `${tokens.targetScale}|${tokens.typographyScale}|${tokens.lineHeight}` : 'neutral';
  useEffect(() => {
    const root = document.documentElement.style;
    root.setProperty('--aura-target-scale', String(tokens?.targetScale ?? 1));
    root.setProperty('--aura-type-scale', String(tokens?.typographyScale ?? 1));
    root.setProperty('--aura-line-height', String(tokens?.lineHeight ?? 1.55));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

function LiveSignals({ live }: { live: LiveState }) {
  const pct = (x?: number) => (x === undefined ? undefined : `${Math.round(x * 100)}%`);
  return (
    <details className="mt-auto rounded-xl border px-5 py-3 text-sm" style={{ borderColor: 'var(--aura-border)' }}>
      <summary className="cursor-pointer select-none" style={{ color: 'var(--aura-muted)' }}>
        Live signals from Aura
      </summary>
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
        <Stat k="Keys / s" v={live.features.keys_per_second?.toFixed(1)} />
        <Stat k="Error rate" v={pct(live.features.error_rate)} />
        <Stat k="Flight CoV" v={live.features.cov?.toFixed(2)} />
        <Stat k="Mouse px (5 s)" v={live.features.mouse_distance?.toFixed(0)} />
        <Stat k="Calibrated" v={live.calibrated ? 'yes' : 'no'} />
        <Stat k="Focus blocking" v={live.focus_blocking ? 'on' : 'off'} />
        <Stat k="Breathing guide" v={live.breathing_active ? 'open' : 'closed'} />
        <Stat k="Recording" v={live.recording ? 'yes' : 'no'} />
        <Stat k="Held notifications" v={String(live.held_count)} />
      </div>
    </details>
  );
}

function Stat({ k, v }: { k: string; v?: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span style={{ color: 'var(--aura-muted)' }}>{k}</span>
      <span className="tabular-nums">{v ?? '--'}</span>
    </div>
  );
}
