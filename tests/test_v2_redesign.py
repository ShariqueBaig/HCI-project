"""Verification suite for Aura v2 HCI redesign improvements."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.daemon_controller import AuraController
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.providers import FixtureProvider, ProviderChain
from backend.search.server import create_app
from backend.search.state_fusion import BehaviourLog, fuse
from backend.search.synthesis import StageA
from backend.stress_engine import DEFAULT_SETTINGS, StressEngine


class StressEngineV2Tests(unittest.TestCase):
    def test_dpi_normalized_mouse_agitation_invariant_to_resolution(self):
        # 1080p user moving 14,000px vs 4K user moving 28,000px (same physical screen fraction)
        s_1080 = dict(DEFAULT_SETTINGS, screen_diag_px=2203.0)
        s_4k = dict(DEFAULT_SETTINGS, screen_diag_px=4406.0)
        e1 = StressEngine(s_1080)
        e2 = StressEngine(s_4k)
        f_1080 = {'keys_per_second': 2.5, 'error_rate': 0.02, 'mean_dwell': 0.1,
                  'mean_flight': 0.16, 'std_flight': 0.03, 'flight_count': 6, 'mouse_distance': 14000}
        f_4k = dict(f_1080, mouse_distance=28000)
        e1.update(f_1080)
        e2.update(f_4k)
        self.assertAlmostEqual(e1.score, e2.score, places=2)

    def test_calibrated_dwell_baseline_prevents_false_penalty(self):
        # User whose resting dwell is 180ms should not get penalized at 200ms
        s_cal = dict(DEFAULT_SETTINGS, baseline_dwell=0.18)
        s_uncal = dict(DEFAULT_SETTINGS, baseline_dwell=0.0)
        e_cal = StressEngine(s_cal)
        e_uncal = StressEngine(s_uncal)
        feats = {'keys_per_second': 2.5, 'error_rate': 0.0, 'mean_dwell': 0.20,
                 'mean_flight': 0.15, 'std_flight': 0.0, 'flight_count': 6, 'mouse_distance': 500}
        for _ in range(10):
            e_cal.update(feats)
            e_uncal.update(feats)
        self.assertLess(e_cal.score, e_uncal.score)


class PersonalizedFusionTests(unittest.TestCase):
    def test_calibrated_kps_personalizes_energized_and_fatigued_and_xai(self):
        # Fast typist (baseline 5.5 kps): 4.2 kps is normal, NOT energized; 2.0 kps IS fatigued
        live = build_snapshot(
            score=20.0, tier=0, features={}, condition='intervention',
            calibrated=True, baseline_kps=5.5, baseline_dwell=0.08,
        )
        typing_normal = {'fresh': True, 'score': 15.0,
                         'features': {'keys_per_second': 4.2, 'mean_dwell': 0.08, 'error_rate': 0.01}}
        vec = fuse(live, typing=typing_normal)
        self.assertEqual(vec['state'], 'focused')
        # XAI energized threshold must reflect 5.5 * 1.25 = 6.88 kps
        energized_rule = next(m for m in vec['xai']['moods'] if m['state'] == 'energized')
        tempo_cond = next(c for c in energized_rule['clauses'][0]['conditions'] if c['label'] == 'Typing tempo')
        self.assertAlmostEqual(tempo_cond['threshold'], 6.88, places=2)

        typing_slow = {'fresh': True, 'score': 20.0,
                       'features': {'keys_per_second': 1.9, 'mean_dwell': 0.16, 'error_rate': 0.02}}
        vec2 = fuse(live, typing=typing_slow)
        self.assertEqual(vec2['state'], 'fatigued')

    def test_scroll_thrash_and_hover_abandon_count_toward_disoriented(self):
        log = BehaviourLog()
        log.add_event('scroll_thrash', t=100.0)
        log.add_event('hover_abandon', t=101.0)
        c = log.counts(now=102.0)
        self.assertEqual(c['hesitations'], 2)


class ControllerCalmTechTests(unittest.TestCase):
    def test_silent_focus_mode_holds_and_releases_digest(self):
        ctrl = AuraController(standalone=True, persist=False)
        ctrl.engine.smoothed = 85.0
        _ = ctrl.engine.tier  # enter tier 2
        ctrl.poll_once(features={'keys_per_second': 5.0, 'error_rate': 0.2, 'mean_dwell': 0.2,
                                 'mean_flight': 0.1, 'std_flight': 0.15, 'flight_count': 6,
                                 'mouse_distance': 15000, 'mouse_clicks': 10}, now=1000.0)
        res = ctrl.notify('Slack', 'Ping', now=1001.0)
        self.assertEqual(res['status'], 'held')
        self.assertIsNone(ctrl._focus_digest)

        # Recover to Calm
        ctrl.engine.smoothed = 10.0
        _ = ctrl.engine.tier
        ctrl.poll_once(features={'keys_per_second': 0.0, 'mouse_distance': 0.0}, now=1005.0)
        self.assertIsNotNone(ctrl._focus_digest)
        self.assertEqual(ctrl._focus_digest['count'], 1)
        self.assertEqual(ctrl._focus_digest['apps'], ['Slack'])

    def test_tiered_escalation_waits_15s_before_corner_nudge(self):
        ctrl = AuraController(standalone=True, persist=False)
        ctrl.engine.smoothed = 85.0
        feats = {'keys_per_second': 6.0, 'error_rate': 0.25, 'mean_dwell': 0.22,
                 'mean_flight': 0.09, 'std_flight': 0.12, 'flight_count': 8,
                 'mouse_distance': 16000, 'mouse_clicks': 12}
        ctrl.poll_once(features=feats, now=2000.0)
        self.assertIsNone(ctrl._active_nudge)
        ctrl.poll_once(features=feats, now=2010.0)
        self.assertIsNone(ctrl._active_nudge)
        ctrl.poll_once(features=feats, now=2016.0)
        self.assertIsNotNone(ctrl._active_nudge)

    def test_withdraw_requires_confirmation_and_journal_does_not_stop_recording(self):
        ctrl = AuraController(standalone=True, persist=False)
        with self.assertRaises(ValueError):
            ctrl.withdraw_consent(confirm=False)

        # Simulate active collector stub
        class FakeCollector:
            closed = False
            def log_tick(self, *a, **k): pass
            def end(self, *a, **k): self.closed = True
        ctrl._collector = FakeCollector()
        res = ctrl.save_journal_note('Mid-session note', 'Still going')
        self.assertTrue(res['recording_still_active'])
        self.assertIsNotNone(ctrl._collector)


class ServerV2ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = LiveStateStore()
        self.ctrl = AuraController(standalone=True, persist=False, live_state=self.store, lab_unlocked=True)
        fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'search_fixtures')
        chain = ProviderChain(fixtures=FixtureProvider([fixtures_dir]))
        self.app = create_app(self.store, token='tok', chain=chain, stage_a=StageA(llm=None), controller=self.ctrl)
        self.client = TestClient(self.app)
        self.hdr = {'X-Aura-Token': 'tok'}

    def test_sse_stream_order_and_truth_invariance(self):
        with self.client.stream('POST', '/api/search/stream',
                                json={'query': 'how does caffeine affect sleep'},
                                headers=self.hdr) as resp:
            self.assertEqual(resp.status_code, 200)
            events = []
            for line in resp.iter_lines():
                if line.startswith('data:'):
                    events.append(json.loads(line[5:].strip()))
        kinds = [e['event'] for e in events]
        self.assertIn('stageA', kinds)
        self.assertEqual(kinds[-1], 'done')
        self.assertLess(kinds.index('stageA'), kinds.index('done'))
        result = events[-1]['result']
        stage_a_ids = {c['id'] for c in result['stageA']['claims']}
        self.assertTrue(set(result['spec']['claims_shown']) <= stage_a_ids)

    def test_blinded_mode_blocks_simulation_and_settings_until_unlocked(self):
        class FakeCollector:
            closed = False
            def end(self, *a, **k): pass
        self.ctrl._collector = FakeCollector()
        self.ctrl.lock_lab()
        self.assertTrue(self.ctrl.blinded)

        r1 = self.client.post('/api/simulate', json={'state': 'overwhelmed'}, headers=self.hdr)
        self.assertEqual(r1.status_code, 403)

        r2 = self.client.post('/api/app/settings', json={'study_condition': 'control'}, headers=self.hdr)
        self.assertEqual(r2.status_code, 403)

        r3 = self.client.post('/api/app/lab/unlock', json={}, headers=self.hdr)
        self.assertEqual(r3.status_code, 200)
        r4 = self.client.post('/api/simulate', json={'state': 'fatigued'}, headers=self.hdr)
        self.assertEqual(r4.status_code, 200)

    def test_companion_endpoints_roundtrip(self):
        st = self.client.get('/api/app/status', headers=self.hdr)
        self.assertEqual(st.status_code, 200)
        self.assertIn('comfort', st.json())

        c = self.client.post('/api/app/comfort', json={'theme': 'light', 'auto_adapt': False}, headers=self.hdr)
        self.assertEqual(c.status_code, 200)
        self.assertEqual(c.json()['comfort']['theme'], 'light')
        self.assertFalse(c.json()['comfort']['auto_adapt'])

        for theme_id in ('dark', 'slate', 'light', 'sepia', 'contrast'):
            tr = self.client.post('/api/app/comfort', json={'theme': theme_id}, headers=self.hdr)
            self.assertEqual(tr.status_code, 200)
            self.assertEqual(tr.json()['comfort']['theme'], theme_id)

        chat = self.client.post('/api/app/chat/send', json={'text': 'I feel stuck on a bug'}, headers=self.hdr)
        self.assertEqual(chat.status_code, 200)
        self.assertGreaterEqual(len(chat.json()['messages']), 2)

    def test_simulation_overrides_stale_view_override_and_rerender_all_policies(self):
        # Seed live state as happens in a running app
        self.ctrl.poll_once()
        # User previously forced Standard view (neutral) and disabled auto_adapt
        self.client.post('/api/app/comfort', json={'view_mode_override': 'neutral', 'auto_adapt': False}, headers=self.hdr)
        # Start a mood simulation -> active simulation should win on new search
        sim = self.client.post('/api/simulate', json={'state': 'fatigued', 'duration_s': 45}, headers=self.hdr)
        self.assertEqual(sim.status_code, 200)
        # Force tracker committed state to fatigued for deterministic unit test (bypassing 3s dwell)
        self.app.state.hub.tracker.committed = 'fatigued'
        self.app.state.hub.tick()

        r = self.client.post('/api/search', json={'query': 'how does caffeine affect sleep'}, headers=self.hdr)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['policy']['name'], 'fatigued')

        # Manual rerender across all 6 policies works cleanly
        for pol in ('neutral', 'focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented'):
            rr = self.client.post(f"/api/search/{data['search_id']}/rerender", json={'policy': pol}, headers=self.hdr)
            self.assertEqual(rr.status_code, 200)
            self.assertEqual(rr.json()['policy']['name'], pol)

    def test_study_audit_export_and_zip(self):
        import io
        import zipfile
        au = self.client.get('/api/app/study/audit', headers=self.hdr)
        self.assertEqual(au.status_code, 200)
        self.assertIn('chain_ok', au.json())
        self.assertIn('sessions', au.json())

        ex = self.client.post('/api/app/study/export', headers=self.hdr)
        self.assertEqual(ex.status_code, 200)
        self.assertIn('export_dir', ex.json())
        self.assertTrue(os.path.isdir(ex.json()['export_dir']))

        zp = self.client.get('/api/app/study/export.zip', headers=self.hdr)
        self.assertEqual(zp.status_code, 200)
        self.assertEqual(zp.headers['content-type'], 'application/zip')
        with zipfile.ZipFile(io.BytesIO(zp.content)) as zf:
            names = set(zf.namelist())
            for expected in ('sessions.csv', 'ticks.csv', 'searches.csv', 'search_events.csv', 'tasks.csv', 'surveys.csv'):
                self.assertIn(expected, names)

    def test_condition_switch_updates_live_state_and_rerender(self):
        self.ctrl.poll_once()

        # Switch to Control (A) — Prompt-only
        s1 = self.client.post('/api/app/settings', json={'study_condition': 'control'}, headers=self.hdr)
        self.assertEqual(s1.status_code, 200)
        st1 = self.client.get('/api/state', headers=self.hdr).json()
        self.assertEqual(st1['live']['condition'], 'control')
        self.assertFalse(st1['state']['adaptive'])
        self.assertEqual(st1['app']['study']['condition'], 'control')

        res = self.client.post('/api/search', json={'query': 'how does caffeine affect sleep'}, headers=self.hdr)
        self.assertEqual(res.status_code, 200)
        search_data = res.json()
        self.assertEqual(search_data['policy']['name'], 'neutral')
        self.assertFalse(search_data['adaptive'])

        # Switch back to Active (B) — State-aware: live/state/app must update synchronously
        s2 = self.client.post('/api/app/settings', json={'study_condition': 'intervention'}, headers=self.hdr)
        self.assertEqual(s2.status_code, 200)
        st2 = self.client.get('/api/state', headers=self.hdr).json()
        self.assertEqual(st2['live']['condition'], 'intervention')
        self.assertTrue(st2['state']['adaptive'])
        self.assertEqual(st2['app']['study']['condition'], 'intervention')

        # Switching view mode on the existing search works cleanly
        rr = self.client.post(f"/api/search/{search_data['search_id']}/rerender",
                              json={'policy': 'energized'}, headers=self.hdr)
        self.assertEqual(rr.status_code, 200)
        self.assertEqual(rr.json()['policy']['name'], 'energized')


if __name__ == '__main__':
    unittest.main()
