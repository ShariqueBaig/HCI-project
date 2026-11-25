import { Eye, Lightbulb, Undo2 } from 'lucide-react';
import type { Anticipation } from '../types';

/**
 * Mixed-initiative offer (ported idea: the webcam app's CoPilotProposalBar).
 * Aura never re-lays out on its own: it offers, the user decides, and an
 * accepted change can always be undone. role="status" announces offers to
 * screen readers without stealing focus.
 */
export function ProposalBar({ antic, searchId, busy, onAnswer }: {
  antic: Anticipation | undefined;
  searchId: string;
  busy: boolean;
  onAnswer: (action: 'accept' | 'dismiss' | 'undo', proposalId?: string) => void;
}) {
  const p = antic?.proposal && antic.proposal.search_id === searchId ? antic.proposal : null;
  const mine = antic?.view?.search_id === searchId;

  if (p) {
    return (
      <div
        role="status"
        className="flex flex-wrap items-center gap-3 rounded-xl border p-3"
        style={{ borderColor: 'var(--aura-calm)', background: 'var(--aura-surface)' }}
      >
        <Lightbulb size={18} style={{ color: 'var(--aura-calm)' }} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{p.text}</p>
          <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>{p.reason} Same facts, different layout.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {antic?.can_undo && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('undo')}
              className="aura-target flex items-center gap-1.5 rounded-lg text-sm disabled:opacity-50"
              style={{ color: 'var(--aura-muted)' }}
            >
              <Undo2 size={14} aria-hidden /> Undo last change
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => onAnswer('accept', p.id)}
            className="aura-target rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
          >
            Yes, show it
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onAnswer('dismiss', p.id)}
            className="aura-target rounded-lg border text-sm disabled:opacity-50"
            style={{ borderColor: 'var(--aura-border)' }}
          >
            Keep this
          </button>
        </div>
      </div>
    );
  }

  if (mine && antic?.can_undo) {
    return (
      <div role="status" className="flex items-center gap-3 text-sm" style={{ color: 'var(--aura-muted)' }}>
        <span>Layout changed at your request.</span>
        <button
          type="button"
          disabled={busy}
          onClick={() => onAnswer('undo')}
          className="aura-target flex items-center gap-1.5 rounded-lg border text-sm disabled:opacity-50"
          style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-text)' }}
        >
          <Undo2 size={14} aria-hidden /> Undo
        </button>
      </div>
    );
  }

  if (mine && antic?.ack) {
    return (
      <p role="status" className="flex items-center gap-2 text-xs" style={{ color: 'var(--aura-muted)' }}>
        <Eye size={13} aria-hidden /> {antic.ack.text}
      </p>
    );
  }
  return null;
}
