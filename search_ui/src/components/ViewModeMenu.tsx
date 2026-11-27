import { Check, SlidersHorizontal, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { isLightTheme, MODE_ORDER, VIEW_MODES } from '../modes';
import type { StateSnapshot, ThemeId, ViewPolicyName } from '../types';

/**
 * Presentation-mode selector replacing v1's clinical StatePill.
 * Describes the layout ("Simple View", "Easy-Read View") instead of diagnosing
 * the user ("Overwhelmed 82%"), and gives direct agency to pick any mode or
 * toggle Auto-adapt.
 */
export function ViewModeMenu({
  snap,
  currentPolicy,
  autoAdapt,
  blinded = false,
  isControl = false,
  theme = 'dark',
  onSelectPolicy,
  onToggleAutoAdapt,
  onExitControl,
}: {
  snap: StateSnapshot | null;
  currentPolicy: ViewPolicyName;
  autoAdapt: boolean;
  blinded?: boolean;
  isControl?: boolean;
  theme?: ThemeId;
  onSelectPolicy: (policy: ViewPolicyName) => void;
  onToggleAutoAdapt: (next: boolean) => void;
  onExitControl?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const meta = VIEW_MODES[currentPolicy] ?? VIEW_MODES.neutral;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="aura-target flex items-center gap-2 rounded-full border text-sm hover:border-[var(--aura-calm)]"
        style={{ borderColor: 'var(--aura-border-interactive)', background: 'var(--aura-surface)' }}
        title="Choose how search results are laid out"
      >
        {autoAdapt ? (
          <Sparkles size={14} style={{ color: 'var(--aura-calm)' }} aria-hidden />
        ) : (
          <SlidersHorizontal size={14} style={{ color: 'var(--aura-muted)' }} aria-hidden />
        )}
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ background: isLightTheme(theme) ? meta.swatchLight : meta.swatchDark }}
          aria-hidden
        />
        <span className="font-medium">{meta.name}</span>
        {autoAdapt && (
          <span className="text-xs" style={{ color: 'var(--aura-subtle)' }}>
            Auto
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Presentation mode"
          className="aura-scale-in origin-top-right absolute right-0 z-30 mt-2 w-[min(340px,calc(100vw-24px))] rounded-2xl border p-4 text-sm shadow-2xl"
          style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
        >
          <div className="flex items-center justify-between gap-3 border-b pb-3" style={{ borderColor: 'var(--aura-border)' }}>
            <div>
              <p className="font-medium">Auto-adapt layout</p>
              <p className="text-xs" style={{ color: 'var(--aura-muted)' }}>
                Adjusts readability &amp; density to your pace
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={autoAdapt}
              onClick={() => onToggleAutoAdapt(!autoAdapt)}
              className="aura-target rounded-full border px-3 text-xs font-medium"
              style={{
                borderColor: autoAdapt ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
                background: autoAdapt ? 'var(--aura-calm)' : 'var(--aura-surface-elev)',
                color: autoAdapt ? 'var(--aura-bg)' : 'var(--aura-text)',
              }}
            >
              {autoAdapt ? 'On' : 'Off'}
            </button>
          </div>

          <p className="mt-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-subtle)' }}>
            Choose layout mode
          </p>
          <p className="mb-2 text-[11px]" style={{ color: 'var(--aura-muted)' }}>
            Picking a mode pins it and pauses Auto-adapt.
          </p>
          {isControl && (
            <div
              className="mb-2.5 flex flex-col gap-2 rounded-xl border p-2.5 text-xs"
              style={{ borderColor: 'var(--aura-mild)', background: 'var(--aura-surface-elev)' }}
            >
              <p style={{ color: 'var(--aura-text)' }}>
                Prompt-only (Control A) is active in Lab — layouts stay Standard until State-aware mode is restored.
              </p>
              {onExitControl && (
                <button
                  type="button"
                  onClick={() => {
                    onExitControl();
                    setOpen(false);
                  }}
                  className="aura-target w-fit rounded-lg px-3 text-xs font-medium"
                  style={{ background: 'var(--aura-calm)', color: 'var(--aura-bg)' }}
                >
                  Switch to State-aware
                </button>
              )}
            </div>
          )}
          <ul className="space-y-1">
            {MODE_ORDER.map((id) => {
              const m = VIEW_MODES[id];
              const selected = id === currentPolicy;
              return (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelectPolicy(id);
                      setOpen(false);
                    }}
                    className="flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-[var(--aura-surface-elev)]"
                    style={selected ? { background: 'var(--aura-surface-elev)' } : undefined}
                  >
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                      {selected ? (
                        <Check size={14} style={{ color: 'var(--aura-calm)' }} aria-hidden />
                      ) : (
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ background: isLightTheme(theme) ? m.swatchLight : m.swatchDark }}
                          aria-hidden
                        />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-medium">{m.name}</span>
                        {!blinded && (
                          <span className="rounded px-1.5 py-0.5 text-[11px]" style={{ background: 'var(--aura-bg)', color: 'var(--aura-subtle)' }}>
                            {m.moodHint}
                          </span>
                        )}
                      </span>
                      <span className="block text-xs" style={{ color: 'var(--aura-muted)' }}>
                        {m.shortDesc}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {snap && snap.fused.evidence.length > 0 && (
            <p className="mt-3 border-t pt-2.5 text-xs" style={{ borderColor: 'var(--aura-border)', color: 'var(--aura-subtle)' }}>
              Current pacing note: {snap.fused.evidence[0]}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
