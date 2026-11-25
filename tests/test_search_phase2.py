"""Phase 2 tests for Aura Search: query typing, state fusion, hysteresis, policy.

Run:  python -m unittest discover -s tests -v
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.search.hub import StateHub
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.policy import POLICY_NAMES, get_policy, policy_for
from backend.search.state_fusion import BehaviourLog, StateTracker, fuse, is_reformulation
from backend.search.typing import QueryTypingTracker, features

TOKEN = 't'


def live(score=20.0, tier=0, condition='intervention', blocking=False, breathing=False):
    return build_snapshot(score=score, tier=tier, features={}, condition=condition, calibrated=True,
                          focus_blocking=blocking, breathing_active=breathing)


def typing(score=10.0, kps=3.0, dwell=0.1, err=0.0, fresh=True):
    return {'fresh': fresh, 'score': score,
            'features': {'keys_per_second': kps, 'mean_dwell': dwell, 'error_rate': err}}


class TypingParityTests(unittest.TestCase):
    """Browser events through typing.features() == pynput events through TelemetryDaemon."""

    def test_matches_telemetry_daemon(self):
        import backend.telemetry_daemon as td
        from pynput import keyboard
        from pynput.keyboard import KeyCode
        real_time = td.time.time
        try:
            for seed in range(60):
                r, clock = random.Random(seed), [1000.0]
                td.time.time = lambda: clock[0]
                d = td.TelemetryDaemon(window_size_seconds=5)
                ev, t = [], 1000.0
                for _ in range(50):
                    kind = r.choices(['n', 'b', 'hold', 'ctrl', 'pause'], [70, 12, 4, 4, 10])[0]
                    if kind == 'pause':
                        t += r.uniform(2.1, 3.0)
                        continue
                    t += r.uniform(0.05, 0.35)
                    if kind in ('n', 'b'):
                        key = KeyCode(vk=65 + r.randrange(26)) if kind == 'n' else keyboard.Key.backspace
                        dw = r.uniform(0.05, 0.2)
                        clock[0] = t; d.on_press(key)
                        clock[0] = t + dw; d.on_release(key)
                        ev.append({'d': t * 1000, 'u': (t + dw) * 1000, 'k': kind}); t += dw
                    elif kind == 'hold':
                        key = keyboard.Key.backspace
                        clock[0] = t; d.on_press(key)
                        for j in range(3):
                            clock[0] = t + 0.5 + 0.03 * j; d.on_press(key)
                            ev.append({'d': clock[0] * 1000, 'k': 'rb'})
                        clock[0] = t + 0.7; d.on_release(key)
                        ev.append({'d': t * 1000, 'u': (t + 0.7) * 1000, 'k': 'b'}); t += 0.7
                    else:
                        clock[0] = t; d.on_press(keyboard.Key.ctrl_l)
                        clock[0] = t + 0.05; d.on_press(keyboard.Key.backspace)
                        clock[0] = t + 0.15; d.on_release(keyboard.Key.backspace)
                        clock[0] = t + 0.2; d.on_release(keyboard.Key.ctrl_l)
                        ev.append({'d': (t + 0.05) * 1000, 'u': (t + 0.15) * 1000, 'k': 'c'})
                        ev.append({'u': (t + 0.2) * 1000, 'k': 'm'}); t += 0.2
                clock[0] = t + 0.4
                a, b = d.get_features(), features(ev, (t + 0.4) * 1000)
                for k in a:
                    self.assertAlmostEqual(a[k], b[k], places=6, msg='seed {} {}'.format(seed, k))
        finally:
            td.time.time = real_time

    def test_tracker_ignores_bad_events_and_page_reload(self):
        tr = QueryTypingTracker()
        tr.ingest([{'k': 'x'}, 'junk', {'d': 'a', 'k': 'n'},
                   {'d': 60000, 'u': 60080, 'k': 'n'}], 60100, wall=50)
        self.assertEqual(len(tr._events), 1)                        # only the valid event kept
        tr.ingest([{'d': 10, 'u': 90, 'k': 'n'}], 100, wall=51)     # page reload: performance.now() restarted
        self.assertEqual(tr._events, [{'d': 10, 'u': 90, 'k': 'n'}])

    def test_freshness(self):
        tr = QueryTypingTracker()
        tr.ingest([{'d': 0, 'u': 80, 'k': 'n'}], 100, wall=1000.0)
        self.assertTrue(tr.snapshot(1005.0)['fresh'])
        self.assertFalse(tr.snapshot(1011.0)['fresh'])


class FusionRuleTests(unittest.TestCase):
    def test_no_signals_is_low_confidence_focused(self):
        v = fuse(None)
        self.assertEqual((v['state'], v['confidence']), ('focused', 0.3))

    def test_aura_stress_alone_drives_overwhelmed(self):
        v = fuse(live(82, 2))                       # Aura "Simulate Stress"
        self.assertEqual(v['state'], 'overwhelmed')
        self.assertIn('aura_stress', v['contributions'])

    def test_moderate_stress_plus_friction(self):
        self.assertEqual(fuse(live(50, 1), behaviour={'rage_clicks': 2})['state'], 'overwhelmed')
        self.assertEqual(fuse(live(50, 1), behaviour={'rage_clicks': 1})['state'], 'focused')

    def test_focus_mode_blocking(self):
        self.assertEqual(fuse(live(55, 2, blocking=True))['state'], 'overwhelmed')

    def test_typing_stress_is_weighted_in(self):
        v = fuse(live(40, 1), typing(score=95))
        self.assertAlmostEqual(v['stress'], (40 * 1.0 + 95 * 0.6) / 1.6, places=1)
        self.assertEqual(v['state'], 'overwhelmed')
        stale = fuse(live(40, 1), typing(score=90, fresh=False))
        self.assertEqual(stale['stress'], 40.0)

    def test_reformulations_disoriented(self):
        self.assertEqual(fuse(live(20), behaviour={'reformulations': 2})['state'], 'disoriented')

    def test_fatigued_and_energized_need_typing(self):
        self.assertEqual(fuse(live(20), typing(kps=1.0, dwell=0.22))['state'], 'fatigued')
        self.assertEqual(fuse(live(10), typing(score=5, kps=5.0, err=0.02))['state'], 'energized')
        self.assertEqual(fuse(live(10))['state'], 'focused')        # no typing -> no tempo claims

    def test_breathing_sets_quiet(self):
        self.assertTrue(fuse(live(80, 2, breathing=True))['quiet'])

    def test_evidence_always_present(self):
        for v in (fuse(live(82, 2)), fuse(live(10)), fuse(None)):
            self.assertTrue(v['evidence'])


class ReformulationTests(unittest.TestCase):
    def test_detection(self):
        self.assertTrue(is_reformulation('best budget laptop for students', 'cheap student laptop 2026'))
        self.assertFalse(is_reformulation('best budget laptop', 'best budget laptop'))
        self.assertFalse(is_reformulation('caffeine sleep', 'compost at home'))

    def test_log_counts_within_window(self):
        log = BehaviourLog()
        log.add_query('budget laptop students', t=100)
        self.assertTrue(log.add_query('cheap laptop students', t=110))
        self.assertTrue(log.add_query('student laptop under 500', t=120))
        self.assertEqual(log.counts(now=130)['reformulations'], 2)
        self.assertEqual(log.counts(now=400)['reformulations'], 0)
        log.add_event('rage_click', t=125)
        self.assertEqual(log.counts(now=130)['rage_clicks'], 1)
        self.assertEqual(log.counts(now=200)['rage_clicks'], 0)


class TrackerTests(unittest.TestCase):
    def v(self, s):
        return {'state': s, 'confidence': 0.8, 'evidence': ['x']}

    def test_first_state_commits_immediately(self):
        tr = StateTracker()
        self.assertEqual(tr.update(self.v('overwhelmed'), 0)['committed_state'], 'overwhelmed')

    def test_dwell_and_cooldown(self):
        tr = StateTracker(dwell_s=3, cooldown_s=5)
        tr.update(self.v('focused'), 0)
        out = tr.update(self.v('overwhelmed'), 6)
        self.assertEqual((out['committed_state'], out['candidate_state']), ('focused', 'overwhelmed'))
        self.assertEqual(tr.update(self.v('overwhelmed'), 8.9)['committed_state'], 'focused')
        self.assertEqual(tr.update(self.v('overwhelmed'), 9.1)['committed_state'], 'overwhelmed')
        # cooldown: a new candidate that dwells 3 s still waits for 5 s after the last commit
        tr.update(self.v('focused'), 9.2)
        self.assertEqual(tr.update(self.v('focused'), 12.5)['committed_state'], 'overwhelmed')
        self.assertEqual(tr.update(self.v('focused'), 14.2)['committed_state'], 'focused')

    def test_brief_spike_is_a_prevented_flicker(self):
        tr = StateTracker(dwell_s=3, cooldown_s=0)
        tr.update(self.v('focused'), 0)
        tr.update(self.v('overwhelmed'), 1)
        out = tr.update(self.v('focused'), 2)
        self.assertEqual(out['committed_state'], 'focused')
        self.assertEqual(out['flickers_prevented'], 1)
        self.assertEqual(out['transitions'], 0)


class PolicyTests(unittest.TestCase):
    def test_all_policies_valid(self):
        for name in POLICY_NAMES:
            p = get_policy(name)
            self.assertEqual(p['name'], name)
            for w in p['required_widgets']:
                self.assertIn(w, p['allowed_widgets'], '{} requires {}'.format(name, w))
            self.assertGreaterEqual(p['max_primary_options'], 1)

    def test_overwhelmed_is_strictest(self):
        o = get_policy('overwhelmed')
        self.assertEqual(o['max_primary_options'], 1)
        self.assertLess(o['answer_word_budget'], get_policy('focused')['answer_word_budget'])
        self.assertGreater(o['tokens']['targetScale'], 1.2)
        self.assertFalse(o['allow_custom_widget'])

    def test_control_is_always_neutral(self):
        self.assertEqual(policy_for('overwhelmed', 'control')['name'], 'neutral')
        self.assertEqual(policy_for('overwhelmed', 'intervention')['name'], 'overwhelmed')
        self.assertEqual(get_policy('nonsense')['name'], 'neutral')

    def test_policies_are_copies(self):
        get_policy('focused')['allowed_widgets'].append('Evil')
        self.assertNotIn('Evil', get_policy('focused')['allowed_widgets'])


class HubAndEndpointTests(unittest.TestCase):
    def setUp(self):
        self.store = LiveStateStore()
        self.hub = StateHub(self.store)
        from backend.search.providers import FixtureProvider, ProviderChain, SearchResult, Source
        from backend.search.synthesis import StageA

        class Wiki:
            def search(self, q, k=5):
                return SearchResult(q, 'wikipedia', [Source('s1', 'T', 'https://e/t', 's',
                                                            'Laptops for students are cheap and light.')])

        class NoTavily:
            available = False

        chain = ProviderChain(FixtureProvider(['/nonexistent']), NoTavily(), Wiki())
        self.client = TestClient(create_app_for(self.store, self.hub, chain, StageA(None)))
        self.h = {'X-Aura-Token': TOKEN}

    def test_simulate_stress_flows_to_overwhelmed_after_dwell(self):
        self.store.set(live(15, 0))
        self.hub.tick(now=0)
        self.store.set(live(82, 2))                 # Aura "Simulate Stress" pressed
        self.assertEqual(self.hub.tick(now=6)['fused']['committed_state'], 'focused')
        out = self.hub.tick(now=9.5)
        self.assertEqual(out['fused']['committed_state'], 'overwhelmed')
        self.assertEqual(out['policy']['name'], 'overwhelmed')
        self.assertTrue(out['adaptive'])

    def test_control_mode_records_but_does_not_adapt(self):
        self.store.set(live(82, 2, condition='control'))
        out = self.hub.tick(now=0)
        self.assertEqual(out['fused']['committed_state'], 'overwhelmed')
        self.assertFalse(out['adaptive'])
        self.assertEqual(out['policy']['name'], 'neutral')

    def test_typing_endpoint_feeds_query_stress(self):
        self.store.set(live(20))
        evs = [{'d': i * 300.0, 'u': i * 300.0 + 90, 'k': 'n'} for i in range(12)]
        r = self.client.post('/api/telemetry/typing', json={'events': evs, 'now': 12 * 300.0}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()['fresh'])
        snap = self.hub.tick()
        self.assertIn('query_typing_stress', snap['fused']['contributions'])
        self.assertGreater(snap['typing']['features']['keys_per_second'], 0)

    def test_typing_and_behaviour_validation(self):
        self.assertEqual(self.client.post('/api/telemetry/typing', json={'events': []}, headers=self.h).status_code, 422)
        self.assertEqual(self.client.post('/api/behavior', json={'type': 'keylog'}, headers=self.h).status_code, 422)
        self.assertEqual(self.client.post('/api/behavior', json={'type': 'rage_click'}).status_code, 401)
        self.assertEqual(self.client.post('/api/behavior', json={'type': 'rage_click'}, headers=self.h).status_code, 200)
        self.assertEqual(self.hub.behaviour.counts()['rage_clicks'], 1)

    def test_state_endpoint_and_search_carry_state_and_policy(self):
        self.store.set(live(82, 2))
        s = self.client.get('/api/state', headers=self.h).json()
        self.assertEqual(s['state']['fused']['committed_state'], 'overwhelmed')
        r1 = self.client.post('/api/search', json={'query': 'budget laptop students'}, headers=self.h).json()
        self.assertFalse(r1['reformulation'])
        self.assertEqual(r1['policy']['name'], 'overwhelmed')
        r2 = self.client.post('/api/search', json={'query': 'cheap laptop for students'}, headers=self.h).json()
        self.assertTrue(r2['reformulation'])


def create_app_for(store, hub, chain, stage_a):
    from backend.search.server import create_app
    return create_app(store, TOKEN, ui_dist=None, chain=chain, stage_a=stage_a, hub=hub)


if __name__ == '__main__':
    unittest.main()
