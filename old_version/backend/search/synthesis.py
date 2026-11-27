"""Stage A: grounded, state-blind synthesis ("facts first").

Turns retrieved sources into a canonical set of cited claims. It never sees the
user's state -- that is what guarantees the later state-conditioned stage can
only change the *form* of the answer, never the facts (docs/AURA_SEARCH_PLAN.md
section 4). Output (`StageA`):

    {tldr, tldr_source_ids, claims[{id, text, source_ids, importance}],
     key_entities[], comparison_axes[], steps[], used_llm, model, note}

Every claim must cite at least one retrieved source; anything else is dropped
by `sanitise`. With no OpenRouter key (or when every model fails), an
extractive fallback builds the same structure from source sentences, so search
always returns something.
"""
import json
import re
import threading
from collections import OrderedDict

MAX_SOURCES = 6
SOURCE_CHARS = 1600
MAX_CLAIMS = 10

SYSTEM = (
    "You are the fact-synthesis stage of a search engine. You receive a user query "
    "and numbered web sources. Produce ONLY a JSON object with these keys:\n"
    '  "tldr": one or two plain sentences that directly answer the query,\n'
    '  "tldr_source_ids": source ids supporting the tldr,\n'
    '  "claims": 4-10 items {"text": one self-contained factual sentence, '
    '"source_ids": ["s1", ...], "importance": 1|2|3 (3 = essential to the answer)},\n'
    '  "key_entities": up to 6 short names (products, people, concepts) the answer is about,\n'
    '  "comparison_axes": up to 5 short dimensions along which options differ (empty if not a comparison),\n'
    '  "steps": if the query asks how to do, make, start, fix or choose something, 3-8 ordered '
    'imperative steps drawn from the sources (each one short sentence); otherwise [].\n'
    "Rules: use ONLY facts stated in the sources; every claim and the tldr must cite the "
    "source ids that state it; never invent sources or ids; no advice beyond the sources; "
    "neutral tone; do not mention 'the sources' in the text. Write in English."
)


def _sources_block(sources):
    parts = []
    for s in sources[:MAX_SOURCES]:
        text = (s.get('content') or s.get('snippet') or '')[:SOURCE_CHARS]
        parts.append('[{}] {} ({})\n{}'.format(s['id'], s.get('title', ''), s.get('url', ''), text))
    return '\n\n'.join(parts)


def build_messages(query, sources):
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': 'Query: {}\n\nSources:\n\n{}'.format(query, _sources_block(sources))}]


def _str_list(x, n, maxlen=80):
    if not isinstance(x, list):
        return []
    out = []
    for v in x:
        if isinstance(v, dict):     # models sometimes wrap items: {"step": "..."} / {"name": "..."}
            v = next((w for w in v.values() if isinstance(w, str) and w.strip()), '')
        if isinstance(v, str) and v.strip():
            out.append(v.strip()[:maxlen])
        if len(out) >= n:
            break
    return out


def sanitise(raw, source_ids):
    """Validate an LLM Stage A object. Drops anything uncited or citing unknown
    sources, renumbers claims c1..cN. Returns None if nothing usable remains."""
    valid = set(source_ids)
    if not isinstance(raw, dict):
        return None

    def ids(v):
        return [i for i in (v if isinstance(v, list) else []) if isinstance(i, str) and i in valid]

    claims = []
    for c in raw.get('claims') or []:
        if not isinstance(c, dict):
            continue
        text = (c.get('text') or '').strip()
        sids = list(dict.fromkeys(ids(c.get('source_ids'))))
        if not text or not sids:
            continue
        try:
            imp = int(c.get('importance', 2))
        except (TypeError, ValueError):
            imp = 2
        claims.append({'id': 'c{}'.format(len(claims) + 1), 'text': text[:400],
                       'source_ids': sids, 'importance': min(3, max(1, imp))})
        if len(claims) >= MAX_CLAIMS:
            break
    tldr = (raw.get('tldr') or '').strip()
    tldr_ids = list(dict.fromkeys(ids(raw.get('tldr_source_ids'))))
    if not claims:
        return None
    if not tldr or not tldr_ids:
        top = max(claims, key=lambda c: c['importance'])
        tldr, tldr_ids = tldr or top['text'], tldr_ids or top['source_ids']
    return {
        'tldr': tldr[:500], 'tldr_source_ids': tldr_ids, 'claims': claims,
        'key_entities': _str_list(raw.get('key_entities'), 6),
        'comparison_axes': _str_list(raw.get('comparison_axes'), 5),
        'steps': _str_list(raw.get('steps'), 8, maxlen=240),
    }


# ------------------------------------------------------- extractive fallback --

_STOP = set('a an the of to in on for and or is are was were be by with how what why when '
            'which who does do did can could should would i my me you your it its this that '
            'vs versus best from at as about into than'.split())


def _terms(text):
    return {w for w in re.findall(r'[a-z0-9]+', (text or '').lower()) if w not in _STOP and len(w) > 2}


def _sentences(text):
    text = re.sub(r'\s+', ' ', text or '').strip()
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', text) if 40 <= len(s.strip()) <= 320]


def extractive(query, sources):
    """No-LLM Stage A: rank source sentences by query-term overlap."""
    q = _terms(query)
    scored = []
    for rank, s in enumerate(sources[:MAX_SOURCES]):
        for pos, sent in enumerate(_sentences(s.get('content') or s.get('snippet'))[:25]):
            overlap = len(q & _terms(sent))
            # earlier sources and earlier sentences are usually more on-topic
            score = overlap * 3 - rank * 0.6 - pos * 0.15
            scored.append((score, s['id'], sent))
    scored.sort(key=lambda x: -x[0])
    claims, seen = [], set()
    for score, sid, sent in scored:
        key = sent.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        claims.append({'id': 'c{}'.format(len(claims) + 1), 'text': sent, 'source_ids': [sid],
                       'importance': 3 if len(claims) < 2 else (2 if len(claims) < 5 else 1)})
        if len(claims) >= 6:
            break
    if not claims:
        return None
    return {'tldr': claims[0]['text'], 'tldr_source_ids': claims[0]['source_ids'], 'claims': claims,
            'key_entities': [s.get('title', '') for s in sources[:4] if s.get('title')],
            'comparison_axes': [], 'steps': []}


# ------------------------------------------------------------------ public --

class StageA:
    """Synthesises and caches Stage A by (normalised query, source urls)."""

    def __init__(self, llm=None, cache_size=64):
        self.llm = llm
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self.cache_size = cache_size

    def _key(self, query, sources):
        return (re.sub(r'\s+', ' ', query.lower()).strip(), tuple(s.get('url', '') for s in sources))

    def run(self, query, sources):
        key = self._key(query, sources)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return dict(self._cache[key], cached=True)
        out = self._synthesise(query, sources)
        with self._lock:
            self._cache[key] = out
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return dict(out, cached=False)

    def _synthesise(self, query, sources):
        if not sources:
            return {'tldr': '', 'tldr_source_ids': [], 'claims': [], 'key_entities': [],
                    'comparison_axes': [], 'steps': [], 'used_llm': False, 'model': None,
                    'note': 'no sources found'}
        ids = [s['id'] for s in sources]
        note = ''
        if self.llm is not None and getattr(self.llm, 'key', ''):
            try:
                raw, model = self.llm.complete_json(build_messages(query, sources),
                                                    max_tokens=4000, timeout=30, temperature=0.1)
                clean = sanitise(raw, ids)
                if clean:
                    return dict(clean, used_llm=True, model=model, note='')
                note = 'LLM reply had no cited claims; used extractive fallback'
            except Exception as e:
                note = 'LLM unavailable ({}); used extractive fallback'.format(str(e)[:120])
        else:
            note = 'no OpenRouter key; extractive answer'
        ex = extractive(query, sources) or {'tldr': '', 'tldr_source_ids': [], 'claims': [],
                                            'key_entities': [], 'comparison_axes': [], 'steps': []}
        return dict(ex, used_llm=False, model=None, note=note)


def dumps_compact(stage_a):
    return json.dumps(stage_a, ensure_ascii=False, separators=(',', ':'))
