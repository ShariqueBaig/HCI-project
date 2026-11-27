import { useEffect, useState } from 'react';
import {
  Activity,
  Bot,
  BrainCircuit,
  Camera,
  CameraOff,
  CheckSquare,
  FlaskConical,
  RotateCcw,
  Shield,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
} from 'lucide-react';
import type {
  ActiveTrial,
  AgencyMode,
  ExperimentCondition,
  HciState,
  ScenarioType,
  TelemetryData,
  UISchema,
} from '../types/aura';
import type { BehavioralCounters } from '../hooks/useBehavioralTelemetry';

interface TopBarProps {
  telemetry: TelemetryData;
  schema: UISchema;
  connected: boolean;
  scenario: ScenarioType;
  condition: ExperimentCondition;
  activeTrial: ActiveTrial | null;
  counters: BehavioralCounters;
  visualTypeLabel: string;
  navTypeLabel: string;
  onChangeScenario: (s: ScenarioType) => void;
  onChangeCondition: (c: ExperimentCondition) => void;
  onFinishTrial: () => void;
  onToggleCamera: () => void;
  onChangeAgency: (mode: AgencyMode) => void;
  onSimulate: (state: HciState | null) => void;
  onUndo: () => void;
  onOpenInspector: () => void;
}

const STATE_OPTIONS: Array<{ id: HciState; label: string }> = [
  { id: 'focused', label: 'Focused' },
  { id: 'overwhelmed', label: 'Overwhelmed' },
  { id: 'fatigued', label: 'Fatigued' },
  { id: 'energized', label: 'Energized' },
  { id: 'disoriented', label: 'Disoriented' },
];

export function TopBar({
  telemetry,
  schema,
  connected,
  scenario,
  condition,
  activeTrial,
  counters,
  visualTypeLabel,
  navTypeLabel,
  onChangeScenario,
  onChangeCondition,
  onFinishTrial,
  onToggleCamera,
  onChangeAgency,
  onSimulate,
  onUndo,
  onOpenInspector,
}: TopBarProps) {
  const isMinimalChrome = condition === 'emotional_agent' && schema.layout.navigationChrome === 'minimal';
  const dwellPct = Math.round(telemetry.dwell_progress * 100);
  const candidateDiffers = telemetry.candidate_state !== telemetry.active_state;

  const [elapsedSec, setElapsedSec] = useState(0);
  useEffect(() => {
    if (!activeTrial) {
      setElapsedSec(0);
      return;
    }
    const tick = () => setElapsedSec(Math.floor((Date.now() - activeTrial.startedAtMs) / 1000));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [activeTrial]);

  return (
    <header
      className="sticky top-0 z-30 border-b backdrop-blur-md transition-colors duration-300"
      style={{
        backgroundColor: 'color-mix(in srgb, var(--aura-panel) 92%, transparent)',
        borderColor: 'var(--aura-border)',
      }}
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
        {/* Brand + Active Visual/Nav Taxonomy */}
        <div className="flex items-center gap-3">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl font-bold text-white shadow-sm"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            <BrainCircuit className="h-5 w-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-bold tracking-tight">AURA</span>
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold"
                style={{
                  backgroundColor: 'var(--aura-accent-soft)',
                  color: 'var(--aura-accent)',
                }}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${connected ? 'animate-pulse' : ''}`}
                  style={{ backgroundColor: connected ? 'var(--aura-accent)' : '#94A3B8' }}
                />
                {condition === 'prompt_only_control' ? 'Prompt-Only Control' : schema.modeName}
              </span>
              {condition === 'emotional_agent' && schema.interaction.notificationPolicy === 'silent-shield' && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
                  <Shield className="h-3 w-3" /> Silent Shield
                </span>
              )}
            </div>
            <p className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>
              Visual: <strong className="font-medium">{visualTypeLabel}</strong> • Nav: <strong className="font-medium">{navTypeLabel}</strong>
              {candidateDiffers && (
                <span className="ml-2 text-amber-700">
                  • Sensing <strong>{telemetry.candidate_state}</strong> ({dwellPct}%)
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Scenario Tabs: Commerce Agent | Study Workspace | HCI Lab & Data */}
        <nav
          aria-label="AURA Scenario Switcher"
          className="flex items-center rounded-xl border p-0.5 text-xs"
          style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
        >
          {[
            { id: 'commerce' as ScenarioType, label: 'Commerce Agent', icon: ShoppingBag },
            { id: 'workspace' as ScenarioType, label: 'Study Workspace', icon: Bot },
            { id: 'research' as ScenarioType, label: 'HCI Lab & Data', icon: FlaskConical },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = scenario === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onChangeScenario(tab.id)}
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-semibold transition-colors cursor-pointer"
                style={{
                  backgroundColor: active ? 'var(--aura-accent)' : 'transparent',
                  color: active ? '#FFFFFF' : 'var(--aura-text)',
                }}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Condition A/B Toggle */}
          <div
            className="flex items-center rounded-xl border p-0.5 text-xs"
            style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel)' }}
            title="Toggle between Treatment (Emotional AI Agent) and Control (Prompt-Only Static UI)"
          >
            <button
              type="button"
              onClick={() => onChangeCondition('emotional_agent')}
              className="rounded-lg px-2 py-1 font-semibold cursor-pointer"
              style={{
                backgroundColor: condition === 'emotional_agent' ? 'var(--aura-accent-soft)' : 'transparent',
                color: condition === 'emotional_agent' ? 'var(--aura-accent)' : 'var(--aura-muted)',
              }}
            >
              Emotional AI
            </button>
            <button
              type="button"
              onClick={() => onChangeCondition('prompt_only_control')}
              className="rounded-lg px-2 py-1 font-semibold cursor-pointer"
              style={{
                backgroundColor: condition === 'prompt_only_control' ? '#E2E8F0' : 'transparent',
                color: condition === 'prompt_only_control' ? '#0F172A' : 'var(--aura-muted)',
              }}
            >
              Control
            </button>
          </div>

          {/* State Simulator */}
          {!isMinimalChrome && (
            <div
              className="hidden items-center gap-1 rounded-xl border p-1 xl:flex"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
            >
              {STATE_OPTIONS.map((opt) => {
                const active = telemetry.active_state === opt.id;
                const simulated = telemetry.simulated_state === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => onSimulate(simulated ? null : opt.id)}
                    className="rounded-lg px-2 py-1 text-xs font-medium transition-all cursor-pointer"
                    style={{
                      backgroundColor: active ? 'var(--aura-accent)' : 'transparent',
                      color: active ? '#FFFFFF' : 'var(--aura-muted)',
                    }}
                  >
                    {opt.label}
                  </button>
                );
              })}
              {telemetry.simulated_state && (
                <button
                  type="button"
                  onClick={() => onSimulate(null)}
                  className="rounded-lg px-2 py-1 text-[11px] font-semibold text-amber-700 hover:bg-amber-100 cursor-pointer"
                >
                  Clear Sim
                </button>
              )}
            </div>
          )}

          <select
            aria-label="Affective state override"
            value={telemetry.simulated_state ?? ''}
            onChange={(e) => onSimulate((e.target.value || null) as HciState | null)}
            className={`rounded-lg border px-2 py-1.5 text-xs font-medium ${isMinimalChrome ? '' : 'xl:hidden'}`}
            style={{
              borderColor: 'var(--aura-border)',
              backgroundColor: 'var(--aura-panel)',
              color: 'var(--aura-text)',
            }}
          >
            <option value="">Live CV ({telemetry.active_state})</option>
            {STATE_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                Simulate: {opt.label}
              </option>
            ))}
          </select>

          {/* Agency Mode Selector */}
          <div
            className="flex items-center rounded-xl border p-0.5 text-xs"
            style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel)' }}
          >
            {(['copilot', 'autonomous', 'manual'] as AgencyMode[]).map((mode) => {
              const selected = telemetry.agency_mode === mode;
              return (
                <button
                  key={mode}
                  type="button"
                  onClick={() => onChangeAgency(mode)}
                  className="rounded-lg px-2 py-1 capitalize font-medium transition-colors cursor-pointer"
                  style={{
                    backgroundColor: selected ? 'var(--aura-accent-soft)' : 'transparent',
                    color: selected ? 'var(--aura-accent)' : 'var(--aura-muted)',
                  }}
                >
                  {mode === 'copilot' ? 'Co-Pilot' : mode}
                </button>
              );
            })}
          </div>

          {telemetry.previous_state && telemetry.previous_state !== telemetry.active_state && (
            <button
              type="button"
              onClick={onUndo}
              className="aura-target inline-flex items-center gap-1 rounded-xl border text-xs font-semibold cursor-pointer"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel)' }}
            >
              <RotateCcw className="h-3.5 w-3.5" /> Undo
            </button>
          )}

          <button
            type="button"
            onClick={onToggleCamera}
            className="aura-target inline-flex items-center gap-1.5 rounded-xl border text-xs font-semibold cursor-pointer"
            style={{
              borderColor: telemetry.camera_active ? 'var(--aura-accent)' : 'var(--aura-border)',
              backgroundColor: telemetry.camera_active ? 'var(--aura-accent-soft)' : 'var(--aura-panel)',
              color: telemetry.camera_active ? 'var(--aura-accent)' : 'var(--aura-text)',
            }}
          >
            {telemetry.camera_active ? <Camera className="h-3.5 w-3.5" /> : <CameraOff className="h-3.5 w-3.5" />}
            <span>{telemetry.camera_active ? 'Cam Live' : 'Cam Off'}</span>
          </button>

          <button
            type="button"
            onClick={onOpenInspector}
            className="aura-target inline-flex items-center gap-1.5 rounded-xl text-xs font-semibold text-white shadow-sm cursor-pointer"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            {telemetry.face_detected ? <Activity className="h-3.5 w-3.5" /> : <SlidersHorizontal className="h-3.5 w-3.5" />}
            <span>XAI &amp; CV</span>
            <Sparkles className="h-3 w-3 opacity-80" />
          </button>
        </div>
      </div>

      {/* Active Timed Experiment HUD Strip */}
      {activeTrial && (
        <div
          className="border-t px-4 py-2 text-xs sm:px-6"
          style={{ backgroundColor: 'var(--aura-accent-soft)', borderColor: 'var(--aura-border)' }}
        >
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-bold" style={{ color: 'var(--aura-accent)' }}>
                TRIAL ACTIVE: {activeTrial.participantId}
              </span>
              <span className="rounded bg-white/70 px-2 py-0.5 font-semibold text-slate-800">
                {activeTrial.condition === 'emotional_agent' ? 'Emotional AI Agent' : 'Prompt-Only Control'}
              </span>
              <span className="font-mono-code">
                {elapsedSec}s • {counters.clicks} clicks • {counters.rageClicks} rage • {counters.hesitations} hesitations
              </span>
            </div>
            <button
              type="button"
              onClick={onFinishTrial}
              className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1 font-bold text-white shadow-sm cursor-pointer"
              style={{ backgroundColor: 'var(--aura-accent)' }}
            >
              <CheckSquare className="h-3.5 w-3.5" /> Finish &amp; Rate (SUS / SAM)
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
