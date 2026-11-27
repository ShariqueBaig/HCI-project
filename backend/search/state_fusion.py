"""Fuse Aura's live signals into one of five interaction states.

Inputs (camera off is the default and fully supported):
  * Aura LiveState  -- calibrated system-wide stress (score/tier) from what the
    user was doing *before* opening search, plus intervention flags.
  * Query typing    -- a second StressEngine on the search box's own keystroke
    timing (backend.search.typing), only while fresh (< 10 s old).
  * Behaviour       -- rage clicks, hesitations, backtracks in the last minute.
  * Context         -- reformulations (similar consecutive queries) in 3 minutes.
  * Camera affect   -- optional, reserved for Phase 6 (valence / arousal).

Rules are deterministic and every decision carries `evidence` and per-signal
`contributions`, so the "Why this layout?" panel can explain itself. A
StateTracker adds dwell + cooldown hysteresis (ported from the webcam app's
AffectiveEngine: 3 s dwell, 5 s cooldown) so layouts never flicker.
"""
import re
import threading
import time
from collections import deque

STATES = ('focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented')

AURA_WEIGHT = 1.0
TYPING_WEIGHT = 0.6
BEHAVIOUR_WINDOW_S = 60.0
CAMERA_FRESH_S = 2.0
REFORMULATION_WINDOW_S = 180.0

_STOP = set('a an the of to in on for and or is are how what why which does do best vs '
             'under over with without about from me my i can should good top'.split())


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def query_terms(q):
    return {_stem(w) for w in re.findall(r'[a-z0-9]+', (q or '').lower()) if w not in _STOP and len(w) > 1}


def is_reformulation(prev, cur):
    """Same information need, reworded: overlapping terms but not identical."""
    a, b = query_terms(prev), query_terms(cur)
    if not a or not b or a == b:
        return False
    return len(a & b) / len(a | b) >= 0.3


class BehaviourLog:
    """Timestamps of friction events and recent queries (wall clock)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.events = deque(maxlen=200)       # (t, kind)
        self.queries = deque(maxlen=20)       # (t, query, is_reformulation)

    def add_event(self, kind, t=None):
        with self._lock:
            self.events.append((t or time.time(), kind))

    def add_query(self, query, t=None):
        t = t or time.time()
        with self._lock:
            prev = self.queries[-1][1] if self.queries else None
            ref = bool(prev) and (t - self.queries[-1][0]) <= REFORMULATION_WINDOW_S and is_reformulation(prev, query)
            self.queries.append((t, query, ref))
            return ref

    def counts_since(self, t0):
        """Friction events since t0 (e.g. since the current results appeared)."""
        with self._lock:
            ev = [k for t, k in self.events if t >= t0]
        return {'rage_clicks': ev.count('rage_click'), 'hesitations': ev.count('hesitation'),
                'backtracks': ev.count('backtrack')}

    def counts(self, now=None):
        now = now or time.time()
        with self._lock:
            ev = [k for t, k in self.events if now - t <= BEHAVIOUR_WINDOW_S]
            refs = sum(1 for t, _, r in self.queries if r and now - t <= REFORMULATION_WINDOW_S)
            trail = [q for t, q, _ in list(self.queries)[-5:]]
        return {'rage_clicks': ev.count('rage_click'), 'hesitations': ev.count('hesitation'),
                'backtracks': ev.count('backtrack'), 'reformulations': refs, 'query_trail': trail}


def fuse(live, typing=None, behaviour=None, affect=None):
    """Return the instantaneous UserStateVector (before hysteresis)."""
    behaviour = behaviour or {}
    contributions, evidence, sources = {}, [], []

    stress_parts = []
    if live:
        stress_parts.append((float(live.get('score') or 0.0), AURA_WEIGHT, 'aura'))
        contributions['aura_stress'] = round(float(live.get('score') or 0.0), 1)
        sources.append('aura')
    typing_fresh = bool(typing and typing.get('fresh'))
    tf = (typing or {}).get('features') or {}
    if typing_fresh:
        stress_parts.append((float(typing.get('score') or 0.0), TYPING_WEIGHT, 'query_typing'))
        contributions['query_typing_stress'] = round(float(typing.get('score') or 0.0), 1)
        sources.append('query_typing')
    # Optional camera (Phase 6): only a detected face with a fresh reading counts.
    cam = affect if (affect and affect.get('face') and time.time() - affect.get('ts', 0) <= CAMERA_FRESH_S) else None
    val = aro = load = None
    if cam:
        sources.append('camera')
        val, aro, load = cam['valence'], cam['arousal'], cam['cognitive_load']
        contributions['camera_valence'] = round(val, 2)
        contributions['camera_arousal'] = round(aro, 2)
    stress = (sum(s * w for s, w, _ in stress_parts) / sum(w for _, w, _ in stress_parts)) if stress_parts else None
    if stress is None and cam:
        # camera only (no Aura state yet): map arousal/load onto the stress scale
        stress = max(0.0, min(100.0, 50 * (aro + 1) * 0.5 + 50 * load))

    friction = behaviour.get('rage_clicks', 0) + behaviour.get('backtracks', 0)
    hes = behaviour.get('hesitations', 0)
    refs = behaviour.get('reformulations', 0)
    if friction:
        contributions['friction_events'] = friction
    if hes:
        contributions['hesitations'] = hes
    if refs:
        contributions['reformulations'] = refs
    kps, dwell, err = tf.get('keys_per_second', 0.0), tf.get('mean_dwell', 0.0), tf.get('error_rate', 0.0)
    if typing_fresh:
        contributions['typing_tempo_kps'] = round(kps, 2)

    tier = int((live or {}).get('tier') or 0)
    blocking = bool((live or {}).get('focus_blocking'))

    if stress is None:
        state, conf = 'focused', 0.3
        evidence.append('No live signals yet; using the default layout.')
    elif (stress >= 60 or (stress >= 45 and friction >= 2) or (tier == 2 and blocking)
          or (cam and stress >= 35 and ((val < -0.28 and aro > 0.22) or load >= 0.72))):
        state = 'overwhelmed'
        conf = 0.5 + (stress - 45) / 60 + 0.08 * friction + (0.1 if cam and val < -0.28 else 0)
        if cam and stress < 60 and ((val < -0.28 and aro > 0.22) or load >= 0.72):
            evidence.append('Your expression looks tense (camera) and stress is rising ({:.0f}/100).'.format(stress))
        if stress >= 60:
            evidence.append('Stress is high ({:.0f}/100).'.format(stress))
        if friction >= 2:
            evidence.append('Repeated rapid clicks or quick back-outs ({}).'.format(friction))
        if tier == 2 and blocking:
            evidence.append("Aura's Focus mode is holding notifications.")
    elif refs >= 2 or (hes >= 2 and stress < 60):
        state = 'disoriented'
        conf = 0.55 + 0.1 * max(refs, hes - 1)
        if refs >= 2:
            evidence.append('The query was reworded {} times in a few minutes.'.format(refs))
        if hes >= 2:
            evidence.append('Long pauses before clicking ({}).'.format(hes))
    elif ((typing_fresh and stress < 45 and 0 < kps < 1.6 and dwell > 0.14)
          or (cam and stress < 45 and val < -0.18 and aro < -0.20)):
        state = 'fatigued'
        if typing_fresh and 0 < kps < 1.6 and dwell > 0.14:
            conf = 0.55 + min(0.25, (dwell - 0.14) * 2)
            evidence.append('Slow, heavy typing ({:.1f} keys/s, {:.0f} ms per key).'.format(kps, dwell * 1000))
        else:
            conf = 0.55
        if cam and val < -0.18 and aro < -0.20:
            conf += 0.1
            evidence.append('You look tired (camera: low energy, low mood).')
    elif ((typing_fresh and stress < 30 and kps >= 4.0 and err < 0.08)
          or (cam and stress < 30 and val >= 0.32 and aro >= 0.15)):
        state = 'energized'
        if typing_fresh and kps >= 4.0 and err < 0.08:
            conf = 0.55 + min(0.3, (kps - 4.0) * 0.1)
            evidence.append('Fast, accurate typing ({:.1f} keys/s) with low stress.'.format(kps))
        else:
            conf = 0.55
        if cam and val >= 0.32 and aro >= 0.15:
            conf += 0.1
            evidence.append('You look upbeat and alert (camera).')
    else:
        state = 'focused'
        conf = 0.5 + max(0.0, (45 - stress)) / 100
        evidence.append('Stress is moderate or low ({:.0f}/100); no friction.'.format(stress))

    if (live or {}).get('breathing_active'):
        evidence.append("Aura's breathing guide is open; Search will stay quiet.")

    from backend.search.xai import explain
    xai = explain(state=state, stress=stress, tier=tier, blocking=blocking, friction=friction, hes=hes,
                  refs=refs, typing_fresh=typing_fresh, kps=kps, dwell=dwell, err=err, cam=cam,
                  val=val, aro=aro, load=load, parts=stress_parts)
    return {
        'xai': xai,
        'state': state,
        'confidence': round(max(0.0, min(0.95, conf)), 2),
        'stress': round(stress, 1) if stress is not None else None,
        'evidence': evidence,
        'contributions': contributions,
        'sources': sources,
        'quiet': bool((live or {}).get('breathing_active')),
    }


class StateTracker:
    """Dwell + cooldown hysteresis over fused vectors (one instance per server)."""

    def __init__(self, dwell_s=3.0, cooldown_s=5.0):
        self.dwell_s, self.cooldown_s = dwell_s, cooldown_s
        self._lock = threading.Lock()
        self.committed = None
        self.candidate = None
        self._candidate_since = 0.0
        self._last_commit = 0.0
        self.flickers_prevented = 0
        self.transitions = 0
        self.latest = None

    def expedite(self):
        """Skip the cooldown once (a mood simulation just started); dwell still applies."""
        with self._lock:
            self._last_commit = float('-inf')

    def update(self, vector, now=None):
        now = now if now is not None else time.time()
        with self._lock:
            s = vector['state']
            if self.committed is None:
                self.committed, self._last_commit = s, now
                self.candidate, self._candidate_since = s, now
            elif s == self.committed:
                if self.candidate != s:
                    self.flickers_prevented += 1
                self.candidate, self._candidate_since = s, now
            else:
                if s != self.candidate:
                    if self.candidate != self.committed:
                        self.flickers_prevented += 1
                    self.candidate, self._candidate_since = s, now
                dwelled = now - self._candidate_since >= self.dwell_s
                cooled = now - self._last_commit >= self.cooldown_s
                if dwelled and cooled:
                    self.committed, self._last_commit = s, now
                    self.transitions += 1
            pending = self.candidate != self.committed
            progress = min(1.0, (now - self._candidate_since) / self.dwell_s) if pending else 1.0
            self.latest = dict(vector, committed_state=self.committed,
                               candidate_state=self.candidate if pending else None,
                               dwell_progress=round(progress, 2),
                               flickers_prevented=self.flickers_prevented,
                               transitions=self.transitions)
            return self.latest
