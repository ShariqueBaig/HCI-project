import { useState } from 'react';
import { Bot, Sparkles } from 'lucide-react';
import type {
  AgentResult,
  ExperimentCondition,
  TelemetryData,
  UIComponentNode,
  UISchema,
  WorkspaceData,
} from '../types/aura';
import { AdaptiveFocusTimer } from './widgets/AdaptiveFocusTimer';
import { ContextAnchorBanner } from './widgets/ContextAnchorBanner';
import { DeepDocumentEditor } from './widgets/DeepDocumentEditor';
import { DivergentIdeaCanvas } from './widgets/DivergentIdeaCanvas';
import { HydrationStretchCard } from './widgets/HydrationStretchCard';
import { QuickWinDeckWidget } from './widgets/QuickWinDeckWidget';
import { SomaticResetWidget } from './widgets/SomaticResetWidget';
import { TaskQueuePanel } from './widgets/TaskQueuePanel';
import { TaskTriagerWidget } from './widgets/TaskTriagerWidget';

interface GenerativeWorkspaceProps {
  schema: UISchema;
  workspace: WorkspaceData;
  telemetry: TelemetryData;
  condition: ExperimentCondition;
  sessionId: string | null;
  actions: {
    addTask: (title: string, priority: 'high' | 'medium' | 'low', minutes: number, category: string) => void;
    updateTask: (id: string, patch: Record<string, unknown>) => void;
    toggleMicroStep: (taskId: string, stepId: string) => void;
    deleteTask: (id: string) => void;
    addNote: (title: string, content?: string) => Promise<any>;
    updateNote: (id: string, title?: string, content?: string) => Promise<void>;
    addIdea: (text: string, tag: string) => void;
    deleteIdea: (id: string) => void;
    promoteIdea: (id: string) => void;
  };
}

export function GenerativeWorkspace({
  schema,
  workspace,
  telemetry,
  condition,
  sessionId,
  actions,
}: GenerativeWorkspaceProps) {
  const [wsPrompt, setWsPrompt] = useState('What should I focus on next given my current mood?');
  const [agentOut, setAgentOut] = useState<AgentResult | null>(null);
  const [asking, setAsking] = useState(false);

  const askWorkspaceAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wsPrompt.trim()) return;
    setAsking(true);
    try {
      const res = await fetch('/api/agent/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: wsPrompt,
          scenario: 'workspace',
          condition,
          session_id: sessionId,
        }),
      });
      const data = await res.json();
      if (data.result) setAgentOut(data.result);
    } finally {
      setAsking(false);
    }
  };
  const renderNode = (node: UIComponentNode) => {
    const props = node.props ?? {};
    switch (node.type) {
      case 'TaskTriagerWidget':
        return (
          <TaskTriagerWidget
            key={node.id}
            task={(props.task as any) ?? null}
            hiddenTaskCount={Number(props.hiddenTaskCount ?? 0)}
            onCompleteTask={(id) => actions.updateTask(id, { completed: true })}
            onToggleMicroStep={actions.toggleMicroStep}
          />
        );
      case 'SomaticResetWidget':
        return <SomaticResetWidget key={node.id} />;
      case 'QuickWinDeckWidget':
        return (
          <QuickWinDeckWidget
            key={node.id}
            tasks={(props.quickTasks as any[]) ?? []}
            onCompleteTask={(id) => actions.updateTask(id, { completed: true })}
          />
        );
      case 'HydrationStretchCard':
        return <HydrationStretchCard key={node.id} />;
      case 'DeepDocumentEditor':
        return (
          <DeepDocumentEditor
            key={node.id}
            notes={workspace.notes}
            collapsible={Boolean(props.collapsible)}
            defaultCollapsed={Boolean(props.defaultCollapsed)}
            voiceAssist={Boolean(props.voiceAssist)}
            onSaveNote={actions.updateNote}
            onAddNote={actions.addNote}
          />
        );
      case 'TaskQueuePanel':
        return (
          <TaskQueuePanel
            key={node.id}
            tasks={workspace.tasks}
            viewMode={(props.viewMode as 'compact' | 'kanban' | 'guided') ?? 'compact'}
            maxVisible={Number(props.maxVisible ?? 20)}
            onAddTask={actions.addTask}
            onToggleTask={(id, completed) => actions.updateTask(id, { completed })}
            onDeleteTask={actions.deleteTask}
          />
        );
      case 'DivergentIdeaCanvas':
        return (
          <DivergentIdeaCanvas
            key={node.id}
            ideas={workspace.ideas}
            compact={Boolean(props.compact)}
            onAddIdea={actions.addIdea}
            onDeleteIdea={actions.deleteIdea}
            onPromoteIdea={actions.promoteIdea}
          />
        );
      case 'ContextAnchorBanner':
        return (
          <ContextAnchorBanner
            key={node.id}
            activeGoal={String(props.activeGoal ?? '')}
            lastNoteTitle={String(props.lastNoteTitle ?? '')}
            lastNoteExcerpt={String(props.lastNoteExcerpt ?? '')}
            completedCount={Number(props.completedCount ?? 0)}
            totalCount={Number(props.totalCount ?? 0)}
          />
        );
      case 'AdaptiveFocusTimer':
        return (
          <AdaptiveFocusTimer
            key={node.id}
            preset={schema.interaction.timerPreset}
          />
        );
      default:
        return null;
    }
  };

  const byRegion = (region: string) =>
    schema.components.filter((c) => c.region === region).map(renderNode);

  const topology = condition === 'prompt_only_control' ? 'tri-pane-studio' : schema.layout.topology;

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      {/* Compact Emotional AI Workspace Prompt Bar */}
      <section
        className="mb-5 rounded-2xl border p-3.5 shadow-sm"
        style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      >
        <form onSubmit={askWorkspaceAgent} className="flex flex-wrap items-center gap-2">
          <Bot className="h-4 w-4 shrink-0" style={{ color: 'var(--aura-accent)' }} />
          <input
            type="text"
            value={wsPrompt}
            onChange={(e) => setWsPrompt(e.target.value)}
            placeholder="Ask the Emotional Workspace Agent..."
            className="min-w-[200px] flex-1 rounded-xl border px-3 py-1.5 text-xs outline-none"
            style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
          />
          <button
            type="submit"
            disabled={asking}
            className="inline-flex items-center gap-1 rounded-xl px-3 py-1.5 text-xs font-bold text-white cursor-pointer"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            <Sparkles className="h-3.5 w-3.5" />
            {asking ? 'Thinking...' : 'Ask Workspace Agent'}
          </button>
        </form>

        {agentOut && (
          <div className="mt-3 rounded-xl border p-3 text-xs" style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}>
            <div className="flex flex-wrap items-center gap-2 font-bold">
              <span>{agentOut.headline}</span>
              <span className="rounded-full px-2 py-0.5 text-[10px]" style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}>
                {agentOut.visualType} • {agentOut.navType}
              </span>
            </div>
            <p className="mt-1" style={{ color: 'var(--aura-muted)' }}>{agentOut.message}</p>
          </div>
        )}
      </section>

      {/* Mode Context Header */}
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">
            {condition === 'prompt_only_control' ? 'Standard Study Workspace (Control)' : schema.modeName}
          </h1>
          <p className="text-sm" style={{ color: 'var(--aura-muted)' }}>
            {condition === 'prompt_only_control'
              ? 'Static tri-pane baseline ignoring live emotion (' + telemetry.active_state + ').'
              : schema.modeSubtitle}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {schema.hciRationale.slice(0, 2).map((r, idx) => (
            <span
              key={idx}
              className="rounded-full border px-2.5 py-1 text-[11px] font-medium"
              style={{
                borderColor: 'var(--aura-border)',
                backgroundColor: 'var(--aura-panel)',
                color: 'var(--aura-muted)',
              }}
            >
              {r.principle}
            </span>
          ))}
        </div>
      </div>

      {/* Structural Topologies */}
      {topology === 'single-focus-tunnel' && (
        <div className="mx-auto max-w-3xl space-y-5">
          {byRegion('tunnel-primary')}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {byRegion('tunnel-secondary')}
          </div>
          {byRegion('tunnel-collapsible')}
        </div>
      )}

      {topology === 'low-friction-deck' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-7">{byRegion('main-left')}</div>
            <div className="space-y-6 lg:col-span-5">{byRegion('main-right')}</div>
          </div>
          {byRegion('bottom-full')}
        </div>
      )}

      {topology === 'divergent-board' && (
        <div className="space-y-6">
          {byRegion('hero-top')}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-8">{byRegion('main-left')}</div>
            <div className="space-y-6 lg:col-span-4">{byRegion('sidebar-right')}</div>
          </div>
        </div>
      )}

      {topology === 'orientation-split' && (
        <div className="space-y-6">
          {byRegion('hero-top')}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-4">{byRegion('main-left')}</div>
            <div className="space-y-6 lg:col-span-5">{byRegion('main-right')}</div>
            <div className="space-y-6 lg:col-span-3">{byRegion('sidebar-right')}</div>
          </div>
        </div>
      )}

      {topology === 'tri-pane-studio' && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          <div className="space-y-5 lg:col-span-4">{byRegion('studio-left')}</div>
          <div className="space-y-5 lg:col-span-5">{byRegion('studio-center')}</div>
          <div className="space-y-5 lg:col-span-3">{byRegion('studio-right')}</div>
        </div>
      )}
    </main>
  );
}
