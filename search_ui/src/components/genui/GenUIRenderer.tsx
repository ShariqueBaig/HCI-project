import { Component, useMemo, useState } from 'react';
import type { SearchResponse, Spec, SpecComponent, ThemeId, ViewPolicyName } from '../../types';
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

class WidgetBoundary extends Component<{ type: string; children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: unknown) {
    console.error(`[Aura] widget ${this.props.type} failed:`, err);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function GenUIRenderer({
  data,
  spec,
  onQuery,
  theme = 'dark',
  checkedSteps,
  onToggleStep,
}: {
  data: SearchResponse;
  spec: Spec;
  onQuery: (q: string) => void;
  theme?: ThemeId;
  checkedSteps?: Set<number>;
  onToggleStep?: (index: number) => void;
}) {
  const [focusSource, setFocusSource] = useState<string | null>(null);
  const [localSteps, setLocalSteps] = useState<Set<number>>(new Set());

  const activeSteps = checkedSteps ?? localSteps;
  const toggleStep = onToggleStep ?? ((idx: number) => {
    setLocalSteps((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  });

  const ctx: GenCtx = useMemo(() => {
    const answer = spec.components.find((c) => c.type === 'AnswerCard')?.props.text ?? data.stageA.tldr;
    return {
      searchId: data.search_id,
      policyName: (spec.policy as ViewPolicyName) || 'neutral',
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
      checkedSteps: activeSteps,
      onToggleStep: toggleStep,
    };
  }, [data, spec, focusSource, onQuery, activeSteps, toggleStep]);

  const render = (c: SpecComponent, idx: number) => {
    const W = WIDGETS[c.type];
    return W ? (
      <div
        key={c.id}
        data-widget={c.type}
        className="aura-fade-up"
        style={{ animationDelay: `${Math.min(idx * 45, 225)}ms` }}
      >
        <WidgetBoundary type={c.type}><W {...c.props} /></WidgetBoundary>
      </div>
    ) : null;
  };

  const main = spec.components.filter((c) => c.region !== 'side');
  const side = spec.components.filter((c) => c.region === 'side');
  const custom = spec.custom_widget && (
    <div className="aura-fade-up" style={{ animationDelay: `${Math.min(spec.components.length * 45, 250)}ms` }}>
      <CustomWidgetFrame
        title={spec.custom_widget.title}
        html={spec.custom_widget.html}
        theme={theme}
        mood={(spec.policy as ViewPolicyName) || 'energized'}
      />
    </div>
  );

  return (
    <Ctx.Provider value={ctx}>
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
