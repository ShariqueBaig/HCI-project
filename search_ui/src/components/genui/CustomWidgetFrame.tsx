import { useMemo } from 'react';
import { Heading } from './widgets';

/**
 * The one free-form GenUI slot (energized policy only). LLM-written HTML runs in
 * an iframe with:
 *   sandbox="allow-scripts"  -> scripts run, but in a unique opaque origin:
 *                               no access to this page, its token, cookies or storage
 *   CSP default-src 'none'   -> no network at all (no fetch, images, fonts, beacons)
 * The server has already stripped external src/href and capped the size.
 */
const CSP =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:";

export function CustomWidgetFrame({ title, html }: { title: string; html: string }) {
  const doc = useMemo(
    () => `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${CSP}">
<style>html,body{margin:0;padding:12px;background:#15131d;color:#e8e6ed;font:14px/1.5 system-ui,sans-serif}
a{color:#7fae9d}</style></head><body>${html}</body></html>`,
    [html],
  );
  return (
    <section aria-label={title}>
      <Heading>{title} · interactive</Heading>
      <iframe
        title={title}
        srcDoc={doc}
        sandbox="allow-scripts"
        referrerPolicy="no-referrer"
        className="h-80 w-full rounded-xl border"
        style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}
      />
      <p className="mt-1 text-xs" style={{ color: 'var(--aura-muted)' }}>
        Generated view. It runs isolated from this page and cannot load anything from the internet.
      </p>
    </section>
  );
}
