import { LayoutGrid, Loader2, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiPost } from '../api';
import { VIEW_MODES } from '../modes';
import type {
  ProposalResponse,
  RerenderResponse,
  SearchResponse,
  Spec,
  StateSnapshot,
  StreamStageAPayload,
  ThemeId,
  ViewPolicyName,
} from '../types';
import { GenUIRenderer } from './genui/GenUIRenderer';
import { ProposalBar } from './ProposalBar';
import { ResultsSkeleton } from './SearchResults';

const DEV = new URLSearchParams(window.location.search).get('dev') === '1';
const COMPARE_ORDER = ['neutral', 'focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented'] as const;

export function ResultsView({
  data,
  partialStageA,
  snap,
  blinded,
  labUnlocked,
  theme,
  checkedStepsMap,
  onToggleStep,
  onQuery,
  onPolicyApplied,
  onStandardChange,
}: {
  data: SearchResponse | null;
  partialStageA?: StreamStageAPayload | null;
  snap: StateSnapshot | null;
  blinded: boolean;
  labUnlocked: boolean;
  theme: ThemeId;
  checkedStepsMap: Record<string, number[]>;
  onToggleStep: (searchId: string, index: number) => void;
  onQuery: (q: string) => void;
  onPolicyApplied?: (policyName: ViewPolicyName) => void;
  onStandardChange?: (standard: boolean) => void;
}) {
  const [standard, setStandard] = useState(false);
  const [standardSpec, setStandardSpec] = useState<Spec | null>(null);
  const [loadingStd, setLoadingStd] = useState(false);
  const [compare, setCompare] = useState<Record<string, Spec> | null>(null);
  const [adapted, setAdapted] = useState<{ spec: Spec; policy: string } | null>(
    data ? { spec: data.spec, policy: data.policy.name } : null,
  );
  const [busy, setBusy] = useState(false);
  const [proposalErr, setProposalErr] = useState<string | null>(null);

  useEffect(() => {
    onStandardChange?.(standard);
  }, [standard, onStandardChange]);

  useEffect(() => () => {
    onStandardChange?.(false);
  }, [onStandardChange]);

  useEffect(() => {
    setStandard(false);
    setStandardSpec(null);
    setCompare(null);
    setProposalErr(null);
    if (data) {
      setAdapted({ spec: data.spec, policy: data.policy.name });
    } else {
      setAdapted(null);
    }
  }, [data?.search_id, data?.spec, data?.policy.name]);

  // Progressive preview while Stage B is still composing
  if (!data && partialStageA) {
    const partialMood = (partialStageA.policy?.name as ViewPolicyName) || 'neutral';
    return (
      <div className="aura-fade-up flex flex-col gap-5" aria-busy="true">
        <div className="rounded-xl border p-5" style={{ borderColor: 'var(--aura-calm)', background: 'var(--aura-surface)' }}>
          <div className="mb-2 flex items-center gap-2 text-xs font-medium" style={{ color: 'var(--aura-calm)' }}>
            <Loader2 size={13} className="aura-spin" aria-hidden /> Cited facts ready · tailoring layout…
          </div>
          <p className="aura-readable text-[1.05rem]">{partialStageA.stageA.tldr}</p>
        </div>
        {partialStageA.sources.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {partialStageA.sources.slice(0, 4).map((s) => (
              <div key={s.id} className="aura-fade-in rounded-lg border px-3 py-2 text-xs" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}>
                <span className="font-medium">{s.title}</span>
              </div>
            ))}
          </div>
        )}
        <ResultsSkeleton
          compact
          stage="composing"
          message="Assembling tailored layout…"
          mood={partialMood}
        />
      </div>
    );
  }

  if (!data || !adapted) return null;

  if (!data.stageA.claims.length) {
    return (
      <p className="text-sm" style={{ color: 'var(--aura-muted)' }}>
        No results found for “{data.query}”. Try different words.
      </p>
    );
  }

  const adaptive = data.adaptive && data.policy.name !== 'neutral';

  const answer = async (action: 'accept' | 'dismiss' | 'undo', proposalId?: string) => {
    setBusy(true);
    setProposalErr(null);
    try {
      const r = await apiPost<ProposalResponse>(`/api/search/${data.search_id}/proposal`, {
        proposal_id: proposalId ?? '',
        action,
      });
      if (r.spec && r.policy) {
        setAdapted({ spec: r.spec, policy: r.policy.name });
        setStandard(false);
        onPolicyApplied?.(r.policy.name);
      }
    } catch (e) {
      setProposalErr((e as Error).message || 'Could not update layout.');
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

  const spec = standard ? standardSpec : adapted.spec;
  const a = data.stageA;
  const activeModeMeta = VIEW_MODES[(adapted.policy as ViewPolicyName)] ?? VIEW_MODES.neutral;
  const checkedSet = new Set(checkedStepsMap[data.search_id] ?? []);

  return (
    <div
      key={`${data.search_id}-${adapted.policy}-${standard ? 'std' : 'adp'}`}
      className="aura-fade-up flex flex-col gap-5"
    >
      {adaptive && !blinded && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2" style={{ color: 'var(--aura-muted)' }}>
            {standard ? <LayoutGrid size={15} aria-hidden /> : <Sparkles size={15} aria-hidden />}
            {standard ? 'Standard View' : `${activeModeMeta.name}`}
          </span>
          <button
            type="button"
            onClick={toggleStandard}
            aria-pressed={standard}
            className="aura-target rounded-lg border text-sm hover:border-[var(--aura-calm)]"
            style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-surface)' }}
          >
            {standard ? 'Back to tailored view' : 'Standard view'}
          </button>
        </div>
      )}

      {adaptive && !standard && (
        <ProposalBar antic={snap?.anticipation} searchId={data.search_id} busy={busy} onAnswer={answer} />
      )}
      {proposalErr && (
        <p role="status" className="text-xs" style={{ color: 'var(--aura-elev)' }}>
          {proposalErr}
        </p>
      )}

      {loadingStd || !spec ? (
        <ResultsSkeleton
          compact
          stage="composing"
          message="Loading Standard View…"
          mood="neutral"
        />
      ) : (
        <GenUIRenderer
          data={data}
          spec={spec}
          theme={theme}
          checkedSteps={checkedSet}
          onToggleStep={(idx) => onToggleStep(data.search_id, idx)}
          onQuery={onQuery}
        />
      )}

      {/* Only show technical model/timing telemetry when Lab Mode is unlocked and NOT blinded */}
      {!blinded && labUnlocked ? (
        <footer className="text-xs" style={{ color: 'var(--aura-subtle)' }}>
          {sourceLabel(data.provider)} · facts by {a.used_llm ? a.model : 'extractive fallback'}
          {spec && ` · layout by ${spec.source === 'llm' ? spec.model : 'template'}`}
          {' · '}
          {(data.timings_ms.total / 1000).toFixed(1)} s
          {spec?.report?.ungrounded_before_fix ? ` · ${spec.report.ungrounded_before_fix} unsupported phrase(s) removed` : ''}
        </footer>
      ) : (
        <footer className="text-xs" style={{ color: 'var(--aura-subtle)' }}>
          {sourceLabel(data.provider)} · {(data.timings_ms.total / 1000).toFixed(1)} s
        </footer>
      )}

      {DEV && !blinded && labUnlocked && (
        <section className="border-t pt-4" style={{ borderColor: 'var(--aura-border)' }}>
          <button
            type="button"
            onClick={loadCompare}
            className="aura-target rounded-lg border text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)' }}
          >
            Compare this search across all states (dev)
          </button>
          {compare && (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              {COMPARE_ORDER.map((n) => compare[n] && (
                <div key={n} className="rounded-xl border p-3" style={{ borderColor: 'var(--aura-border)' }}>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-calm)' }}>
                    {VIEW_MODES[n].name} · {compare[n].topology} · {compare[n].source}
                  </div>
                  <div className="max-h-[28rem] overflow-auto text-[0.85em]">
                    <GenUIRenderer data={data} spec={compare[n]} theme={theme} onQuery={onQuery} />
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
  return p === 'tavily' ? 'Web results' : p === 'wikipedia' ? 'Wikipedia' : p === 'fixture' ? 'Study sources' : p;
}
