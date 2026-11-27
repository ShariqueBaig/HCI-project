import { useCallback, useEffect, useRef, useState } from 'react';
import { apiGet, TOKEN, wsUrl } from '../api';
import type { AppStatus, ConnectionStatus, LiveState, StatePayload, StateSnapshot } from '../types';

/** Live Aura state + unified companion status over WebSocket (2 Hz), reconnecting. */
export function useAuraState() {
  const [live, setLive] = useState<LiveState | null>(null);
  const [snap, setSnap] = useState<StateSnapshot | null>(null);
  const [app, setApp] = useState<AppStatus | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>(TOKEN ? 'connecting' : 'unauthorized');
  const retry = useRef<number | undefined>(undefined);

  const applyPayload = useCallback((p: StatePayload) => {
    if (p.live) setLive(p.live);
    if (p.state) setSnap(p.state);
    if (p.app !== undefined && p.app !== null) setApp(p.app);
  }, []);

  const refreshNow = useCallback(async () => {
    if (!TOKEN) return;
    try {
      const p = await apiGet<StatePayload>('/api/state');
      applyPayload(p);
    } catch { /* ignore */ }
  }, [applyPayload]);

  useEffect(() => {
    if (!TOKEN) return;
    let ws: WebSocket | null = null;
    let closed = false;

    apiGet<StatePayload>('/api/state')
      .then(applyPayload)
      .catch((e: Error) => {
        if (e.message.startsWith('401')) setStatus('unauthorized');
      });

    const connect = () => {
      ws = new WebSocket(wsUrl('/ws/state'));
      ws.onopen = () => setStatus('live');
      ws.onmessage = (ev) => {
        applyPayload(JSON.parse(ev.data) as StatePayload);
      };
      ws.onclose = (ev) => {
        if (closed) return;
        if (ev.code === 4401) {
          setStatus('unauthorized');
          return;
        }
        setStatus('offline');
        retry.current = window.setTimeout(connect, 1500);
      };
    };
    connect();

    return () => {
      closed = true;
      window.clearTimeout(retry.current);
      ws?.close();
    };
  }, [applyPayload]);

  return { live, snap, app, setApp, status, refreshNow };
}
