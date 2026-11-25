"""CameraSensor: the one object Aura Search talks to for webcam affect.

* Lazy: OpenCV/onnxruntime are imported and models loaded only on first enable.
* Fixed-rate: a single 5 Hz thread advances the AffectiveEngine; readers get a
  cached copy (the webcam app advanced its engine on every read, so its timing
  depended on how many tabs were open).
* Minimal: `latest()` returns only the numbers fusion uses -- no frames, no
  landmarks, no per-emotion probabilities leave this module.
"""
import threading
import time

TICK_S = 0.2


def vision_available():
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        return True, None
    except Exception as e:
        return False, 'camera support not installed (pip install ".[vision]"): {}'.format(e)


class CameraSensor:
    def __init__(self):
        self._lock = threading.Lock()
        self._vision = None
        self._affect = None
        self._thread = None
        self._stop = threading.Event()
        self._latest = None
        self.error = None
        self.loading = False

    @property
    def active(self):
        return self._thread is not None and self._thread.is_alive()

    def status(self):
        ok, why = vision_available()
        with self._lock:
            latest = dict(self._latest) if self._latest else None
        return {'available': ok, 'active': self.active, 'loading': self.loading,
                'error': self.error or (None if ok else why), 'latest': latest}

    def start(self):
        ok, why = vision_available()
        if not ok:
            self.error = why
            return self.status()
        if self.active:
            return self.status()
        self.loading, self.error = True, None
        try:
            if self._vision is None:
                from backend.vision.affective_engine import AffectiveEngine
                from backend.vision.model_manager import ModelBundle
                from backend.vision.vision_engine import VisionEngine
                models = ModelBundle().load()
                if not models.ready:
                    raise RuntimeError(models.error or 'emotion models unavailable')
                self._vision = VisionEngine(models)
                self._affect = AffectiveEngine(dwell_seconds=3.0)
                self._affect.configure(agency_mode='manual')   # Aura Search owns state + offers
            res = self._vision.start_camera()
            if res.get('error'):
                raise RuntimeError(res['error'])
        except Exception as e:
            self.error = str(e)[:200]
            self.loading = False
            return self.status()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='aura-camera', daemon=True)
        self._thread.start()
        self.loading = False
        return self.status()

    def stop(self):
        self._stop.set()
        if self._vision is not None:
            self._vision.stop_camera()          # releases the device now
        t = self._thread
        if t:
            t.join(timeout=1.0)
        self._thread = None
        with self._lock:
            self._latest = None
        return self.status()

    def _run(self):
        while not self._stop.is_set():
            try:
                obs = self._vision.get_latest()
                if obs.get('camera_error'):
                    self.error = obs['camera_error']
                tel = self._affect.update(obs, task_pressure=0.2)
                sample = summarise(tel)
                with self._lock:
                    self._latest = sample
            except Exception as e:
                self.error = 'camera tick failed: {}'.format(e)[:200]
            self._stop.wait(TICK_S)

    def latest(self):
        with self._lock:
            return dict(self._latest) if self._latest else None


def summarise(tel):
    """AffectiveEngine telemetry -> the few numbers state fusion may use."""
    return {
        'face': bool(tel.get('face_detected')),
        'valence': round(float(tel.get('valence') or 0.0), 3),
        'arousal': round(float(tel.get('arousal') or 0.0), 3),
        'cognitive_load': round(float(tel.get('cognitive_load') or 0.0), 3),
        'attention': round(float(tel.get('attention_score') or 0.0), 3),
        'camera_state': tel.get('active_state'),
        'confidence': round(float(tel.get('raw_confidence') or 0.0), 3),
        'ts': time.time(),
    }
