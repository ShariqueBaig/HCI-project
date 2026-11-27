"""XAI explanation + mood simulation tests for Aura Search.

Run:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.search.hub import SIM_PROFILES, StateHub
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.state_fusion import fuse

TOKEN = 't'


def live(score=20.0, tier=0, blocking=False):
    return build_snapshot(score=score, tier=tier, features={}, condition='intervention',
                          calibrated=True, focus_blocking=blocking)


def typing(score=10.0, kps=3.0, dwell=0.1, err=0.0):
    return {'fresh': True, 'score': score,
            'features': {'keys_per_second': kps, 'mean_dwell': dwell, 'error_rate': err}}


class ExplainTests(unittest.TestCase):
    def chosen(self, v):
        return [m['state'] for m in v['xai']['moods'] if m['chosen']]

    def test_explanation_agrees_with_decision(self):
        cases = [
            (live(80, 2), None, {}),
            (live(50), None, {'rage_clicks': 2}),
            (live(20), None, {'reformulations': 2}),
            (live(20), typing(20, kps=1.0, dwell=0.2), {}),
            (live(10), typing(10, kps=5.0, err=0.02), {}),
            (live(35), None, {}),
        ]
        for lv, ty, beh in cases:
            v = fuse(lv, ty, beh)
            self.assertEqual(self.chosen(v), [v['state']])
            winner = next(m for m in v['xai']['moods'] if m['chosen'])
            self.assertTrue(winner['matched'])
            self.assertEqual(winner['closeness'], 1.0)
            # every higher-priority mood must not have matched
            for m in v['xai']['moods']:
                if m['priority'] < winner['priority']:
                    self.assertFalse(m['matched'], (v['state'], m['state']))

    def test_conditions_report_values_and_thresholds(self):
        v = fuse(live(42), None, {})
        over = next(m for m in v['xai']['moods'] if m['state'] == 'overwhelmed')
        c = over['clauses'][0]['conditions'][0]
        self.assertEqual((c['value'], c['op'], c['threshold'], c['met']), (42.0, '>=', 60, False))
        self.assertAlmostEqual(c['progress'], 0.7, places=2)

    def test_stress_fusion_breakdown(self):
        v = fuse(live(80), typing(20), {})
        parts = {p['source']: p for p in v['xai']['stress_fusion']['parts']}
        self.assertEqual(set(parts), {'aura', 'query_typing'})
        self.assertAlmostEqual(parts['aura']['share'] + parts['query_typing']['share'], 1.0, places=2)
        self.assertEqual(v['xai']['stress_fusion']['fused'], v['stress'])


class MoodSimulationTests(unittest.TestCase):
    def setUp(self):
        self.store = LiveStateStore()
        self.store.set(live(20))
        self.hub = StateHub(self.store)

    def test_each_mood_is_predicted_by_the_real_rules(self):
        t = 1000.0
        self.hub.tick(t)
        for mood in SIM_PROFILES:
            self.hub.simulate(mood, 45, now=t)
            for i in range(8):
                out = self.hub.tick(t + i * 0.5)
            self.assertEqual(out['fused']['state'], mood)
            self.assertEqual(out['fused']['committed_state'], mood)
            self.assertEqual(out['simulation']['state'], mood)
            t += 10

    def test_simulation_expires_and_stops(self):
        self.hub.simulate('fatigued', 5, now=0.0)
        self.assertIsNotNone(self.hub.simulation_status(4.0))
        self.assertIsNone(self.hub.simulation_status(6.0))
        self.hub.simulate('energized', 45)
        self.hub.simulate(None)
        self.assertIsNone(self.hub.current()['simulation'])

    def test_api(self):
        from backend.search.server import create_app
        from backend.search.providers import ProviderChain
        from backend.search.synthesis import StageA
        c = TestClient(create_app(self.store, TOKEN, ui_dist=None, chain=ProviderChain(),
                                  stage_a=StageA(None), hub=self.hub))
        h = {'X-Aura-Token': TOKEN}
        r = c.post('/api/simulate', json={'state': 'overwhelmed'}, headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['simulation']['state'], 'overwhelmed')
        self.assertEqual(c.post('/api/simulate', json={'state': 'sleepy'}, headers=h).status_code, 422)
        self.assertEqual(c.post('/api/simulate', json={'state': None}).status_code, 401)
        r = c.post('/api/simulate', json={'state': None}, headers=h)
        self.assertIsNone(r.json()['simulation'])
        snap = c.get('/api/state', headers=h).json()['state']
        self.assertIn('xai', snap['fused'])


class CameraExplainTests(unittest.TestCase):
    def test_detail_explains_load_and_mood(self):
        try:
            from backend.vision.sensor import explain_detail
            explain_detail({}, {})
        except ImportError as e:
            self.skipTest('vision extras not installed: {}'.format(e))
        obs = {'annotated_frame_b64': 'abc', 'face_count': 1, 'confidence': 0.7,
               'emotions': {'fear': 0.7, 'neutral': 0.3}, 'latency_ms': 12}
        tel = {'face_detected': True, 'emotions': {'fear': 0.5, 'anger': 0.2, 'neutral': 0.3},
               'dominant_emotion': 'fear', 'valence': -0.5, 'arousal': 0.6, 'attention_score': 0.6,
               'volatility': 0.2, 'cognitive_load': 0.5, 'active_state': 'overwhelmed',
               'state_confidence': 0.8}
        d = explain_detail(obs, tel)
        self.assertEqual(d['frame_jpeg_b64'], 'abc')
        self.assertEqual(d['camera_state'], 'overwhelmed')
        parts = {p['weight']: p for p in d['load_parts']}
        self.assertAlmostEqual(parts[0.45]['value'], 0.7, places=3)        # anger + fear
        self.assertAlmostEqual(parts[0.25]['value'], 0.4, places=3)        # 1 - attention
        self.assertAlmostEqual(sum(p['contribution'] for p in d['load_parts']), 0.315 + 0.1 + 0.03 + 0.03, places=3)
        self.assertIn('happiness', d['anchors'])

    def test_endpoint_when_camera_off(self):
        from backend.search.providers import ProviderChain
        from backend.search.server import create_app
        from backend.search.synthesis import StageA
        store = LiveStateStore()
        store.set(live(20))
        c = TestClient(create_app(store, TOKEN, ui_dist=None, chain=ProviderChain(),
                                  stage_a=StageA(None), hub=StateHub(store)))
        r = c.get('/api/camera/explain', headers={'X-Aura-Token': TOKEN})
        self.assertEqual(r.json(), {'active': False, 'detail': None, 'used_by_fusion': False})
        self.assertEqual(c.get('/api/camera/explain').status_code, 401)


if __name__ == '__main__':
    unittest.main()
