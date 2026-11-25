"""Thread-safe snapshot of Aura's live state, shared with the search server.

The Tk main thread writes a fresh snapshot every tick (AmbientApp._refresh);
the search server thread only ever reads copies. Nothing here touches the
engine directly, so the stateful `StressEngine.tier` getter is never called
from another thread.
"""
import copy
import math
import threading
import time

TIER_LABELS = ['Calm', 'Mild', 'Elevated']


class LiveStateStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = None
        self._version = 0

    def set(self, state):
        state = dict(state)
        state.setdefault('ts', time.time())
        with self._lock:
            self._state = state
            self._version += 1

    def get(self):
        """Return a deep copy of the latest snapshot (or None before the first tick)."""
        with self._lock:
            return copy.deepcopy(self._state) if self._state is not None else None

    @property
    def version(self):
        with self._lock:
            return self._version


def build_snapshot(*, score, tier, features, condition, calibrated,
                   baseline_cov=0.0, baseline_err=0.0, dnd_active=False,
                   focus_blocking=False, breathing_active=False, held_count=0,
                   simulated=False, demo=False, recording=False,
                   brightness=None, session_stats=None):
    """Build the LiveState dict from values the Tk thread already holds."""
    feats = {k: (round(v, 4) if isinstance(v, float) else v)
             for k, v in (features or {}).items()}
    mf, sf = feats.get('mean_flight', 0) or 0, feats.get('std_flight', 0) or 0
    feats['cov'] = round(min(sf / mf, 3.0), 4) if (mf > 0 and feats.get('flight_count', 0) >= 3) else 0.0
    return {
        'ts': time.time(),
        'score': round(float(score), 2),
        'tier': int(tier),
        'label': TIER_LABELS[int(tier)],
        'features': feats,
        'condition': condition,               # 'intervention' (Active B) | 'control' (A) | ...
        'calibrated': bool(calibrated),
        'baseline_cov': baseline_cov,
        'baseline_err': baseline_err,
        'dnd_active': bool(dnd_active),
        'focus_blocking': bool(focus_blocking),
        'breathing_active': bool(breathing_active),
        'held_count': int(held_count),
        'simulated': bool(simulated),
        'demo': bool(demo),
        'recording': bool(recording),
        'brightness': brightness,
        'session_stats': session_stats or {},
    }


class SimulatedLiveState:
    """Stand-in for --standalone dev mode: a slow wave through Calm/Mild/Elevated."""

    def __init__(self, store, period_s=90.0):
        self.store = store
        self.period_s = period_s
        self._t0 = time.time()
        self._tier = 0
        self._stop = threading.Event()

    def _tick(self):
        t = time.time() - self._t0
        score = 45 + 40 * math.sin(2 * math.pi * t / self.period_s)
        # same hysteresis as StressEngine.tier
        if self._tier == 2:
            self._tier = 0 if score < 26 else (1 if score < 52 else 2)
        elif self._tier == 1:
            self._tier = 2 if score >= 60 else (0 if score < 26 else 1)
        else:
            self._tier = 2 if score >= 60 else (1 if score >= 30 else 0)
        self.store.set(build_snapshot(
            score=score, tier=self._tier,
            features={'keys_per_second': 2.5, 'error_rate': 0.05, 'mean_dwell': 0.11,
                      'std_dwell': 0.03, 'mean_flight': 0.18, 'std_flight': 0.07,
                      'flight_count': 12, 'mouse_distance': 1800, 'mouse_clicks': 2},
            condition='intervention', calibrated=False, simulated=True))

    def run(self):
        while not self._stop.is_set():
            self._tick()
            self._stop.wait(0.333)

    def start(self):
        self._tick()
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self._stop.set()
