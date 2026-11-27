import { useMemo } from 'react';
import { isLightTheme } from '../../modes';
import type { ThemeId, ViewPolicyName } from '../../types';
import { Heading } from './widgets';

const CSP =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:";

export function CustomWidgetFrame({
  title,
  html,
  theme = 'dark',
  mood = 'energized',
}: {
  title: string;
  html: string;
  theme?: ThemeId;
  mood?: ViewPolicyName;
}) {
  const doc = useMemo(() => {
    const cs = typeof document !== 'undefined' ? getComputedStyle(document.documentElement) : null;
    const light = isLightTheme(theme);
    const bg = cs?.getPropertyValue('--aura-surface').trim() || (light ? '#ffffff' : '#1b142b');
    const fg = cs?.getPropertyValue('--aura-text').trim() || (light ? '#1e1433' : '#f2ecfc');
    const link = cs?.getPropertyValue('--aura-calm').trim() || (light ? '#6324c7' : '#b794ff');
    return `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${CSP}">
<style>html,body{margin:0;padding:12px;background:${bg};color:${fg};font:14px/1.55 'Segoe UI',system-ui,sans-serif}
a,button{color:${link}}</style></head><body>${html}</body></html>`;
  }, [html, theme, mood]);

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
        Isolated interactive view (no external network access).
      </p>
    </section>
  );
}
