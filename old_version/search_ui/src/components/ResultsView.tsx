import { LayoutGrid, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiPost } from '../api';
import type { ProposalResponse, RerenderResponse, SearchResponse, Spec, StateSnapshot } from '../types';
import { GenUIRenderer } from './genui/GenUIRenderer';
import { ProposalBar } from './ProposalBar';
import { STATE_LABEL } from './StatePill';
import { ResultsSkeleton } from './SearchResults';

const DEV = new URLSearchParams(window.location.search).get('dev') === '1';
const COMPARE_ORDER = ['neutral', 'focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented'] as const;

export function ResultsView({ data, snap, onQuery }: {
  data: SearchResponse;
  snap: StateSnapshot | null;
  onQuery: (q: string) => void;
}) {
  const adaptive = data.adaptive && data.policy.name !== 'neutral';
  const [standard, setStandard] = useState(false);
  const [standardSpec, setStandardSpec] = useState<Spec | null>(null);
  const [loadingStd, setLoadingStd] = useState(false);
  const [compare, setCompare] = useState<Record<string, Spec> | null>(null);
  // The adapted layout on screen; accepting an offer (or undoing one) replaces it.
  const [adapted, setAdapted] = useState<{ spec: Spec; policy: string }>({ spec: data.spec, policy: data.policy.name });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setStandard(false);
    setStandardSpec(null);
    setCompare(null);
    setAdapted({ spec: data.spec, policy: data.policy.name });
  }, [data.search_id, data.spec, data.policy.name]);

  const answer = async (action: 'accept' | 'dismiss' | 'undo', proposalId?: string) => {
    setBusy(true);
    try {
      const r = await apiPost<ProposalResponse>(`/api/search/${data.search_id}/proposal`, {
        proposal_id: proposalId ?? '',
        action,
      });
      if (r.spec && r.policy) {
        setAdapted({ spec: r.spec, policy: r.policy.name });
        setStandard(false);
      }
    } catch {
      /* offer expired or was superseded; the next state push clears the bar */
    } finally {
      setBusy(false);
    }
  };

  const toggleStandard = async () => {
    if (standard) {
      setStandard(false);
      void apiPost(`/api/search/${data.search_id}/view`, { policy: adapted.policy }).catch(() => undefined);
      return;
    }
    setStandard(true);
    if (standardSpec) return;
    setLoadingStd(true);
    try {
      const r = await apiPost<RerenderResponse>(`/api/search/${data.search_id}/rerender`, { policy: 'neutral' });
      setStandardSpec(r.spec);
    } catch {
      setStandard(false);
    } finally {
      setLoadingStd(false);
    }
  };

  const loadCompare = async () => {
    const r = await apiPost<{ specs: Record<string, Spec> }>(`/api/search/${data.search_id}/compare`, {});
    setCompare(r.specs);
  };

  if (!data.stageA.claims.length) {
    return (
      <p className="text-sm" style={{ color: 'var(--aura-muted)' }}>
        No results found for “{data.query}”. Try different words.
      </p>
    );
  }

  const spec = standard ? standardSpec : adapted.spec;
  const a = data.stageA;
  return (
    <div className="flex flex-col gap-5">
      {adaptive && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2" style={{ color: 'var(--aura-muted)' }}>
            {standard ? <LayoutGrid size={15} aria-hidden /> : <Sparkles size={15} aria-hidden />}
            {standard
              ? 'Standard layout (same for everyone)'
              : `Laid out for: ${STATE_LABEL[adapted.policy as keyof typeof STATE_LABEL] ?? data.policy.label}`}
          </span>
          <button
            type="button"
            onClick={toggleStandard}
            aria-pressed={standard}
            className="aura-target rounded-lg border text-sm hover:border-[var(--aura-calm)]"
            style={{ borderColor: 'var(--aura-border)' }}
          >
            {standard ? 'Back to adapted view' : 'Standard view'}
          </button>
        </div>
      )}

      {adaptive && !standard && (
        <ProposalBar antic={snap?.anticipation} searchId={data.search_id} busy={busy} onAnswer={answer} />
      )}

      {loadingStd || !spec ? <ResultsSkeleton /> : <GenUIRenderer data={data} spec={spec} onQuery={onQuery} />}

      <footer className="text-xs" style={{ color: 'var(--aura-muted)' }}>
        {sourceLabel(data.provider)} · facts by {a.used_llm ? a.model : 'extractive fallback'}
        {spec && ` · layout by ${spec.source === 'llm' ? spec.model : 'template'}`}
        {' · '}
        {(data.timings_ms.total / 1000).toFixed(1)} s
        {spec?.report?.ungrounded_before_fix ? ` · ${spec.report.ungrounded_before_fix} unsupported phrase(s) removed` : ''}
        {[data.provider_note, a.note, spec?.note].filter(Boolean).length > 0 && (
          <span className="block pt-1">{[data.provider_note, a.note, spec?.note].filter(Boolean).join(' · ')}</span>
        )}
      </footer>

      {DEV && (
        <section className="border-t pt-4" style={{ borderColor: 'var(--aura-border)' }}>
          <button type="button" onClick={loadCompare} className="aura-target rounded-lg border text-sm" style={{ borderColor: 'var(--aura-border)' }}>
            Compare this search across all states (dev)
          </button>
          {compare && (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              {COMPARE_ORDER.map((n) => compare[n] && (
                <div key={n} className="rounded-xl border p-3" style={{ borderColor: 'var(--aura-border)' }}>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-calm)' }}>
                    {n === 'neutral' ? 'Standard (prompt-only)' : STATE_LABEL[n]} · {compare[n].topology} · {compare[n].source}
                  </div>
                  <div className="max-h-[28rem] overflow-auto text-[0.85em]">
                    <GenUIRenderer data={data} spec={compare[n]} onQuery={onQuery} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function sourceLabel(p: string) {
  return p === 'tavily' ? 'Web results (Tavily)' : p === 'wikipedia' ? 'Wikipedia results' : p === 'fixture' ? 'Recorded study results' : p;
}
