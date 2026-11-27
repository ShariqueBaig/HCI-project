import {
  BellOff, BookOpen, MessageCircle, Music, Pause, Play,
  Send, Shield, SkipBack, SkipForward, Sparkles, Trash2, Volume2, Wind,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { apiGet, apiPost } from '../api';
import type { AmbientSoundController, SoundscapeId } from '../hooks/useAmbientSound';
import type { AppStatus, ThemeId } from '../types';
import { ThemeCards } from './ThemePicker';

const SOUNDSCAPES: { id: SoundscapeId; label: string }[] = [
  { id: 'off', label: 'Off' },
  { id: 'rain', label: 'Soft Rain' },
  { id: 'brown', label: 'Brown Noise' },
  { id: 'drone', label: 'Calm Drone' },
];

interface ChatMsg { id: string; role: 'user' | 'aura' | 'note'; text: string; ts: number }
interface JournalEntry { time: string; note: string; reflection: string; stats: { duration_s: number; peak: number; avg: number } }

export function WellnessView({
  app,
  ambientSound,
  onOpenBreathing,
  onOpenOnboarding,
  onRefresh,
}: {
  app: AppStatus | null;
  ambientSound: AmbientSoundController;
  onOpenBreathing: () => void;
  onOpenOnboarding: (step?: 0 | 1 | 2) => void;
  onRefresh: () => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatBusy, setChatBusy] = useState(false);

  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [statsText, setStatsText] = useState('');
  const [note, setNote] = useState('');
  const [reflection, setReflection] = useState('');
  const [journalMsg, setJournalMsg] = useState<string | null>(null);
  const [journalBusy, setJournalBusy] = useState(false);

  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [confirmWithdraw, setConfirmWithdraw] = useState(false);
  const [withdrawMsg, setWithdrawMsg] = useState<string | null>(null);

  const loadCompanion = useCallback(() => {
    apiGet<{ messages: ChatMsg[] }>('/api/app/chat').then((r) => setMessages(r.messages)).catch(() => undefined);
    apiGet<{ entries: JournalEntry[]; current_stats_text: string }>('/api/app/journal')
      .then((r) => {
        setEntries(r.entries);
        setStatsText(r.current_stats_text);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    loadCompanion();
  }, [loadCompanion]);

  const toggleComfort = async (key: 'auto_bright' | 'focus_mode' | 'auto_music', val: boolean) => {
    await apiPost('/api/app/comfort', { [key]: val });
    onRefresh();
  };

  const setTheme = async (id: ThemeId) => {
    await apiPost('/api/app/comfort', { theme: id });
    onRefresh();
  };

  const sendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text || chatBusy) return;
    setChatInput('');
    setChatBusy(true);
    try {
      const r = await apiPost<{ messages: ChatMsg[] }>('/api/app/chat/send', { text });
      setMessages(r.messages);
    } finally {
      setChatBusy(false);
    }
  };

  const clearChat = async () => {
    const r = await apiPost<{ messages: ChatMsg[] }>('/api/app/chat/reset', {});
    setMessages(r.messages);
  };

  const reflectNote = async () => {
    setJournalBusy(true);
    setJournalMsg(null);
    try {
      const r = await apiPost<{ reflection: string }>('/api/app/journal/reflect', { note });
      setReflection(r.reflection);
    } finally {
      setJournalBusy(false);
    }
  };

  const saveNote = async () => {
    setJournalBusy(true);
    setJournalMsg(null);
    try {
      const r = await apiPost<{ saved: boolean; recording_still_active: boolean }>('/api/app/journal/note', {
        note,
        reflection,
      });
      setNote('');
      setReflection('');
      setJournalMsg(
        r.recording_still_active
          ? 'Note saved to your journal. Active recording continues uninterrupted.'
          : 'Note saved to your journal.',
      );
      loadCompanion();
    } finally {
      setJournalBusy(false);
    }
  };

  const doWithdraw = async () => {
    const r = await apiPost<{ local_deleted: number; cloud_deleted: number }>('/api/app/consent/withdraw', {
      confirm: true,
    });
    setConfirmWithdraw(false);
    setWithdrawMsg(`Consent withdrawn. Deleted ${r.local_deleted} local file(s) and ${r.cloud_deleted} cloud doc(s).`);
    onRefresh();
  };

  const c = app?.comfort;
  const a = app?.audio;
  const cal = app?.calibration;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Left column: Ambient Comfort & Audio */}
      <div className="space-y-5">
        <section className="rounded-2xl border p-5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}>
          <h2 className="mb-4 text-base font-semibold">Ambient Comfort</h2>

          <div className="space-y-3">
            {/* Color Theme Picker */}
            <div className="rounded-xl border p-3.5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
              <p className="mb-2 font-medium">Color Theme</p>
              <ThemeCards theme={(c?.theme ?? 'dark') as ThemeId} onSelect={(id) => void setTheme(id)} />
            </div>
            {/* Screen Comfort */}
            <div className="flex items-center justify-between gap-3 rounded-xl border p-3.5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
              <div>
                <p className="font-medium">Screen Comfort (Brightness + Warmth)</p>
                <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                  Live: {c?.brightness ?? '--'}% brightness · {c?.color_temp ?? 6500}K color warmth
                </p>
              </div>
              <Switch checked={Boolean(c?.auto_bright)} onChange={(v) => void toggleComfort('auto_bright', v)} label="Auto-adjust screen comfort" />
            </div>

            {/* Focus Mode */}
            <div className="flex items-center justify-between gap-3 rounded-xl border p-3.5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
              <div>
                <p className="flex items-center gap-1.5 font-medium">
                  <BellOff size={14} style={{ color: 'var(--aura-calm)' }} aria-hidden /> Focus Mode (Silent Shield)
                </p>
                <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                  {c?.focus_blocking
                    ? `Active — holding alerts silently (${c.held_count} queued)`
                    : `Standing by · Held ${c?.held_total ?? 0} · Delivered ${c?.delivered_count ?? 0}`}
                </p>
              </div>
              <Switch checked={Boolean(c?.focus_mode)} onChange={(v) => void toggleComfort('focus_mode', v)} label="Focus mode" />
            </div>

            {/* Audio Easing */}
            <div className="rounded-xl border p-3.5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="flex items-center gap-1.5 font-medium">
                    <Music size={14} style={{ color: 'var(--aura-calm)' }} aria-hidden /> Audio Easing
                  </p>
                  <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                    {a?.track ? `${a.track.title} — ${a.track.artist}` : `Source: ${a?.backend ?? 'System audio'}`}
                    {a?.volume !== null && a?.volume !== undefined ? ` · ${a.volume}%` : ''}
                  </p>
                </div>
                <Switch checked={Boolean(c?.auto_music)} onChange={(v) => void toggleComfort('auto_music', v)} label="Auto-lower audio volume" />
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t pt-3" style={{ borderColor: 'var(--aura-border)' }}>
                {a?.spotify_connected ? (
                  <>
                    <div className="flex gap-1.5">
                      <button type="button" aria-label="Previous track" onClick={() => void apiPost('/api/app/audio', { action: 'prev' })}
                        className="aura-target rounded-lg border px-2.5" style={{ borderColor: 'var(--aura-border-interactive)' }}>
                        <SkipBack size={14} aria-hidden />
                      </button>
                      <button type="button" aria-label={a.track?.is_playing ? 'Pause' : 'Play'} onClick={() => void apiPost('/api/app/audio', { action: 'play_pause' })}
                        className="aura-target rounded-lg border px-2.5" style={{ borderColor: 'var(--aura-border-interactive)' }}>
                        {a.track?.is_playing ? <Pause size={14} aria-hidden /> : <Play size={14} aria-hidden />}
                      </button>
                      <button type="button" aria-label="Next track" onClick={() => void apiPost('/api/app/audio', { action: 'next' })}
                        className="aura-target rounded-lg border px-2.5" style={{ borderColor: 'var(--aura-border-interactive)' }}>
                        <SkipForward size={14} aria-hidden />
                      </button>
                    </div>
                    <button type="button" onClick={() => void apiPost('/api/app/audio', { action: 'disconnect' }).then(onRefresh)}
                      className="aura-target rounded-lg border text-xs" style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}>
                      Disconnect Spotify
                    </button>
                  </>
                ) : (
                  <>
                    <span className="text-xs" style={{ color: 'var(--aura-subtle)' }}>{a?.spotify_status}</span>
                    {a?.spotify_configured && (
                      <button type="button" onClick={() => void apiPost('/api/app/audio', { action: 'connect' }).then(onRefresh)}
                        className="aura-target rounded-lg border text-xs" style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-calm)' }}>
                        Connect Spotify
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Procedural Ambient Soundscapes */}
            <div className="rounded-xl border p-3.5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="flex items-center gap-1.5 font-medium">
                    <Volume2 size={14} style={{ color: 'var(--aura-calm)' }} aria-hidden /> Ambient Soundscapes
                  </p>
                  <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                    Built-in synthesized sound — zero accounts or audio files needed.
                  </p>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="Ambient soundscape">
                {SOUNDSCAPES.map((s) => {
                  const active = ambientSound.sound === s.id;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => ambientSound.setSound(s.id)}
                      className="aura-target rounded-lg border text-xs font-medium"
                      style={{
                        borderColor: active ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
                        background: active ? 'var(--aura-calm)' : 'var(--aura-surface)',
                        color: active ? 'var(--aura-bg)' : 'var(--aura-text)',
                      }}
                    >
                      {s.label}
                    </button>
                  );
                })}
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t pt-3 text-xs" style={{ borderColor: 'var(--aura-border)' }}>
                <label className="flex items-center gap-2">
                  <span style={{ color: 'var(--aura-muted)' }}>Volume</span>
                  <input
                    type="range"
                    min={0.05}
                    max={1}
                    step={0.05}
                    value={ambientSound.volume}
                    onChange={(e) => ambientSound.setVolume(Number(e.target.value))}
                    className="w-24 accent-[var(--aura-calm)]"
                  />
                  <span className="tabular-nums">{Math.round(ambientSound.volume * 100)}%</span>
                </label>
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={ambientSound.autoOnStress}
                    onChange={(e) => ambientSound.setAutoOnStress(e.target.checked)}
                    className="h-3.5 w-3.5 accent-[var(--aura-calm)]"
                  />
                  <span style={{ color: 'var(--aura-muted)' }}>Auto-play in Simple / Easy-Read</span>
                </label>
              </div>
            </div>
          </div>
        </section>

        {/* Calibration & Privacy */}
        <section className="rounded-2xl border p-5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}>
          <h2 className="mb-3 text-base font-semibold">Setup &amp; Privacy</h2>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium">Typing Rhythm Calibration</p>
                <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                  {cal?.calibrated
                    ? `Calibrated (${cal.baselines.kps.toFixed(1)} keys/s · ${(cal.baselines.dwell * 1000).toFixed(0)} ms hold)`
                    : 'Not calibrated yet — improves pacing accuracy'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onOpenOnboarding(1)}
                className="aura-target rounded-lg border text-xs"
                style={{ borderColor: 'var(--aura-border-interactive)' }}
              >
                {cal?.calibrated ? 'Recalibrate' : 'Calibrate (30s)'}
              </button>
            </div>

            <div className="flex items-center justify-between gap-3 border-t pt-3" style={{ borderColor: 'var(--aura-border)' }}>
              <div>
                <p className="flex items-center gap-1.5 font-medium">
                  <Shield size={14} style={{ color: 'var(--aura-calm)' }} aria-hidden /> Privacy &amp; Research Data
                </p>
                <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                  {app?.consent.granted
                    ? `Consent active (${app.consent.participant_code}) · ${app.consent.local_sessions} local session(s)`
                    : 'No research consent saved'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPrivacyOpen(true)}
                className="aura-target rounded-lg border text-xs"
                style={{ borderColor: 'var(--aura-border-interactive)' }}
              >
                Manage data
              </button>
            </div>
            {withdrawMsg && <p role="status" className="text-xs" style={{ color: 'var(--aura-calm)' }}>{withdrawMsg}</p>}
          </div>
        </section>
      </div>

      {/* Right column: Co-Regulation (Breathing + Chat) & Session Journal */}
      <div className="space-y-5">
        <section className="rounded-2xl border p-5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <MessageCircle size={16} style={{ color: 'var(--aura-calm)' }} aria-hidden /> Aura Check-in
            </h2>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onOpenBreathing}
                className="aura-target flex items-center gap-1.5 rounded-lg border text-xs"
                style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-calm)' }}
              >
                <Wind size={13} aria-hidden /> Physiological Sigh
              </button>
              <button
                type="button"
                onClick={clearChat}
                className="aura-target rounded-lg border text-xs"
                style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
              >
                I&apos;m Good
              </button>
            </div>
          </div>

          <div className="mb-3 max-h-56 space-y-2 overflow-auto rounded-xl border p-3" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-bg)' }}>
            {messages.map((m) => (
              <div
                key={m.id}
                className={`aura-fade-in rounded-xl px-3 py-2 text-sm ${m.role === 'user' ? 'ml-8 text-right' : 'mr-4'}`}
                style={{
                  background: m.role === 'user' ? 'var(--aura-surface-elev)' : 'var(--aura-surface)',
                  color: m.role === 'note' ? 'var(--aura-muted)' : m.role === 'aura' ? 'var(--aura-calm)' : 'var(--aura-text)',
                }}
              >
                {m.text}
              </div>
            ))}
          </div>

          <form onSubmit={sendChat} className="flex gap-2">
            <label htmlFor="aura-chat-input" className="sr-only">Message Aura</label>
            <input
              id="aura-chat-input"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Share what's on your mind…"
              className="flex-1 rounded-xl border px-3.5 py-2 text-sm"
              style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-bg)' }}
            />
            <button
              type="submit"
              disabled={chatBusy || !chatInput.trim()}
              className="aura-target flex items-center gap-1.5 rounded-xl px-4 text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
            >
              <Send size={14} aria-hidden /> Send
            </button>
          </form>
        </section>

        {/* Session Journal (never stops active recording!) */}
        <section className="rounded-2xl border p-5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}>
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <BookOpen size={16} style={{ color: 'var(--aura-calm)' }} aria-hidden /> Session Journal
          </h2>
          <p className="mt-1 whitespace-pre-line text-xs" style={{ color: 'var(--aura-muted)' }}>
            {statsText || 'Session stats updating…'}
          </p>
          <p className="mt-1 text-xs" style={{ color: 'var(--aura-subtle)' }}>
            Saving a note here does not interrupt any active study recording.
          </p>

          <textarea
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Write a quick reflection note…"
            className="mt-3 w-full rounded-xl border p-3 text-sm"
            style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-bg)' }}
          />
          {reflection && (
            <p className="aura-fade-in mt-2 rounded-xl border p-3 text-xs" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface-elev)' }}>
              {reflection}
            </p>
          )}
          <div className="mt-2.5 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={journalBusy}
              onClick={reflectNote}
              className="aura-target flex items-center gap-1.5 rounded-xl border text-xs"
              style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-calm)' }}
            >
              <Sparkles size={13} aria-hidden /> Reflect with Aura
            </button>
            <button
              type="button"
              disabled={journalBusy || (!note.trim() && !reflection.trim())}
              onClick={saveNote}
              className="aura-target rounded-xl px-4 text-xs font-medium disabled:opacity-50"
              style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
            >
              Save note
            </button>
          </div>
          {journalMsg && <p role="status" className="aura-fade-in mt-2 text-xs" style={{ color: 'var(--aura-calm)' }}>{journalMsg}</p>}

          {entries.length > 0 && (
            <details className="mt-4 border-t pt-3" style={{ borderColor: 'var(--aura-border)' }}>
              <summary className="cursor-pointer text-xs font-medium" style={{ color: 'var(--aura-muted)' }}>
                Past entries ({entries.length})
              </summary>
              <ul className="mt-2 max-h-40 space-y-2 overflow-auto text-xs">
                {entries.slice(0, 10).map((e, idx) => (
                  <li key={idx} className="rounded-lg border p-2.5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-bg)' }}>
                    <span className="font-medium">{e.time}</span> · peak {e.stats.peak.toFixed(0)}
                    {e.note && <p className="mt-1" style={{ color: 'var(--aura-muted)' }}>{e.note}</p>}
                    <p className="mt-1">{e.reflection}</p>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      </div>

      {/* Privacy & Confirmed Withdrawal Modal */}
      {privacyOpen && (
        <div role="dialog" aria-modal="true" aria-label="Manage privacy and research data"
          className="aura-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="aura-scale-in w-full max-w-lg rounded-2xl border p-6 shadow-2xl" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}>
            <h3 className="text-lg font-semibold">Privacy &amp; Research Data</h3>
            <p className="mt-1 text-sm" style={{ color: 'var(--aura-muted)' }}>{app?.consent.storage_summary}</p>
            <p className="mt-3 rounded-xl border p-3 text-xs leading-relaxed" style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-muted)' }}>
              {app?.consent.consent_text}
            </p>
            <div className="mt-4 flex flex-wrap justify-between gap-2">
              <button type="button" onClick={() => { setPrivacyOpen(false); onOpenOnboarding(0); }}
                className="aura-target rounded-xl border px-4 text-sm" style={{ borderColor: 'var(--aura-border-interactive)' }}>
                Update consent
              </button>
              {!confirmWithdraw ? (
                <button type="button" onClick={() => setConfirmWithdraw(true)}
                  className="aura-target flex items-center gap-1.5 rounded-xl border px-4 text-sm"
                  style={{ borderColor: 'var(--aura-elev)', color: 'var(--aura-elev)' }}>
                  <Trash2 size={14} aria-hidden /> Withdraw &amp; delete data…
                </button>
              ) : (
                <div className="mt-2 w-full rounded-xl border p-3 text-xs" style={{ borderColor: 'var(--aura-elev)', background: 'var(--aura-surface-elev)' }}>
                  <p className="font-semibold" style={{ color: 'var(--aura-elev)' }}>
                    Permanently delete {app?.consent.local_sessions ?? 0} local session(s) and all uploaded cloud copies?
                  </p>
                  <div className="mt-2 flex gap-2">
                    <button type="button" onClick={() => setConfirmWithdraw(false)}
                      className="aura-target rounded-lg border px-3 text-xs" style={{ borderColor: 'var(--aura-border-interactive)' }}>
                      Cancel
                    </button>
                    <button type="button" onClick={() => { void doWithdraw(); setPrivacyOpen(false); }}
                      className="aura-target rounded-lg px-3 text-xs font-medium"
                      style={{ background: 'var(--aura-elev)', color: 'var(--aura-bg)' }}>
                      Yes, permanently delete everything
                    </button>
                  </div>
                </div>
              )}
              <button type="button" onClick={() => { setConfirmWithdraw(false); setPrivacyOpen(false); }}
                className="aura-target ml-auto rounded-xl border px-4 text-sm" style={{ borderColor: 'var(--aura-border-interactive)' }}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="aura-target shrink-0 rounded-full border px-3.5 text-xs font-medium"
      style={{
        borderColor: checked ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
        background: checked ? 'var(--aura-calm)' : 'var(--aura-surface)',
        color: checked ? 'var(--aura-bg)' : 'var(--aura-text)',
      }}
    >
      {checked ? 'On' : 'Off'}
    </button>
  );
}
