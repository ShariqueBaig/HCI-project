import type { SearchResponse, StreamStageAPayload } from './types';

export const TOKEN = new URLSearchParams(window.location.search).get('t') ?? '';

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { 'X-Aura-Token': TOKEN } });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      if (typeof j.detail === 'string') detail = j.detail;
    } catch { /* ignore */ }
    throw new Error(`${r.status} ${detail}`);
  }
  return (await r.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'X-Aura-Token': TOKEN, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      detail = typeof j.detail === 'string' ? j.detail : detail;
    } catch { /* not JSON */ }
    throw new Error(`${r.status} ${detail}`);
  }
  return (await r.json()) as T;
}

export function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}?t=${encodeURIComponent(TOKEN)}`;
}

export interface StreamHandlers {
  onStage: (stage: string, message: string, meta?: { sourceCount?: number; provider?: string }) => void;
  onStageA: (payload: StreamStageAPayload) => void;
  onDone: (result: SearchResponse) => void;
}

export async function apiStreamSearch(
  query: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch('/api/search/stream', {
    method: 'POST',
    headers: { 'X-Aura-Token': TOKEN, 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal,
  });
  if (!r.ok || !r.body) {
    throw new Error(`${r.status} ${r.statusText}`);
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx = buf.indexOf('\n\n');
    while (idx !== -1) {
      const raw = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      idx = buf.indexOf('\n\n');
      for (const line of raw.split('\n')) {
        if (!line.startsWith('data:')) continue;
        const msg = JSON.parse(line.slice(5).trim()) as {
          event: string;
          stage?: string;
          message?: string;
          source_count?: number;
          provider?: string;
          detail?: string;
          result?: SearchResponse;
        } & StreamStageAPayload;
        if (msg.event === 'stage' && msg.stage) {
          handlers.onStage(msg.stage, msg.message ?? '', {
            sourceCount: msg.source_count,
            provider: msg.provider,
          });
        } else if (msg.event === 'stageA') {
          handlers.onStageA(msg);
        } else if (msg.event === 'done' && msg.result) {
          handlers.onDone(msg.result);
        } else if (msg.event === 'error') {
          throw new Error(msg.detail || 'Search failed');
        }
      }
    }
  }
}
