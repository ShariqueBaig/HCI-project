"""Phase 0 tests for Aura Search: engine extraction, live state, local server.

Run:  python -m unittest discover -s tests -v
"""
import json
import os
import socket
import sys
import time
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.llm_controller import LLMController
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.server import SearchServer, create_app
from backend.stress_engine import DEFAULT_SETTINGS, StressEngine

TOKEN = 'test-token'


def _snapshot(score=40.0, tier=1):
    return build_snapshot(score=score, tier=tier,
                          features={'mean_flight': 0.2, 'std_flight': 0.1, 'flight_count': 5},
                          condition='intervention', calibrated=True)


class StressEngineTests(unittest.TestCase):
    def test_run_still_reexports_engine(self):
        # experiments/run_experiment.py does `from run import StressEngine`
        with open(os.path.join(os.path.dirname(__file__), '..', 'run.py'), encoding='utf-8') as f:
            self.assertIn('from backend.stress_engine import StressEngine', f.read())

    def test_hysteresis_and_idle_decay(self):
        e = StressEngine(dict(DEFAULT_SETTINGS))
        self.assertEqual(e.tier, 0)
        e.smoothed = 61; self.assertEqual(e.tier, 2)
        e.smoothed = 55; self.assertEqual(e.tier, 2)    # stays Elevated until < 52
        e.smoothed = 51; self.assertEqual(e.tier, 1)
        e.smoothed = 27; self.assertEqual(e.tier, 1)    # stays Mild until < 26
        e.smoothed = 25; self.assertEqual(e.tier, 0)
        e.smoothed = 50
        e.update({'keys_per_second': 0, 'mouse_distance': 0})
        self.assertLess(e.score, 50)
        e.smoothed = 40
        self.assertEqual(e.tier, 1)
        self.assertEqual(e.target_brightness, DEFAULT_SETTINGS['bright_mild'])
        self.assertEqual(e.target_temp, DEFAULT_SETTINGS['temp_mild'])


class LiveStateTests(unittest.TestCase):
    def test_snapshot_fields_and_copy(self):
        store = LiveStateStore()
        self.assertIsNone(store.get())
        store.set(_snapshot())
        got = store.get()
        self.assertEqual(got['label'], 'Mild')
        self.assertAlmostEqual(got['features']['cov'], 0.5)
        got['score'] = 999                       # callers get a copy
        self.assertEqual(store.get()['score'], 40.0)
        self.assertEqual(store.version, 1)

    def test_cov_needs_three_flights(self):
        s = build_snapshot(score=0, tier=0, features={'mean_flight': 0.2, 'std_flight': 0.1,
                                                      'flight_count': 2},
                           condition='control', calibrated=False)
        self.assertEqual(s['features']['cov'], 0.0)


class ServerAppTests(unittest.TestCase):
    def setUp(self):
        self.store = LiveStateStore()
        self.client = TestClient(create_app(self.store, TOKEN, ui_dist=None))

    def test_token_required(self):
        self.assertEqual(self.client.get('/api/health').status_code, 401)
        self.assertEqual(self.client.get('/api/health', headers={'X-Aura-Token': 'nope'}).status_code, 401)
        self.assertEqual(self.client.get('/api/health', headers={'X-Aura-Token': TOKEN}).status_code, 200)
        self.assertEqual(self.client.get('/api/health?t=' + TOKEN).status_code, 200)

    def test_state_503_then_live(self):
        h = {'X-Aura-Token': TOKEN}
        self.assertEqual(self.client.get('/api/state', headers=h).status_code, 503)
        self.store.set(_snapshot(score=70, tier=2))
        r = self.client.get('/api/state', headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['live']['label'], 'Elevated')

    def test_websocket_requires_token_and_pushes(self):
        self.store.set(_snapshot())
        with self.client.websocket_connect('/ws/state?t=' + TOKEN) as ws:
            self.assertEqual(json.loads(ws.receive_text())['live']['tier'], 1)
        with self.assertRaises(Exception):
            with self.client.websocket_connect('/ws/state?t=wrong') as ws:
                ws.receive_text()

    def test_placeholder_index_without_build(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Aura Search', r.text)

    def test_serves_built_ui(self):
        dist = os.path.join(os.path.dirname(__file__), '..', 'search_ui', 'dist')
        if not os.path.isfile(os.path.join(dist, 'index.html')):
            self.skipTest('search_ui not built')
        client = TestClient(create_app(self.store, TOKEN, ui_dist=dist))
        r = client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('<div id="root">', r.text)


class ServerThreadTests(unittest.TestCase):
    def test_start_serve_stop(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        store = LiveStateStore()
        store.set(_snapshot())
        srv = SearchServer(store, port=port, token=TOKEN, ui_dist='').start()
        try:
            self.assertTrue(srv.wait_started(5), srv.error)
            req = urllib.request.Request('http://127.0.0.1:{}/api/state'.format(port),
                                         headers={'X-Aura-Token': TOKEN})
            with urllib.request.urlopen(req, timeout=3) as r:
                self.assertEqual(json.load(r)['live']['label'], 'Mild')
            self.assertIn('t=' + TOKEN, srv.url)
        finally:
            srv.stop()
        time.sleep(0.2)
        self.assertFalse(srv._thread.is_alive())


class LlmJsonTests(unittest.TestCase):
    def test_extract_json(self):
        x = LLMController.extract_json
        self.assertEqual(x('{"a": 1}'), {'a': 1})
        self.assertEqual(x('```json\n{"a": 2}\n```'), {'a': 2})
        self.assertEqual(x('Here: {"a": {"b": "x}y"}} done'), {'a': {'b': 'x}y'}})
        with self.assertRaises(ValueError):
            x('no json here')

    def test_complete_json_without_key_raises(self):
        c = LLMController()
        c.key = ''
        with self.assertRaises(RuntimeError):
            c.complete_json([{'role': 'user', 'content': 'hi'}])


if __name__ == '__main__':
    unittest.main()
