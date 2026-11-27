import { useEffect, useRef } from 'react';
import { apiPost } from '../api';

/**
 * Validated behavioural friction cues for Aura v2:
 *   - rage_click: 3+ clicks within 750ms & 48px, EXCLUDING checkboxes, radios, labels, and text selection.
 *   - hover_abandon: hovering 3+ distinct interactive controls (350ms-2500ms each) within 8s without clicking.
 *   - scroll_thrash: 3+ alternating vertical scroll direction reversals (>=180px each) within 4s.
 *   - backtrack: returning within 10s after opening an external source link.
 *
 * NOTE: Removed v1's broken `pauseMs >= 4000` click heuristic which falsely classified
 * normal reading pauses as `Disoriented`.
 */
export function useBehaviourSignals(enabled = true) {
  const clicks = useRef<{ t: number; x: number; y: number }[]>([]);

  useEffect(() => {
    if (!enabled) return;
    const send = (type: 'rage_click' | 'backtrack' | 'scroll_thrash' | 'hover_abandon') =>
      apiPost('/api/behavior', { type }).catch(() => undefined);

    // 1. Quick return after opening a source
    let openedAt = 0;
    const onReturn = () => {
      if (document.visibilityState === 'hidden' || !openedAt) return;
      if (performance.now() - openedAt < 10_000) void send('backtrack');
      openedAt = 0;
    };
    const onSourceOpen = (e: MouseEvent) => {
      if ((e.target as HTMLElement | null)?.closest?.('a[data-source-link]')) {
        openedAt = performance.now();
      }
    };
    window.addEventListener('focus', onReturn);
    document.addEventListener('visibilitychange', onReturn);
    window.addEventListener('click', onSourceOpen, { capture: true });

    // 2. Smart rage-click (ignore form controls & text selection)
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest('input[type="checkbox"], input[type="radio"], label')) return;
      if (e.detail >= 2 && !target?.closest('button, a')) return; // double/triple-click text selection
      const now = performance.now();
      const recent = clicks.current.filter((c) => now - c.t < 750);
      recent.push({ t: now, x: e.clientX, y: e.clientY });
      clicks.current = recent;
      if (recent.length >= 3 && Math.hypot(e.clientX - recent[0].x, e.clientY - recent[0].y) <= 48) {
        clicks.current = [];
        void send('rage_click');
      }
    };
    window.addEventListener('click', onClick, { capture: true });

    // 3. Hover-and-abandon across distinct interactive targets
    let currentEl: HTMLElement | null = null;
    let enteredAt = 0;
    let lastHoverSent = 0;
    const abandons: { t: number; el: HTMLElement }[] = [];

    const onMouseOver = (e: MouseEvent) => {
      const el = (e.target as HTMLElement | null)?.closest?.('a, button') as HTMLElement | null;
      if (!el || el === currentEl) return;
      const now = performance.now();
      if (currentEl) {
        const dur = now - enteredAt;
        if (dur >= 350 && dur <= 2500) {
          abandons.push({ t: now, el: currentEl });
          while (abandons.length && now - abandons[0].t > 8000) abandons.shift();
          const unique = new Set(abandons.map((a) => a.el));
          if (unique.size >= 3 && now - lastHoverSent > 8000) {
            abandons.length = 0;
            lastHoverSent = now;
            void send('hover_abandon');
          }
        }
      }
      currentEl = el;
      enteredAt = now;
    };
    const onMouseDownClear = () => {
      currentEl = null;
      abandons.length = 0;
    };
    window.addEventListener('mouseover', onMouseOver, { passive: true });
    window.addEventListener('mousedown', onMouseDownClear, { passive: true });

    // 4. Scroll thrash (rapid back-and-forth vertical scrolling)
    let lastY = window.scrollY;
    let dir: 1 | -1 | 0 = 0;
    let segmentDist = 0;
    let reversals: number[] = [];
    let lastThrashSent = 0;
    const onScroll = () => {
      const y = window.scrollY;
      const dy = y - lastY;
      lastY = y;
      if (Math.abs(dy) < 4) return;
      const nextDir: 1 | -1 = dy > 0 ? 1 : -1;
      if (dir === 0) {
        dir = nextDir;
        segmentDist = Math.abs(dy);
        return;
      }
      if (nextDir === dir) {
        segmentDist += Math.abs(dy);
      } else {
        if (segmentDist >= 180) {
          const now = performance.now();
          reversals = reversals.filter((t) => now - t < 4000);
          reversals.push(now);
          if (reversals.length >= 3 && now - lastThrashSent > 6000) {
            reversals = [];
            lastThrashSent = now;
            void send('scroll_thrash');
          }
        }
        dir = nextDir;
        segmentDist = Math.abs(dy);
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      window.removeEventListener('focus', onReturn);
      document.removeEventListener('visibilitychange', onReturn);
      window.removeEventListener('click', onSourceOpen, { capture: true });
      window.removeEventListener('click', onClick, { capture: true });
      window.removeEventListener('mouseover', onMouseOver);
      window.removeEventListener('mousedown', onMouseDownClear);
      window.removeEventListener('scroll', onScroll);
    };
  }, [enabled]);
}
