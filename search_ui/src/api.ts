// The per-launch token arrives in the window URL (?t=...) and must accompany
// every API and WebSocket request. It is never stored.
export const TOKEN = new URLSearchParams(window.location.search).get('t') ?? '';

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { 'X-Aura-Token': TOKEN } });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'X-Aura-Token': TOKEN, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      detail = typeof j.detail === 'string' ? j.detail : detail;
    } catch {
      /* not JSON */
    }
    throw new Error(`${r.status} ${detail}`);
  }
  return (await r.json()) as T;
}

export function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}?t=${encodeURIComponent(TOKEN)}`;
}
