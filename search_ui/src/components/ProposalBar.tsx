import { Eye, Lightbulb, Undo2 } from 'lucide-react';
import { VIEW_MODES } from '../modes';
import type { Anticipation, ViewPolicyName } from '../types';

export function ProposalBar({ antic, searchId, busy, onAnswer }: {
  antic: Anticipation | undefined;
  searchId: string;
  busy: boolean;
  onAnswer: (action: 'accept' | 'dismiss' | 'undo', proposalId?: string) => void;
}) {
  const p = antic?.proposal && antic.proposal.search_id === searchId ? antic.proposal : null;
  const mine = antic?.view?.search_id === searchId;

  if (p) {
    const targetName = VIEW_MODES[p.target as ViewPolicyName]?.name ?? p.target;
    return (
      <div
        role="status"
        className="aura-slide-in-up flex flex-wrap items-center gap-3 rounded-xl border p-3.5"
        style={{ borderColor: 'var(--aura-calm)', background: 'var(--aura-surface)' }}
      >
        <Lightbulb size={18} style={{ color: 'var(--aura-calm)' }} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{p.text}</p>
          <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
            Switch to {targetName}. Same cited facts, calmer layout.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {antic?.can_undo && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('undo')}
              className="aura-target flex items-center gap-1.5 rounded-lg border text-sm disabled:opacity-50"
              style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-muted)' }}
            >
              <Undo2 size={14} aria-hidden /> Undo
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => onAnswer('accept', p.id)}
            className="aura-target rounded-lg px-4 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
          >
            Yes, switch
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onAnswer('dismiss', p.id)}
            className="aura-target rounded-lg border text-sm disabled:opacity-50"
            style={{ borderColor: 'var(--aura-border-interactive)' }}
          >
            Keep this
          </button>
        </div>
      </div>
    );
  }

  if (mine && antic?.can_undo) {
    return (
      <div role="status" className="aura-fade-in flex items-center gap-3 text-sm" style={{ color: 'var(--aura-muted)' }}>
        <span>Layout updated.</span>
        <button
          type="button"
          disabled={busy}
          onClick={() => onAnswer('undo')}
          className="aura-target flex items-center gap-1.5 rounded-lg border text-sm disabled:opacity-50"
          style={{ borderColor: 'var(--aura-border-interactive)', color: 'var(--aura-text)' }}
        >
          <Undo2 size={14} aria-hidden /> Undo
        </button>
      </div>
    );
  }

  if (mine && antic?.ack) {
    return (
      <p role="status" className="aura-fade-in flex items-center gap-2 text-xs" style={{ color: 'var(--aura-subtle)' }}>
        <Eye size={13} aria-hidden /> {antic.ack.text}
      </p>
    );
  }
  return null;
}
