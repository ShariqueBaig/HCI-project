import { useEffect, useRef } from 'react';
import { apiPost } from '../api';

/**
 * Keystroke *timing* in the search box -> /api/telemetry/typing about once a second.
 * Never records characters or which key was pressed: only press/release times
 * and a kind, mirroring Aura's TelemetryDaemon error weights
 * (backend/search/typing.py documents the event format).
 */
type Kind = 'n' | 'b' | 'r' | 'rb' | 'c' | 'm';
interface KeyEvent {
  d?: number;
  u?: number;
  k: Kind;
}

const MODIFIERS = new Set(['Control', 'Alt', 'Meta']);
const DELETES = new Set(['Backspace', 'Delete']);
const FLUSH_MS = 1000;

export function useTypingDynamics(input: React.RefObject<HTMLInputElement | null>, enabled = true) {
  const pending = useRef<KeyEvent[]>([]);
  // physical key -> {press time, kind}; e.code is used only as a map key, never sent
  const down = useRef(new Map<string, { d: number; k: Kind }>());

  useEffect(() => {
    const el = input.current;
    if (!el || !enabled) return;

    const onDown = (e: KeyboardEvent) => {
      const t = performance.now();
      if (MODIFIERS.has(e.key)) return;
      const isDel = DELETES.has(e.key);
      const mod = e.ctrlKey || e.altKey || e.metaKey;
      if (mod && !isDel) return; // shortcut (Ctrl+A, Ctrl+V...) is not typing
      if (e.repeat) {
        pending.current.push({ d: t, k: isDel ? 'rb' : 'r' });
        return;
      }
      down.current.set(e.code, { d: t, k: isDel ? (mod ? 'c' : 'b') : 'n' });
    };

    const onUp = (e: KeyboardEvent) => {
      const t = performance.now();
      if (MODIFIERS.has(e.key)) {
        if (!e.ctrlKey && !e.altKey && !e.metaKey) pending.current.push({ u: t, k: 'm' });
        return;
      }
      const start = down.current.get(e.code);
      if (!start) return;
      down.current.delete(e.code);
      pending.current.push({ d: start.d, u: t, k: start.k });
    };

    const onBlur = () => down.current.clear();

    el.addEventListener('keydown', onDown);
    el.addEventListener('keyup', onUp);
    el.addEventListener('blur', onBlur);

    const timer = window.setInterval(() => {
      if (!pending.current.length) return;
      const events = pending.current.splice(0, pending.current.length);
      apiPost('/api/telemetry/typing', { events, now: performance.now() }).catch(() => {
        /* the state just goes stale; search still works */
      });
    }, FLUSH_MS);

    return () => {
      el.removeEventListener('keydown', onDown);
      el.removeEventListener('keyup', onUp);
      el.removeEventListener('blur', onBlur);
      window.clearInterval(timer);
    };
  }, [input, enabled]);
}
