"""Query-box typing dynamics -> the same 9 features as Aura's TelemetryDaemon.

The search window reports *timing only* for keys typed in the search box --
never characters or key identities. Each event is one of:

    {"d": t_down_ms, "u": t_up_ms, "k": "n"}  normal key (press + release)
    {"d": t_down_ms, "u": t_up_ms, "k": "b"}  Backspace / Delete
    {"d": t_down_ms, "k": "r"}                auto-repeat of a held key (no release)
    {"d": t_down_ms, "k": "rb"}               auto-repeat of a held Backspace/Delete
    {"d": t_down_ms, "u": t_up_ms, "k": "c"}  Ctrl/Alt+Backspace (word delete)
    {"u": t_ms, "k": "m"}                     shortcut modifier released (resets flight)

Times are the browser's performance.now() in ms; features are computed in that
clock (the request carries the browser's `now`), so no clock sync is needed.

`features()` reproduces backend/telemetry_daemon.py exactly:
  * error weight per press: normal 0, Backspace 1, auto-repeat Backspace 3, Ctrl+Backspace 4
  * dwell = release - press (0..2 s), counted at release time
  * flight = release-to-release gap < 2 s; a longer gap (or a modifier release) resets it
  * keys_per_second = dwells in window / window; error_rate = sum(weights)/presses
"""
import statistics
import threading
import time

from backend.stress_engine import DEFAULT_SETTINGS, StressEngine

WINDOW_S = 5.0
MAX_EVENTS = 400
FRESH_S = 10.0          # typing older than this no longer counts as a live signal
ERR_WEIGHT = {'n': 0, 'r': 0, 'b': 1, 'rb': 3, 'c': 4}
FEATURE_KEYS = ('mean_dwell', 'std_dwell', 'mean_flight', 'std_flight', 'error_rate',
                'keys_per_second', 'flight_count', 'mouse_distance', 'mouse_clicks')


def features(events, now_ms, window_s=WINDOW_S):
    """Pure function: browser key events -> TelemetryDaemon-compatible features."""
    cutoff = now_ms - window_s * 1000.0
    presses, dwells, flights = [], [], []
    releases = []                     # (t_up, is_reset_marker)
    for e in events:
        k = e.get('k')
        if k in ERR_WEIGHT and e.get('d') is not None:
            presses.append((float(e['d']), ERR_WEIGHT[k]))
        if k in ('n', 'b', 'c') and e.get('u') is not None and e.get('d') is not None:
            dw = (float(e['u']) - float(e['d'])) / 1000.0
            if 0.0 <= dw <= 2.0:
                dwells.append((float(e['u']), dw))
        if e.get('u') is not None and k in ('n', 'b', 'c', 'm'):
            releases.append((float(e['u']), k == 'm'))

    last = None
    for t, reset in sorted(releases):
        if reset:
            last = None
            continue
        if last is not None:
            gap = (t - last) / 1000.0
            if gap < 2.0:
                flights.append((t, gap))
            else:
                last = None
        last = t

    p = [w for t, w in presses if t >= cutoff]
    d = [x for t, x in dwells if t >= cutoff]
    f = [x for t, x in flights if t >= cutoff]
    return {
        'mean_dwell': statistics.mean(d) if d else 0.0,
        'std_dwell': statistics.stdev(d) if len(d) > 1 else 0.0,
        'mean_flight': statistics.mean(f) if f else 0.0,
        'std_flight': statistics.stdev(f) if len(f) > 1 else 0.0,
        'error_rate': min(1.0, sum(p) / max(len(p), 1)),
        'keys_per_second': len(d) / window_s,
        'flight_count': len(f),
        'mouse_distance': 0.0,
        'mouse_clicks': 0,
    }


def _valid(e):
    if not isinstance(e, dict) or e.get('k') not in ('n', 'b', 'r', 'rb', 'c', 'm'):
        return False
    for key in ('d', 'u'):
        v = e.get(key)
        if v is not None and not isinstance(v, (int, float)):
            return False
    return e.get('d') is not None or e.get('u') is not None


class QueryTypingTracker:
    """Keeps the last few seconds of search-box typing and a dedicated
    StressEngine for it, calibrated with Aura's resting baseline."""

    def __init__(self, settings=None):
        self._lock = threading.Lock()
        self._events = []
        self._last_now_ms = None
        self._last_wall = 0.0
        self.engine = StressEngine(dict(settings or DEFAULT_SETTINGS))
        self.features = features([], 0.0)

    def set_baseline(self, baseline_cov, baseline_err):
        with self._lock:
            self.engine.settings['baseline_cov'] = float(baseline_cov or 0.0)
            self.engine.settings['baseline_err'] = float(baseline_err or 0.0)

    def ingest(self, events, now_ms, wall=None):
        evs = [e for e in (events or []) if _valid(e)][:MAX_EVENTS]
        with self._lock:
            # A new page load restarts performance.now(); drop the old timeline.
            if self._last_now_ms is not None and now_ms < self._last_now_ms - 1000:
                self._events = []
            self._events.extend(evs)
            keep_from = now_ms - (WINDOW_S + 2.5) * 1000.0
            self._events = [e for e in self._events
                            if max(e.get('d') or 0, e.get('u') or 0) >= keep_from][-MAX_EVENTS:]
            self._last_now_ms = now_ms
            self.features = features(self._events, now_ms)
            # Aura's engine runs at 3 Hz; reports arrive ~1 Hz, so step it 3x.
            for _ in range(3):
                self.engine.update(self.features)
            if evs:
                self._last_wall = wall if wall is not None else time.time()
            return self.snapshot(wall)

    def snapshot(self, wall=None):
        wall = wall if wall is not None else time.time()
        age = wall - self._last_wall if self._last_wall else None
        return {
            'fresh': age is not None and age <= FRESH_S,
            'age_s': round(age, 1) if age is not None else None,
            'score': round(self.engine.score, 2),
            'features': {k: (round(v, 4) if isinstance(v, float) else v)
                         for k, v in self.features.items()},
        }
