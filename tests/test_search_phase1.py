"""Phase 1 tests for Aura Search: providers, Stage A, /api/search. No network.

Run:  python -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.providers import (FixtureProvider, ProviderChain, ProviderError,
                                      SearchResult, Source, TavilyProvider,
                                      WikipediaProvider, normalise_query)
from backend.search.server import create_app
from backend.search.synthesis import StageA, extractive, sanitise

TOKEN = 't'
SOURCES = [
    {'id': 's1', 'title': 'Caffeine', 'url': 'https://en.wikipedia.org/wiki/Caffeine', 'snippet': '',
     'content': 'Caffeine is a central nervous system stimulant. Caffeine blocks adenosine receptors '
                'in the brain, which reduces sleepiness for several hours.'},
    {'id': 's2', 'title': 'Sleep', 'url': 'https://en.wikipedia.org/wiki/Sleep', 'snippet': '',
     'content': 'Sleep is a state of reduced mental and physical activity. Caffeine taken late in the '
                'day delays sleep onset and reduces deep sleep in many adults.'},
]


class FakeLLM:
    key = 'fake'

    def __init__(self, reply=None, fail=False):
        self.reply, self.fail, self.calls = reply, fail, 0

    def complete_json(self, messages, **kw):
        self.calls += 1
        if self.fail:
            raise RuntimeError('all models failed')
        return self.reply, 'fake/model'


class FakeTavily:
    def __init__(self, available=True, fail=False):
        self.available, self.fail, self.calls = available, fail, 0

    def search(self, q, k=6):
        self.calls += 1
        if self.fail:
            raise ProviderError('Tavily HTTP 500')
        return SearchResult(q, 'tavily', [Source('s1', 'T', 'https://t.example/a', 'snip', 'Tavily content here.')])


class FakeWiki:
    def __init__(self):
        self.calls = 0

    def search(self, q, k=5):
        self.calls += 1
        return SearchResult(q, 'wikipedia', [Source('s1', 'W', 'https://en.wikipedia.org/wiki/W', 's', 'Wiki text.')])


class SanitiseTests(unittest.TestCase):
    def test_drops_uncited_and_unknown_sources(self):
        raw = {'tldr': 'Caffeine delays sleep.', 'tldr_source_ids': ['s2', 's9'],
               'claims': [{'text': 'Blocks adenosine.', 'source_ids': ['s1'], 'importance': 3},
                          {'text': 'Invented fact.', 'source_ids': ['s7']},
                          {'text': 'No citation.', 'source_ids': []},
                          {'text': 'Delays onset.', 'source_ids': ['s2', 's2'], 'importance': '9'}],
               'key_entities': ['caffeine', 5, ''], 'comparison_axes': 'nope', 'steps': []}
        out = sanitise(raw, ['s1', 's2'])
        self.assertEqual([c['id'] for c in out['claims']], ['c1', 'c2'])
        self.assertEqual(out['claims'][1]['source_ids'], ['s2'])
        self.assertEqual(out['claims'][1]['importance'], 3)       # clamped
        self.assertEqual(out['tldr_source_ids'], ['s2'])
        self.assertEqual(out['key_entities'], ['caffeine'])
        self.assertEqual(out['comparison_axes'], [])

    def test_wrapped_list_items_are_unwrapped(self):
        out = sanitise({'claims': [{'text': 'A.', 'source_ids': ['s1']}],
                        'steps': [{'step': 'Collect scraps.'}, 'Add browns.', {'n': 3}],
                        'key_entities': [{'name': 'Compost'}]}, ['s1'])
        self.assertEqual(out['steps'], ['Collect scraps.', 'Add browns.'])
        self.assertEqual(out['key_entities'], ['Compost'])

    def test_nothing_usable_returns_none(self):
        self.assertIsNone(sanitise({'claims': [{'text': 'x', 'source_ids': ['s5']}]}, ['s1']))
        self.assertIsNone(sanitise('not a dict', ['s1']))

    def test_missing_tldr_falls_back_to_top_claim(self):
        out = sanitise({'claims': [{'text': 'A.', 'source_ids': ['s1'], 'importance': 1},
                                   {'text': 'B.', 'source_ids': ['s2'], 'importance': 3}]}, ['s1', 's2'])
        self.assertEqual((out['tldr'], out['tldr_source_ids']), ('B.', ['s2']))


class StageATests(unittest.TestCase):
    def test_extractive_cites_real_sources(self):
        out = extractive('how does caffeine affect sleep', SOURCES)
        self.assertTrue(out['claims'])
        for c in out['claims']:
            self.assertIn(c['source_ids'][0], {'s1', 's2'})
        self.assertIn('affeine', out['tldr'])

    def test_llm_path_and_cache(self):
        llm = FakeLLM({'tldr': 'It delays sleep.', 'tldr_source_ids': ['s2'],
                       'claims': [{'text': 'Blocks adenosine.', 'source_ids': ['s1'], 'importance': 3}]})
        sa = StageA(llm)
        a = sa.run('caffeine sleep', SOURCES)
        self.assertTrue(a['used_llm'])
        self.assertEqual(a['model'], 'fake/model')
        self.assertFalse(a['cached'])
        b = sa.run('  Caffeine   sleep ', SOURCES)
        self.assertTrue(b['cached'])
        self.assertEqual(llm.calls, 1)

    def test_llm_failure_falls_back(self):
        a = StageA(FakeLLM(fail=True)).run('caffeine sleep', SOURCES)
        self.assertFalse(a['used_llm'])
        self.assertIn('fallback', a['note'])
        self.assertTrue(a['claims'])

    def test_bad_llm_json_falls_back(self):
        a = StageA(FakeLLM({'claims': [{'text': 'made up', 'source_ids': ['s99']}]})).run('q', SOURCES)
        self.assertFalse(a['used_llm'])
        self.assertTrue(a['claims'])

    def test_no_sources(self):
        a = StageA(None).run('q', [])
        self.assertEqual(a['claims'], [])
        self.assertEqual(a['note'], 'no sources found')


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, 'fx.json'), 'w', encoding='utf-8') as f:
            json.dump({'query': 'How does Caffeine affect sleep?', 'recorded_at': '2026-11-25',
                       'recorded_provider': 'wikipedia',
                       'sources': [{'id': 'x', 'title': 'C', 'url': 'https://e/c', 'snippet': 's',
                                    'content': 'c', 'published': '', 'provider': 'wikipedia'}]}, f)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_normalise(self):
        self.assertEqual(normalise_query('  How does Caffeine, affect sleep?? '), 'how does caffeine affect sleep')

    def test_fixture_match_and_renumber(self):
        r = FixtureProvider([self.dir]).search('how does caffeine affect sleep')
        self.assertEqual(r.provider, 'fixture')
        self.assertEqual(r.sources[0].id, 's1')
        self.assertIsNone(FixtureProvider([self.dir]).search('something else'))

    def test_chain_order(self):
        tav, wiki = FakeTavily(), FakeWiki()
        chain = ProviderChain(FixtureProvider([self.dir]), tav, wiki)
        self.assertEqual(chain.search('how does caffeine affect sleep').provider, 'fixture')
        self.assertEqual(chain.search('other').provider, 'tavily')
        self.assertEqual(wiki.calls, 0)

    def test_chain_falls_back_to_wikipedia(self):
        wiki = FakeWiki()
        r = ProviderChain(FixtureProvider([self.dir]), FakeTavily(fail=True), wiki).search('other')
        self.assertEqual(r.provider, 'wikipedia')
        self.assertIn('Tavily HTTP 500', r.note)
        r = ProviderChain(FixtureProvider([self.dir]), FakeTavily(available=False), wiki).search('other')
        self.assertIn('no Tavily key', r.note)

    def test_tavily_parse(self):
        r = TavilyProvider.parse('q', {'results': [
            {'title': 'A', 'url': 'https://a.com/x', 'content': 'alpha ' * 10, 'published_date': '2026-01-01'},
            {'title': '', 'url': 'https://b.com', 'content': 'beta'}]}, 6)
        self.assertEqual([s.id for s in r.sources], ['s1', 's2'])
        self.assertEqual(r.sources[1].title, 'https://b.com')
        self.assertEqual(r.sources[0].domain, 'a.com')

    def test_wikipedia_parse_keeps_search_order(self):
        s = {'query': {'search': [{'pageid': 2}, {'pageid': 1}, {'pageid': 3}]}}
        x = {'query': {'pages': {'1': {'title': 'One', 'extract': 'First.', 'fullurl': 'https://w/1'},
                                 '2': {'title': 'Two', 'extract': 'Second.', 'fullurl': 'https://w/2'},
                                 '3': {'title': 'Three', 'extract': ''}}}}
        r = WikipediaProvider.parse('q', s, x, 5)
        self.assertEqual([src.title for src in r.sources], ['Two', 'One'])

    def test_clean_text_strips_markdown_keeps_link_text(self):
        from backend.search.providers import _clip
        out = _clip('Intro ## Best pick ### Who? [...] **Bold** see [the review](https://x.com/a) '
                    '![img](https://i.png) | a | https://bare.example/x')
        self.assertNotIn('#', out)
        self.assertNotIn('[...]', out)
        self.assertNotIn('**', out)
        self.assertNotIn('http', out)
        self.assertIn('the review', out)
        self.assertIn('Who?', out)
        self.assertNotIn('?.', out)

    def test_repo_fixtures_load(self):
        root = os.path.join(os.path.dirname(__file__), '..', 'search_fixtures')
        if not os.path.isdir(root):
            self.skipTest('no fixtures recorded')
        fx = FixtureProvider([root]).list()
        self.assertTrue(fx)
        for f in fx:
            self.assertGreater(f['n_sources'], 0)


class LlmFailoverTests(unittest.TestCase):
    def test_truncated_reply_moves_to_next_model(self):
        from backend.llm_controller import LLMController
        c = LLMController()
        c.key = 'k'
        seen = []

        def fake(model, messages, max_tokens, timeout, temperature):
            seen.append(model)
            if model == 'a':
                raise RuntimeError('reply truncated at max_tokens')
            return {'ok': True}
        c._complete_json_model = fake
        out, model = c.complete_json([], models=['a', 'b'])
        self.assertEqual((out, model, seen), ({'ok': True}, 'b', ['a', 'b']))

    def test_models_override_from_secrets(self):
        import backend.llm_controller as lc
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'secrets.json')
            with open(path, 'w') as f:
                json.dump({'openrouter_models': ['x/y:free']}, f)
            old = lc.SECRETS_FILE
            lc.SECRETS_FILE = path
            try:
                self.assertEqual(lc._load_models(), ['x/y:free'])
                with open(path, 'w') as f:
                    json.dump({'openrouter_models': 'bad'}, f)
                self.assertEqual(lc._load_models(), lc.DEFAULT_MODELS)
            finally:
                lc.SECRETS_FILE = old
        finally:
            shutil.rmtree(d)


class SearchEndpointTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, 'fx.json'), 'w', encoding='utf-8') as f:
            json.dump({'query': 'caffeine sleep', 'task': 'Explain', 'sources': SOURCES}, f)
        self.store = LiveStateStore()
        self.store.set(build_snapshot(score=70, tier=2, features={}, condition='intervention', calibrated=True))
        chain = ProviderChain(FixtureProvider([self.dir]), FakeTavily(available=False), FakeWiki())
        self.client = TestClient(create_app(self.store, TOKEN, ui_dist=None, chain=chain, stage_a=StageA(None)))
        self.h = {'X-Aura-Token': TOKEN}

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_search_returns_cited_answer(self):
        r = self.client.post('/api/search', json={'query': '  caffeine   sleep '}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d['provider'], 'fixture')
        self.assertEqual(d['query'], 'caffeine sleep')
        self.assertEqual(d['state_at_query']['label'], 'Elevated')
        self.assertEqual(d['condition'], 'intervention')
        ids = {s['id'] for s in d['sources']}
        self.assertTrue(d['stageA']['claims'])
        for c in d['stageA']['claims']:
            self.assertTrue(set(c['source_ids']) <= ids)
        self.assertNotIn('content', d['sources'][0])      # full text stays server-side
        self.assertIn('total', d['timings_ms'])

    def test_search_validation_and_auth(self):
        self.assertEqual(self.client.post('/api/search', json={'query': 'x'}).status_code, 401)
        self.assertEqual(self.client.post('/api/search', json={'query': ''}, headers=self.h).status_code, 422)
        self.assertEqual(self.client.post('/api/search', json={'query': 'x' * 301}, headers=self.h).status_code, 422)

    def test_fixtures_and_status(self):
        f = self.client.get('/api/fixtures', headers=self.h).json()['fixtures']
        self.assertEqual(f[0]['task'], 'Explain')
        s = self.client.get('/api/search/status', headers=self.h).json()
        self.assertFalse(s['providers']['tavily'])
        self.assertFalse(s['llm'])


if __name__ == '__main__':
    unittest.main()
