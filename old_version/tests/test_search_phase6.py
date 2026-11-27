"""Phase 6 tests: optional camera affect in state fusion. Never opens a real webcam.

Run:  python -m unittest discover -s tests -v
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.search.hub import StateHub
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.search.state_fusion import fuse
from backend.vision import sensor as sensor_mod
from backend.vision.sensor import CameraSensor, summarise


def live(score=20.0, tier=0):
    return build_snapshot(score=score, tier=tier, features={}, condition='intervention', calibrated=True)


def cam(valence=0.0, arousal=0.0, load=0.1, face=True, age=0.0):
    return {'face': face, 'valence': valence, 'arousal': arousal, 'cognitive_load': load,
            'attention': 0.9, 'camera_state': 'focused', 'confidence': 0.8, 'ts': time.time() - age}


class CameraFusionTests(unittest.TestCase):
    def test_camera_off_changes_nothing(self):
        self.assertEqual(fuse(live(20)), fuse(live(20), affect=None))

    def test_tense_face_with_rising_stress_is_overwhelmed(self):
        self.assertEqual(fuse(live(40, 1))['state'], 'focused')
        v = fuse(live(40, 1), affect=cam(valence=-0.5, arousal=0.4))
        self.assertEqual(v['state'], 'overwhelmed')
        self.assertIn('camera', v['sources'])
        self.assertTrue(any('camera' in e for e in v['evidence']))

    def test_tense_face_alone_with_low_stress_is_not_enough(self):
        self.assertNotEqual(fuse(live(15), affect=cam(valence=-0.5, arousal=0.4))['state'], 'overwhelmed')

    def test_tired_face_is_fatigued_without_typing(self):
        self.assertEqual(fuse(live(20), affect=cam(valence=-0.3, arousal=-0.4))['state'], 'fatigued')

    def test_upbeat_face_is_energized(self):
        self.assertEqual(fuse(live(15), affect=cam(valence=0.5, arousal=0.3))['state'], 'energized')

    def test_no_face_or_stale_reading_is_ignored(self):
        for a in (cam(-0.3, -0.4, face=False), cam(-0.3, -0.4, age=5)):
            v = fuse(live(20), affect=a)
            self.assertEqual(v['state'], 'focused')
            self.assertNotIn('camera', v['sources'])

    def test_contributions_are_reported(self):
        v = fuse(live(20), affect=cam(0.4, 0.2))
        self.assertEqual((v['contributions']['camera_valence'], v['contributions']['camera_arousal']), (0.4, 0.2))


class FakeVision:
    def __init__(self):
        self.started = self.stopped = 0

    def start_camera(self):
        self.started += 1
        return {'camera_active': True, 'error': None}

    def stop_camera(self):
        self.stopped += 1
        return {'camera_active': False}

    def get_latest(self):
        return {'face_detected': True}


class FakeAffect:
    def update(self, obs, task_pressure=0.2):
        return {'face_detected': True, 'valence': -0.4, 'arousal': 0.5, 'cognitive_load': 0.3,
                'attention_score': 0.8, 'active_state': 'overwhelmed', 'raw_confidence': 0.7}


class SensorLifecycleTests(unittest.TestCase):
    def make(self):
        s = CameraSensor()
        s._vision, s._affect = FakeVision(), FakeAffect()
        return s

    def test_start_tick_stop_releases_device(self):
        s = self.make()
        st = s.start()
        self.assertTrue(st['active'], st)
        time.sleep(0.5)
        latest = s.latest()
        self.assertEqual((latest['valence'], latest['arousal'], latest['face']), (-0.4, 0.5, True))
        self.assertNotIn('frame', ' '.join(latest))
        s.stop()
        self.assertFalse(s.active)
        self.assertIsNone(s.latest())
        self.assertEqual(s._vision.stopped, 1)

    def test_unavailable_dependencies_reported(self):
        orig = sensor_mod.vision_available
        sensor_mod.vision_available = lambda: (False, 'camera support not installed')
        try:
            st = CameraSensor().start()
            self.assertFalse(st['active'])
            self.assertIn('not installed', st['error'])
        finally:
            sensor_mod.vision_available = orig

    def test_summary_has_numbers_only(self):
        out = summarise({'face_detected': True, 'valence': 0.1, 'arousal': 0.2, 'cognitive_load': 0.3,
                         'attention_score': 0.4, 'active_state': 'focused', 'raw_confidence': 0.5,
                         'emotions': {'anger': 0.9}, 'annotated_frame_b64': 'xxxx'})
        self.assertNotIn('emotions', out)
        self.assertNotIn('annotated_frame_b64', out)

    def test_hub_uses_camera_and_endpoints(self):
        store = LiveStateStore()
        store.set(live(40, 1))
        hub = StateHub(store)
        hub.camera = self.make()
        hub.camera.start()
        try:
            time.sleep(0.4)
            out = hub.tick()
            self.assertTrue(out['camera']['active'])
            self.assertIn('camera', out['fused']['sources'])
            self.assertEqual(out['fused']['state'], 'overwhelmed')
            from backend.search.server import create_app
            client = TestClient(create_app(store, 't', ui_dist=None, hub=hub))
            st = client.post('/api/camera', json={'enabled': False}, headers={'X-Aura-Token': 't'}).json()
            self.assertFalse(st['active'])
            self.assertFalse(hub.tick()['camera']['active'])
            self.assertEqual(client.post('/api/camera', json={'enabled': True}).status_code, 401)
        finally:
            hub.camera.stop()


if __name__ == '__main__':
    unittest.main()
