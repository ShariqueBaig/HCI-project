import { useEffect, useState } from 'react';
import { CommerceAgentView } from './components/CommerceAgentView';
import { CoPilotProposalBar } from './components/CoPilotProposalBar';
import { GenerativeWorkspace } from './components/GenerativeWorkspace';
import { HciResearchLab } from './components/HciResearchLab';
import { PostTaskSurveyModal } from './components/PostTaskSurveyModal';
import { TopBar } from './components/TopBar';
import { XaiInspectorDrawer } from './components/XaiInspectorDrawer';
import { useAuraSocket } from './hooks/useAuraSocket';
import { useBehavioralTelemetry } from './hooks/useBehavioralTelemetry';
import type { ActiveTrial, ExperimentCondition, ScenarioType } from './types/aura';

export default function App() {
  const {
    workspace,
    telemetry,
    schema,
    models,
    frameB64,
    visionLatencyMs,
    connected,
    error,
    actions,
  } = useAuraSocket();

  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [scenario, setScenario] = useState<ScenarioType>('commerce');
  const [condition, setCondition] = useState<ExperimentCondition>('emotional_agent');
  const [activeTrial, setActiveTrial] = useState<ActiveTrial | null>(null);
  const [surveyOpen, setSurveyOpen] = useState(false);
  const [commerceMeta, setCommerceMeta] = useState<{ visual: string; nav: string }>({
    visual: 'Focused & Spotlight',
    nav: 'Bento Box',
  });

  const { counters, logEvent } = useBehavioralTelemetry(activeTrial?.sessionId ?? null);

  // Sync adaptive surface tokens + HCI scaling rules onto document root
  useEffect(() => {
    if (!schema) return;
    const root = document.documentElement;
    const isControl = condition === 'prompt_only_control';
    const t = schema.surfaceTokens;

    if (isControl) {
      root.style.setProperty('--aura-canvas', '#F8FAFC');
      root.style.setProperty('--aura-panel', '#FFFFFF');
      root.style.setProperty('--aura-panel-alt', '#F1F5F9');
      root.style.setProperty('--aura-accent', '#2563EB');
      root.style.setProperty('--aura-accent-soft', '#DBEAFE');
      root.style.setProperty('--aura-text', '#0F172A');
      root.style.setProperty('--aura-muted', '#475569');
      root.style.setProperty('--aura-border', '#CBD5E1');
      root.style.setProperty('--aura-target-scale', '1');
      root.style.setProperty('--aura-type-scale', '1');
      root.style.setProperty('--aura-line-height', '1.55');
      return;
    }

    root.style.setProperty('--aura-canvas', t.canvasBg);
    root.style.setProperty('--aura-panel', t.panelBg);
    root.style.setProperty('--aura-panel-alt', t.panelAltBg);
    root.style.setProperty('--aura-accent', t.accent);
    root.style.setProperty('--aura-accent-soft', t.accentSoft);
    root.style.setProperty('--aura-text', t.textPrimary);
    root.style.setProperty('--aura-muted', t.textMuted);
    root.style.setProperty('--aura-border', t.border);
    root.style.setProperty('--aura-target-scale', String(schema.interaction.targetScale));
    root.style.setProperty('--aura-type-scale', String(schema.interaction.typographyScale));
    root.style.setProperty('--aura-line-height', String(schema.interaction.lineHeight));
  }, [schema, condition]);

  if (!workspace || !telemetry || !schema) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="h-9 w-9 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        <p className="text-sm font-semibold">Initializing AURA Affective Generative UI...</p>
        {error && <p className="text-xs text-red-600">Backend connection error: {error}</p>}
      </div>
    );
  }

  const startTrial = async (params: {
    participantId: string;
    scenario: 'commerce' | 'workspace';
    condition: ExperimentCondition;
    taskPrompt: string;
  }) => {
    const res = await fetch('/api/research/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        participant_id: params.participantId,
        scenario: params.scenario,
        condition: params.condition,
        task_prompt: params.taskPrompt,
      }),
    });
    const data = await res.json();
    if (data.session) {
      setCondition(params.condition);
      setScenario(params.scenario);
      setActiveTrial({
        sessionId: data.session.id,
        participantId: params.participantId,
        scenario: params.scenario,
        condition: params.condition,
        taskPrompt: params.taskPrompt,
        startedAtMs: Date.now(),
      });
    }
  };

  const visualLabel =
    condition === 'prompt_only_control'
      ? 'Standard Z-Pattern Grid (Control)'
      : scenario === 'commerce'
        ? commerceMeta.visual
        : schema.layout.visualType ?? 'Focused & Spotlight';

  const navLabel =
    condition === 'prompt_only_control'
      ? 'Horizontal Top-Down (Control)'
      : scenario === 'commerce'
        ? commerceMeta.nav
        : schema.layout.navType ?? 'Bento Box';

  return (
    <div className="min-h-screen pb-14">
      <TopBar
        telemetry={telemetry}
        schema={schema}
        connected={connected}
        scenario={scenario}
        condition={condition}
        activeTrial={activeTrial}
        counters={counters}
        visualTypeLabel={visualLabel}
        navTypeLabel={navLabel}
        onChangeScenario={setScenario}
        onChangeCondition={setCondition}
        onFinishTrial={() => setSurveyOpen(true)}
        onToggleCamera={() => actions.toggleCamera(!telemetry.camera_active)}
        onChangeAgency={(mode) => actions.setAgency(mode)}
        onSimulate={(st) => actions.simulateState(st)}
        onUndo={() => actions.respondProposal('undo')}
        onOpenInspector={() => setInspectorOpen(true)}
      />

      {condition === 'emotional_agent' && telemetry.pending_proposal && scenario !== 'research' && (
        <CoPilotProposalBar
          proposal={telemetry.pending_proposal}
          onAccept={() => actions.respondProposal('accept')}
          onDismiss={() => actions.respondProposal('dismiss')}
        />
      )}

      {scenario === 'commerce' && (
        <CommerceAgentView
          telemetry={telemetry}
          condition={condition}
          sessionId={activeTrial?.sessionId ?? null}
          initialPrompt={activeTrial?.scenario === 'commerce' ? activeTrial.taskPrompt : undefined}
          onLogEvent={logEvent}
          onSchemaMetadataChange={(visual, nav) => setCommerceMeta({ visual, nav })}
        />
      )}

      {scenario === 'workspace' && (
        <GenerativeWorkspace
          schema={schema}
          workspace={workspace}
          telemetry={telemetry}
          condition={condition}
          sessionId={activeTrial?.sessionId ?? null}
          actions={actions}
        />
      )}

      {scenario === 'research' && <HciResearchLab onStartTrial={startTrial} />}

      <PostTaskSurveyModal
        open={surveyOpen}
        trial={activeTrial}
        counters={counters}
        visualType={visualLabel}
        navType={navLabel}
        onClose={() => setSurveyOpen(false)}
        onSubmitted={() => {
          setSurveyOpen(false);
          setActiveTrial(null);
          setScenario('research');
        }}
      />

      <XaiInspectorDrawer
        open={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
        telemetry={telemetry}
        schema={schema}
        models={models}
        frameB64={frameB64}
        visionLatencyMs={visionLatencyMs}
        onToggleCamera={() => actions.toggleCamera(!telemetry.camera_active)}
        onUpdateDwell={(d) => actions.setAgency(telemetry.agency_mode, d)}
      />
    </div>
  );
}
