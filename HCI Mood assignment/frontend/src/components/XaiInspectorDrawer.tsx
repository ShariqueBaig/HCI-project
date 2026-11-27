import { useState } from 'react';
import {
  Activity,
  Camera,
  CameraOff,
  Code2,
  Download,
  ImagePlus,
  ShieldCheck,
  X,
} from 'lucide-react';
import type { ModelStatus, TelemetryData, UISchema } from '../types/aura';

interface XaiInspectorDrawerProps {
  open: boolean;
  onClose: () => void;
  telemetry: TelemetryData;
  schema: UISchema;
  models: ModelStatus | null;
  frameB64: string | null;
  visionLatencyMs: number;
  onToggleCamera: () => void;
  onUpdateDwell: (dwellSeconds: number) => void;
}

type TabId = 'cv' | 'schema' | 'photo' | 'analytics';

export function XaiInspectorDrawer({
  open,
  onClose,
  telemetry,
  schema,
  models,
  frameB64,
  visionLatencyMs,
  onToggleCamera,
  onUpdateDwell,
}: XaiInspectorDrawerProps) {
  const [tab, setTab] = useState<TabId>('cv');
  const [photoResult, setPhotoResult] = useState<Record<string, any> | null>(null);
  const [uploading, setUploading] = useState(false);

  if (!open) return null;

  const emotionsSorted = Object.entries(telemetry.emotions).sort((a, b) => b[1] - a[1]);

  const handlePhotoUpload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/api/analyze-image', { method: 'POST', body: fd });
      const data = await res.json();
      setPhotoResult(data);
    } finally {
      setUploading(false);
    }
  };

  // Russell Circumplex SVG coordinates (-1..+1 mapped into 180x180 box)
  const cx = 90 + telemetry.valence * 74;
  const cy = 90 - telemetry.arousal * 74;

  return (
    <aside
      className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l shadow-2xl"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
      aria-label="Explainable AI and HCI Telemetry Inspector"
    >
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-5 py-3.5"
        style={{ borderColor: 'var(--aura-border)' }}
      >
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
          <div>
            <h2 className="text-sm font-bold">Explainable AI &amp; HCI Inspector</h2>
            <p className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>
              {models?.emotion_model?.toUpperCase() ?? 'ONNX'} + YuNet • Local RAM Only
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 hover:opacity-75 cursor-pointer"
          style={{ color: 'var(--aura-muted)' }}
          aria-label="Close inspector"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b px-5 py-2" style={{ borderColor: 'var(--aura-border)' }}>
        {[
          { id: 'cv', label: 'Live CV & Circumplex' },
          { id: 'schema', label: 'Generated UISchema' },
          { id: 'photo', label: 'Test Photo' },
          { id: 'analytics', label: 'HCI Metrics' },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id as TabId)}
            className="rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors cursor-pointer"
            style={{
              backgroundColor: tab === t.id ? 'var(--aura-accent-soft)' : 'transparent',
              color: tab === t.id ? 'var(--aura-accent)' : 'var(--aura-muted)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 space-y-5 overflow-y-auto p-5 text-xs">
        {tab === 'cv' && (
          <>
            {/* Webcam Preview / Privacy Shutter */}
            <div
              className="overflow-hidden rounded-2xl border"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: '#0F172A' }}
            >
              {telemetry.camera_active && frameB64 ? (
                <div className="relative">
                  <img
                    src={`data:image/jpeg;base64,${frameB64}`}
                    alt="Annotated OpenCV YuNet feed"
                    className="h-56 w-full object-cover"
                  />
                  <span className="font-mono-code absolute bottom-2 right-2 rounded bg-black/70 px-2 py-0.5 text-[10px] text-emerald-300">
                    {visionLatencyMs.toFixed(1)} ms/frame
                  </span>
                </div>
              ) : (
                <div className="flex h-44 flex-col items-center justify-center gap-2.5 p-4 text-center text-slate-300">
                  <CameraOff className="h-7 w-7 text-slate-400" />
                  <div className="text-xs font-semibold">
                    {telemetry.camera_error ?? 'Hardware Privacy Shutter Active (Camera Released)'}
                  </div>
                  <button
                    type="button"
                    onClick={onToggleCamera}
                    className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white cursor-pointer"
                    style={{ backgroundColor: 'var(--aura-accent)' }}
                  >
                    <Camera className="h-3.5 w-3.5" />
                    Enable Local OpenCV Webcam
                  </button>
                </div>
              )}
            </div>

            {/* Circumplex + Cognitive Load */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div
                className="rounded-2xl border p-3.5"
                style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
              >
                <div className="mb-2 font-bold">Russell&apos;s Circumplex (V × A)</div>
                <svg viewBox="0 0 180 180" className="mx-auto h-40 w-40">
                  <rect x="4" y="4" width="172" height="172" rx="14" fill="var(--aura-panel)" stroke="var(--aura-border)" />
                  <line x1="90" y1="8" x2="90" y2="172" stroke="var(--aura-border)" strokeDasharray="3 3" />
                  <line x1="8" y1="90" x2="172" y2="90" stroke="var(--aura-border)" strokeDasharray="3 3" />
                  <text x="12" y="20" fontSize="8" fill="var(--aura-muted)">Overwhelmed</text>
                  <text x="126" y="20" fontSize="8" fill="var(--aura-muted)">Energized</text>
                  <text x="12" y="166" fontSize="8" fill="var(--aura-muted)">Fatigued</text>
                  <text x="132" y="166" fontSize="8" fill="var(--aura-muted)">Calm</text>

                  {telemetry.circumplex_trail.map((pt, idx) => (
                    <circle
                      key={idx}
                      cx={90 + pt.valence * 74}
                      cy={90 - pt.arousal * 74}
                      r={2}
                      fill="var(--aura-accent)"
                      opacity={0.15 + (idx / Math.max(1, telemetry.circumplex_trail.length)) * 0.5}
                    />
                  ))}
                  <circle cx={cx} cy={cy} r={6} fill="var(--aura-accent)" stroke="#FFFFFF" strokeWidth="2" />
                </svg>
                <div className="font-mono-code mt-1 flex justify-between text-[11px]" style={{ color: 'var(--aura-muted)' }}>
                  <span>V: {telemetry.valence.toFixed(2)}</span>
                  <span>A: {telemetry.arousal.toFixed(2)}</span>
                </div>
              </div>

              <div
                className="space-y-3 rounded-2xl border p-3.5"
                style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
              >
                <div className="font-bold">Cognitive &amp; Attention Signals</div>
                {[
                  { label: 'Cognitive Load', val: telemetry.cognitive_load },
                  { label: 'Attention Score', val: telemetry.attention_score },
                  { label: 'Dwell Lock Progress', val: telemetry.dwell_progress },
                ].map((m) => (
                  <div key={m.label}>
                    <div className="mb-1 flex justify-between text-[11px]">
                      <span>{m.label}</span>
                      <span className="font-mono-code font-semibold">{Math.round(m.val * 100)}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full" style={{ backgroundColor: 'var(--aura-panel)' }}>
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{ width: `${Math.round(m.val * 100)}%`, backgroundColor: 'var(--aura-accent)' }}
                      />
                    </div>
                  </div>
                ))}

                <div className="pt-1">
                  <label className="flex items-center justify-between text-[11px]">
                    <span>Hysteresis Dwell ({telemetry.dwell_seconds.toFixed(1)}s)</span>
                    <input
                      type="range"
                      min={1}
                      max={6}
                      step={0.5}
                      value={telemetry.dwell_seconds}
                      onChange={(e) => onUpdateDwell(Number(e.target.value))}
                      className="w-24 accent-blue-600"
                    />
                  </label>
                </div>
              </div>
            </div>

            {/* 8-Class AffectNet Emotion Distribution */}
            <div
              className="rounded-2xl border p-4"
              style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
            >
              <div className="mb-2.5 flex items-center justify-between font-bold">
                <span>Smoothed 8-Class Emotion Probabilities</span>
                <span className="font-mono-code text-[11px]" style={{ color: 'var(--aura-accent)' }}>
                  {telemetry.dominant_emotion.toUpperCase()}
                </span>
              </div>
              <div className="space-y-1.5">
                {emotionsSorted.map(([label, prob]) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className="w-20 capitalize">{label}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full" style={{ backgroundColor: 'var(--aura-panel)' }}>
                      <div
                        className="h-full rounded-full transition-all duration-200"
                        style={{ width: `${Math.round(prob * 100)}%`, backgroundColor: 'var(--aura-accent)' }}
                      />
                    </div>
                    <span className="font-mono-code w-10 text-right">{Math.round(prob * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {tab === 'schema' && (
          <div className="space-y-4">
            <div
              className="rounded-2xl border p-4"
              style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
            >
              <div className="mb-2 flex items-center gap-2 font-bold">
                <ShieldCheck className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
                Active HCI Adaptation Rationale
              </div>
              <div className="space-y-2.5">
                {schema.hciRationale.map((r, i) => (
                  <div
                    key={i}
                    className="rounded-xl border p-3"
                    style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
                  >
                    <div className="font-bold">{r.principle}</div>
                    <div className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>
                      {r.citation} • Trigger: {r.trigger}
                    </div>
                    <div className="mt-1 font-medium" style={{ color: 'var(--aura-accent)' }}>
                      {r.uiMutation}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div
              className="rounded-2xl border p-4"
              style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
            >
              <div className="mb-2 flex items-center gap-2 font-bold">
                <Code2 className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
                Live Generated UISchema AST
              </div>
              <pre className="font-mono-code max-h-96 overflow-auto rounded-xl bg-slate-950 p-3 text-[11px] text-slate-100">
                {JSON.stringify(schema, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {tab === 'photo' && (
          <div className="space-y-4">
            <div
              className="rounded-2xl border border-dashed p-5 text-center"
              style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
            >
              <ImagePlus className="mx-auto mb-2 h-7 w-7" style={{ color: 'var(--aura-accent)' }} />
              <p className="font-semibold">Run Real OpenCV YuNet + HSEmotion on Any Face Image</p>
              <p className="mt-1 text-[11px]" style={{ color: 'var(--aura-muted)' }}>
                Useful for reproducible offline evaluation without a live webcam.
              </p>
              <label
                className="mt-3 inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold text-white cursor-pointer"
                style={{ backgroundColor: 'var(--aura-accent)' }}
              >
                {uploading ? 'Analyzing...' : 'Upload Portrait Image'}
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => handlePhotoUpload(e.target.files?.[0])}
                />
              </label>
            </div>

            {photoResult && (
              <div
                className="space-y-3 rounded-2xl border p-4"
                style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
              >
                {photoResult.vision?.annotated_frame_b64 && (
                  <img
                    src={`data:image/jpeg;base64,${photoResult.vision.annotated_frame_b64}`}
                    alt="Analyzed face result"
                    className="max-h-60 w-full rounded-xl object-contain bg-slate-950"
                  />
                )}
                <div className="flex flex-wrap justify-between gap-2 font-semibold">
                  <span>Inferred HCI State: {String(photoResult.inferred_state).toUpperCase()}</span>
                  <span>Dominant: {photoResult.vision?.dominant_emotion}</span>
                </div>
                <div className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>
                  Generated Mode: <strong>{photoResult.preview_schema?.modeName}</strong> ({photoResult.preview_schema?.layout?.topology})
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'analytics' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Flickers Prevented (Hysteresis)', value: telemetry.metrics.flickers_prevented },
                { label: 'State Transitions', value: telemetry.metrics.transitions_count },
                { label: 'Co-Pilot Accepted', value: telemetry.metrics.proposals_accepted },
                { label: 'Co-Pilot Dismissed', value: telemetry.metrics.proposals_dismissed },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-2xl border p-3.5"
                  style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
                >
                  <div className="text-[11px]" style={{ color: 'var(--aura-muted)' }}>
                    {stat.label}
                  </div>
                  <div className="mt-1 text-2xl font-bold tabular-nums">{stat.value}</div>
                </div>
              ))}
            </div>

            <div
              className="rounded-2xl border p-4"
              style={{ backgroundColor: 'var(--aura-panel-alt)', borderColor: 'var(--aura-border)' }}
            >
              <div className="mb-2 font-bold">Time Spent per Adaptive Topology (seconds)</div>
              <div className="space-y-1.5">
                {Object.entries(telemetry.metrics.time_in_state).map(([st, secs]) => (
                  <div key={st} className="flex items-center justify-between">
                    <span className="capitalize">{st}</span>
                    <span className="font-mono-code font-semibold">{secs.toFixed(1)}s</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <a
                href="/api/analytics/export?format=json"
                download="aura_hci_session.json"
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border px-3 py-2 font-semibold"
                style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
              >
                <Download className="h-3.5 w-3.5" /> Export JSON
              </a>
              <a
                href="/api/analytics/export?format=csv"
                download="aura_hci_session.csv"
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl px-3 py-2 font-semibold text-white"
                style={{ backgroundColor: 'var(--aura-accent)' }}
              >
                <Download className="h-3.5 w-3.5" /> Export CSV
              </a>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
