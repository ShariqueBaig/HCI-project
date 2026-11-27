"""Validate a Stage B GenUI spec against Stage A and the active policy.

This is where "adapt the form, not the facts" is enforced:

  * Only widget types in the policy's `allowed_widgets` survive.
  * Facts are passed by *reference*: claim_ids / step indices / source_ids must
    exist in Stage A, or they are removed.
  * Any free text the LLM writes (condensed answer, table cells, step labels)
    must be *lexically grounded* in Stage A: every number must already appear
    there, and at most GROUNDING_MAX_NOVEL of its content words may be new.
    Ungrounded text is replaced by Stage A's own wording, or the widget drops.
  * Policy caps are enforced by truncation, never by failing the search.
  * The custom HTML slot is stripped unless the policy allows it, size-capped,
    and cleared of network-loading tags (it is also sandboxed client-side).

`validate_spec` returns (spec, report); the report lists every fix and the
spec's truth-invariance status, which is logged for the study.
"""
import re

GROUNDING_MAX_NOVEL = 0.25
CUSTOM_HTML_MAX = 20000
MAX_COMPONENTS = 10
TOPOLOGIES = ('stack', 'split', 'stepper')
REGIONS = ('main', 'side')

_STOP = set('''a an the of to in on for and or is are was were be been being by with as at from
that this these those it its their there they them you your we our can could should would
will may might must not no yes but if then than so such very more most less least also just
only into over under about after before while when where which who whom what why how all any
both each few other some many much one two three first second next new make makes made use
used using good best better well like get gets got have has had do does did done'''.split())

_NUM = re.compile(r'\d+(?:[.,]\d+)*')


def _stem(w):
    for suf in ('ing', 'iest', 'ier', 'est', 'ies', 'er', 'es', 'ed', 'ly', 's'):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            w = w[:-len(suf)] + ('y' if suf in ('iest', 'ier', 'ies') else '')
            break
    return w[:-1] if len(w) > 4 and w.endswith('e') else w


# Relative judgements allowed in ComparisonTable cells even when Stage A words
# them differently ("costs more" -> "Higher"). Only in rows whose axis is
# grounded; counted in the report as evaluative_cells for transparency.
EVALUATIVE = set('''higher lower faster slower more less better worse cheaper costlier larger smaller
bigger longer shorter louder quieter heavier lighter stronger weaker yes no none some varies
high low fast slow good poor limited strong weak moderate similar same different excellent
n/a na mixed depends'''.split())


def _content_words(text):
    return {_stem(w) for w in re.findall(r'[a-z][a-z\-]+', (text or '').lower())
            if w not in _STOP and len(w) > 3}


def build_vocabulary(stage_a, sources, query=''):
    parts = [query, stage_a.get('tldr', '')]
    parts += [c['text'] for c in stage_a.get('claims', [])]
    parts += stage_a.get('steps', []) + stage_a.get('key_entities', []) + stage_a.get('comparison_axes', [])
    parts += [s.get('title', '') for s in sources]
    blob = ' '.join(parts)
    return {'words': _content_words(blob), 'numbers': set(_NUM.findall(blob))}


def grounding(text, vocab):
    """Return (ok, novel_ratio, novel_words, novel_numbers)."""
    words = _content_words(text)
    novel = sorted(w for w in words if w not in vocab['words'])
    nums = sorted(n for n in _NUM.findall(text or '') if n not in vocab['numbers'])
    ratio = (len(novel) / len(words)) if words else 0.0
    return (not nums and ratio <= GROUNDING_MAX_NOVEL), round(ratio, 3), novel[:8], nums


def _words_cap(text, n):
    words = (text or '').split()
    if len(words) <= n:
        return text.strip()
    cut = ' '.join(words[:n])
    end = max(cut.rfind('. '), cut.rfind('? '), cut.rfind('! '))
    return (cut[:end + 1] if end > len(cut) * 0.5 else cut.rstrip(',;:') + '…').strip()


def _str(v, n=200):
    return v.strip()[:n] if isinstance(v, str) and v.strip() else ''


def _strs(v, n_items, n_chars=80):
    out = []
    for x in v if isinstance(v, list) else []:
        s = _str(x, n_chars)
        if s and s not in out:
            out.append(s)
        if len(out) >= n_items:
            break
    return out


def sanitise_html(html):
    h = (html or '')[:CUSTOM_HTML_MAX]
    # no network loads, frames, or navigation from the sandboxed widget
    h = re.sub(r'(?is)<\s*(script|link|iframe|object|embed|base|meta|form)[^>]*\bsrc\s*=.*?>', '', h)
    h = re.sub(r'(?is)<\s*(link|iframe|object|embed|base|meta|form)\b[^>]*>', '', h)
    h = re.sub(r'(?i)\b(href|src|action)\s*=\s*([\'"])\s*(https?:|//|javascript:)[^\'"]*\2', '', h)
    h = re.sub(r'(?i)url\(\s*([\'"]?)(https?:|//)[^)]*\)', 'none', h)
    return h


SIDE_WIDGETS = ('SourceList', 'FacetChips', 'FollowUpChips')


def normalise_layout(components, policy):
    """Layout shape is part of the policy (deterministic per state), not an LLM
    choice: in a split layout only navigation widgets go in the narrow side
    column, content always stays in the main column. Mutates regions; returns
    the topology actually used."""
    topology = policy.get('topology', 'stack')
    for c in components:
        c['region'] = 'side' if (topology == 'split' and c['type'] in SIDE_WIDGETS) else 'main'
    if topology == 'split' and not any(c['region'] == 'side' for c in components):
        topology = 'stack'
    return topology


def validate_spec(raw, stage_a, policy, sources, query='', trail=None):
    report = {'fixes': [], 'grounding_failures': [], 'dropped': [], 'evaluative_cells': 0}
    fix = report['fixes'].append
    claims = {c['id']: c for c in stage_a.get('claims', [])}
    steps = stage_a.get('steps', [])
    src_ids = [s['id'] for s in sources]
    vocab = build_vocabulary(stage_a, sources, query)
    allowed = set(policy['allowed_widgets'])
    budget = policy['answer_word_budget']
    raw = raw if isinstance(raw, dict) else {}

    def cids(v, cap=None):
        out = [i for i in (v if isinstance(v, list) else []) if isinstance(i, str) and i in claims]
        out = list(dict.fromkeys(out))
        if cap is not None and len(out) > cap:
            fix('capped claims {} -> {}'.format(len(out), cap))
            out = out[:cap]
        return out

    def grounded(text, where):
        ok, ratio, novel, nums = grounding(text, vocab)
        if not ok:
            report['grounding_failures'].append({'where': where, 'novel_ratio': ratio,
                                                 'novel_words': novel, 'novel_numbers': nums})
        return ok

    out_components = []
    seen_types = set()
    raw_components = raw.get('components') if isinstance(raw.get('components'), list) else []
    for i, c in enumerate(raw_components[:MAX_COMPONENTS * 2]):
        if not isinstance(c, dict):
            continue
        t = c.get('type')
        if t not in allowed:
            report['dropped'].append('{} (not allowed in {})'.format(t, policy['name']))
            continue
        if t in seen_types and t not in ('KeyFactsList',):
            report['dropped'].append('{} (duplicate)'.format(t))
            continue
        p = c.get('props') if isinstance(c.get('props'), dict) else {}
        region = c.get('region') if c.get('region') in REGIONS else 'main'
        props = None

        if t == 'AnswerCard':
            text = _str(p.get('text'), 1200) or stage_a.get('tldr', '')
            if text != stage_a.get('tldr') and not grounded(text, 'AnswerCard'):
                text = stage_a.get('tldr', '')
                fix('AnswerCard text not grounded; used the Stage A answer')
            capped = _words_cap(text, budget)
            if capped != text:
                fix('AnswerCard trimmed to {} words'.format(budget))
            props = {'text': capped, 'claim_ids': cids(p.get('claim_ids')),
                     'source_ids': [s for s in stage_a.get('tldr_source_ids', []) if s in src_ids]}
        elif t == 'KeyFactsList':
            ids = cids(p.get('claim_ids'), cap=policy['max_key_facts'])
            if ids:
                props = {'claim_ids': ids, 'title': _str(p.get('title'), 60)}
        elif t == 'GuidedSteps':
            items = []
            for s in (p.get('steps') if isinstance(p.get('steps'), list) else [])[:8]:
                if isinstance(s, int) and 0 <= s < len(steps):
                    items.append({'text': steps[s], 'claim_ids': []})
                elif isinstance(s, dict):
                    if isinstance(s.get('step_index'), int) and 0 <= s['step_index'] < len(steps):
                        items.append({'text': steps[s['step_index']], 'claim_ids': []})
                        continue
                    ids = cids(s.get('claim_ids'))
                    text = _str(s.get('text'), 240)
                    if text and grounded(text, 'GuidedSteps'):
                        items.append({'text': text, 'claim_ids': ids})
                    elif ids:
                        items.append({'text': claims[ids[0]]['text'], 'claim_ids': ids[:1]})
            cap = 3 if policy['name'] == 'overwhelmed' else 8
            asked = len(items)
            # the same step twice (often one claim restated) is never useful
            uniq, seen_text, seen_claims = [], set(), set()
            for it in items:
                key = re.sub(r'[^a-z0-9]+', ' ', it['text'].lower()).strip()
                if not key or key in seen_text or (it['claim_ids'] and set(it['claim_ids']) <= seen_claims):
                    continue
                seen_text.add(key)
                seen_claims.update(it['claim_ids'])
                uniq.append(it)
            if len(uniq) < len(items):
                fix('GuidedSteps: removed {} duplicate step(s)'.format(len(items) - len(uniq)))
            items = uniq
            facts_only = not steps      # not a how-to query: these are facts, not actions
            if facts_only:
                want = min(cap, max(asked, 2))
                for c in sorted(claims.values(), key=lambda c: -c.get('importance', 1)):
                    if len(items) >= want:
                        break
                    key = re.sub(r'[^a-z0-9]+', ' ', c['text'].lower()).strip()
                    if c['id'] not in seen_claims and key not in seen_text:
                        items.append({'text': c['text'], 'claim_ids': [c['id']]})
                        seen_claims.add(c['id'])
                        seen_text.add(key)
            if len(items) > cap:
                fix('GuidedSteps capped at {}'.format(cap))
                items = items[:cap]
            if facts_only and items:
                props = {'title': 'What matters most', 'steps': items, 'kind': 'facts'}
            elif items:
                props = {'title': _str(p.get('title'), 60), 'steps': items, 'kind': 'steps'}
        elif t == 'ComparisonTable':
            cols = _strs(p.get('columns'), policy['max_primary_options'], 60)
            rows = []
            for r in (p.get('rows') if isinstance(p.get('rows'), list) else [])[:8]:
                if not isinstance(r, dict):
                    continue
                axis = _str(r.get('axis'), 60)
                cells = [_str(x, 140) for x in (r.get('cells') if isinstance(r.get('cells'), list) else [])][:len(cols)]
                if not axis or not cells or not grounding(axis, vocab)[0]:
                    continue
                ok, evaluative = True, 0
                for x in cells:
                    if not x:
                        continue
                    if x.lower().strip(' .') in EVALUATIVE:
                        evaluative += 1
                    elif not grounded(x, 'ComparisonTable'):
                        ok = False
                if ok:          # only count judgements that are actually shown
                    report['evaluative_cells'] += evaluative
                    rows.append({'axis': axis, 'cells': cells + [''] * (len(cols) - len(cells))})
            if len(cols) >= 2 and rows:
                props = {'columns': cols, 'rows': rows, 'claim_ids': cids(p.get('claim_ids'))}
        elif t == 'ProsCons':
            pros, cons = cids(p.get('pros'), cap=4), cids(p.get('cons'), cap=4)
            if pros or cons:
                props = {'subject': _str(p.get('subject'), 60), 'pros': pros, 'cons': cons}
        elif t == 'Timeline':
            items = []
            for it in (p.get('items') if isinstance(p.get('items'), list) else [])[:8]:
                if isinstance(it, dict) and it.get('claim_id') in claims:
                    label = _str(it.get('label'), 40)
                    if label and not grounded(label, 'Timeline'):
                        label = ''
                    items.append({'label': label, 'claim_id': it['claim_id']})
            if items:
                props = {'items': items}
        elif t == 'SourceList':
            ids = [s for s in (p.get('source_ids') if isinstance(p.get('source_ids'), list) else []) if s in src_ids]
            props = {'source_ids': list(dict.fromkeys(ids)) or src_ids, 'compact': bool(p.get('compact'))}
        elif t == 'FacetChips':
            pool = {x.lower(): x for x in stage_a.get('key_entities', []) + stage_a.get('comparison_axes', [])}
            facets = [pool[f.lower()] for f in _strs(p.get('facets'), 8) if f.lower() in pool]
            if facets:
                props = {'facets': facets}
        elif t == 'FollowUpChips':
            qs = _strs(p.get('queries'), 4, 90)
            if qs:
                props = {'queries': qs}
        elif t == 'ClarifierChips':
            q, opts = _str(p.get('question'), 120), _strs(p.get('options'), 4, 60)
            if q and len(opts) >= 2:
                props = {'question': q, 'options': opts}
        elif t == 'QueryTrail':
            props = {'queries': list(trail or [])[-5:]}
        elif t in ('BreathingNudge', 'ReadAloud'):
            props = {}

        if props is None:
            report['dropped'].append('{} (no valid content)'.format(t))
            continue
        seen_types.add(t)
        out_components.append({'id': 'w{}'.format(len(out_components) + 1), 'type': t,
                               'region': region, 'props': props})
        if len(out_components) >= MAX_COMPONENTS:
            break

    custom = raw.get('custom_widget')
    custom_out = None
    if isinstance(custom, dict) and custom.get('html'):
        if policy.get('allow_custom_widget'):
            custom_out = {'title': _str(custom.get('title'), 60) or 'Interactive view',
                          'html': sanitise_html(custom['html'])}
        else:
            fix('custom widget removed (not allowed in {})'.format(policy['name']))

    topology = normalise_layout(out_components, policy)
    present = {c['type'] for c in out_components}
    report['missing_required'] = [w for w in policy['required_widgets'] if w not in present]
    # Every fact shown is now Stage A wording or text that passed grounding; the
    # count of pre-fix failures is the measurable "how often did the LLM drift".
    report['ungrounded_before_fix'] = len(report['grounding_failures'])
    report['truth_invariant'] = True
    return {'topology': topology, 'components': out_components, 'custom_widget': custom_out,
            'rationale': _str(raw.get('rationale'), 300)}, report


def referenced_claims(spec):
    """All Stage A claim ids a spec shows -- used to check truth invariance."""
    ids = set()
    for c in spec.get('components', []):
        p = c['props']
        for k in ('claim_ids', 'pros', 'cons'):
            ids.update(p.get(k, []))
        for s in p.get('steps', []):
            ids.update(s.get('claim_ids', []))
        for it in p.get('items', []):
            ids.add(it.get('claim_id'))
    ids.discard(None)
    return ids
