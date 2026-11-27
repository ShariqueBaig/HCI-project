import { useEffect, useState } from 'react';
import {
  ArrowRight,
  Award,
  BatteryCharging,
  Bot,
  CheckCircle2,
  GitCompare,
  KeyRound,
  LayoutGrid,
  Navigation,
  Search,
  Sparkles,
  Star,
  Tag,
  Volume2,
  X,
} from 'lucide-react';
import type {
  AgentResult,
  ExperimentCondition,
  LlmConfig,
  ProductItem,
  TelemetryData,
} from '../types/aura';

interface CommerceAgentViewProps {
  telemetry: TelemetryData;
  condition: ExperimentCondition;
  sessionId: string | null;
  initialPrompt?: string;
  onLogEvent?: (type: 'backtrack' | 'error' | 'filter_change' | 'task_complete', targetId?: string, meta?: Record<string, unknown>) => void;
  onSchemaMetadataChange?: (visualType: string, navType: string) => void;
}

const BENCHMARK_PROMPTS = [
  'Find the best university smartphone under 60,000 PKR with long battery',
  'Compare noise-canceling headphones for quiet studying',
  'Recommend a lightweight laptop for HCI research & coding',
];

export function CommerceAgentView({
  telemetry,
  condition,
  sessionId,
  initialPrompt,
  onLogEvent,
  onSchemaMetadataChange,
}: CommerceAgentViewProps) {
  const [prompt, setPrompt] = useState(initialPrompt || BENCHMARK_PROMPTS[0]);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stepperStep, setStepperStep] = useState<1 | 2 | 3>(1);
  const [showAllOverwhelmed, setShowAllOverwhelmed] = useState(false);
  const [facetCategory, setFacetCategory] = useState<string>('all');
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [showLlmSettings, setShowLlmSettings] = useState(false);
  const [llmConfig, setLlmConfig] = useState<LlmConfig>({
    enabled: false,
    provider: 'gemini',
    api_key: '',
  });

  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [comparisons, setComparisons] = useState<Array<Record<string, any>>>([]);
  const [comparing, setComparing] = useState(false);

  const runPrompt = async (overridePrompt?: string) => {
    const q = (overridePrompt ?? prompt).trim();
    if (!q) return;
    setLoading(true);
    try {
      const res = await fetch('/api/agent/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: q,
          scenario: 'commerce',
          condition,
          session_id: sessionId,
          llm_config: llmConfig.enabled && llmConfig.api_key ? llmConfig : null,
        }),
      });
      const data = await res.json();
      if (data.result) {
        setResult(data.result);
        setStepperStep(1);
        setShowAllOverwhelmed(false);
        setFacetCategory('all');
        onSchemaMetadataChange?.(data.result.visualType, data.result.navType);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialPrompt) {
      setPrompt(initialPrompt);
      runPrompt(initialPrompt);
    } else {
      runPrompt(BENCHMARK_PROMPTS[0]);
    }
    // Re-run whenever condition or active_state changes so the user immediately sees the structural shift
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [condition, telemetry.active_state]);

  const openCrossEmotionComparison = async () => {
    setCompareModalOpen(true);
    setComparing(true);
    try {
      const res = await fetch('/api/agent/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, scenario: 'commerce' }),
      });
      const data = await res.json();
      setComparisons(data.comparisons ?? []);
    } finally {
      setComparing(false);
    }
  };

  const speakSummary = () => {
    if (!result || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(`${result.headline}. ${result.message}`);
    utter.rate = 0.95;
    window.speechSynthesis.speak(utter);
  };

  const handleSelectProduct = (item: ProductItem) => {
    if (selectedId && selectedId !== item.id) {
      onLogEvent?.('backtrack', item.id, { prev: selectedId });
    }
    setSelectedId(item.id);
    onLogEvent?.('task_complete', item.id, { name: item.name, pricePkr: item.pricePkr });
  };

  const toggleComparePin = (id: string) => {
    setCompareIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev.slice(-2), id],
    );
  };

  const items = (result?.matchedItems ?? []) as ProductItem[];
  const spotlight = (result?.spotlightItem as ProductItem | null) ?? items[0] ?? null;
  const isControl = condition === 'prompt_only_control';
  const activeState = isControl ? 'control' : telemetry.active_state;

  const filteredItems =
    facetCategory === 'all' ? items : items.filter((p) => p.category === facetCategory || p.vendor.toLowerCase() === facetCategory);

  const renderProductCard = (item: ProductItem, compact = false) => {
    const isChosen = selectedId === item.id;
    const isPinned = compareIds.includes(item.id);
    return (
      <div
        key={item.id}
        className="flex flex-col justify-between rounded-2xl border p-4 transition-all"
        style={{
          backgroundColor: 'var(--aura-panel)',
          borderColor: isChosen ? 'var(--aura-accent)' : 'var(--aura-border)',
          boxShadow: isChosen ? '0 0 0 2px var(--aura-accent-soft)' : undefined,
        }}
      >
        <div>
          <div className="flex flex-wrap items-center justify-between gap-1.5">
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
              style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
            >
              {item.vendor} • {item.category}
            </span>
            {result?.uiOverrides.showPromos && item.isBudgetPick && (
              <span className="inline-flex items-center gap-1 rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-700">
                <Tag className="h-2.5 w-2.5" /> FLASH DEAL -12%
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-xs font-semibold">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-500" /> {item.rating}
            </span>
          </div>

          <h3 className="mt-2.5 text-base font-bold leading-snug">{item.name}</h3>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-lg font-bold" style={{ color: 'var(--aura-accent)' }}>
              {item.pricePkr.toLocaleString()} PKR
            </span>
            <span className="text-xs" style={{ color: 'var(--aura-muted)' }}>
              (${item.priceUsd})
            </span>
          </div>

          <p className="aura-readable mt-1.5 text-xs" style={{ color: 'var(--aura-muted)' }}>
            {item.bestFor}
          </p>

          {!compact && (
            <div className="mt-3 grid grid-cols-2 gap-1.5 text-[11px]">
              {Object.entries(item.specs).map(([k, v]) => (
                <div
                  key={k}
                  className="rounded-lg px-2 py-1"
                  style={{ backgroundColor: 'var(--aura-panel-alt)' }}
                >
                  <span className="uppercase opacity-65">{k}: </span>
                  <span className="font-semibold">{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => handleSelectProduct(item)}
            className="aura-target inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl text-xs font-semibold text-white cursor-pointer"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {isChosen ? 'Selected Decision' : 'Choose This Option'}
          </button>
          {activeState === 'energized' && (
            <button
              type="button"
              onClick={() => toggleComparePin(item.id)}
              className="aura-target rounded-xl border px-2.5 text-xs font-semibold cursor-pointer"
              style={{
                borderColor: isPinned ? 'var(--aura-accent)' : 'var(--aura-border)',
                backgroundColor: isPinned ? 'var(--aura-accent-soft)' : 'var(--aura-panel-alt)',
                color: isPinned ? 'var(--aura-accent)' : 'var(--aura-text)',
              }}
            >
              {isPinned ? 'Pinned' : 'Compare'}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6">
      {/* Prompt & Agent Controls */}
      <section
        className="rounded-3xl border p-5 shadow-sm"
        style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5" style={{ color: 'var(--aura-accent)' }} />
            <div>
              <h1 className="text-base font-bold">
                Emotional AI Product &amp; Decision Agent
              </h1>
              <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                Same prompt, structurally different Visual Type &amp; Nav Type based on live affect vs. Control baseline.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowLlmSettings((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold cursor-pointer"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
            >
              <KeyRound className="h-3.5 w-3.5" />
              {llmConfig.enabled && llmConfig.api_key ? `LLM: ${llmConfig.provider}` : 'Hybrid Offline Mode'}
            </button>
            <button
              type="button"
              onClick={openCrossEmotionComparison}
              className="inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold cursor-pointer"
              style={{
                borderColor: 'var(--aura-accent)',
                backgroundColor: 'var(--aura-accent-soft)',
                color: 'var(--aura-accent)',
              }}
            >
              <GitCompare className="h-3.5 w-3.5" />
              Compare Same Prompt Across Emotions
            </button>
          </div>
        </div>

        {showLlmSettings && (
          <div
            className="mt-3 flex flex-wrap items-center gap-3 rounded-2xl border p-3 text-xs"
            style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
          >
            <label className="flex items-center gap-1.5 font-semibold">
              <input
                type="checkbox"
                checked={llmConfig.enabled}
                onChange={(e) => setLlmConfig((c) => ({ ...c, enabled: e.target.checked }))}
              />
              Enable Optional Live LLM
            </label>
            <select
              value={llmConfig.provider}
              onChange={(e) => setLlmConfig((c) => ({ ...c, provider: e.target.value as 'gemini' | 'openai' }))}
              className="rounded-lg border px-2 py-1"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel)' }}
            >
              <option value="gemini">Google Gemini (2.0 Flash)</option>
              <option value="openai">OpenAI (GPT-4o-mini)</option>
            </select>
            <input
              type="password"
              value={llmConfig.api_key}
              onChange={(e) => setLlmConfig((c) => ({ ...c, api_key: e.target.value }))}
              placeholder="Paste API key (optional; stays in memory only)..."
              className="min-w-[240px] flex-1 rounded-lg border px-2.5 py-1"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel)' }}
            />
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            runPrompt();
          }}
          className="mt-4 flex flex-wrap gap-2"
        >
          <div className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 opacity-50" />
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask for a product recommendation or comparison..."
              className="w-full rounded-2xl border py-2.5 pl-9 pr-4 text-sm outline-none"
              style={{
                backgroundColor: 'var(--aura-panel-alt)',
                borderColor: 'var(--aura-border)',
                color: 'var(--aura-text)',
              }}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="aura-target inline-flex items-center gap-1.5 rounded-2xl text-xs font-bold text-white cursor-pointer"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            <Sparkles className="h-4 w-4" />
            {loading ? 'Generating UI...' : 'Ask Emotional Agent'}
          </button>
        </form>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold" style={{ color: 'var(--aura-muted)' }}>
            Benchmark Prompts:
          </span>
          {BENCHMARK_PROMPTS.map((bp) => (
            <button
              key={bp}
              type="button"
              onClick={() => {
                setPrompt(bp);
                runPrompt(bp);
              }}
              className="rounded-lg border px-2.5 py-1 text-[11px] font-medium hover:opacity-80 cursor-pointer"
              style={{
                borderColor: 'var(--aura-border)',
                backgroundColor: prompt === bp ? 'var(--aura-accent-soft)' : 'var(--aura-panel-alt)',
                color: prompt === bp ? 'var(--aura-accent)' : 'var(--aura-text)',
              }}
            >
              {bp}
            </button>
          ))}
        </div>
      </section>

      {/* Emotion-Conditioned Agent Synthesis Banner */}
      {result && (
        <section
          className="rounded-3xl border p-5 shadow-sm"
          style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-accent)' }}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold"
                style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
              >
                <LayoutGrid className="h-3.5 w-3.5" /> Visual Type: {result.visualType}
              </span>
              <span
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold"
                style={{ backgroundColor: 'var(--aura-panel-alt)', color: 'var(--aura-text)' }}
              >
                <Navigation className="h-3.5 w-3.5" /> Nav Type: {result.navType}
              </span>
              <span className="rounded-full border px-2.5 py-0.5 text-[11px] font-medium" style={{ borderColor: 'var(--aura-border)' }}>
                Tone: {result.agentTone}
              </span>
              {result.usedLlm && (
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">
                  Live LLM Generated
                </span>
              )}
            </div>

            {result.uiOverrides.voiceRecommended && (
              <button
                type="button"
                onClick={speakSummary}
                className="aura-target inline-flex items-center gap-1.5 rounded-xl text-xs font-semibold text-white cursor-pointer"
                style={{ backgroundColor: 'var(--aura-accent)' }}
              >
                <Volume2 className="h-4 w-4" /> Read Summary Aloud
              </button>
            )}
          </div>

          <h2 className="mt-3 text-lg font-bold">{result.headline}</h2>
          <p className="aura-readable mt-1 text-sm" style={{ color: 'var(--aura-muted)' }}>
            {result.message}
          </p>

          <ul className="mt-3 grid gap-2 sm:grid-cols-3">
            {result.rationaleBullets.map((b, i) => (
              <li
                key={i}
                className="rounded-xl border px-3 py-2 text-xs font-medium"
                style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
              >
                {b}
              </li>
            ))}
          </ul>

          <div className="mt-3 text-[11px]" style={{ color: 'var(--aura-muted)' }}>
            <strong>HCI Rationale:</strong> {result.hciExplanation}
          </div>
        </section>
      )}

      {/* STRUCTURAL RENDERER 1: OVERWHELMED -> Focused & Spotlight + Single-Path Guided Stepper */}
      {result && activeState === 'overwhelmed' && spotlight && (
        <section className="mx-auto max-w-3xl space-y-4">
          {/* Guided Stepper Navigation */}
          <div
            className="flex items-center justify-between rounded-2xl border p-3"
            style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
          >
            {[
              { step: 1 as const, label: '1. Review Top Pick' },
              { step: 2 as const, label: '2. Verify Key Fit' },
              { step: 3 as const, label: '3. Confirm Choice' },
            ].map((s) => (
              <button
                key={s.step}
                type="button"
                onClick={() => {
                  if (s.step < stepperStep) onLogEvent?.('backtrack', `stepper-${s.step}`);
                  setStepperStep(s.step);
                }}
                className="aura-target flex-1 rounded-xl text-xs font-bold transition-colors cursor-pointer"
                style={{
                  backgroundColor: stepperStep === s.step ? 'var(--aura-accent)' : 'transparent',
                  color: stepperStep === s.step ? '#FFFFFF' : 'var(--aura-muted)',
                }}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div
            className="rounded-3xl border p-6 shadow-sm sm:p-8"
            style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-accent)' }}
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold"
                style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
              >
                <Award className="h-4 w-4" /> Single Spotlight Match ({result.totalCatalogCount - 1} distractions hidden)
              </span>
              <span className="text-sm font-bold">{spotlight.pricePkr.toLocaleString()} PKR</span>
            </div>

            <h3 className="mt-4 text-2xl font-bold">{spotlight.name}</h3>
            <p className="aura-readable mt-1 text-sm" style={{ color: 'var(--aura-muted)' }}>
              {spotlight.bestFor}
            </p>

            {stepperStep === 1 && (
              <div className="mt-5 space-y-2">
                {spotlight.pros.map((pro, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 rounded-xl border p-3 text-sm font-medium"
                    style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
                  >
                    <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: 'var(--aura-accent)' }} />
                    {pro}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setStepperStep(2)}
                  className="aura-target mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl text-sm font-bold text-white cursor-pointer"
                  style={{ backgroundColor: 'var(--aura-accent)' }}
                >
                  Next: Verify Specs <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            )}

            {stepperStep === 2 && (
              <div className="mt-5 space-y-3">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {Object.entries(spotlight.specs).map(([k, v]) => (
                    <div
                      key={k}
                      className="rounded-xl border p-3 text-sm"
                      style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
                    >
                      <div className="text-[11px] uppercase" style={{ color: 'var(--aura-muted)' }}>{k}</div>
                      <div className="font-bold">{v}</div>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setStepperStep(3)}
                  className="aura-target inline-flex w-full items-center justify-center gap-2 rounded-2xl text-sm font-bold text-white cursor-pointer"
                  style={{ backgroundColor: 'var(--aura-accent)' }}
                >
                  Next: Final Confirmation <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            )}

            {stepperStep === 3 && (
              <div className="mt-5 space-y-3">
                <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: 'var(--aura-panel-alt)' }}>
                  Vendor: <strong>{spotlight.vendor}</strong> • Warranty: <strong>{spotlight.warranty}</strong> • Delivery: <strong>{spotlight.deliveryDays} day(s)</strong>
                </p>
                <button
                  type="button"
                  onClick={() => handleSelectProduct(spotlight)}
                  className="aura-target inline-flex w-full items-center justify-center gap-2 rounded-2xl text-sm font-bold text-white cursor-pointer"
                  style={{ backgroundColor: 'var(--aura-accent)' }}
                >
                  <CheckCircle2 className="h-5 w-5" />
                  {selectedId === spotlight.id ? 'Decision Confirmed!' : `Confirm ${spotlight.name}`}
                </button>
              </div>
            )}

            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={() => setShowAllOverwhelmed((v) => !v)}
                className="text-xs font-semibold underline opacity-75 hover:opacity-100 cursor-pointer"
              >
                {showAllOverwhelmed ? 'Hide extra alternatives' : 'Need another option? Reveal 2 backups'}
              </button>
            </div>
          </div>
        </section>
      )}

      {/* STRUCTURAL RENDERER 2: FATIGUED -> Minimalist Calm List + Low-Friction Linear Stack */}
      {result && activeState === 'fatigued' && (
        <section className="mx-auto max-w-3xl space-y-4">
          {items.map((item, idx) => (
            <div
              key={item.id}
              className="flex flex-col justify-between gap-4 rounded-3xl border p-6 shadow-sm sm:flex-row sm:items-center"
              style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
            >
              <div className="space-y-1.5">
                <span className="text-xs font-bold uppercase" style={{ color: 'var(--aura-accent)' }}>
                  Calm Pick #{idx + 1} • {item.vendor}
                </span>
                <h3 className="text-lg font-bold">{item.name}</h3>
                <p className="aura-readable" style={{ color: 'var(--aura-muted)' }}>
                  {item.bestFor} — {item.pros[0]}
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <span className="text-lg font-bold" style={{ color: 'var(--aura-accent)' }}>
                  {item.pricePkr.toLocaleString()} PKR
                </span>
                <button
                  type="button"
                  onClick={() => handleSelectProduct(item)}
                  className="aura-target rounded-xl text-xs font-bold text-white cursor-pointer"
                  style={{ backgroundColor: 'var(--aura-accent)' }}
                >
                  {selectedId === item.id ? 'Selected' : 'Select Calmly'}
                </button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* STRUCTURAL RENDERER 3: ENERGIZED -> Visual Bento & Card Grid + Bento Box Facets */}
      {result && activeState === 'energized' && (
        <section className="space-y-4">
          <div
            className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border p-3"
            style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
          >
            <div className="flex flex-wrap gap-1.5">
              {['all', 'smartphone', 'headphones', 'laptop', 'monitor', 'daraz', 'priceoye'].map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => {
                    onLogEvent?.('filter_change', f);
                    setFacetCategory(f);
                  }}
                  className="rounded-xl px-3 py-1.5 text-xs font-semibold capitalize cursor-pointer"
                  style={{
                    backgroundColor: facetCategory === f ? 'var(--aura-accent)' : 'var(--aura-panel-alt)',
                    color: facetCategory === f ? '#FFFFFF' : 'var(--aura-text)',
                  }}
                >
                  {f}
                </button>
              ))}
            </div>
            <span className="text-xs font-medium" style={{ color: 'var(--aura-muted)' }}>
              Pinned for compare: <strong>{compareIds.length}/3</strong>
            </span>
          </div>

          {compareIds.length >= 2 && (
            <div
              className="overflow-x-auto rounded-2xl border p-4"
              style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-accent)' }}
            >
              <div className="mb-2 text-xs font-bold" style={{ color: 'var(--aura-accent)' }}>
                Live Side-by-Side Bento Comparison
              </div>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--aura-border)' }}>
                    <th className="py-1.5">Model</th>
                    <th>Price</th>
                    <th>Rating</th>
                    <th>Battery</th>
                    <th>Vendor</th>
                  </tr>
                </thead>
                <tbody>
                  {items
                    .filter((p) => compareIds.includes(p.id))
                    .map((p) => (
                      <tr key={p.id} className="border-b last:border-none" style={{ borderColor: 'var(--aura-border)' }}>
                        <td className="py-2 font-bold">{p.name}</td>
                        <td>{p.pricePkr.toLocaleString()} PKR</td>
                        <td>{p.rating}/5</td>
                        <td>{p.batteryHours > 0 ? `${p.batteryHours}h` : 'AC'}</td>
                        <td>{p.vendor}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            {filteredItems.map((item) => renderProductCard(item))}
          </div>
        </section>
      )}

      {/* STRUCTURAL RENDERER 4: DISORIENTED -> Guided Z-Pattern & Anchor + Breadcrumbs */}
      {result && activeState === 'disoriented' && (
        <section className="space-y-4">
          <div
            className="flex flex-wrap items-center gap-2 rounded-2xl border px-4 py-3 text-xs"
            style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-accent)' }}
          >
            <span className="font-bold" style={{ color: 'var(--aura-accent)' }}>Goal Breadcrumbs:</span>
            {result.criteriaTags.map((tag) => (
              <span
                key={tag}
                className="rounded-lg px-2.5 py-1 font-semibold"
                style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
              >
                {tag}
              </span>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {items.map((item) => renderProductCard(item))}
          </div>
        </section>
      )}

      {/* STRUCTURAL RENDERER 5: FOCUSED -> Focused & Spotlight + Bento Box */}
      {result && activeState === 'focused' && (
        <section className="space-y-5">
          {spotlight && (
            <div
              className="grid gap-5 rounded-3xl border p-6 shadow-sm lg:grid-cols-12"
              style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
            >
              <div className="space-y-2 lg:col-span-7">
                <span
                  className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold"
                  style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
                >
                  <Award className="h-3.5 w-3.5" /> Spotlight Top Match
                </span>
                <h3 className="text-2xl font-bold">{spotlight.name}</h3>
                <p className="text-sm" style={{ color: 'var(--aura-muted)' }}>
                  {spotlight.bestFor} • {spotlight.warranty} • {spotlight.vendor}
                </p>
                <div className="flex flex-wrap gap-2 pt-2">
                  {spotlight.pros.map((p, i) => (
                    <span
                      key={i}
                      className="rounded-lg px-2.5 py-1 text-xs font-medium"
                      style={{ backgroundColor: 'var(--aura-panel-alt)' }}
                    >
                      ✓ {p}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex flex-col justify-between gap-3 rounded-2xl border p-4 lg:col-span-5" style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}>
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold" style={{ color: 'var(--aura-accent)' }}>
                    {spotlight.pricePkr.toLocaleString()} PKR
                  </span>
                  <span className="inline-flex items-center gap-1 text-sm font-bold">
                    <BatteryCharging className="h-4 w-4" /> {spotlight.batteryHours > 0 ? `${spotlight.batteryHours}h` : 'AC'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleSelectProduct(spotlight)}
                  className="aura-target inline-flex items-center justify-center gap-1.5 rounded-xl text-xs font-bold text-white cursor-pointer"
                  style={{ backgroundColor: 'var(--aura-accent)' }}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {selectedId === spotlight.id ? 'Selected Decision' : 'Choose Spotlight Match'}
                </button>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {items.slice(1).map((item) => renderProductCard(item))}
          </div>
        </section>
      )}

      {/* STRUCTURAL RENDERER 6: PROMPT-ONLY CONTROL -> Classic Dense Z-Pattern Grid + Horizontal Top-Down */}
      {result && isControl && (
        <section className="space-y-4">
          <div
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border px-4 py-2 text-xs"
            style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
          >
            <div className="flex flex-wrap gap-3 font-semibold">
              {['all', 'smartphone', 'headphones', 'laptop', 'monitor'].map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => {
                    onLogEvent?.('filter_change', cat);
                    setFacetCategory(cat);
                  }}
                  className="capitalize underline-offset-4 hover:underline cursor-pointer"
                  style={{ color: facetCategory === cat ? 'var(--aura-accent)' : 'var(--aura-muted)' }}
                >
                  {cat}
                </button>
              ))}
            </div>
            <span style={{ color: 'var(--aura-muted)' }}>
              Showing all {filteredItems.length} catalog items (Standard Horizontal Top-Down Nav)
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {filteredItems.map((item) => renderProductCard(item, true))}
          </div>
        </section>
      )}

      {/* Cross-Emotion Same-Prompt Comparison Modal */}
      {compareModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div
            className="max-h-[88vh] w-full max-w-5xl overflow-y-auto rounded-3xl border p-6 shadow-2xl"
            style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
          >
            <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: 'var(--aura-border)' }}>
              <div>
                <h2 className="text-base font-bold">
                  Same-Prompt Divergence Proof: &ldquo;{prompt}&rdquo;
                </h2>
                <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                  Proves how an Emotional AI Agent transforms Visual Type, Nav Type, and decision load for the exact same prompt.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCompareModalOpen(false)}
                className="rounded-lg p-1.5 hover:opacity-75 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {comparing ? (
              <p className="py-10 text-center text-sm">Synthesizing comparisons...</p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'var(--aura-border)' }}>
                      <th className="py-2 pr-3">Condition / Emotion</th>
                      <th className="py-2 pr-3">Visual Type</th>
                      <th className="py-2 pr-3">Nav Type</th>
                      <th className="py-2 pr-3">Cards</th>
                      <th className="py-2">Generated Agent Output</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisons.map((row, idx) => (
                      <tr key={idx} className="border-b align-top" style={{ borderColor: 'var(--aura-border)' }}>
                        <td className="py-3 pr-3 font-bold">{row.label}</td>
                        <td className="py-3 pr-3 font-medium" style={{ color: 'var(--aura-accent)' }}>
                          {row.visualType}
                        </td>
                        <td className="py-3 pr-3">{row.navType}</td>
                        <td className="font-mono-code py-3 pr-3 font-bold">{row.visibleCount}</td>
                        <td className="py-3">
                          <div className="font-bold">{row.headline}</div>
                          <div className="mt-0.5" style={{ color: 'var(--aura-muted)' }}>{row.message}</div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
