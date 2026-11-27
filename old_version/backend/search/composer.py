"""Stage B: state-conditioned GenUI composer ("then form").

Input: Stage A (canonical claims, state-blind), the active policy, and a short
state summary. Output: a widget spec that may only *select, order and
condense* Stage A -- never add facts (validator.py enforces it).

Two paths, same output shape:
  * LLM  -- the model chooses widgets/props within the policy (OpenRouter JSON).
  * template -- a deterministic layout per policy; used offline, when the LLM
    fails, and to fill any required widget the LLM left out.

For the prompt-only condition (policy 'neutral') the LLM is *not* told the
user's state, so C1 (prompt-only GenUI) vs C2 (state-aware GenUI) differ only
in the state input -- the core comparison of the study.
"""
import json
import time

from backend.search.validator import normalise_layout, validate_spec

WIDGET_CATALOG = {
    'AnswerCard': '{"text": condensed answer (<= word budget, only facts from the claims), "claim_ids": [...]}',
    'KeyFactsList': '{"title": short heading, "claim_ids": [ids in display order]}',
    'GuidedSteps': '{"title": short heading, "steps": [step index (int, into stage_a.steps) | '
                   '{"text": short imperative from the claims, "claim_ids": [...]}]}',
    'ComparisonTable': '{"columns": [options being compared], "rows": [{"axis": dimension, '
                       '"cells": [one short phrase per column, only facts from the claims]}], "claim_ids": [...]}',
    'ProsCons': '{"subject": what is evaluated, "pros": [claim_ids], "cons": [claim_ids]}',
    'Timeline': '{"items": [{"label": short date/phase, "claim_id": id}]}',
    'SourceList': '{"source_ids": [...], "compact": true|false}',
    'FacetChips': '{"facets": [values copied from key_entities or comparison_axes]}',
    'FollowUpChips': '{"queries": [2-4 natural next searches]}',
    'ClarifierChips': '{"question": one short question, "options": [2-4 short answers]}',
    'QueryTrail': '{} (filled by the system with recent searches)',
    'BreathingNudge': '{} (a small calm-down prompt)',
    'ReadAloud': '{} (a read-aloud button for the answer)',
}

SYSTEM = (
    "You design the results page of a search engine as a JSON layout made of predefined widgets. "
    "The facts were already extracted (stage_a); you may only SELECT, ORDER and CONDENSE them. "
    "Never add facts, numbers, names or advice that are not in stage_a. Refer to facts by claim_id. "
    "Obey the policy exactly: use only allowed_widgets, include every required widget, respect "
    "answer_word_budget, max_key_facts and max_primary_options, and match the tone. "
    "Return ONLY JSON: {\"topology\": \"stack\"|\"split\"|\"stepper\", \"components\": "
    "[{\"type\": widget, \"region\": \"main\"|\"side\", \"props\": {...}}], "
    "\"custom_widget\": null or {\"title\": str, \"html\": self-contained HTML+inline JS, no external "
    "resources} (ONLY if policy.allow_custom_widget and an interactive view genuinely helps), "
    "\"rationale\": one sentence on why this layout fits}. "
    "topology: stack = one column; split = main column plus a side column; stepper = one guided column."
)


def _compact_stage_a(stage_a):
    return {
        'tldr': stage_a.get('tldr', ''),
        'claims': [{'id': c['id'], 'text': c['text'], 'importance': c['importance']}
                   for c in stage_a.get('claims', [])],
        'steps': list(enumerate(stage_a.get('steps', []))),
        'key_entities': stage_a.get('key_entities', []),
        'comparison_axes': stage_a.get('comparison_axes', []),
    }


def build_messages(query, stage_a, sources, policy, state_summary=None, history=None):
    pol = {k: policy[k] for k in ('name', 'answer_word_budget', 'reading_level', 'max_primary_options',
                                   'max_key_facts', 'required_widgets', 'allowed_widgets', 'density',
                                   'tone', 'show_facets', 'show_sources_inline', 'proactive',
                                   'allow_custom_widget', 'topology')}
    payload = {
        'query': query,
        'policy': pol,
        'widget_props': {w: WIDGET_CATALOG[w] for w in policy['allowed_widgets'] if w in WIDGET_CATALOG},
        'stage_a': _compact_stage_a(stage_a),
        'sources': [{'id': s['id'], 'title': s.get('title', '')} for s in sources],
    }
    # Fixed parts first, changing parts last (prefix caching): earlier searches,
    # then the user's state. History is one line per earlier search.
    if history:
        payload['earlier_searches'] = list(history)[-10:]
    if state_summary:
        payload['user_state'] = state_summary       # omitted for the prompt-only condition
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]


# ----------------------------------------------------------------- templates --

def _by_importance(stage_a, n, min_imp=1):
    cl = [c for c in stage_a.get('claims', []) if c['importance'] >= min_imp]
    cl = sorted(cl, key=lambda c: -c['importance'])[:n]
    order = {c['id']: i for i, c in enumerate(stage_a.get('claims', []))}
    return [c['id'] for c in sorted(cl, key=lambda c: order[c['id']])]


def _first_sentence(text):
    for sep in ('. ', '? ', '! '):
        if sep in text:
            return text.split(sep)[0] + sep.strip()
    return text


def template_spec(stage_a, policy, sources, trail=None):
    """Deterministic layout for a policy, in raw (pre-validation) spec form."""
    name = policy['name']
    steps = stage_a.get('steps', [])
    src = [s['id'] for s in sources]
    tldr = stage_a.get('tldr', '')
    axes, ents = stage_a.get('comparison_axes', []), stage_a.get('key_entities', [])
    C = []

    def add(t, props=None, region='main'):
        C.append({'type': t, 'region': region, 'props': props or {}})

    def step_widget(n, title):
        if steps:
            add('GuidedSteps', {'title': title, 'steps': list(range(min(n, len(steps))))})
        else:
            add('GuidedSteps', {'title': title,
                                'steps': [{'claim_ids': [i]} for i in _by_importance(stage_a, n, 2)]})

    if name == 'overwhelmed':
        add('AnswerCard', {'text': _first_sentence(tldr)})
        step_widget(3, 'Start here' if steps else 'What matters most')
        add('BreathingNudge')
        add('SourceList', {'source_ids': src[:3], 'compact': True})
        topology = 'stepper'
    elif name == 'fatigued':
        add('AnswerCard', {'text': tldr})
        add('ReadAloud')
        add('KeyFactsList', {'title': 'In short', 'claim_ids': _by_importance(stage_a, 4, 2)})
        add('SourceList', {'source_ids': src, 'compact': True})
        topology = 'stack'
    elif name == 'disoriented':
        add('QueryTrail')
        add('AnswerCard', {'text': tldr})
        if steps:
            step_widget(5, 'Step by step')
        else:
            add('KeyFactsList', {'title': 'Key facts', 'claim_ids': _by_importance(stage_a, 5)})
        if len(axes) >= 2:
            add('ClarifierChips', {'question': 'What matters most to you?', 'options': axes[:4]})
        add('SourceList', {'source_ids': src})
        topology = 'stack'
    elif name == 'energized':
        add('AnswerCard', {'text': tldr})
        facets = (axes + ents)[:8]
        if facets:
            add('FacetChips', {'facets': facets})
        if steps:
            step_widget(8, 'Steps')
        add('KeyFactsList', {'title': 'Explore the facts', 'claim_ids': _by_importance(stage_a, 10)})
        add('SourceList', {'source_ids': src}, region='side')
        topology = 'split'
    elif name == 'focused':
        add('AnswerCard', {'text': tldr})
        if steps:
            step_widget(8, 'Steps')
        add('KeyFactsList', {'title': 'Key facts', 'claim_ids': _by_importance(stage_a, 10)})
        add('SourceList', {'source_ids': src, 'compact': True}, region='side')
        topology = 'split'
    else:   # neutral / prompt-only
        add('AnswerCard', {'text': tldr})
        if steps:
            step_widget(8, 'Steps')
        add('KeyFactsList', {'title': 'Key facts', 'claim_ids': _by_importance(stage_a, policy['max_key_facts'])})
        add('SourceList', {'source_ids': src})
        topology = 'stack'
    return {'topology': topology, 'components': C,
            'rationale': 'Template layout for the {} rules.'.format(policy['label'].lower())}


def _merge_required(spec, report, stage_a, policy, sources, query, trail):
    """Add required widgets the LLM left out, taken from the template."""
    missing = list(report.get('missing_required') or [])
    present = {c['type'] for c in spec['components']}
    pro = policy.get('proactive', {})
    if pro.get('clarifiers') and len(stage_a.get('comparison_axes', [])) >= 2 and 'ClarifierChips' not in present:
        missing.append('ClarifierChips')
    if pro.get('breathing_nudge') and 'BreathingNudge' not in present:
        missing.append('BreathingNudge')
    facets_available = stage_a.get('key_entities') or stage_a.get('comparison_axes')
    if policy.get('show_facets') and facets_available and 'FacetChips' not in present:
        missing.append('FacetChips')
    if not missing:
        return spec
    tpl, _ = validate_spec(template_spec(stage_a, policy, sources, trail), stage_a, policy, sources, query, trail)
    comps = list(spec['components'])
    for w in missing:
        c = next((x for x in tpl['components'] if x['type'] == w), None)
        if c:
            if w == 'QueryTrail':
                pos = 0
            elif w == 'AnswerCard':
                pos = 1 if comps and comps[0]['type'] == 'QueryTrail' else 0
            elif w == 'SourceList' or not any(x['type'] == 'SourceList' for x in comps):
                pos = len(comps)
            else:       # keep sources last
                pos = next(i for i, x in enumerate(comps) if x['type'] == 'SourceList')
            comps.insert(pos, dict(c))
            report['fixes'].append('added required {} from template'.format(w))
    for i, c in enumerate(comps, 1):
        c['id'] = 'w{}'.format(i)
    report['missing_required'] = []
    topology = normalise_layout(comps, policy)
    return dict(spec, components=comps, topology=topology)


class Composer:
    def __init__(self, llm=None):
        self.llm = llm

    def compose(self, query, stage_a, sources, policy, state_summary=None, trail=None, use_llm=True,
                history=None):
        t0 = time.perf_counter()
        meta = {'policy': policy['name'], 'source': 'template', 'model': None, 'note': '',
                'tokens': dict(policy['tokens'])}   # applied to this layout only, client-side
        raw = None
        if not stage_a.get('claims'):
            spec = {'topology': 'stack', 'components': [], 'custom_widget': None,
                    'rationale': 'No results.'}
            return dict(spec, **meta, report={}, ms=0)
        if use_llm and self.llm is not None and getattr(self.llm, 'key', ''):
            try:
                raw, model = self.llm.complete_json(
                    build_messages(query, stage_a, sources, policy,
                                   None if policy['name'] == 'neutral' else state_summary,
                                   None if policy['name'] == 'neutral' else history),
                    max_tokens=3000, timeout=30, temperature=0.2)
                meta.update(source='llm', model=model)
            except Exception as e:
                meta['note'] = 'LLM unavailable ({}); template layout'.format(str(e)[:100])
        if raw is None:
            raw = template_spec(stage_a, policy, sources, trail)
        spec, report = validate_spec(raw, stage_a, policy, sources, query, trail)
        if meta['source'] == 'llm' and len(spec['components']) < 2:
            meta.update(source='template', note='LLM layout was empty after validation; template layout')
            spec, report = validate_spec(template_spec(stage_a, policy, sources, trail),
                                         stage_a, policy, sources, query, trail)
        spec = _merge_required(spec, report, stage_a, policy, sources, query, trail)
        meta['ms'] = round((time.perf_counter() - t0) * 1000)
        return dict(spec, **meta, report=report)


def state_summary_from(fused):
    """What the composer is told about the user (never raw sensor values)."""
    if not fused:
        return None
    return {'state': fused.get('committed_state') or fused.get('state'),
            'confidence': fused.get('confidence'),
            'why': fused.get('evidence', [])[:3]}
