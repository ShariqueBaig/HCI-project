import { useCallback, useEffect, useRef, useState } from 'react';

export interface BehavioralCounters {
  clicks: number;
  rageClicks: number;
  hesitations: number;
  backtracks: number;
  errors: number;
}

const ZERO_COUNTERS: BehavioralCounters = {
  clicks: 0,
  rageClicks: 0,
  hesitations: 0,
  backtracks: 0,
  errors: 0,
};

export function useBehavioralTelemetry(sessionId: string | null) {
  const [counters, setCounters] = useState<BehavioralCounters>(ZERO_COUNTERS);
  const recentClicksRef = useRef<Array<{ t: number; x: number; y: number }>>([]);
  const lastMoveRef = useRef<number>(Date.now());
  const movedRef = useRef<boolean>(false);

  useEffect(() => {
    setCounters(ZERO_COUNTERS);
    recentClicksRef.current = [];
    lastMoveRef.current = Date.now();
    movedRef.current = false;
  }, [sessionId]);

  const sendEvent = useCallback(
    async (eventType: string, targetId = '', metadata: Record<string, unknown> = {}) => {
      if (!sessionId) return;
      try {
        await fetch('/api/research/event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            event_type: eventType,
            target_id: targetId,
            metadata,
          }),
        });
      } catch {
        // non-blocking telemetry
      }
    },
    [sessionId],
  );

  const logEvent = useCallback(
    (type: 'backtrack' | 'error' | 'filter_change' | 'task_complete', targetId = '', metadata: Record<string, unknown> = {}) => {
      if (!sessionId) return;
      if (type === 'backtrack') {
        setCounters((c) => ({ ...c, backtracks: c.backtracks + 1 }));
      } else if (type === 'error') {
        setCounters((c) => ({ ...c, errors: c.errors + 1 }));
      }
      sendEvent(type, targetId, metadata);
    },
    [sessionId, sendEvent],
  );

  useEffect(() => {
    if (!sessionId) return;

    const handleMove = () => {
      lastMoveRef.current = Date.now();
      movedRef.current = true;
    };

    const handleClick = (e: MouseEvent) => {
      const now = Date.now();
      const targetEl = e.target as HTMLElement | null;
      const label = targetEl?.tagName?.toLowerCase() ?? 'unknown';

      let isRage = false;
      const recent = recentClicksRef.current.filter((c) => now - c.t < 750);
      recent.push({ t: now, x: e.clientX, y: e.clientY });
      recentClicksRef.current = recent;

      if (recent.length >= 3) {
        const first = recent[0];
        const dist = Math.hypot(e.clientX - first.x, e.clientY - first.y);
        if (dist <= 48) {
          isRage = true;
          recentClicksRef.current = [];
        }
      }

      const isHesitation = movedRef.current && now - lastMoveRef.current >= 4000;
      movedRef.current = false;
      lastMoveRef.current = now;

      setCounters((c) => ({
        ...c,
        clicks: c.clicks + 1,
        rageClicks: c.rageClicks + (isRage ? 1 : 0),
        hesitations: c.hesitations + (isHesitation ? 1 : 0),
      }));

      if (isRage) {
        sendEvent('rage_click', label, { x: e.clientX, y: e.clientY });
      } else if (isHesitation) {
        sendEvent('hesitation_click', label, { pauseMs: now - lastMoveRef.current });
      }
    };

    window.addEventListener('mousemove', handleMove, { passive: true });
    window.addEventListener('click', handleClick, { capture: true });
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('click', handleClick, { capture: true });
    };
  }, [sessionId, sendEvent]);

  return { counters, logEvent };
}
