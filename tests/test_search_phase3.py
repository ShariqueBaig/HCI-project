"""Phase 3 tests for Aura Search: Stage B composer, validator, layouts per state.

Run:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.search.composer import Composer, build_messages, template_spec
from backend.search.hub import StateHub
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.policy import POLICY_NAMES, get_policy
from backend.search.validator import grounding, build_vocabulary, referenced_claims, sanitise_html, validate_spec

TOKEN = 't'
SOURCES = [{'id': 's1', 'title': 'Solid-state drive', 'url': 'https://w/ssd', 'snippet': ''},
           {'id': 's2', 'title': 'Hard disk drive', 'url': 'https://w/hdd', 'snippet': ''}]
STAGE_A = {
    'tldr': 'SSDs are faster and more shock resistant than HDDs, but cost more per gigabyte.',
    'tldr_source_ids': ['s1'],
    'claims': [
        {'id': 'c1', 'text': 'SSDs store data in flash memory and have no moving parts.', 'source_ids': ['s1'], 'importance': 3},
        {'id': 'c2', 'text': 'SSDs offer much faster access times and lower latency than HDDs.', 'source_ids': ['s1'], 'importance': 3},
        {'id': 'c3', 'text': 'HDDs cost less per gigabyte and offer larger capacities.', 'source_ids': ['s2'], 'importance': 2},
        {'id': 'c4', 'text': 'HDDs use spinning platters and are more prone to mechanical failure.', 'source_ids': ['s2'], 'importance': 2},
        {'id': 'c5', 'text': 'SSDs have limited write endurance.', 'source_ids': ['s1'], 'importance': 1},
    ],
    'key_entities': ['SSD', 'HDD'],
    'comparison_axes': ['speed', 'cost per gigabyte', 'capacity'],
    'steps': [],
}
HOWTO = dict(STAGE_A, steps=['Collect kitchen scraps.', 'Add dry brown material.', 'Keep the pile moist.',
                             'Turn it every few days.'])


def v(raw, policy='energized', stage_a=STAGE_A, trail=None):
    return validate_spec(raw, stage_a, get_policy(policy), SOURCES, 'ssd vs hdd', trail)


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.vocab = build_vocabulary(STAGE_A, SOURCES, 'ssd vs hdd')

    def test_paraphrase_of_stage_a_passes(self):
        self.assertTrue(grounding('SSDs are faster with lower latency but cost more per gigabyte.', self.vocab)[0])

    def test_new_numbers_and_new_claims_fail(self):
        ok, _, _, nums = grounding('SSDs are 5 times faster.', self.vocab)
        self.assertFalse(ok)
        self.assertEqual(nums, ['5'])
        self.assertFalse(grounding('Samsung recommends buying the cheapest warranty bundle today.', self.vocab)[0])


class ValidatorTests(unittest.TestCase):
    def test_disallowed_and_unknown_widgets_dropped(self):
        spec, rep = v({'components': [{'type': 'ComparisonTable', 'props': {}},
                                      {'type': 'EvilWidget', 'props': {}},
                                      {'type': 'AnswerCard', 'props': {'text': STAGE_A['tldr']}}]}, 'overwhelmed')
        self.assertEqual([c['type'] for c in spec['components']], ['AnswerCard'])
        self.assertTrue(any('ComparisonTable' in d for d in rep['dropped']))

    def test_unknown_claims_and_sources_removed(self):
        spec, _ = v({'components': [{'type': 'KeyFactsList', 'props': {'claim_ids': ['c1', 'c99', 'c1']}},
                                    {'type': 'SourceList', 'props': {'source_ids': ['s9', 's2']}}]}, 'focused')
        self.assertEqual(spec['components'][0]['props']['claim_ids'], ['c1'])
        self.assertEqual(spec['components'][1]['props']['source_ids'], ['s2'])

    def test_ungrounded_answer_replaced_with_stage_a(self):
        spec, rep = v({'components': [{'type': 'AnswerCard', 'props': {
            'text': 'Buy the Samsung 990 Pro, it is 7 times faster and comes with free shipping.'}}]}, 'focused')
        self.assertEqual(spec['components'][0]['props']['text'], STAGE_A['tldr'])
        self.assertEqual(rep['ungrounded_before_fix'], 1)

    def test_answer_trimmed_to_word_budget(self):
        long = ' '.join([STAGE_A['claims'][1]['text']] * 8)
        spec, _ = v({'components': [{'type': 'AnswerCard', 'props': {'text': long}}]}, 'overwhelmed')
        self.assertLessEqual(len(spec['components'][0]['props']['text'].split()), get_policy('overwhelmed')['answer_word_budget'])

    def test_key_facts_capped(self):
        spec, _ = v({'components': [{'type': 'KeyFactsList', 'props': {'claim_ids': ['c1', 'c2', 'c3', 'c4', 'c5']}}]}, 'fatigued')
        self.assertEqual(len(spec['components'][0]['props']['claim_ids']), get_policy('fatigued')['max_key_facts'])

    def test_table_cells_grounded_or_evaluative(self):
        spec, rep = v({'components': [{'type': 'ComparisonTable', 'props': {
            'columns': ['SSD', 'HDD'],
            'rows': [{'axis': 'Speed', 'cells': ['Faster', 'Slower']},
                     {'axis': 'Cost per gigabyte', 'cells': ['Higher', 'Lower']},
                     {'axis': 'Warranty', 'cells': ['5 years', '2 years']},       # not in Stage A
                     {'axis': 'Capacity', 'cells': ['Smaller', 'Up to 30 TB']}]}}]}, 'focused')
        rows = spec['components'][0]['props']['rows']
        self.assertEqual([r['axis'] for r in rows], ['Speed', 'Cost per gigabyte'])
        self.assertEqual(rep['evaluative_cells'], 4)

    def test_steps_by_index_and_cap(self):
        spec, _ = validate_spec({'components': [{'type': 'GuidedSteps', 'props': {'steps': [0, 1, 2, 3, 99]}}]},
                                HOWTO, get_policy('overwhelmed'), SOURCES)
        steps = spec['components'][0]['props']['steps']
        self.assertEqual([s['text'] for s in steps], HOWTO['steps'][:3])

    def test_facets_must_come_from_stage_a(self):
        spec, _ = v({'components': [{'type': 'FacetChips', 'props': {'facets': ['speed', 'RGB lighting', 'SSD']}}]})
        self.assertEqual(spec['components'][0]['props']['facets'], ['speed', 'SSD'])

    def test_topology_comes_from_policy(self):
        raw = {'topology': 'split', 'components': [{'type': 'AnswerCard', 'props': {}},
                                                   {'type': 'SourceList', 'props': {}}]}
        self.assertEqual(v(raw, 'overwhelmed')[0]['topology'], 'stepper')
        s, _ = v(dict(raw, topology='stack'), 'focused')
        self.assertEqual(s['topology'], 'split')
        self.assertEqual([c['region'] for c in s['components']], ['main', 'side'])

    def test_custom_widget_only_when_allowed_and_sanitised(self):
        raw = {'components': [{'type': 'AnswerCard', 'props': {}}],
               'custom_widget': {'title': 'Chart', 'html': '<script src="https://evil.example/x.js"></script>'
                                 '<img src="https://track.example/p.gif"><div onclick="x()">ok</div>'}}
        self.assertIsNone(v(raw, 'focused')[0]['custom_widget'])
        cw = v(raw, 'energized')[0]['custom_widget']
        self.assertNotIn('evil.example', cw['html'])
        self.assertNotIn('track.example', cw['html'])
        self.assertIn('ok', cw['html'])

    def test_sanitise_html_strips_network(self):
        h = sanitise_html('<link rel=stylesheet href="https://x/s.css"><iframe src="//x"></iframe>'
                          '<div style="background:url(https://x/i.png)">a</div><a href="javascript:alert(1)">b</a>')
        for bad in ('https://x', '//x', 'javascript:'):
            self.assertNotIn(bad, h)


class TemplateTests(unittest.TestCase):
    def test_every_policy_template_is_valid_and_distinct(self):
        shapes = {}
        for name in POLICY_NAMES:
            pol = get_policy(name)
            spec, rep = validate_spec(template_spec(HOWTO, pol, SOURCES, ['a', 'b']), HOWTO, pol, SOURCES, 'q', ['a', 'b'])
            self.assertFalse(rep['dropped'], (name, rep['dropped']))
            self.assertFalse(rep['missing_required'], (name, rep['missing_required']))
            self.assertTrue(referenced_claims(spec) <= {c['id'] for c in HOWTO['claims']})
            shapes[name] = (spec['topology'], tuple(c['type'] for c in spec['components']))
        self.assertEqual(len(set(shapes.values())), len(POLICY_NAMES), shapes)


class FakeLLM:
    key = 'k'

    def __init__(self, raw=None, fail=False):
        self.raw, self.fail, self.messages = raw, fail, None

    def complete_json(self, messages, **kw):
        self.messages = messages
        if self.fail:
            raise RuntimeError('down')
        return self.raw, 'fake/m'


class ComposerTests(unittest.TestCase):
    def test_llm_layout_used_and_required_widgets_filled(self):
        llm = FakeLLM({'components': [{'type': 'AnswerCard', 'props': {'text': STAGE_A['tldr']}},
                                      {'type': 'KeyFactsList', 'props': {'claim_ids': ['c2']}}]})
        out = Composer(llm).compose('q', HOWTO, SOURCES, get_policy('overwhelmed'), {'state': 'overwhelmed'})
        self.assertEqual(out['source'], 'llm')
        types = [c['type'] for c in out['components']]
        for req in ('AnswerCard', 'GuidedSteps', 'SourceList', 'BreathingNudge'):
            self.assertIn(req, types)
        self.assertEqual(types[-1], 'SourceList')

    def test_content_never_in_side_column(self):
        llm = FakeLLM({'components': [{'type': 'AnswerCard', 'region': 'side', 'props': {}},
                                      {'type': 'KeyFactsList', 'region': 'side', 'props': {'claim_ids': ['c1']}},
                                      {'type': 'FacetChips', 'region': 'main', 'props': {'facets': ['speed']}}]})
        out = Composer(llm).compose('q', STAGE_A, SOURCES, get_policy('energized'), {'state': 'energized'})
        self.assertEqual(out['topology'], 'split')
        regions = {c['type']: c['region'] for c in out['components']}
        self.assertEqual((regions['AnswerCard'], regions['KeyFactsList']), ('main', 'main'))
        self.assertEqual((regions['FacetChips'], regions['SourceList']), ('side', 'side'))

    def test_energized_always_offers_facets_when_available(self):
        llm = FakeLLM({'components': [{'type': 'AnswerCard', 'props': {}},
                                      {'type': 'KeyFactsList', 'props': {'claim_ids': ['c1']}}]})
        out = Composer(llm).compose('q', STAGE_A, SOURCES, get_policy('energized'), {'state': 'energized'})
        self.assertIn('FacetChips', [c['type'] for c in out['components']])
        no_facets = dict(STAGE_A, key_entities=[], comparison_axes=[])
        out = Composer(llm).compose('q', no_facets, SOURCES, get_policy('energized'), {'state': 'energized'})
        self.assertNotIn('FacetChips', [c['type'] for c in out['components']])

    def test_fatigued_always_offers_read_aloud(self):
        llm = FakeLLM({'components': [{'type': 'AnswerCard', 'props': {}},
                                      {'type': 'KeyFactsList', 'props': {'claim_ids': ['c1']}}]})
        out = Composer(llm).compose('q', STAGE_A, SOURCES, get_policy('fatigued'), {'state': 'fatigued'})
        self.assertIn('ReadAloud', [c['type'] for c in out['components']])
        self.assertEqual(out['topology'], 'stack')
        self.assertTrue(all(c['region'] == 'main' for c in out['components']))

    def test_disoriented_gets_clarifier_when_axes_exist(self):
        llm = FakeLLM({'components': [{'type': 'AnswerCard', 'props': {}}, {'type': 'SourceList', 'props': {}}]})
        out = Composer(llm).compose('q', STAGE_A, SOURCES, get_policy('disoriented'), {'state': 'disoriented'}, trail=['a'])
        types = [c['type'] for c in out['components']]
        self.assertIn('ClarifierChips', types)
        self.assertEqual(types[0], 'QueryTrail')

    def test_failure_or_empty_falls_back_to_template(self):
        a = Composer(FakeLLM(fail=True)).compose('q', STAGE_A, SOURCES, get_policy('focused'))
        self.assertEqual(a['source'], 'template')
        b = Composer(FakeLLM({'components': []})).compose('q', STAGE_A, SOURCES, get_policy('focused'))
        self.assertEqual(b['source'], 'template')
        self.assertGreaterEqual(len(b['components']), 2)

    def test_prompt_only_never_sees_user_state(self):
        llm = FakeLLM({'components': []})
        Composer(llm).compose('q', STAGE_A, SOURCES, get_policy('neutral'), {'state': 'overwhelmed'})
        self.assertNotIn('user_state', llm.messages[1]['content'])
        Composer(llm).compose('q', STAGE_A, SOURCES, get_policy('focused'), {'state': 'focused'})
        self.assertIn('user_state', llm.messages[1]['content'])

    def test_messages_contain_no_raw_sensor_values(self):
        msgs = build_messages('q', STAGE_A, SOURCES, get_policy('focused'), {'state': 'focused', 'why': ['x']})
        self.assertNotIn('keys_per_second', msgs[1]['content'])
        self.assertNotIn('score', msgs[1]['content'])


class EndpointTests(unittest.TestCase):
    def setUp(self):
        from backend.search.providers import FixtureProvider, ProviderChain, SearchResult, Source
        from backend.search.synthesis import StageA

        class Wiki:
            def search(self, q, k=5):
                return SearchResult(q, 'wikipedia', [
                    Source('s1', 'SSD', 'https://w/ssd', 's', 'SSDs are fast and have no moving parts. '
                           'SSDs cost more per gigabyte than hard drives.'),
                    Source('s2', 'HDD', 'https://w/hdd', 's', 'Hard disk drives use spinning platters. '
                           'Hard disk drives offer large capacity at low cost.')])

        class NoTavily:
            available = False

        self.store = LiveStateStore()
        self.hub = StateHub(self.store)
        chain = ProviderChain(FixtureProvider(['/nonexistent']), NoTavily(), Wiki())
        from backend.search.server import create_app
        self.client = TestClient(create_app(self.store, TOKEN, ui_dist=None, chain=chain,
                                            stage_a=StageA(None), hub=self.hub, composer=Composer(None)))
        self.h = {'X-Aura-Token': TOKEN}

    def _live(self, score, tier, condition='intervention'):
        self.store.set(build_snapshot(score=score, tier=tier, features={}, condition=condition, calibrated=True))

    def test_search_returns_spec_for_current_state(self):
        self._live(85, 2)
        d = self.client.post('/api/search', json={'query': 'ssd vs hdd'}, headers=self.h).json()
        self.assertEqual(d['policy']['name'], 'overwhelmed')
        self.assertEqual(d['spec']['topology'], 'stepper')
        self.assertIn('stageB', d['timings_ms'])
        self.assertNotIn('_specs', d)

    def test_control_gets_neutral_layout(self):
        self._live(85, 2, 'control')
        d = self.client.post('/api/search', json={'query': 'ssd vs hdd'}, headers=self.h).json()
        self.assertEqual(d['policy']['name'], 'neutral')

    def test_rerender_keeps_facts_and_compare_gives_six_layouts(self):
        self._live(20, 0)
        d = self.client.post('/api/search', json={'query': 'ssd vs hdd'}, headers=self.h).json()
        sid = d['search_id']
        r = self.client.post('/api/search/{}/rerender'.format(sid), json={'policy': 'neutral'}, headers=self.h).json()
        self.assertEqual(r['policy']['name'], 'neutral')
        stage_ids = {c['id'] for c in d['stageA']['claims']}
        self.assertTrue(set(r['spec']['claims_shown']) <= stage_ids)
        c = self.client.post('/api/search/{}/compare'.format(sid), headers=self.h).json()
        self.assertEqual(len(c['specs']), 6)
        self.assertTrue(c['all_within_stage_a'])
        shapes = {(s['topology'], tuple(w['type'] for w in s['components'])) for s in c['specs'].values()}
        self.assertEqual(len(shapes), 6)

    def test_rerender_errors(self):
        self.assertEqual(self.client.post('/api/search/nope/rerender', json={'policy': 'neutral'}, headers=self.h).status_code, 404)
        self._live(20, 0)
        sid = self.client.post('/api/search', json={'query': 'x'}, headers=self.h).json()['search_id']
        self.assertEqual(self.client.post('/api/search/{}/rerender'.format(sid), json={'policy': 'evil'}, headers=self.h).status_code, 422)


if __name__ == '__main__':
    unittest.main()
