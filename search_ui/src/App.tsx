import { FlaskConical, History, Loader2, Search, SlidersHorizontal, Volume2, VolumeX, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { apiGet, apiPost, apiStreamSearch, TOKEN } from './api';
import { AmbientNudgePill, FocusDigestBanner } from './components/AmbientNudgePill';
import { CameraToggle } from './components/CameraToggle';
import { LabConsoleDrawer } from './components/LabConsoleDrawer';
import { OnboardingWizard } from './components/OnboardingWizard';
import { ResultsView } from './components/ResultsView';
import { ResultsSkeleton, type SearchLoadingStage } from './components/SearchResults';
import { SessionWrapUpModal } from './components/SessionWrapUpModal';
import { StudyPanel } from './components/study/StudyPanel';
import { ThemeMenu } from './components/ThemePicker';
import { UnifiedBreathing } from './components/UnifiedBreathing';
import { ViewModeMenu } from './components/ViewModeMenu';
import { WellnessView } from './components/WellnessView';
import { useAmbientSound } from './hooks/useAmbientSound';
import { useAuraState } from './hooks/useAuraState';
import { useBehaviourSignals } from './hooks/useBehaviourSignals';
import { useTypingDynamics } from './hooks/useTypingDynamics';
import { isLightTheme, LAB_STATE_LABEL, VIEW_MODES } from './modes';
import type {
  FixtureInfo,
  HciState,
  RerenderResponse,
  SearchResponse,
  StateSnapshot,
  StreamStageAPayload,
  ThemeId,
  ViewPolicyName,
} from './types';

type NavTab = 'search' | 'wellness';

const URL_PARAMS = new URLSearchParams(window.location.search);
const SIM_MOODS: HciState[] = ['focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented'];
const MOOD_TOKENS: Record<ViewPolicyName, { targetScale: number; typographyScale: number; lineHeight: number }> = {
  neutral: { targetScale: 1.0, typographyScale: 1.0, lineHeight: 1.55 },
  focused: { targetScale: 1.0, typographyScale: 1.0, lineHeight: 1.55 },
  overwhelmed: { targetScale: 1.26, typographyScale: 1.1, lineHeight: 1.72 },
  fatigued: { targetScale: 1.16, typographyScale: 1.14, lineHeight: 1.82 },
  energized: { targetScale: 1.04, typographyScale: 1.02, lineHeight: 1.6 },
  disoriented: { targetScale: 1.1, typographyScale: 1.06, lineHeight: 1.66 },
};

export default function App() {
  const { live, snap, app, status, refreshNow } = useAuraState();

  const [tab, setTab] = useState<NavTab>(URL_PARAMS.get('view') === 'wellness' ? 'wellness' : 'search');
  const [labOpen, setLabOpen] = useState(URL_PARAMS.get('lab') === '1');
  const [showMoodBar, setShowMoodBar] = useState(false);
  const [breathingOpen, setBreathingOpen] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState<0 | 1 | 2 | null>(null);
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);

  const [query, setQuery] = useState('');
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [partialStageA, setPartialStageA] = useState<StreamStageAPayload | null>(null);
  const [loadingStage, setLoadingStage] = useState<string | null>(null);
  const [loadingStep, setLoadingStep] = useState<SearchLoadingStage | null>(null);
  const [loadingSourceCount, setLoadingSourceCount] = useState<number | null>(null);
  const [switchingMode, setSwitchingMode] = useState<ViewPolicyName | null>(null);
  const [localOverride, setLocalOverride] = useState<ViewPolicyName | ''>('');
  const [standardViewActive, setStandardViewActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fixtures, setFixtures] = useState<FixtureInfo[]>([]);
  const [recentQueries, setRecentQueries] = useState<string[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [checkedStepsMap, setCheckedStepsMap] = useState<Record<string, number[]>>({});

  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const blinded = Boolean(app?.study.blinded);
  const labUnlocked = Boolean(app?.study.lab_unlocked);
  const isControl = (app?.study.condition ?? live?.condition) === 'control';
  const theme: ThemeId = app?.comfort.theme ?? 'dark';
  const autoAdapt = app?.comfort.auto_adapt ?? true;
  const overridePolicy = (localOverride || app?.comfort.view_mode_override || '') as ViewPolicyName | '';
  const activePolicyName: ViewPolicyName =
    switchingMode ??
    (overridePolicy
      ? overridePolicy
      : (result?.policy.name as ViewPolicyName | undefined) ??
        (!autoAdapt ? 'neutral' : (snap?.policy.name as ViewPolicyName | undefined) ?? 'neutral'));

  // Determine the visual atmosphere active across the whole workspace
  const effectiveMood: ViewPolicyName =
    isControl || standardViewActive
      ? 'neutral'
      : snap?.simulation?.state && snap.fused.committed_state === snap.simulation.state
      ? snap.simulation.state
      : activePolicyName;

  const calmChrome = !blinded && Boolean(VIEW_MODES[effectiveMood]?.calmChrome);
  const ambientSound = useAmbientSound(effectiveMood);

  useSimulatedRelayout(snap, result, setResult, setSwitchingMode);

  // Apply theme + mood atmosphere attributes to root html
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-mood', effectiveMood);
  }, [theme, effectiveMood]);

  // Apply policy typography & hit-target tokens for the active mood/view
  useEffect(() => {
    const tokens =
      effectiveMood === 'neutral'
        ? MOOD_TOKENS.neutral
        : result?.policy.name === effectiveMood
        ? result.policy.tokens
        : snap?.policy.name === effectiveMood
        ? snap.policy.tokens
        : MOOD_TOKENS[effectiveMood];
    const root = document.documentElement.style;
    root.setProperty('--aura-target-scale', String(tokens?.targetScale ?? 1));
    root.setProperty('--aura-type-scale', String(tokens?.typographyScale ?? 1));
    root.setProperty('--aura-line-height', String(tokens?.lineHeight ?? 1.55));
  }, [effectiveMood, result?.policy.name, result?.policy.tokens, snap?.policy.name, snap?.policy.tokens]);

  // Offer onboarding once on unconsented / uncalibrated fresh start
  useEffect(() => {
    if (
      app &&
      !app.comfort.onboarding_complete &&
      !app.consent.granted &&
      !app.recording.recording &&
      !onboardingDismissed &&
      onboardingStep === null
    ) {
      setOnboardingStep(0);
    }
  }, [app, onboardingDismissed, onboardingStep]);

  // Global shortcuts: `/` focuses search; `Ctrl+Shift+L` toggles Lab Console
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'l') {
        e.preventDefault();
        setLabOpen((o) => !o);
        return;
      }
      if (
        e.key === '/' &&
        tab === 'search' &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tab]);

  useTypingDynamics(inputRef, status !== 'unauthorized');
  useBehaviourSignals(status !== 'unauthorized');

  useEffect(() => {
    inputRef.current?.focus();
    if (TOKEN) {
      apiGet<{ fixtures: FixtureInfo[] }>('/api/fixtures')
        .then((r) => setFixtures(r.fixtures))
        .catch(() => setFixtures([]));
    }
  }, []);

  const cancelSearch = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoadingStage(null);
    setLoadingStep(null);
    setLoadingSourceCount(null);
    setPartialStageA(null);
  };

  const runSearch = async (q: string) => {
    const text = q.trim();
    if (!text) return;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setTab('search');
    setQuery(text);
    setResult(null);
    setPartialStageA(null);
    setError(null);
    setLoadingStage('Searching sources…');
    setLoadingStep('retrieving');
    setLoadingSourceCount(null);
    setHistoryOpen(false);
    setRecentQueries((prev) => [text, ...prev.filter((x) => x !== text)].slice(0, 10));

    try {
      await apiStreamSearch(
        text,
        {
          onStage: (stage, msg, meta) => {
            if (stage === 'retrieving' || stage === 'synthesizing' || stage === 'composing') {
              setLoadingStep(stage);
            }
            if (typeof meta?.sourceCount === 'number') {
              setLoadingSourceCount(meta.sourceCount);
            }
            setLoadingStage(msg || 'Working…');
          },
          onStageA: (payload) => setPartialStageA(payload),
          onDone: (res) => {
            setResult(res);
            setPartialStageA(null);
            setLoadingStage(null);
            setLoadingStep(null);
            setLoadingSourceCount(null);
          },
        },
        ac.signal,
      );
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setError((e as Error).message);
      setLoadingStage(null);
      setLoadingStep(null);
      setLoadingSourceCount(null);
      setPartialStageA(null);
    }
  };

  const selectViewMode = async (policy: ViewPolicyName) => {
    setStandardViewActive(false);
    setLocalOverride(policy);
    setSwitchingMode(policy);
    try {
      if (snap?.simulation) {
        await apiPost('/api/simulate', { state: null }).catch(() => undefined);
      }
      await apiPost('/api/app/comfort', { view_mode_override: policy, auto_adapt: false }).catch(() => undefined);
      if (result && !isControl) {
        const r = await apiPost<RerenderResponse>(`/api/search/${result.search_id}/rerender`, { policy }).catch(() => null);
        if (r) {
          setResult((prev) => (prev ? { ...prev, adaptive: policy !== 'neutral', policy: r.policy, spec: r.spec } : prev));
        } else {
          void runSearch(result.query);
        }
      }
      await refreshNow();
    } finally {
      setSwitchingMode(null);
    }
  };

  const toggleAutoAdapt = async (next: boolean) => {
    setStandardViewActive(false);
    if (next) {
      setLocalOverride('');
      setSwitchingMode(((snap?.policy.name as ViewPolicyName | undefined) ?? 'focused'));
      try {
        await apiPost('/api/app/comfort', { auto_adapt: true, view_mode_override: '' }).catch(() => undefined);
        const target = (snap?.policy.name as ViewPolicyName | undefined) || 'focused';
        if (result && !isControl) {
          const r = await apiPost<RerenderResponse>(`/api/search/${result.search_id}/rerender`, { policy: target }).catch(() => null);
          if (r) {
            setResult((prev) => (prev ? { ...prev, adaptive: target !== 'neutral', policy: r.policy, spec: r.spec } : prev));
          }
        }
        await refreshNow();
      } finally {
        setSwitchingMode(null);
      }
      return;
    }
    setLocalOverride(activePolicyName);
    await apiPost('/api/app/comfort', {
      auto_adapt: false,
      view_mode_override: activePolicyName,
    }).catch(() => undefined);
    await refreshNow();
  };

  // Restore layout adaptation automatically when switching back from Control (A) to State-aware (B)
  const prevControlRef = useRef(false);
  useEffect(() => {
    const wasControl = prevControlRef.current;
    prevControlRef.current = isControl;
    if (!wasControl || isControl || !result) return;
    setStandardViewActive(false);
    const target: ViewPolicyName = overridePolicy || (autoAdapt ? ((snap?.policy.name as ViewPolicyName | undefined) || 'focused') : 'neutral');
    if (result.policy.name === target && result.adaptive === (target !== 'neutral')) return;
    setSwitchingMode(target);
    apiPost<RerenderResponse>(`/api/search/${result.search_id}/rerender`, { policy: target })
      .then((r) => {
        setResult((prev) => (prev ? { ...prev, adaptive: target !== 'neutral', policy: r.policy, spec: r.spec } : prev));
      })
      .catch(() => undefined)
      .finally(() => setSwitchingMode(null));
  }, [isControl, result, overridePolicy, autoAdapt, snap?.policy.name]);

  const simulateMood = async (state: HciState | null) => {
    await apiPost('/api/simulate', { state, duration_s: 45 }).catch(() => undefined);
    void refreshNow();
  };

  const toggleStep = (searchId: string, index: number) => {
    setCheckedStepsMap((prev) => {
      const cur = new Set(prev[searchId] ?? []);
      if (cur.has(index)) cur.delete(index);
      else cur.add(index);
      return { ...prev, [searchId]: Array.from(cur) };
    });
  };

  // Ambient orb color reflects calm/mild/elevated subtly without clinical numbers
  const orbColor = !live
    ? 'var(--aura-subtle)'
    : live.tier === 2
    ? 'var(--aura-elev)'
    : live.tier === 1
    ? 'var(--aura-mild)'
    : 'var(--aura-calm)';

  return (
    <div className="aura-atmosphere-canvas flex min-h-screen flex-col" data-calm-chrome={calmChrome ? 'true' : 'false'}>
      <header
        className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-6"
        style={{ borderColor: 'var(--aura-border)' }}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <span
              className="relative flex h-2.5 w-2.5 items-center justify-center"
              title={live ? `Ambient state: ${live.label}` : 'Connecting…'}
              aria-hidden
            >
              {live && live.tier > 0 && (
                <span className="aura-orb-ping absolute inset-0 rounded-full" style={{ background: orbColor }} />
              )}
              <span
                className="relative h-2.5 w-2.5 rounded-full transition-colors duration-500"
                style={{ background: orbColor }}
              />
            </span>
            <h1 className="text-lg font-semibold tracking-tight">Aura</h1>
          </div>

          <nav className="flex gap-1" aria-label="Main navigation">
            {([
              ['search', 'Search'],
              ['wellness', 'Wellness'],
            ] as const).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className="aura-target rounded-lg px-3 text-sm font-medium transition-colors"
                style={{
                  background: tab === id ? 'var(--aura-surface-elev)' : 'transparent',
                  color: tab === id ? 'var(--aura-text)' : 'var(--aura-muted)',
                }}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>

        <div className="aura-secondary-chrome flex flex-wrap items-center gap-2">
          {status !== 'unauthorized' && <CameraToggle face={snap?.camera?.face} />}

          {!blinded && status !== 'unauthorized' && (
            <ViewModeMenu
              snap={snap}
              currentPolicy={effectiveMood}
              autoAdapt={autoAdapt}
              blinded={blinded}
              isControl={isControl}
              theme={theme}
              onSelectPolicy={(p) => void selectViewMode(p)}
              onToggleAutoAdapt={(n) => void toggleAutoAdapt(n)}
              onExitControl={() => void apiPost('/api/app/settings', { study_condition: 'intervention' }).then(refreshNow)}
            />
          )}

          {!blinded && (
            <button
              type="button"
              onClick={() => setShowMoodBar((v) => !v)}
              aria-pressed={showMoodBar}
              className="aura-target flex items-center gap-1.5 rounded-full border text-xs"
              style={{
                borderColor: showMoodBar || snap?.simulation ? 'var(--aura-mild)' : 'var(--aura-border-interactive)',
                background: 'var(--aura-surface)',
                color: showMoodBar || snap?.simulation ? 'var(--aura-mild)' : 'var(--aura-muted)',
              }}
              title="Show quick mood simulator bar above search results"
            >
              Moods{snap?.simulation ? ` · ${LAB_STATE_LABEL[snap.simulation.state]}` : ''}
            </button>
          )}

          {ambientSound.playing && (
            <button
              type="button"
              onClick={ambientSound.mute}
              className="aura-target flex items-center gap-1.5 rounded-full border text-xs"
              style={{ borderColor: 'var(--aura-calm)', background: 'var(--aura-accent-soft)', color: 'var(--aura-calm)' }}
              title="Mute ambient soundscape"
            >
              <Volume2 size={13} aria-hidden />
              <span className="capitalize">{ambientSound.sound}</span>
              <VolumeX size={12} aria-hidden />
            </button>
          )}

          {!blinded && (
            <button
              type="button"
              onClick={() => setLabOpen(true)}
              className="aura-target flex items-center gap-1.5 rounded-full border text-xs"
              style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-surface)', color: 'var(--aura-muted)' }}
              title="Open Researcher & Developer Lab (Ctrl+Shift+L)"
            >
              <FlaskConical size={13} aria-hidden /> Lab
            </button>
          )}

          <ThemeMenu
            theme={theme}
            onSelect={(id) => void apiPost('/api/app/comfort', { theme: id }).then(refreshNow)}
          />

          <button
            type="button"
            onClick={() => setOnboardingStep(0)}
            className="aura-target rounded-full border p-2"
            style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-surface)', color: 'var(--aura-muted)' }}
            aria-label="Open Setup & Calibration"
            title="Setup & Calibration"
          >
            <SlidersHorizontal size={14} aria-hidden />
          </button>
        </div>
      </header>

      <main className={`mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-7 ${calmChrome ? 'gap-7' : 'gap-5'}`}>
        {status === 'unauthorized' && (
          <p className="rounded-xl border p-4 text-sm" style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}>
            This window needs to be opened from Aura (tray menu or Ctrl+Shift+Space).
          </p>
        )}

        <FocusDigestBanner
          digest={app?.focus_digest ?? null}
          onClear={() => void apiPost('/api/app/focus/clear-digest', {}).then(refreshNow)}
        />

        {tab === 'search' ? (
          <div key="tab-search" className="aura-fade-up flex flex-col gap-5">
            <div className="relative">
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void runSearch(query);
                }}
              >
                <label className="sr-only" htmlFor="q">Search</label>
                <div
                  className="aura-search-box flex flex-1 items-center gap-2 rounded-xl border px-4"
                  style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-surface)' }}
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
                    placeholder="Ask anything  (press / to focus)"
                    disabled={status === 'unauthorized'}
                  />
                </div>
                {recentQueries.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setHistoryOpen((o) => !o)}
                    aria-expanded={historyOpen}
                    aria-label="Recent searches"
                    title="Recent searches"
                    className="aura-target rounded-xl border px-3"
                    style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-surface)', color: 'var(--aura-muted)' }}
                  >
                    <History size={16} aria-hidden />
                  </button>
                )}
                {loadingStage ? (
                  <button
                    type="button"
                    onClick={cancelSearch}
                    className="aura-target flex items-center gap-1.5 rounded-xl border px-4 text-sm font-medium"
                    style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)', background: 'var(--aura-surface)' }}
                  >
                    <X size={15} aria-hidden /> Cancel
                  </button>
                ) : (
                  <button
                    type="submit"
                    className="aura-target rounded-xl px-5 text-sm font-medium disabled:opacity-50"
                    style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
                    disabled={!query.trim() || status === 'unauthorized'}
                  >
                    Search
                  </button>
                )}
              </form>

              {historyOpen && recentQueries.length > 0 && (
                <div
                  className="aura-scale-in origin-top-right absolute right-0 z-20 mt-2 w-72 rounded-xl border p-2 shadow-xl"
                  style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
                >
                  <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-subtle)' }}>
                    Recent searches
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {recentQueries.map((rq) => (
                      <li key={rq}>
                        <button
                          type="button"
                          onClick={() => void runSearch(rq)}
                          className="w-full truncate rounded-lg px-2.5 py-1.5 text-left text-sm hover:bg-[var(--aura-surface-elev)]"
                        >
                          {rq}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <StudyPanel
              recording={Boolean(live?.recording)}
              onTaskStart={() => {
                setResult(null);
                setPartialStageA(null);
                setQuery('');
                inputRef.current?.focus();
              }}
            />

            {!result && !loadingStage && !live?.recording && fixtures.length > 0 && (
              <section aria-label="Sample topics" className="aura-fade-up flex flex-wrap gap-2">
                {fixtures.map((f) => (
                  <button
                    key={f.query}
                    type="button"
                    title={f.task || 'Sample search'}
                    onClick={() => void runSearch(f.query)}
                    className="aura-target rounded-full border text-sm transition-all duration-150 hover:-translate-y-0.5 hover:border-[var(--aura-calm)]"
                    style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)', background: 'var(--aura-surface)' }}
                  >
                    {f.query}
                  </button>
                ))}
              </section>
            )}

            {!blinded && (Boolean(snap?.simulation) || labOpen || showMoodBar) && (
              <section
                aria-label="Quick mood simulator"
                className="aura-fade-up flex flex-col gap-2 rounded-xl border px-3.5 py-2.5 text-xs"
                style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
                    Test mood:
                  </span>
                  {SIM_MOODS.map((m) => {
                    const active = snap?.simulation?.state === m;
                    const meta = VIEW_MODES[m];
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => void simulateMood(active ? null : m)}
                        aria-pressed={active}
                        className="aura-target flex items-center gap-1.5 rounded-lg border text-xs font-medium hover:border-[var(--aura-calm)]"
                        style={{
                          borderColor: active ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
                          background: active ? 'var(--aura-accent-soft)' : 'var(--aura-surface-elev)',
                          color: 'var(--aura-text)',
                        }}
                      >
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: isLightTheme(theme) ? meta.swatchLight : meta.swatchDark }}
                          aria-hidden
                        />
                        {LAB_STATE_LABEL[m]}
                      </button>
                    );
                  })}
                  {snap?.simulation && (
                    <button
                      type="button"
                      onClick={() => void simulateMood(null)}
                      className="aura-target ml-auto rounded-lg border text-xs"
                      style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}
                    >
                      Stop ({Math.ceil(snap.simulation.remaining_s)}s)
                    </button>
                  )}
                </div>
                {snap?.fused.candidate_state && (
                  <div className="flex items-center gap-3">
                    <span style={{ color: 'var(--aura-calm)' }}>
                      Adapting atmosphere to {LAB_STATE_LABEL[snap.fused.candidate_state]} ({Math.max(0, 3 * (1 - snap.fused.dwell_progress)).toFixed(1)}s)…
                    </span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: 'var(--aura-track)' }}>
                      <div
                        className="h-full rounded-full transition-all duration-200"
                        style={{ width: `${snap.fused.dwell_progress * 100}%`, background: 'var(--aura-calm)' }}
                      />
                    </div>
                  </div>
                )}
              </section>
            )}

            {switchingMode && (
              <div
                role="status"
                className="aura-fade-in flex w-fit items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium"
                style={{
                  borderColor: 'var(--aura-calm)',
                  background: 'var(--aura-accent-soft)',
                  color: 'var(--aura-calm)',
                }}
              >
                <Loader2 size={13} className="aura-spin" aria-hidden />
                Switching to {VIEW_MODES[switchingMode]?.name ?? switchingMode}…
              </div>
            )}

            {error && (
              <p role="alert" className="aura-fade-in rounded-xl border p-4 text-sm" style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}>
                Search failed: {error}
              </p>
            )}

            {loadingStage && !partialStageA ? (
              <ResultsSkeleton
                stage={loadingStep}
                message={loadingStage}
                mood={effectiveMood}
                query={query}
                sourceCount={loadingSourceCount}
              />
            ) : (
              (result || partialStageA) && (
                <ResultsView
                  data={result}
                  partialStageA={partialStageA}
                  snap={snap}
                  blinded={blinded}
                  labUnlocked={labUnlocked}
                  theme={theme}
                  checkedStepsMap={checkedStepsMap}
                  onToggleStep={toggleStep}
                  onStandardChange={setStandardViewActive}
                  onQuery={(q) => void runSearch(q)}
                />
              )
            )}
          </div>
        ) : (
          <div key="tab-wellness" className="aura-fade-up">
            <WellnessView
              app={app}
              ambientSound={ambientSound}
              onOpenBreathing={() => setBreathingOpen(true)}
              onOpenOnboarding={(s = 0) => setOnboardingStep(s)}
              onRefresh={() => void refreshNow()}
            />
          </div>
        )}
      </main>

      {/* Non-focus-stealing Tier-2 corner nudge */}
      <AmbientNudgePill
        nudge={app?.nudge ?? null}
        onBreathe={() => setBreathingOpen(true)}
        onChat={() => setTab('wellness')}
        onRefresh={() => void refreshNow()}
      />

      {breathingOpen && <UnifiedBreathing onClose={() => setBreathingOpen(false)} />}

      {onboardingStep !== null && (
        <OnboardingWizard
          app={app}
          initialStep={onboardingStep}
          onClose={() => {
            setOnboardingStep(null);
            setOnboardingDismissed(true);
          }}
          onRefresh={() => void refreshNow()}
        />
      )}

      {app && <SessionWrapUpModal app={app} onDone={() => void refreshNow()} />}

      <LabConsoleDrawer
        open={labOpen}
        onClose={() => setLabOpen(false)}
        live={live}
        snap={snap}
        app={app}
        onRefresh={() => void refreshNow()}
        onOpenConsent={() => setOnboardingStep(0)}
      />
    </div>
  );
}

/** While a mood is simulated, re-lay out results on screen for the mood the model
 *  commits to (Stage B only), so layout differences are immediately visible. */
function useSimulatedRelayout(
  snap: StateSnapshot | null,
  result: SearchResponse | null,
  setResult: (r: SearchResponse) => void,
  setSwitchingMode: (m: ViewPolicyName | null) => void,
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
    setSwitchingMode(committed);
    apiPost<RerenderResponse>(`/api/search/${result.search_id}/rerender`, { policy: committed })
      .then((r) => setResult({ ...result, policy: r.policy, spec: r.spec }))
      .catch(() => undefined)
      .finally(() => setSwitchingMode(null));
  }, [simState, committed, result, setResult, setSwitchingMode]);
}
