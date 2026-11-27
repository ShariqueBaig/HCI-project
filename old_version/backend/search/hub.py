"""StateHub: the one place where search-side state advances.

A single ticker (2 Hz) fuses Aura's live state + query typing + behaviour into
a committed interaction state and its policy. HTTP and WebSocket readers only
read the cached result -- reading never advances dwell timers or EMAs (the
webcam app's AffectiveEngine advanced on every read, so timing depended on how
many tabs were open).
"""
import threading
import time

from backend.search.anticipation import Anticipator
from backend.search.context_window import DenseWindow, TextWindow
from backend.search.policy import policy_for
from backend.search.state_fusion import BehaviourLog, StateTracker, fuse
from backend.search.typing import QueryTypingTracker

TICK_S = 0.5

# Mood simulation: synthetic *inputs* that make the real fusion rules predict each
# mood, so the XAI panel shows the model reasoning, not a hard-coded label.
SIM_PROFILES = {
    'overwhelmed': {'score': 82.0, 'tier': 2},
    'focused':     {'score': 35.0, 'tier': 1},
    'fatigued':    {'score': 25.0, 'tier': 0,
                    'typing': {'keys_per_second': 1.1, 'mean_dwell': 0.21, 'error_rate': 0.04}},
    'energized':   {'score': 15.0, 'tier': 0,
                    'typing': {'keys_per_second': 5.2, 'mean_dwell': 0.08, 'error_rate': 0.02}},
    'disoriented': {'score': 40.0, 'tier': 1, 'behaviour': {'reformulations': 2, 'hesitations': 2}},
}
SIM_MAX_S = 300.0


class StateHub:
    def __init__(self, store, dwell_s=3.0, cooldown_s=5.0):
        self.store = store
        self.typing = QueryTypingTracker()
        self.behaviour = BehaviourLog()
        self.tracker = StateTracker(dwell_s=dwell_s, cooldown_s=cooldown_s)
        self.dense = DenseWindow(30.0)
        self.text = TextWindow(10)
        self.anticipator = Anticipator()
        self.camera = None            # backend.vision.sensor.CameraSensor, created on first enable
        self._lock = threading.Lock()
        self._latest = None
        self.version = 0
        self._stop = threading.Event()
        self._thread = None
        self._sim = None              # {'state', 'started', 'until'} while a mood is simulated

    # ------------------------------------------------------- simulation --
    def simulate(self, state, duration_s=45.0, now=None):
        """Start (state) or stop (None) a mood simulation. Returns its status."""
        now = now if now is not None else time.time()
        with self._lock:
            if state is None:
                self._sim = None
            else:
                if state not in SIM_PROFILES:
                    raise ValueError('unknown mood: {}'.format(state))
                d = max(5.0, min(SIM_MAX_S, float(duration_s)))
                self._sim = {'state': state, 'started': now, 'until': now + d}
        if state is not None:
            self.tracker.expedite()
        self.tick(now)
        return self.simulation_status(now)

    def simulation_status(self, now=None):
        now = now if now is not None else time.time()
        with self._lock:
            sim = self._sim
            if sim and now >= sim['until']:
                self._sim = sim = None
        if not sim:
            return None
        return {'state': sim['state'], 'remaining_s': round(sim['until'] - now, 1),
                'inputs': SIM_PROFILES[sim['state']]}

    @staticmethod
    def _apply_sim(state, live, typing, beh):
        prof = SIM_PROFILES[state]
        live = dict(live or {}, score=prof['score'], tier=prof['tier'],
                    focus_blocking=prof['tier'] == 2 and bool((live or {}).get('focus_blocking')),
                    breathing_active=False)
        if 'typing' in prof:
            typing = {'fresh': True, 'age_s': 0.0, 'score': prof['score'], 'features': dict(prof['typing'])}
        else:
            typing = dict(typing or {}, fresh=False)
        beh = dict(beh, rage_clicks=0, backtracks=0, hesitations=0, reformulations=0)
        beh.update(prof.get('behaviour', {}))
        return live, typing, beh

    def tick(self, now=None):
        now = now if now is not None else time.time()
        live = self.store.get()
        if live:
            self.typing.set_baseline(live.get('baseline_cov'), live.get('baseline_err'))
        typing = self.typing.snapshot(now)
        beh = self.behaviour.counts(now)
        affect = self.camera.latest() if (self.camera and self.camera.active) else None
        sim = self.simulation_status(now)
        f_live, f_typing, f_beh = live, typing, beh
        if sim:
            f_live, f_typing, f_beh = self._apply_sim(sim['state'], live, typing, beh)
            affect = None
        fused = fuse(f_live, f_typing, f_beh, affect)
        if sim:
            fused['sources'] = ['simulation']
            fused['evidence'] = ['Simulated mood: {} ({:.0f} s left).'.format(
                sim['state'], sim['remaining_s'])] + fused['evidence']
        vec = self.tracker.update(fused, now)
        condition = (live or {}).get('condition')
        policy = policy_for(vec['committed_state'], condition)
        adaptive = condition != 'control'
        self.dense.add(now, {'committed': vec['committed_state'], 'state': vec['state'],
                             'stress': vec['stress']})
        view = self.anticipator.snapshot()['view']
        since = self.anticipator.view['rendered_at'] if view else now
        antic = self.anticipator.decide(vec, adaptive, self.behaviour.counts_since(since),
                                        self.dense, now)
        out = {
            'fused': vec,
            'adaptive': adaptive,
            'anticipation': antic,
            'policy': policy,
            'typing': typing,
            'camera': {'active': bool(self.camera and self.camera.active),
                       'face': bool(affect and affect.get('face'))},
            'behaviour': {k: v for k, v in beh.items() if k != 'query_trail'},
            'query_trail': beh['query_trail'],
            'simulation': sim,
        }
        with self._lock:
            self._latest = out
            self.version += 1
        return out

    def on_search(self, search_id, query, policy, widgets, state, reformulation, now=None):
        """A new results page is on screen: reset the anticipation view, log the group."""
        self.text.add_search(search_id, query, policy, widgets, state, reformulation)
        self.anticipator.set_view(search_id, policy, reformulation, now)

    def current(self):
        with self._lock:
            latest = self._latest
        return latest if latest is not None else self.tick()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:          # never let the ticker die silently
                print('[Aura Search] state tick failed:', e)
            self._stop.wait(TICK_S)

    def start(self):
        if not self._thread:
            self._thread = threading.Thread(target=self._run, name='aura-search-state', daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()
