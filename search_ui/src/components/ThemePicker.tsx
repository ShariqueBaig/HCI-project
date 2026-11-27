import { Check, Palette } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { THEMES } from '../modes';
import type { ThemeId } from '../types';

/** Compact header theme dropdown with visual swatch dots + AA/AAA contrast badges. */
export function ThemeMenu({
  theme,
  onSelect,
}: {
  theme: ThemeId;
  onSelect: (id: ThemeId) => void;
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

  const activeMeta = THEMES.find((t) => t.id === theme) ?? THEMES[0];

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`Color theme: ${activeMeta.name}`}
        title={`Color theme: ${activeMeta.name}`}
        className="aura-target flex items-center gap-1.5 rounded-full border text-xs hover:border-[var(--aura-calm)]"
        style={{
          borderColor: 'var(--aura-border-interactive)',
          background: 'var(--aura-surface)',
          color: 'var(--aura-text)',
        }}
      >
        <Palette size={13} style={{ color: 'var(--aura-calm)' }} aria-hidden />
        <span className="hidden sm:inline">{activeMeta.name}</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Choose color theme"
          className="aura-scale-in origin-top-right absolute right-0 z-30 mt-2 w-[min(320px,calc(100vw-24px))] rounded-2xl border p-3.5 text-sm shadow-2xl"
          style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
        >
          <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--aura-subtle)' }}>
            Color Theme
          </p>
          <ul className="space-y-1">
            {THEMES.map((t) => {
              const selected = t.id === theme;
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(t.id);
                      setOpen(false);
                    }}
                    className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-[var(--aura-surface-elev)]"
                    style={selected ? { background: 'var(--aura-surface-elev)' } : undefined}
                  >
                    <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                      {selected ? (
                        <Check size={14} style={{ color: 'var(--aura-calm)' }} aria-hidden />
                      ) : (
                        <span
                          className="flex h-4 w-4 overflow-hidden rounded-full border"
                          style={{ borderColor: 'var(--aura-border-interactive)' }}
                          aria-hidden
                        >
                          <span className="h-full w-1/2" style={{ background: t.swatches[0] }} />
                          <span className="h-full w-1/2" style={{ background: t.swatches[2] }} />
                        </span>
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-medium">{t.name}</span>
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                          style={{ background: 'var(--aura-bg)', color: 'var(--aura-subtle)' }}
                        >
                          {t.badge}
                        </span>
                      </span>
                      <span className="block text-xs" style={{ color: 'var(--aura-muted)' }}>
                        {t.desc}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Visual card grid for Wellness -> Ambient Comfort and Onboarding -> Step 3. */
export function ThemeCards({
  theme,
  onSelect,
}: {
  theme: ThemeId;
  onSelect: (id: ThemeId) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Color theme">
      {THEMES.map((t) => {
        const selected = t.id === theme;
        return (
          <button
            key={t.id}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onSelect(t.id)}
            className="flex flex-col gap-1.5 rounded-xl border p-2.5 text-left transition-all duration-150 hover:border-[var(--aura-calm)]"
            style={{
              borderColor: selected ? 'var(--aura-calm)' : 'var(--aura-border-interactive)',
              background: selected ? 'var(--aura-accent-soft)' : 'var(--aura-surface)',
            }}
          >
            <div className="flex w-full items-center justify-between gap-1">
              <div className="flex h-4 flex-1 overflow-hidden rounded-md border" style={{ borderColor: 'var(--aura-border)' }} aria-hidden>
                <span className="h-full flex-1" style={{ background: t.swatches[0] }} />
                <span className="h-full flex-1" style={{ background: t.swatches[1] }} />
                <span className="h-full w-4" style={{ background: t.swatches[2] }} />
              </div>
              <span className="text-[10px] font-semibold" style={{ color: 'var(--aura-subtle)' }}>
                {t.badge}
              </span>
            </div>
            <span className="text-xs font-medium">{t.name}</span>
          </button>
        );
      })}
    </div>
  );
}
