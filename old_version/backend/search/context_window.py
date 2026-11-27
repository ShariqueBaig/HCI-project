"""Dual sliding window over the session (borrowed from AURA, Lu et al. 2026).

* DenseWindow -- the last N seconds (default 30) of fused-signal samples at the
  hub's tick rate. Used only by the anticipation policy (trends, sustain checks).
  Raw signal values never leave the server.
* TextWindow  -- the last M (default 10) *query groups*: one line per search
  with the layout it got, what the user did with it, and the state at render.
  This compact text is all the LLM ever sees of the session, so prompt size and
  latency stay bounded however long the session runs.
"""
import threading
import time
from collections import deque


class DenseWindow:
    def __init__(self, seconds=30.0):
        self.seconds = seconds
        self._lock = threading.Lock()
        self._samples = deque()          # (t, dict)

    def add(self, t, sample):
        with self._lock:
            self._samples.append((t, sample))
            while self._samples and t - self._samples[0][0] > self.seconds:
                self._samples.popleft()

    def since(self, t0):
        with self._lock:
            return [s for t, s in self._samples if t >= t0]

    def sustained(self, key, value, seconds, now=None):
        """True if every sample in the last `seconds` has sample[key] == value
        and the window actually covers that span."""
        now = now if now is not None else time.time()
        with self._lock:
            recent = [(t, s) for t, s in self._samples if now - t <= seconds]
            if not recent or now - recent[0][0] < seconds * 0.8:
                return False
            return all(s.get(key) == value for _, s in recent)

    def trend(self, key, seconds, now=None):
        """Last minus first value of `key` over the span (None if too few samples)."""
        now = now if now is not None else time.time()
        with self._lock:
            vals = [s.get(key) for t, s in self._samples if now - t <= seconds and s.get(key) is not None]
        return (vals[-1] - vals[0]) if len(vals) >= 2 else None


class TextWindow:
    def __init__(self, max_groups=10):
        self._lock = threading.Lock()
        self._groups = deque(maxlen=max_groups)

    def add_search(self, search_id, query, policy, widgets, state, reformulation):
        with self._lock:
            self._groups.append({'search_id': search_id, 'query': query, 'policy': policy,
                                 'widgets': list(widgets), 'state': state,
                                 'reformulation': bool(reformulation), 'events': []})

    def add_event(self, search_id, event):
        with self._lock:
            for g in reversed(self._groups):
                if g['search_id'] == search_id:
                    if len(g['events']) < 8:
                        g['events'].append(event)
                    return

    def lines(self, exclude=None):
        """One short line per earlier search -- what the composer is told."""
        with self._lock:
            groups = [g for g in self._groups if g['search_id'] != exclude]
        out = []
        for g in groups:
            line = '"{}" -> {} layout ({})'.format(g['query'][:80], g['policy'], ', '.join(g['widgets'][:5]))
            if g['reformulation']:
                line += '; reworded previous search'
            if g['events']:
                line += '; user: ' + ', '.join(g['events'])
            out.append(line)
        return out

    def __len__(self):
        with self._lock:
            return len(self._groups)
