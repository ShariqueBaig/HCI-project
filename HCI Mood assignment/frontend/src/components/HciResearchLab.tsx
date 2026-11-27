import { useCallback, useEffect, useState } from 'react';
import {
  BarChart3,
  Database,
  Download,
  FlaskConical,
  Play,
  Sparkles,
  Trash2,
} from 'lucide-react';
import type { ExperimentCondition, WhiteboardSummary } from '../types/aura';

interface HciResearchLabProps {
  onStartTrial: (params: {
    participantId: string;
    scenario: 'commerce' | 'workspace';
    condition: ExperimentCondition;
    taskPrompt: string;
  }) => void;
}

const PRESET_TASKS = [
  'Find the best university smartphone under 60,000 PKR with long battery',
  'Compare noise-canceling headphones for quiet studying',
  'Recommend a lightweight laptop for HCI research & coding',
  'Identify #1 priority task and draft a 2-sentence reflection in Notes',
];

export function HciResearchLab({ onStartTrial }: HciResearchLabProps) {
  const [summary, setSummary] = useState<WhiteboardSummary | null>(null);
  const [participantId, setParticipantId] = useState('P-03');
  const [scenario, setScenario] = useState<'commerce' | 'workspace'>('commerce');
  const [condition, setCondition] = useState<ExperimentCondition>('emotional_agent');
  const [taskPrompt, setTaskPrompt] = useState(PRESET_TASKS[0]);

  const loadSummary = useCallback(async () => {
    const res = await fetch('/api/research/whiteboard-table');
    if (res.ok) {
      setSummary(await res.json());
    }
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const seedPilot = async () => {
    const res = await fetch('/api/research/seed-demo', { method: 'POST' });
    const data = await res.json();
    if (data.summary) setSummary(data.summary);
  };

  const clearAll = async () => {
    const res = await fetch('/api/research/sessions', { method: 'DELETE' });
    const data = await res.json();
    if (data.summary) setSummary(data.summary);
  };

  const emoAgg = summary?.aggregates.emotional_agent;
  const ctrlAgg = summary?.aggregates.prompt_only_control;

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
      {/* Header + Start Controlled Trial */}
      <section
        className="rounded-3xl border p-6 shadow-sm"
        style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <FlaskConical className="h-5 w-5" style={{ color: 'var(--aura-accent)' }} />
            <div>
              <h1 className="text-lg font-bold">Empirical HCI Research Lab &amp; ISO 9241-11 Logger</h1>
              <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                Run controlled A/B usability trials comparing Prompt-Only Control vs. Emotional AI Agent, log 1Hz CV + clickstream telemetry, and export CSV datasets.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={seedPilot}
              className="inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold cursor-pointer"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
            >
              <Sparkles className="h-3.5 w-3.5" /> Load Sample Pilot Rows
            </button>
            <button
              type="button"
              onClick={clearAll}
              className="inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold text-rose-700 cursor-pointer"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
            >
              <Trash2 className="h-3.5 w-3.5" /> Clear Study DB
            </button>
          </div>
        </div>

        {/* Trial Runner Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onStartTrial({ participantId, scenario, condition, taskPrompt });
          }}
          className="mt-5 grid grid-cols-1 gap-3 rounded-2xl border p-4 md:grid-cols-12"
          style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
        >
          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] font-bold uppercase" style={{ color: 'var(--aura-muted)' }}>
              Participant ID
            </label>
            <input
              type="text"
              value={participantId}
              onChange={(e) => setParticipantId(e.target.value)}
              className="w-full rounded-xl border px-3 py-2 text-xs font-semibold"
              style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
            />
          </div>

          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] font-bold uppercase" style={{ color: 'var(--aura-muted)' }}>
              Scenario
            </label>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value as 'commerce' | 'workspace')}
              className="w-full rounded-xl border px-2.5 py-2 text-xs font-semibold"
              style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
            >
              <option value="commerce">Commerce Agent</option>
              <option value="workspace">Study Workspace</option>
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="mb-1 block text-[11px] font-bold uppercase" style={{ color: 'var(--aura-muted)' }}>
              Experiment Condition
            </label>
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value as ExperimentCondition)}
              className="w-full rounded-xl border px-2.5 py-2 text-xs font-semibold"
              style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
            >
              <option value="emotional_agent">Treatment: Emotional AI Agent</option>
              <option value="prompt_only_control">Control: Prompt-Only (Static)</option>
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="mb-1 block text-[11px] font-bold uppercase" style={{ color: 'var(--aura-muted)' }}>
              Benchmark Task Prompt
            </label>
            <select
              value={taskPrompt}
              onChange={(e) => setTaskPrompt(e.target.value)}
              className="w-full rounded-xl border px-2.5 py-2 text-xs font-medium"
              style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
            >
              {PRESET_TASKS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div className="flex items-end md:col-span-2">
            <button
              type="submit"
              className="aura-target inline-flex w-full items-center justify-center gap-1.5 rounded-xl text-xs font-bold text-white cursor-pointer"
              style={{ backgroundColor: 'var(--aura-accent)' }}
            >
              <Play className="h-3.5 w-3.5" /> Start Timed Trial
            </button>
          </div>
        </form>
      </section>

      {/* Aggregate A/B Comparison Cards */}
      {summary && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {[
            { title: 'Treatment: Emotional AI Agent', agg: emoAgg, accent: true },
            { title: 'Control: Prompt-Only Baseline', agg: ctrlAgg, accent: false },
          ].map((card) => (
            <div
              key={card.title}
              className="rounded-3xl border p-5 shadow-sm"
              style={{
                backgroundColor: 'var(--aura-panel)',
                borderColor: card.accent ? 'var(--aura-accent)' : 'var(--aura-border)',
              }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <BarChart3 className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
                  {card.title}
                </div>
                <span className="font-mono-code text-xs" style={{ color: 'var(--aura-muted)' }}>
                  n = {card.agg?.count ?? 0} trials
                </span>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                <div className="rounded-2xl p-3" style={{ backgroundColor: 'var(--aura-panel-alt)' }}>
                  <div className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>Efficiency</div>
                  <div className="mt-0.5 text-xl font-bold">{card.agg?.avg_efficiency ?? 0}</div>
                </div>
                <div className="rounded-2xl p-3" style={{ backgroundColor: 'var(--aura-panel-alt)' }}>
                  <div className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>Effectiveness</div>
                  <div className="mt-0.5 text-xl font-bold">{card.agg?.avg_effectiveness ?? 0}%</div>
                </div>
                <div className="rounded-2xl p-3" style={{ backgroundColor: 'var(--aura-panel-alt)' }}>
                  <div className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>Satisfaction (SUS)</div>
                  <div className="mt-0.5 text-xl font-bold" style={{ color: card.accent ? 'var(--aura-accent)' : undefined }}>
                    {card.agg?.avg_satisfaction_sus ?? 0}
                  </div>
                </div>
              </div>

              <div className="font-mono-code mt-3 flex flex-wrap justify-between text-[11px]" style={{ color: 'var(--aura-muted)' }}>
                <span>Mean &Delta;Valence: {(card.agg?.avg_delta_valence ?? 0) >= 0 ? '+' : ''}{card.agg?.avg_delta_valence ?? 0}</span>
                <span>CV–SAM Alignment: {card.agg?.avg_cv_sam_alignment ?? 0}%</span>
                <span>Avg Time: {card.agg?.avg_time_sec ?? 0}s</span>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Classroom Whiteboard Evaluation Table */}
      <section
        className="rounded-3xl border p-6 shadow-sm"
        style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-bold">ISO 9241-11 Whiteboard Evaluation Matrix</h2>
            <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
              Matches class framework: Condition | Emotion Type | Visual Type | Nav Type | Efficiency | Effectiveness | Satisfaction (SUS)
            </p>
          </div>
          <div className="font-mono-code text-xs" style={{ color: 'var(--aura-muted)' }}>
            {summary?.counts.affective_samples ?? 0} 1Hz samples • {summary?.counts.interaction_events ?? 0} behavioral events • {summary?.counts.agent_generations ?? 0} generations
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}>
                <th className="py-2 pr-3">Participant / Condition</th>
                <th className="py-2 pr-3">Emotion Type</th>
                <th className="py-2 pr-3">Visual Type</th>
                <th className="py-2 pr-3">Nav Type</th>
                <th className="py-2 pr-3">Efficiency</th>
                <th className="py-2 pr-3">Effectiveness</th>
                <th className="py-2 pr-3">Satisfaction (SUS)</th>
                <th className="py-2 pr-3">&Delta;Valence</th>
                <th className="py-2">Time / Clicks</th>
              </tr>
            </thead>
            <tbody>
              {!summary || summary.rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center" style={{ color: 'var(--aura-muted)' }}>
                    No completed trials yet. Click <strong>Start Timed Trial</strong> above or <strong>Load Sample Pilot Rows</strong> to inspect the matrix.
                  </td>
                </tr>
              ) : (
                summary.rows.map((row) => (
                  <tr key={row.id} className="border-b last:border-none" style={{ borderColor: 'var(--aura-border)' }}>
                    <td className="py-3 pr-3">
                      <div className="font-bold">{row.participant_id}</div>
                      <span
                        className="inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{
                          backgroundColor: row.condition === 'emotional_agent' ? 'var(--aura-accent-soft)' : '#F1F5F9',
                          color: row.condition === 'emotional_agent' ? 'var(--aura-accent)' : '#475569',
                        }}
                      >
                        {row.condition === 'emotional_agent' ? 'Emotional Agent' : 'Control (Prompt-Only)'}
                      </span>
                    </td>
                    <td className="py-3 pr-3 capitalize font-medium">{row.dominant_emotion}</td>
                    <td className="py-3 pr-3 font-medium">{row.visual_type}</td>
                    <td className="py-3 pr-3">{row.nav_type}</td>
                    <td className="font-mono-code py-3 pr-3 font-bold">{row.efficiency_score}</td>
                    <td className="font-mono-code py-3 pr-3 font-bold">{row.effectiveness_score}%</td>
                    <td className="font-mono-code py-3 pr-3 font-bold" style={{ color: row.satisfaction_sus >= 68 ? '#047857' : '#B91C1C' }}>
                      {row.satisfaction_sus}
                    </td>
                    <td className="font-mono-code py-3 pr-3">
                      {row.delta_valence >= 0 ? '+' : ''}{row.delta_valence.toFixed(2)}
                    </td>
                    <td className="font-mono-code py-3">
                      {row.time_on_task_sec.toFixed(0)}s / {row.click_count}c ({row.rage_click_count} rage)
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Raw Research Dataset Export */}
      <section
        className="rounded-3xl border p-5 shadow-sm"
        style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      >
        <div className="mb-3 flex items-center gap-2 font-bold text-sm">
          <Database className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
          Export Empirical Datasets for Statistical Analysis (SPSS / Python / R)
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { id: 'sessions', label: 'Sessions (ISO 9241-11 + SUS + SAM)' },
            { id: 'samples', label: '1Hz Affective Time-Series' },
            { id: 'events', label: 'Behavioral Friction Events' },
            { id: 'generations', label: 'Agent Prompt Generations' },
          ].map((ds) => (
            <div
              key={ds.id}
              className="flex flex-col justify-between gap-2 rounded-2xl border p-3.5 text-xs"
              style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
            >
              <span className="font-semibold">{ds.label}</span>
              <div className="flex gap-2">
                <a
                  href={`/api/research/export?dataset=${ds.id}&format=csv`}
                  download={`aura_${ds.id}.csv`}
                  className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border px-2 py-1.5 font-semibold"
                  style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel)' }}
                >
                  <Download className="h-3 w-3" /> CSV
                </a>
                <a
                  href={`/api/research/export?dataset=${ds.id}&format=json`}
                  download={`aura_${ds.id}.json`}
                  className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg px-2 py-1.5 font-semibold text-white"
                  style={{ backgroundColor: 'var(--aura-accent)' }}
                >
                  <Download className="h-3 w-3" /> JSON
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
