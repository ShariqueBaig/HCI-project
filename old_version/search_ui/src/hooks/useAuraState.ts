import { useEffect, useRef, useState } from 'react';
import { apiGet, TOKEN, wsUrl } from '../api';
import type { ConnectionStatus, LiveState, StatePayload, StateSnapshot } from '../types';

/** Live Aura state: one REST read, then the /ws/state push (2 Hz), reconnecting. */
export function useAuraState() {
  const [live, setLive] = useState<LiveState | null>(null);
  const [snap, setSnap] = useState<StateSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>(TOKEN ? 'connecting' : 'unauthorized');
  const retry = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!TOKEN) return;
    let ws: WebSocket | null = null;
    let closed = false;

    apiGet<StatePayload>('/api/state')
      .then((p) => {
        if (p.live) setLive(p.live);
        if (p.state) setSnap(p.state);
      })
      .catch((e: Error) => {
        if (e.message.startsWith('401')) setStatus('unauthorized');
      });

    const connect = () => {
      ws = new WebSocket(wsUrl('/ws/state'));
      ws.onopen = () => setStatus('live');
      ws.onmessage = (ev) => {
        const p = JSON.parse(ev.data) as StatePayload;
        if (p.live) setLive(p.live);
        if (p.state) setSnap(p.state);
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
  }, []);

  return { live, snap, status };
}
