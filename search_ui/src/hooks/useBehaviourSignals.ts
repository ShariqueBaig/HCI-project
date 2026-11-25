import { useEffect, useRef } from 'react';
import { apiPost } from '../api';

/**
 * Friction cues for state fusion, ported from the webcam app's
 * useBehavioralTelemetry:
 *   rage click  -- 3+ clicks within 750 ms, all within 48 px of the first
 *   hesitation  -- the pointer moved, then sat still >= 4 s before a click
 * Fixed: the original reset lastMove before measuring the pause, so pauseMs
 * was always 0. Only the event type is sent; no coordinates or targets.
 */
export function useBehaviourSignals(enabled = true) {
  const clicks = useRef<{ t: number; x: number; y: number }[]>([]);
  const lastMove = useRef(0);
  const moved = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    const send = (type: 'rage_click' | 'hesitation' | 'backtrack') =>
      apiPost('/api/behavior', { type }).catch(() => undefined);

    // Quick return: a source was opened and the user came back within 10 s --
    // the page didn't have what they needed (a classic search-struggle signal).
    let openedAt = 0;
    const onReturn = () => {
      if (document.visibilityState === 'hidden' || !openedAt) return;
      if (performance.now() - openedAt < 10_000) void send('backtrack');
      openedAt = 0;
    };
    const onSourceOpen = (e: MouseEvent) => {
      if ((e.target as HTMLElement | null)?.closest?.('a[data-source-link]')) openedAt = performance.now();
    };
    window.addEventListener('focus', onReturn);
    document.addEventListener('visibilitychange', onReturn);
    window.addEventListener('click', onSourceOpen, { capture: true });

    const onMove = () => {
      lastMove.current = performance.now();
      moved.current = true;
    };

    const onClick = (e: MouseEvent) => {
      const now = performance.now();
      const recent = clicks.current.filter((c) => now - c.t < 750);
      recent.push({ t: now, x: e.clientX, y: e.clientY });
      clicks.current = recent;
      let rage = false;
      if (recent.length >= 3 && Math.hypot(e.clientX - recent[0].x, e.clientY - recent[0].y) <= 48) {
        rage = true;
        clicks.current = [];
      }
      const pauseMs = now - lastMove.current; // measured BEFORE resetting
      const hesitation = moved.current && pauseMs >= 4000;
      moved.current = false;
      lastMove.current = now;
      if (rage) void send('rage_click');
      else if (hesitation) void send('hesitation');
    };

    window.addEventListener('mousemove', onMove, { passive: true });
    window.addEventListener('click', onClick, { capture: true });
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('click', onClick, { capture: true });
      window.removeEventListener('focus', onReturn);
      document.removeEventListener('visibilitychange', onReturn);
      window.removeEventListener('click', onSourceOpen, { capture: true });
    };
  }, [enabled]);
}
