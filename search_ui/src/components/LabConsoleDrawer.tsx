import {
  Activity, Bell, Brain, Download, FlaskConical, FolderOutput, Lock, Play, ShieldCheck, Sliders, Square, Unlock, Video, X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiGet, apiPost, TOKEN } from '../api';
import { LAB_STATE_LABEL } from '../modes';
import type { AppStatus, HciState, LiveState, StateSnapshot } from '../types';
import { XaiPanel } from './XaiPanel';

interface StudyAudit {
  sessions: number;
  chain_ok: boolean;
  bad_count: number;
  consent: boolean;
  retention_days: number;
  data_root: string;
}

interface ExportResult {
  export_dir: string;
  sessions: number;
  ticks: number;
  searches_rows: number;
  search_events_rows: number;
  tasks_rows: number;
  surveys_rows: number;
}

const SIM_MOODS: HciState[] = ['focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented'];

type Tab = 'study' | 'xai' | 'sim' | 'engine';

const SLIDERS: { key: string; label: string; help: string; min: number; max: number; step: number; unit?: string }[] = [
  { key: 'cov_weight', label: 'Rhythm CoV weight', help: 'Weight of flight-time variability', min: 0, max: 1, step: 0.05 },
  { key: 'error_weight', label: 'Backspace weight', help: 'Weight of deletions/corrections', min: 0, max: 1, step: 0.05 },
  { key: 'smoothing', label: 'EMA smoothing', help: 'Higher responds faster; lower is steadier', min: 0.05, max: 0.5, step: 0.01 },
  { key: 'sensitivity', label: 'Sensitivity', help: 'Multiplier on raw stress score', min: 0.5, max: 3, step: 0.1 },
  { key: 'decay_speed', label: 'Idle recovery speed', help: 'How quickly score drops when idle', min: 0.5, max: 8, step: 0.5 },
  { key: 'bright_calm', label: 'Calm brightness', help: 'Target display % when Calm', min: 10, max: 100, step: 5, unit: '%' },
  { key: 'bright_elev', label: 'Elevated brightness', help: 'Target display % when Elevated', min: 10, max: 100, step: 5, unit: '%' },
  { key: 'temp_elev', label: 'Elevated warmth', help: 'Color temp (Kelvin) when Elevated', min: 2000, max: 6500, step: 100, unit: 'K' },
  { key: 'vol_elev', label: 'Elevated volume', help: 'Audio volume % when Elevated', min: 0, max: 100, step: 5, unit: '%' },
];

export function LabConsoleDrawer({
  open,
  onClose,
  live,
  snap,
  app,
  onRefresh,
  onOpenConsent,
}: {
  open: boolean;
  onClose: () => void;
  live: LiveState | null;
  snap: StateSnapshot | null;
  app: AppStatus | null;
  onRefresh: () => void;
  onOpenConsent: () => void;
}) {
  const [tab, setTab] = useState<Tab>('study');
  const [settings, setSettings] = useState<Record<string, number>>({});
  const [audit, setAudit] = useState<StudyAudit | null>(null);
  const [exportRes, setExportRes] = useState<ExportResult | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiGet<Record<string, number>>('/api/app/settings').then(setSettings).catch(() => undefined);
    apiGet<StudyAudit>('/api/app/study/audit').then(setAudit).catch(() => undefined);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const blinded = Boolean(app?.study.blinded);

  const toggleRecording = async () => {
    setErr(null);
    try {
      if (app?.recording.recording) {
        await apiPost('/api/app/recording/stop', {});
      } else {
        await apiPost('/api/app/recording/start', {});
      }
      onRefresh();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg);
      if (msg.includes('Consent') || msg.includes('Participant')) {
        onOpenConsent();
      }
    }
  };

  const setCondition = async (cond: 'intervention' | 'control') => {
    setErr(null);
    try {
      await apiPost('/api/app/settings', { study_condition: cond });
      onRefresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const updateSlider = async (key: string, val: number) => {
    setSettings((s) => ({ ...s, [key]: val }));
    await apiPost('/api/app/settings', { [key]: val }).catch(() => undefined);
  };

  const runDemo = async (action: 'script' | 'manual' | 'stop' | 'notify', level?: number) => {
    setErr(null);
    try {
      await apiPost('/api/app/demo', { action, level });
      onRefresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <div className="aura-fade-in fixed inset-0 z-50 flex justify-end bg-black/50" role="dialog" aria-modal="true" aria-label="Researcher Lab Console">
      <div
        className="aura-slide-in-right flex h-full w-full max-w-xl flex-col border-l shadow-2xl"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      >
        <header className="flex items-center justify-between gap-2 border-b px-5 py-4" style={{ borderColor: 'var(--aura-border)' }}>
          <div>
            <h2 className="text-base font-semibold">Researcher &amp; Developer Lab</h2>
            <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
              Ctrl+Shift+L · {blinded ? 'Participant Blinded Mode Active' : 'Unlocked for facilitator/dev'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void apiPost(blinded ? '/api/app/lab/unlock' : '/api/app/lab/lock', {}).then(onRefresh)}
              className="aura-target flex items-center gap-1.5 rounded-lg border text-xs"
              style={{ borderColor: 'var(--aura-border-interactive)' }}
            >
              {blinded ? <Unlock size={13} aria-hidden /> : <Lock size={13} aria-hidden />}
              {blinded ? 'Unlock Lab' : 'Lock (Blind UI)'}
            </button>
            <button type="button" onClick={onClose} aria-label="Close Lab Console"
              className="aura-target rounded-lg p-1.5 hover:bg-[var(--aura-surface-elev)]">
              <X size={18} aria-hidden />
            </button>
          </div>
        </header>

        <nav className="flex gap-1 border-b px-5 py-2" aria-label="Lab sections" style={{ borderColor: 'var(--aura-border)' }}>
          {([
            ['study', 'Study', FlaskConical],
            ['xai', 'XAI', Brain],
            ['sim', 'Sim & Demo', Video],
            ['engine', 'Engine', Sliders],
          ] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className="aura-target flex items-center gap-1.5 rounded-lg px-3 text-xs font-medium"
              style={{
                background: tab === id ? 'var(--aura-surface-elev)' : 'transparent',
                color: tab === id ? 'var(--aura-calm)' : 'var(--aura-muted)',
              }}
            >
              <Icon size={13} aria-hidden /> {label}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-auto p-5">
          {err && (
            <p role="alert" className="aura-fade-in mb-4 rounded-xl border p-3 text-xs" style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}>
              {err}
            </p>
          )}

          <div key={tab} className="aura-fade-up">
          {tab === 'study' && (
            <div className="space-y-5">
              <div className="rounded-xl border p-4" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
                  Experimental Condition
                </p>
                <div className="mt-2.5 grid grid-cols-2 gap-2">
                  {([
                    ['intervention', 'Active (B) — State-aware'],
                    ['control', 'Control (A) — Prompt-only'],
                  ] as const).map(([cond, label]) => {
                    const active = app?.study.condition === cond;
                    return (
                      <button
                        key={cond}
                        type="button"
                        disabled={blinded}
                        onClick={() => void setCondition(cond)}
                        className="aura-target rounded-xl border px-3 text-xs font-medium disabled:opacity-50"
                        style={{
                          borderColor: active ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
                          background: active ? 'var(--aura-calm)' : 'var(--aura-surface)',
                          color: active ? 'var(--aura-bg)' : 'var(--aura-text)',
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-xl border p-4" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">Session Recording</p>
                    <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                      {app?.recording.recording
                        ? `Recording (${Math.floor(app.recording.elapsed_s / 60)}m ${app.recording.elapsed_s % 60}s)`
                        : app?.consent.granted
                        ? `Ready (${app.consent.participant_code})`
                        : 'Requires Privacy Consent v4'}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={toggleRecording}
                    className="aura-target flex items-center gap-1.5 rounded-xl px-4 text-xs font-medium"
                    style={{
                      background: app?.recording.recording ? 'var(--aura-elev)' : 'var(--aura-calm)',
                      color: 'var(--aura-bg)',
                    }}
                  >
                    {app?.recording.recording ? <Square size={12} aria-hidden /> : <Play size={12} aria-hidden />}
                    {app?.recording.recording ? 'Stop Recording' : 'Start Recording'}
                  </button>
                </div>
                <p className="mt-3 text-xs" style={{ color: 'var(--aura-subtle)' }}>
                  Starting a recording automatically locks Lab Mode to preserve participant blinding until unlocked or stopped.
                </p>
              </div>

              <div className="rounded-xl border p-4 text-xs" style={{ borderColor: 'var(--aura-border)' }}>
                <p className="font-semibold">Cloud Sync Status</p>
                <p className="mt-1" style={{ color: 'var(--aura-muted)' }}>
                  {app?.consent.cloud_sync_enabled
                    ? `Firebase ready · ${app.consent.pending_uploads} queued · ${app.consent.cloud_status}`
                    : 'Cloud sync disabled (no firebase_config.json / defaults)'}
                </p>
              </div>

              {/* Data Integrity & 1-Click Export */}
              <div className="rounded-xl border p-4 text-xs" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <div className="flex items-center justify-between gap-2">
                  <p className="flex items-center gap-1.5 font-semibold">
                    <ShieldCheck size={14} style={{ color: audit?.chain_ok ? 'var(--aura-calm)' : 'var(--aura-elev)' }} aria-hidden />
                    Data Integrity &amp; Export
                  </p>
                  {audit && (
                    <span style={{ color: audit.chain_ok ? 'var(--aura-calm)' : 'var(--aura-elev)' }}>
                      {audit.chain_ok ? 'SHA-256 Verified ✓' : `${audit.bad_count} bad chain(s)`}
                    </span>
                  )}
                </div>
                <p className="mt-1" style={{ color: 'var(--aura-muted)' }}>
                  {audit
                    ? `${audit.sessions} local session(s) · ${audit.retention_days}-day retention window`
                    : 'Checking session integrity…'}
                </p>

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={exportBusy}
                    onClick={async () => {
                      setExportBusy(true);
                      setErr(null);
                      try {
                        const r = await apiPost<ExportResult>('/api/app/study/export', {});
                        setExportRes(r);
                      } catch (e) {
                        setErr((e as Error).message);
                      } finally {
                        setExportBusy(false);
                      }
                    }}
                    className="aura-target flex items-center gap-1.5 rounded-lg border text-xs font-medium disabled:opacity-50"
                    style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-surface)' }}
                  >
                    <FolderOutput size={13} aria-hidden /> Export CSVs to Folder
                  </button>
                  <button
                    type="button"
                    disabled={exportBusy}
                    onClick={async () => {
                      setExportBusy(true);
                      setErr(null);
                      try {
                        const resp = await fetch('/api/app/study/export.zip', { headers: { 'X-Aura-Token': TOKEN } });
                        if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
                        const blob = await resp.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'aura_study_export.zip';
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (e) {
                        setErr((e as Error).message);
                      } finally {
                        setExportBusy(false);
                      }
                    }}
                    className="aura-target flex items-center gap-1.5 rounded-lg px-3.5 text-xs font-medium disabled:opacity-50"
                    style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
                  >
                    <Download size={13} aria-hidden /> Download .zip
                  </button>
                </div>

                {exportRes && (
                  <p className="mt-2.5 leading-relaxed" style={{ color: 'var(--aura-calm)' }}>
                    Exported {exportRes.sessions} session(s), {exportRes.ticks} tick(s), {exportRes.searches_rows} search(es),{' '}
                    {exportRes.tasks_rows} task event(s), {exportRes.surveys_rows} survey(s) to{' '}
                    <span className="font-mono break-all">{exportRes.export_dir}</span>
                  </p>
                )}
              </div>
            </div>
          )}

          {tab === 'xai' && (
            <XaiPanel snap={snap} embedded />
          )}

          {tab === 'sim' && (
            <div className="space-y-4">
              <div className="rounded-xl border p-4" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <p className="font-medium">Simulate Mood (45 s · Updates Search &amp; Ambient State)</p>
                <p className="mt-0.5 text-xs" style={{ color: 'var(--aura-muted)' }}>
                  Feeds synthetic signals to the fusion model so the active Search layout and XAI rules respond live.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SIM_MOODS.map((m) => {
                    const active = snap?.simulation?.state === m;
                    return (
                      <button
                        key={m}
                        type="button"
                        disabled={blinded}
                        onClick={() => void apiPost('/api/simulate', { state: active ? null : m, duration_s: 45 }).then(onRefresh)}
                        className="aura-target rounded-lg border text-xs font-medium disabled:opacity-50"
                        style={{
                          borderColor: active ? 'var(--aura-mild)' : 'var(--aura-border-interactive)',
                          background: active ? 'var(--aura-mild)' : 'var(--aura-surface)',
                          color: active ? 'var(--aura-bg)' : 'var(--aura-text)',
                        }}
                      >
                        {LAB_STATE_LABEL[m]}
                      </button>
                    );
                  })}
                  {snap?.simulation && (
                    <button
                      type="button"
                      disabled={blinded}
                      onClick={() => void apiPost('/api/simulate', { state: null }).then(onRefresh)}
                      className="aura-target rounded-lg border text-xs disabled:opacity-50"
                      style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}
                    >
                      Stop ({Math.ceil(snap.simulation.remaining_s)}s)
                    </button>
                  )}
                </div>
              </div>

              <div className="rounded-xl border p-4" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <p className="font-medium">Scripted 4-Stage Demo</p>
                <p className="mt-0.5 text-xs" style={{ color: 'var(--aura-muted)' }}>
                  {app?.demo.status} {app?.demo.note ? `· ${app.demo.note}` : ''}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" disabled={blinded} onClick={() => void runDemo('script')}
                    className="aura-target rounded-lg px-3.5 text-xs font-medium disabled:opacity-50"
                    style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}>
                    Run Full Demo
                  </button>
                  <button type="button" disabled={blinded} onClick={() => void runDemo('manual', 10)}
                    className="aura-target rounded-lg border text-xs disabled:opacity-50"
                    style={{ borderColor: 'var(--aura-border-interactive)' }}>
                    Hold Calm
                  </button>
                  <button type="button" disabled={blinded} onClick={() => void runDemo('manual', 48)}
                    className="aura-target rounded-lg border text-xs disabled:opacity-50"
                    style={{ borderColor: 'var(--aura-border-interactive)' }}>
                    Hold Mild
                  </button>
                  <button type="button" disabled={blinded} onClick={() => void runDemo('manual', 85)}
                    className="aura-target rounded-lg border text-xs disabled:opacity-50"
                    style={{ borderColor: 'var(--aura-border-interactive)' }}>
                    Hold Elevated
                  </button>
                  <button type="button" disabled={blinded} onClick={() => void runDemo('stop')}
                    className="aura-target rounded-lg border text-xs disabled:opacity-50"
                    style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}>
                    Stop Demo
                  </button>
                </div>
              </div>

              <div className="rounded-xl border p-4" style={{ borderColor: 'var(--aura-border)' }}>
                <p className="font-medium">Test Silent Focus Mode Notification</p>
                <p className="mt-0.5 text-xs" style={{ color: 'var(--aura-muted)' }}>
                  Sends a simulated notification. When Elevated + Focus Mode are active, it holds silently without popping a toast, then emits a calm digest upon recovery.
                </p>
                <button type="button" onClick={() => void runDemo('notify')}
                  className="aura-target mt-3 flex items-center gap-1.5 rounded-lg border text-xs"
                  style={{ borderColor: 'var(--aura-border-interactive)' }}>
                  <Bell size={13} aria-hidden /> Send Test Notification
                </button>
              </div>
            </div>
          )}

          {tab === 'engine' && (
            <div className="space-y-5">
              <div className="rounded-xl border p-4" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-muted)' }}>
                  <Activity size={13} aria-hidden /> Live Telemetry ({live ? `${live.score.toFixed(0)}/100 · ${live.label}` : '--'})
                </h3>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>Keys/s: <span className="font-semibold tabular-nums">{live?.features.keys_per_second?.toFixed(1) ?? '--'}</span></div>
                  <div>Error rate: <span className="font-semibold tabular-nums">{live?.features.error_rate !== undefined ? `${Math.round(live.features.error_rate * 100)}%` : '--'}</span></div>
                  <div>Dwell: <span className="font-semibold tabular-nums">{live?.features.mean_dwell ? `${Math.round(live.features.mean_dwell * 1000)} ms` : '--'}</span></div>
                  <div>Flight: <span className="font-semibold tabular-nums">{live?.features.mean_flight ? `${Math.round(live.features.mean_flight * 1000)} ms` : '--'}</span></div>
                  <div>Mouse px: <span className="font-semibold tabular-nums">{live?.features.mouse_distance?.toFixed(0) ?? '--'}</span></div>
                  <div>Clicks: <span className="font-semibold tabular-nums">{live?.features.mouse_clicks ?? '--'}</span></div>
                </div>
              </div>

              <div className="space-y-3">
                {SLIDERS.map((s) => (
                  <label key={s.key} className="block rounded-xl border p-3 text-xs" style={{ borderColor: 'var(--aura-border)' }}>
                    <div className="flex justify-between">
                      <span className="font-medium">{s.label}</span>
                      <span className="tabular-nums font-semibold">
                        {settings[s.key] ?? '--'}{s.unit ?? ''}
                      </span>
                    </div>
                    <p className="mb-1.5" style={{ color: 'var(--aura-subtle)' }}>{s.help}</p>
                    <input
                      type="range"
                      disabled={blinded}
                      min={s.min}
                      max={s.max}
                      step={s.step}
                      value={settings[s.key] ?? s.min}
                      onChange={(e) => void updateSlider(s.key, Number(e.target.value))}
                      className="w-full accent-[var(--aura-calm)]"
                    />
                  </label>
                ))}
              </div>
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
