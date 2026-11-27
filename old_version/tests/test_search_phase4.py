"""Phase 4 tests for Aura Search: context window + silent-by-default anticipation.

Traces are simulated second by second; every test checks both the decision
and the decision log (what Phase 5 will analyse as false / missed offers).

Run:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.search import anticipation as ant
from backend.search.anticipation import Anticipator
from backend.search.composer import Composer, build_messages
from backend.search.context_window import DenseWindow, TextWindow
from backend.search.hub import StateHub
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.policy import get_policy

TOKEN = 't'


def fused(committed='focused', stress=20.0, quiet=False, candidate=None):
    return {'state': committed, 'committed_state': committed, 'candidate_state': candidate,
            'stress': stress, 'quiet': quiet, 'confidence': 0.8, 'evidence': ['x']}


class Sim:
    """Drive an Anticipator through a timeline, 1 tick per second."""

    def __init__(self, policy='focused', reformulation=False):
        self.a, self.dense, self.t = Anticipator(), DenseWindow(30), 0.0
        self.a.set_view('s1', policy, reformulation, now=0.0)
        self.beh = {'rage_clicks': 0, 'hesitations': 0, 'backtracks': 0}
        self.proposals_seen = []

    def run(self, seconds, f, adaptive=True):
        out = None
        for _ in range(int(seconds)):
            self.t += 1.0
            self.dense.add(self.t, {'committed': f['committed_state'], 'stress': f['stress']})
            out = self.a.decide(f, adaptive, dict(self.beh), self.dense, now=self.t)
            p = out['proposal']
            if p and (not self.proposals_seen or self.proposals_seen[-1]['id'] != p['id']):
                self.proposals_seen.append(p)
        return out

    def kinds(self):
        return [e['kind'] for e in self.a.log]


class ContextWindowTests(unittest.TestCase):
    def test_dense_window_sustained_and_trend(self):
        d = DenseWindow(30)
        for t in range(10):
            d.add(t, {'committed': 'focused', 'stress': 20 + t})
        self.assertTrue(d.sustained('committed', 'focused', 4, now=9))
        self.assertFalse(d.sustained('committed', 'overwhelmed', 4, now=9))
        self.assertFalse(d.sustained('committed', 'focused', 20, now=9))   # window too short
        self.assertEqual(d.trend('stress', 5, now=9), 5)
        d.add(45, {'committed': 'x'})
        self.assertEqual(len(d.since(0)), 1)                               # old samples dropped

    def test_text_window_bounded_and_compact(self):
        w = TextWindow(3)
        for i in range(5):
            w.add_search('s{}'.format(i), 'query {}'.format(i), 'focused', ['AnswerCard'], 'focused', i == 4)
        w.add_event('s4', 'accept offer')
        lines = w.lines()
        self.assertEqual(len(lines), 3)
        self.assertIn('reworded', lines[-1])
        self.assertIn('accept offer', lines[-1])
        self.assertEqual(len(w.lines(exclude='s4')), 2)

    def test_history_goes_to_llm_only_when_adaptive(self):
        sa = {'tldr': 't', 'claims': [], 'steps': [], 'key_entities': [], 'comparison_axes': []}
        msgs = build_messages('q', sa, [], get_policy('focused'), {'state': 'focused'}, ['"a" -> focused'])
        self.assertIn('earlier_searches', msgs[1]['content'])
        body = msgs[1]['content']
        self.assertLess(body.index('stage_a'), body.index('earlier_searches'))   # fixed parts first
        self.assertLess(body.index('earlier_searches'), body.index('user_state'))


class AnticipationTraceTests(unittest.TestCase):
    def test_calm_reading_stays_silent(self):
        s = Sim('focused')
        out = s.run(180, fused('focused', 15))
        self.assertIsNone(out['proposal'])
        self.assertEqual(s.a.log, [])

    def test_sustained_stress_gives_exactly_one_offer(self):
        s = Sim('focused')
        s.run(10, fused('focused', 20))
        s.run(3, fused('overwhelmed', 75))                 # not sustained yet
        self.assertEqual(s.proposals_seen, [])
        s.run(2, fused('overwhelmed', 75))
        self.assertEqual(len(s.proposals_seen), 1)
        self.assertEqual(s.proposals_seen[0]['target'], 'overwhelmed')
        s.run(120, fused('overwhelmed', 75))               # ignored -> expires, never repeats
        self.assertEqual(len(s.proposals_seen), 1)
        self.assertEqual(s.kinds(), ['proposal', 'expired'])

    def test_brief_spike_is_only_acknowledged(self):
        s = Sim('focused')
        s.run(5, fused('focused', 20))
        out = s.run(2, fused('overwhelmed', 70))
        self.assertIsNone(out['proposal'])
        self.assertIsNotNone(out['ack'])
        out = s.run(30, fused('focused', 20))
        self.assertIsNone(out['ack'])
        self.assertEqual(s.a.log, [])

    def test_reformulation_plus_quick_return_offers_reanchor(self):
        s = Sim('focused', reformulation=True)
        out = s.run(1, fused('focused', 20))
        self.assertIsNone(out['proposal'])                 # read-grace period
        s.run(2, fused('focused', 20))
        self.assertEqual(len(s.proposals_seen), 1)
        self.assertEqual(s.proposals_seen[0]['target'], 'disoriented')
        self.assertIn('reworded', s.proposals_seen[0]['reason'])

    def test_struggle_under_stress_offers_simplify(self):
        s = Sim('focused')
        s.beh.update(backtracks=1, rage_clicks=1)
        s.run(5, fused('focused', 55))
        self.assertEqual(s.proposals_seen[0]['target'], 'overwhelmed')

    def test_one_struggle_signal_is_not_enough(self):
        s = Sim('focused')
        s.beh.update(backtracks=1)
        out = s.run(30, fused('focused', 20))
        self.assertEqual(s.proposals_seen, [])
        self.assertIsNotNone(out['ack'])

    def test_accept_then_undo_stops_offers(self):
        s = Sim('focused')
        s.run(10, fused('overwhelmed', 80))
        p = s.proposals_seen[0]
        self.assertEqual(s.a.respond(p['id'], 'accept', now=s.t), 'overwhelmed')
        self.assertTrue(s.a.snapshot()['can_undo'])
        self.assertEqual(s.a.respond('', 'undo', now=s.t + 1), 'focused')
        s.run(60, fused('overwhelmed', 80))
        self.assertEqual(len(s.proposals_seen), 1)          # user took control
        self.assertEqual(s.kinds(), ['proposal', 'accept', 'undo'])
        self.assertEqual([e['from'] for e in s.a.log], ['focused', 'focused', 'overwhelmed'])

    def test_continuous_mode_allows_a_later_offer_after_accept(self):
        s = Sim('focused')
        s.run(10, fused('overwhelmed', 80))
        s.a.respond(s.proposals_seen[0]['id'], 'accept', now=s.t)
        s.run(10, fused('overwhelmed', 80))
        s.run(60, fused('fatigued', 30))                    # later the state moves again
        self.assertEqual([p['target'] for p in s.proposals_seen], ['overwhelmed', 'fatigued'])

    def test_dismissed_target_never_returns(self):
        s = Sim('focused')
        s.run(10, fused('overwhelmed', 80))
        s.a.respond(s.proposals_seen[0]['id'], 'dismiss', now=s.t)
        s.run(120, fused('overwhelmed', 80))
        self.assertEqual(len(s.proposals_seen), 1)
        self.assertEqual(s.kinds(), ['proposal', 'dismiss'])

    def test_control_logs_counterfactual_once_and_never_offers(self):
        s = Sim('neutral')
        s.a.view['policy'] = 'focused'                      # what the adaptive arm would show
        out = s.run(60, fused('overwhelmed', 80), adaptive=False)
        self.assertIsNone(out['proposal'])
        self.assertEqual(s.kinds(), ['counterfactual'])

    def test_breathing_guide_keeps_search_quiet(self):
        s = Sim('focused')
        out = s.run(60, fused('overwhelmed', 80, quiet=True))
        self.assertIsNone(out['proposal'])

    def test_standard_view_choice_stops_offers(self):
        s = Sim('focused')
        s.a.user_choice('s1', 'neutral', now=1)
        s.run(60, fused('overwhelmed', 80))
        self.assertEqual(s.proposals_seen, [])

    def test_new_search_resets(self):
        s = Sim('focused')
        s.run(10, fused('overwhelmed', 80))
        s.a.set_view('s2', 'overwhelmed', now=s.t)
        self.assertIsNone(s.a.snapshot()['proposal'])
        self.assertEqual(s.kinds()[-1], 'superseded')

    def test_stale_responses_rejected(self):
        s = Sim('focused')
        with self.assertRaises(KeyError):
            s.a.respond('p999', 'accept')
        with self.assertRaises(KeyError):
            s.a.respond('', 'undo')


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
        self._orig = (ant.READ_GRACE_S, ant.SUSTAIN_S)

    def tearDown(self):
        ant.READ_GRACE_S, ant.SUSTAIN_S = self._orig

    def _live(self, score, tier):
        self.store.set(build_snapshot(score=score, tier=tier, features={}, condition='intervention', calibrated=True))

    def test_offer_accept_undo_round_trip(self):
        ant.READ_GRACE_S, ant.SUSTAIN_S = 0.0, 0.0
        import time
        self._live(15, 0)
        base = time.time()
        self.hub.tick(now=base)
        d = self.client.post('/api/search', json={'query': 'ssd vs hdd'}, headers=self.h).json()
        self.assertEqual(d['policy']['name'], 'focused')
        sid = d['search_id']
        self._live(85, 2)
        snap = None
        for i in range(1, 15):                 # results were stamped with wall-clock time
            snap = self.hub.tick(now=base + i)
        p = snap['anticipation']['proposal']
        self.assertEqual((p['target'], p['search_id']), ('overwhelmed', sid))
        r = self.client.post('/api/search/{}/proposal'.format(sid),
                             json={'proposal_id': p['id'], 'action': 'accept'}, headers=self.h).json()
        self.assertEqual(r['policy']['name'], 'overwhelmed')
        self.assertEqual(r['spec']['topology'], 'stepper')
        u = self.client.post('/api/search/{}/proposal'.format(sid), json={'action': 'undo'}, headers=self.h).json()
        self.assertEqual(u['policy']['name'], 'focused')
        again = self.client.post('/api/search/{}/proposal'.format(sid), json={'action': 'undo'}, headers=self.h)
        self.assertEqual(again.status_code, 409)
        log = self.client.get('/api/anticipation/log', headers=self.h).json()['log']
        self.assertEqual([e['kind'] for e in log], ['proposal', 'accept', 'undo'])

    def test_uncertain_typing_adds_clarifier(self):
        self._live(15, 0)
        # many backspaces while typing the query
        evs = []
        for i in range(10):
            evs.append({'d': i * 250.0, 'u': i * 250.0 + 80, 'k': 'b' if i % 2 else 'n'})
        self.client.post('/api/telemetry/typing', json={'events': evs, 'now': 2600.0}, headers=self.h)
        self.hub.tick()
        d = self.client.post('/api/search', json={'query': 'ssd vs hdd'}, headers=self.h).json()
        self.assertTrue(d['query_uncertain'])

    def test_view_choice_endpoint(self):
        self._live(15, 0)
        d = self.client.post('/api/search', json={'query': 'ssd vs hdd'}, headers=self.h).json()
        r = self.client.post('/api/search/{}/view'.format(d['search_id']), json={'policy': 'neutral'}, headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.hub.anticipator.view['override'])


if __name__ == '__main__':
    unittest.main()
