"""Search providers for Aura Search (retrieval, before Stage A).

Chain, first match wins:
  1. FixtureProvider -- recorded results in search_fixtures/*.json. Exact
     (normalised) query match only, so study tasks are reproducible: every
     participant sees the same sources.
  2. TavilyProvider  -- live web search, needs `tavily_api_key` in secrets.json
     or the TAVILY_API_KEY environment variable.
  3. WikipediaProvider -- keyless fallback, so search works out of the box.

Only the submitted query leaves the machine; no user identifiers are sent.

Record a fixture (uses the live chain, skipping fixtures):
    python -m backend.search.providers record "how does caffeine affect sleep"
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field

from backend.paths import base_dir, resource_dirs

USER_AGENT = 'AuraSearch/0.1 (HCI research prototype)'
MAX_CONTENT_CHARS = 2500


@dataclass
class Source:
    id: str                 # 's1', 's2', ... -- stable within one search
    title: str
    url: str
    snippet: str
    content: str = ''
    published: str = ''
    provider: str = ''

    def to_dict(self):
        return asdict(self)

    @property
    def domain(self):
        try:
            return urllib.parse.urlparse(self.url).netloc.replace('www.', '')
        except Exception:
            return ''


@dataclass
class SearchResult:
    query: str
    provider: str
    sources: list = field(default_factory=list)
    note: str = ''          # e.g. why a provider was skipped

    def to_dict(self):
        return {'query': self.query, 'provider': self.provider, 'note': self.note,
                'sources': [s.to_dict() for s in self.sources]}


class ProviderError(RuntimeError):
    pass


def normalise_query(q):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', (q or '').lower())).strip()


def clean_text(text):
    """Strip the markdown/scrape debris web extractors leave behind."""
    t = text or ''
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', t)               # images
    t = re.sub(r'\[([^\]]+)\]\((?:https?://|/)[^)]*\)', r'\1', t)  # links -> text
    t = re.sub(r'\[\s*(?:\.\.\.|…)\s*\]', ' ', t)               # [...] elision marks
    t = re.sub(r'(?m)^\s{0,3}#{1,6}\s*', '', t)                  # heading markers at line start
    t = re.sub(r'\s#{2,6}\s+', '. ', t)                          # inline "## Heading" -> sentence break
    t = re.sub(r'(\*\*|__|`)', '', t)                           # bold / code marks
    t = re.sub(r'(?m)^\s*[-*+]\s+', '', t)                       # list bullets
    t = re.sub(r'\|', ' ', t)                                    # table pipes
    t = re.sub(r'https?://\S+', ' ', t)                          # bare urls
    t = re.sub(r'(\.\s*){2,}', '. ', t)                          # repeated periods
    t = re.sub(r'([!?:])\s*\.', r'\1', t)                        # "best?." -> "best?"
    return t


def _clip(text, n=MAX_CONTENT_CHARS):
    text = re.sub(r'\s+', ' ', clean_text(text)).strip()
    return text if len(text) <= n else text[:n].rsplit(' ', 1)[0] + ' ...'


def _http_json(url, data=None, headers=None, timeout=12):
    h = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, headers=h, method='POST' if body else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _renumber(sources):
    for i, s in enumerate(sources, 1):
        s.id = 's{}'.format(i)
    return sources


# ---------------------------------------------------------------- fixtures --

def fixture_dirs():
    dirs = [os.path.join(base_dir(), 'search_fixtures')]
    for d in resource_dirs():
        p = os.path.join(d, 'search_fixtures')
        if p not in dirs:
            dirs.append(p)
    return dirs


class FixtureProvider:
    name = 'fixture'

    def __init__(self, dirs=None):
        self.dirs = dirs or fixture_dirs()

    def _load_all(self):
        out = {}
        for d in self.dirs:
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith('.json'):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding='utf-8') as f:
                        fx = json.load(f)
                    fx.setdefault('id', fn[:-5])
                    out.setdefault(normalise_query(fx['query']), fx)
                except Exception as e:
                    print('[Aura Search] bad fixture', fn, e)
        return out

    def list(self):
        return [{'id': fx['id'], 'query': fx['query'], 'task': fx.get('task', ''),
                 'n_sources': len(fx.get('sources', []))}
                for fx in self._load_all().values()]

    def by_id(self, task_id):
        return next((fx for fx in self._load_all().values() if fx['id'] == task_id), None)

    def search(self, query, k=6, task_id=None):
        """Exact-query match, or -- during a study task -- the task's recorded
        sources whatever the wording, so every participant sees the same evidence."""
        fx = self.by_id(task_id) if task_id else self._load_all().get(normalise_query(query))
        if not fx:
            return None
        srcs = [Source(**{**s, 'provider': s.get('provider') or 'fixture'}) for s in fx['sources'][:k]]
        return SearchResult(query=query, provider='fixture', sources=_renumber(srcs),
                            note='recorded {} via {}'.format(fx.get('recorded_at', '?'),
                                                             fx.get('recorded_provider', '?')))


# ------------------------------------------------------------------ Tavily --

def load_secret(name, env):
    try:
        with open(os.path.join(base_dir(), 'secrets.json'), encoding='utf-8') as f:
            v = json.load(f).get(name, '')
    except Exception:
        v = ''
    v = (v or os.environ.get(env, '')).strip()
    return '' if v.startswith('YOUR_') else v


class TavilyProvider:
    name = 'tavily'
    ENDPOINT = 'https://api.tavily.com/search'

    def __init__(self, key=None):
        self.key = key if key is not None else load_secret('tavily_api_key', 'TAVILY_API_KEY')

    @property
    def available(self):
        return bool(self.key)

    @staticmethod
    def parse(query, data, k):
        srcs = []
        for r in (data.get('results') or [])[:k]:
            content = r.get('raw_content') or r.get('content') or ''
            srcs.append(Source(id='', title=(r.get('title') or r.get('url') or '').strip(),
                               url=r.get('url') or '', snippet=_clip(r.get('content') or '', 400),
                               content=_clip(content), published=r.get('published_date') or '',
                               provider='tavily'))
        return SearchResult(query=query, provider='tavily', sources=_renumber(srcs))

    def search(self, query, k=6):
        if not self.key:
            raise ProviderError('no Tavily key')
        try:
            data = _http_json(self.ENDPOINT, data={
                'query': query, 'search_depth': 'advanced', 'max_results': k,
                'include_answer': False, 'include_raw_content': False,
            }, headers={'Authorization': 'Bearer ' + self.key})
        except urllib.error.HTTPError as e:
            raise ProviderError('Tavily HTTP {}'.format(e.code))
        except Exception as e:
            raise ProviderError('Tavily: {}'.format(e))
        return self.parse(query, data, k)


# --------------------------------------------------------------- Wikipedia --

class WikipediaProvider:
    name = 'wikipedia'
    API = 'https://en.wikipedia.org/w/api.php'

    @staticmethod
    def parse(query, search_data, extract_data, k):
        order = [h['pageid'] for h in (search_data.get('query', {}).get('search') or [])][:k]
        pages = (extract_data.get('query', {}) or {}).get('pages', {}) or {}
        srcs = []
        for pid in order:
            p = pages.get(str(pid)) or {}
            text = p.get('extract') or ''
            if not text:
                continue
            srcs.append(Source(id='', title=p.get('title', ''),
                               url=p.get('fullurl') or 'https://en.wikipedia.org/?curid={}'.format(pid),
                               snippet=_clip(text, 400), content=_clip(text),
                               provider='wikipedia'))
        return SearchResult(query=query, provider='wikipedia', sources=_renumber(srcs))

    def search(self, query, k=5):
        try:
            s = _http_json(self.API + '?' + urllib.parse.urlencode({
                'action': 'query', 'list': 'search', 'srsearch': query, 'srlimit': k,
                'format': 'json', 'formatversion': 1}))
            ids = [str(h['pageid']) for h in s.get('query', {}).get('search', [])][:k]
            if not ids:
                return SearchResult(query=query, provider='wikipedia', sources=[])
            x = _http_json(self.API + '?' + urllib.parse.urlencode({
                'action': 'query', 'prop': 'extracts|info', 'inprop': 'url',
                'explaintext': 1, 'exintro': 1, 'exlimit': 'max', 'pageids': '|'.join(ids),
                'format': 'json', 'formatversion': 1}))
        except Exception as e:
            raise ProviderError('Wikipedia: {}'.format(e))
        return self.parse(query, s, x, k)


# ------------------------------------------------------------------- chain --

class ProviderChain:
    def __init__(self, fixtures=None, tavily=None, wikipedia=None, use_fixtures=True):
        self.fixtures = fixtures if fixtures is not None else FixtureProvider()
        self.tavily = tavily if tavily is not None else TavilyProvider()
        self.wikipedia = wikipedia if wikipedia is not None else WikipediaProvider()
        self.use_fixtures = use_fixtures

    def status(self):
        return {'tavily': self.tavily.available, 'wikipedia': True,
                'fixtures': len(self.fixtures.list())}

    def search(self, query, k=6, task_id=None):
        notes = []
        if self.use_fixtures:
            r = self.fixtures.search(query, k, task_id=task_id)
            if r:
                return r
        if self.tavily.available:
            try:
                r = self.tavily.search(query, k)
                if r.sources:
                    return r
                notes.append('Tavily returned nothing')
            except ProviderError as e:
                notes.append(str(e))
        else:
            notes.append('no Tavily key: using Wikipedia')
        r = self.wikipedia.search(query, min(k, 5))
        r.note = '; '.join(notes)
        return r


def record_fixture(query, task='', out_dir=None):
    """Run the live chain (no fixtures) and save the result as a fixture."""
    import time
    res = ProviderChain(use_fixtures=False).search(query)
    if not res.sources:
        raise ProviderError('no results to record')
    out_dir = out_dir or os.path.join(base_dir(), 'search_fixtures')
    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', normalise_query(query))[:60].strip('-') or 'query'
    path = os.path.join(out_dir, slug + '.json')
    fx = {'query': query, 'task': task, 'recorded_at': time.strftime('%Y-%m-%d'),
          'recorded_provider': res.provider, 'sources': [s.to_dict() for s in res.sources]}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(fx, f, indent=2, ensure_ascii=False)
    return path, res


def main():
    ap = argparse.ArgumentParser(description='Aura Search providers')
    sub = ap.add_subparsers(dest='cmd', required=True)
    rec = sub.add_parser('record', help='record a fixture from the live providers')
    rec.add_argument('query')
    rec.add_argument('--task', default='', help='study task description stored with it')
    sub.add_parser('list', help='list recorded fixtures')
    args = ap.parse_args()
    if args.cmd == 'record':
        path, res = record_fixture(args.query, args.task)
        print('recorded {} sources via {} -> {}'.format(len(res.sources), res.provider, path))
    else:
        for fx in FixtureProvider().list():
            print('{n_sources:2d} sources  {query}'.format(**fx))


if __name__ == '__main__':
    sys.exit(main())
