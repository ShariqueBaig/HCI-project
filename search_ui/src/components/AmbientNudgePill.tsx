import { BellOff, MessageCircle, Wind, X } from 'lucide-react';
import { apiPost } from '../api';
import type { AppStatus } from '../types';

/**
 * Non-focus-stealing corner pill for Tier-2 sustained elevated tension.
 * Replaces v1's forced topmost modal & self._show() window hijacking.
 */
export function AmbientNudgePill({
  nudge,
  onBreathe,
  onChat,
  onRefresh,
}: {
  nudge: AppStatus['nudge'];
  onBreathe: () => void;
  onChat: () => void;
  onRefresh: () => void;
}) {
  if (!nudge) return null;

  const act = async (action: 'dismiss' | 'snooze' | 'breathe' | 'chat') => {
    await apiPost('/api/app/nudge', { action, snooze_minutes: 30 }).catch(() => undefined);
    onRefresh();
    if (action === 'breathe') onBreathe();
    if (action === 'chat') onChat();
  };

  return (
    <aside
      role="status"
      aria-live="polite"
      aria-label="Gentle break suggestion"
      className="aura-slide-in-up fixed right-4 bottom-4 z-40 w-[min(360px,calc(100vw-32px))] rounded-2xl border p-4 shadow-2xl"
      style={{ borderColor: 'var(--aura-calm)', background: 'var(--aura-surface)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium">{nudge.message}</p>
        <button
          type="button"
          onClick={() => void act('dismiss')}
          aria-label="Dismiss suggestion"
          className="rounded-md p-1 hover:bg-[var(--aura-surface-elev)]"
          style={{ color: 'var(--aura-muted)' }}
        >
          <X size={15} aria-hidden />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void act('breathe')}
          className="aura-target flex items-center gap-1.5 rounded-lg px-3 text-xs font-medium"
          style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
        >
          <Wind size={13} aria-hidden /> 20s sigh
        </button>
        <button
          type="button"
          onClick={() => void act('chat')}
          className="aura-target flex items-center gap-1.5 rounded-lg border text-xs"
          style={{ borderColor: 'var(--aura-border-interactive)' }}
        >
          <MessageCircle size={13} aria-hidden /> Check in
        </button>
        <button
          type="button"
          onClick={() => void act('snooze')}
          className="aura-target rounded-lg border text-xs"
          style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
        >
          Snooze 30m
        </button>
      </div>
    </aside>
  );
}

/** Calm summary banner delivered only AFTER Focus Mode finishes holding alerts silently. */
export function FocusDigestBanner({
  digest,
  onClear,
}: {
  digest: AppStatus['focus_digest'];
  onClear: () => void;
}) {
  if (!digest) return null;
  return (
    <div
      role="status"
      className="aura-fade-up flex flex-wrap items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm"
      style={{ borderColor: 'var(--aura-mild)', background: 'var(--aura-surface)' }}
    >
      <div className="flex items-start gap-2.5">
        <BellOff size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--aura-mild)' }} aria-hidden />
        <div>
          <p className="font-medium">
            Focus digest: {digest.count} {digest.count === 1 ? 'notification' : 'notifications'} held silently
          </p>
          <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
            From {digest.apps.join(', ')}
            {digest.items[0] ? ` — latest: "${digest.items[digest.items.length - 1].text}"` : ''}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={onClear}
        aria-label="Dismiss focus digest"
        className="aura-target rounded-lg border text-xs"
        style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
      >
        Dismiss
      </button>
    </div>
  );
}
