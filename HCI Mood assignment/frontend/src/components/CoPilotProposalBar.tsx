import { ArrowRight, Check, Sparkles, X } from 'lucide-react';
import type { PendingProposal } from '../types/aura';

interface CoPilotProposalBarProps {
  proposal: PendingProposal;
  onAccept: () => void;
  onDismiss: () => void;
}

export function CoPilotProposalBar({ proposal, onAccept, onDismiss }: CoPilotProposalBarProps) {
  return (
    <div
      className="mx-auto mt-4 max-w-7xl px-4 sm:px-6"
      role="region"
      aria-label="Co-Pilot Generative UI Adaptation Proposal"
    >
      <div
        className="flex flex-col justify-between gap-4 rounded-2xl border p-4 shadow-sm sm:flex-row sm:items-center"
        style={{
          backgroundColor: 'var(--aura-panel)',
          borderColor: 'var(--aura-accent)',
        }}
      >
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold"
              style={{ backgroundColor: 'var(--aura-accent-soft)', color: 'var(--aura-accent)' }}
            >
              <Sparkles className="h-3.5 w-3.5" />
              Co-Pilot Adaptation Proposal
            </span>
            <span className="text-sm font-semibold">
              Switch to <span className="capitalize">{proposal.target_state}</span>
              {proposal.target_mode_name ? ` (${proposal.target_mode_name})` : ''}
            </span>
            <span className="font-mono-code text-xs" style={{ color: 'var(--aura-muted)' }}>
              conf {Math.round(proposal.confidence * 100)}%
            </span>
          </div>

          <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
            <strong>Why:</strong> {proposal.cue_summary}
          </p>

          {proposal.structural_diff && proposal.structural_diff.length > 0 && (
            <ul className="flex flex-wrap gap-1.5 pt-0.5">
              {proposal.structural_diff.map((line, i) => (
                <li
                  key={i}
                  className="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-medium"
                  style={{ backgroundColor: 'var(--aura-panel-alt)', color: 'var(--aura-text)' }}
                >
                  <ArrowRight className="h-3 w-3 shrink-0" style={{ color: 'var(--aura-accent)' }} />
                  {line}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onDismiss}
            className="aura-target inline-flex items-center gap-1.5 rounded-xl border text-xs font-semibold hover:opacity-80 cursor-pointer"
            style={{
              borderColor: 'var(--aura-border)',
              backgroundColor: 'var(--aura-panel-alt)',
              color: 'var(--aura-text)',
            }}
          >
            <X className="h-3.5 w-3.5" />
            Keep Current
          </button>
          <button
            type="button"
            onClick={onAccept}
            className="aura-target inline-flex items-center gap-1.5 rounded-xl text-xs font-semibold text-white shadow-sm hover:opacity-95 cursor-pointer"
            style={{ backgroundColor: 'var(--aura-accent)' }}
          >
            <Check className="h-3.5 w-3.5" />
            Apply Generated Layout
          </button>
        </div>
      </div>
    </div>
  );
}
