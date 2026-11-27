import { Component, useMemo, useState } from 'react';
import type { SearchResponse, Spec, SpecComponent } from '../../types';
import { CustomWidgetFrame } from './CustomWidgetFrame';
import {
  AnswerCard, BreathingNudge, ClarifierChips, ComparisonTable, Ctx, FacetChips, FollowUpChips,
  GuidedSteps, KeyFactsList, ProsCons, QueryTrail, ReadAloud, SourceList, Timeline,
  type GenCtx,
} from './widgets';

/* eslint-disable @typescript-eslint/no-explicit-any */
const WIDGETS: Record<SpecComponent['type'], React.ComponentType<any>> = {
  AnswerCard, KeyFactsList, GuidedSteps, ComparisonTable, ProsCons, Timeline, SourceList,
  FacetChips, FollowUpChips, ClarifierChips, QueryTrail, BreathingNudge, ReadAloud,
};

function tokenStyle(spec: Spec): React.CSSProperties {
  const t = spec.tokens ?? { targetScale: 1, typographyScale: 1, lineHeight: 1.55 };
  return {
    '--aura-target-scale': String(t.targetScale),
    '--aura-type-scale': String(t.typographyScale),
    '--aura-line-height': String(t.lineHeight),
  } as React.CSSProperties;
}

/** One misbehaving widget is dropped instead of blanking the whole results page. */
class WidgetBoundary extends Component<{ type: string; children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: unknown) {
    console.error(`[Aura Search] widget ${this.props.type} failed:`, err);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/** Renders a validated Stage B spec. Unknown widget types are skipped, never crash. */
export function GenUIRenderer({ data, spec, onQuery }: {
  data: SearchResponse;
  spec: Spec;
  onQuery: (q: string) => void;
}) {
  const [focusSource, setFocusSource] = useState<string | null>(null);

  const ctx: GenCtx = useMemo(() => {
    const answer = spec.components.find((c) => c.type === 'AnswerCard')?.props.text ?? data.stageA.tldr;
    return {
      stageA: data.stageA,
      claims: Object.fromEntries(data.stageA.claims.map((c) => [c.id, c])),
      sources: Object.fromEntries(data.sources.map((s) => [s.id, s])),
      sourceOrder: data.sources.map((s) => s.id),
      focusSource,
      onCite: (id: string) => {
        setFocusSource(id);
        document.getElementById(`src-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      },
      onQuery,
      answerText: answer,
    };
  }, [data, spec, focusSource, onQuery]);

  const render = (c: SpecComponent) => {
    const W = WIDGETS[c.type];
    // Rendered as elements (not called as functions) so each widget's hooks and
    // context reads happen inside the provider, in its own component.
    return W ? (
      <div key={c.id} data-widget={c.type}>
        <WidgetBoundary type={c.type}><W {...c.props} /></WidgetBoundary>
      </div>
    ) : null;
  };
  const main = spec.components.filter((c) => c.region !== 'side');
  const side = spec.components.filter((c) => c.region === 'side');
  const custom = spec.custom_widget && <CustomWidgetFrame title={spec.custom_widget.title} html={spec.custom_widget.html} />;

  return (
    <Ctx.Provider value={ctx}>
      {/* Each layout carries its own policy tokens, so Standard view and the dev
          comparison never inherit the live state's text size or target scale. */}
      <div className="@container" style={tokenStyle(spec)}>
        {spec.topology === 'split' && side.length > 0 ? (
          <div className="grid grid-cols-1 gap-6 @2xl:grid-cols-[minmax(0,1fr)_minmax(0,18rem)]">
            <div className="flex min-w-0 flex-col gap-6">{main.map(render)}{custom}</div>
            <aside className="flex min-w-0 flex-col gap-6">{side.map(render)}</aside>
          </div>
        ) : (
          <div className={`flex flex-col ${spec.topology === 'stepper' ? 'mx-auto max-w-xl gap-7' : 'gap-6'}`}>
            {spec.components.map(render)}
            {custom}
          </div>
        )}
      </div>
    </Ctx.Provider>
  );
}
