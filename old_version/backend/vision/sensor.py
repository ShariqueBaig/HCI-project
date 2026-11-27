"""CameraSensor: the one object Aura Search talks to for webcam affect.

* Lazy: OpenCV/onnxruntime are imported and models loaded only on first enable.
* Fixed-rate: a single 5 Hz thread advances the AffectiveEngine; readers get a
  cached copy (the webcam app advanced its engine on every read, so its timing
  depended on how many tabs were open).
* Minimal: `latest()` returns only the numbers fusion uses. `explain()` adds the
  per-emotion scores and an annotated preview frame for the user's own explain
  panel; the preview is encoded only while that panel keeps asking for it
  (PREVIEW_IDLE_S), kept in memory, and never stored or recorded.
"""
import threading
import time

TICK_S = 0.2
PREVIEW_IDLE_S = 3.0      # stop encoding preview frames when nobody is looking
TASK_PRESSURE = 0.2


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
        self._detail = None
        self._last_explain = 0.0
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
            self._detail = None
        return self.status()

    def _run(self):
        while not self._stop.is_set():
            try:
                self._vision.preview = time.time() - self._last_explain <= PREVIEW_IDLE_S
                obs = self._vision.get_latest()
                if obs.get('camera_error'):
                    self.error = obs['camera_error']
                tel = self._affect.update(obs, task_pressure=TASK_PRESSURE)
                sample = summarise(tel)
                detail = explain_detail(obs, tel) if self._vision.preview else None
                with self._lock:
                    self._latest = sample
                    self._detail = detail
            except Exception as e:
                self.error = 'camera tick failed: {}'.format(e)[:200]
            self._stop.wait(TICK_S)

    def explain(self):
        """Full camera reasoning + preview frame (starts the preview on first call)."""
        self._last_explain = time.time()
        with self._lock:
            d = dict(self._detail) if self._detail else None
        return d

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


def explain_detail(obs, tel):
    """What the camera saw and how it turned that into mood numbers (for XAI)."""
    from backend.vision.affective_engine import CIRCUMPLEX_ANCHORS
    emo = tel.get('emotions') or {}
    stress_sig = sum(emo.get(k, 0.0) for k in ('anger', 'fear', 'disgust'))
    att = float(tel.get('attention_score') or 0.0)
    vol = float(tel.get('volatility') or 0.0)
    load_parts = [
        {'label': 'Tense emotions (anger + fear + disgust)', 'value': round(stress_sig, 3), 'weight': 0.45},
        {'label': 'Looking away (1 - attention)', 'value': round(1.0 - att, 3), 'weight': 0.25},
        {'label': 'Expression changing (volatility)', 'value': round(vol, 3), 'weight': 0.15},
        {'label': 'Task pressure (fixed)', 'value': TASK_PRESSURE, 'weight': 0.15},
    ]
    for p in load_parts:
        p['contribution'] = round(p['value'] * p['weight'], 3)
    return {
        'ts': time.time(),
        'frame_jpeg_b64': obs.get('annotated_frame_b64'),
        'face': bool(tel.get('face_detected')),
        'face_count': int(obs.get('face_count') or 0),
        'raw_emotions': {k: round(float(v), 3) for k, v in (obs.get('emotions') or {}).items()},
        'emotions': {k: round(float(v), 3) for k, v in emo.items()},
        'dominant': tel.get('dominant_emotion'),
        'detector_confidence': round(float(obs.get('confidence') or 0.0), 3),
        'valence': round(float(tel.get('valence') or 0.0), 3),
        'arousal': round(float(tel.get('arousal') or 0.0), 3),
        'attention': round(att, 3),
        'head_pitch': round(float(tel.get('head_pitch_proxy') or 0.0), 3),
        'volatility': round(vol, 3),
        'cognitive_load': round(float(tel.get('cognitive_load') or 0.0), 3),
        'load_parts': load_parts,
        'camera_state': tel.get('active_state'),
        'camera_candidate': tel.get('candidate_state'),
        'camera_state_confidence': round(float(tel.get('state_confidence') or 0.0), 3),
        'anchors': {k: list(v) for k, v in CIRCUMPLEX_ANCHORS.items()},
        'latency_ms': obs.get('latency_ms'),
    }
