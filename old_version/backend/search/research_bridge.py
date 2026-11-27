"""Bridge from Aura Search into Aura's own research recorder.

Aura owns recording: the Privacy (consent) and "Record session" controls in the
desktop window create a research.ResearchCollector. The search server only
*writes into that collector* through `get_collector()`; with no active,
consented recording, nothing is written anywhere. All records go into the same
hash-chained session file as Aura's stress ticks, so one session = one file.

Study tasks: while a task is active, every search in it uses that task's
recorded sources (FixtureProvider), whatever words the participant types, so
participants see the same evidence (reproducibility) but still type their own
queries (the typing signal).
"""
import threading
import time

from backend.study_metrics import compute_iso_metrics, compute_sus

SUS_LEN = 10


class ResearchBridge:
    def __init__(self, get_collector=None):
        self._get = get_collector or (lambda: None)
        self._lock = threading.Lock()
        self.task = None          # {'id', 'task', 'started', 'searches', 'clicks', 'rage'}

    # -------------------------------------------------------------- state --
    def collector(self):
        c = self._get()
        return c if (c is not None and not getattr(c, 'closed', False)) else None

    @property
    def recording(self):
        return self.collector() is not None

    def status(self):
        with self._lock:
            t = dict(self.task) if self.task else None
        if t:
            t['elapsed_s'] = round(time.time() - t['started'], 1)
        return {'recording': self.recording, 'task': t}

    # --------------------------------------------------------------- tasks --
    def start_task(self, task_id, task_text):
        with self._lock:
            if self.task:
                self._end_locked('abandon')
            self.task = {'id': task_id, 'task': task_text, 'started': time.time(),
                         'searches': 0, 'rage': 0}
        c = self.collector()
        if c:
            c.log_task('start', task_id, task_text)
        return self.status()

    def end_task(self):
        with self._lock:
            return self._end_locked('end')

    def _end_locked(self, event):
        t = self.task
        if not t:
            return None
        self.task = None
        duration = round(time.time() - t['started'], 1)
        c = self.collector()
        if c:
            c.log_task(event, t['id'], t['task'], duration_s=duration, searches=t['searches'])
        return dict(t, duration_s=duration)

    def active_task_id(self):
        with self._lock:
            return self.task['id'] if self.task else None

    # ------------------------------------------------------------- records --
    def record_search(self, rec, spec, snap):
        with self._lock:
            if self.task:
                self.task['searches'] += 1
            task_id = self.task['id'] if self.task else None
        c = self.collector()
        if not c:
            return
        fused = (snap or {}).get('fused') or {}
        typing = (snap or {}).get('typing') or {}
        report = spec.get('report') or {}
        domains = []
        for s in rec.get('sources', []):
            d = (s.get('url') or '').split('/')[2:3]
            if d and d[0] not in domains:
                domains.append(d[0].replace('www.', ''))
        c.log_search({
            'search_id': rec['search_id'], 'task_id': task_id, 'query': rec['query'],
            'condition': rec.get('condition'), 'adaptive': rec.get('adaptive'),
            'policy': (rec.get('policy') or {}).get('name'), 'state': fused.get('committed_state'),
            'confidence': fused.get('confidence'), 'stress': fused.get('stress'),
            'camera': 'camera' in (fused.get('sources') or []),
            'camera_valence': (fused.get('contributions') or {}).get('camera_valence'),
            'camera_arousal': (fused.get('contributions') or {}).get('camera_arousal'),
            'reformulation': rec.get('reformulation'), 'query_uncertain': rec.get('query_uncertain'),
            'query_typing': (typing.get('features') or {}) if typing.get('fresh') else {},
            'provider': rec.get('provider'), 'source_domains': domains,
            'n_claims': len(rec['stageA'].get('claims', [])), 'claims_shown': spec.get('claims_shown'),
            'widgets': [w['type'] for w in spec.get('components', [])], 'topology': spec.get('topology'),
            'layout_source': spec.get('source'), 'model_facts': rec['stageA'].get('model'),
            'model_layout': spec.get('model'), 'ungrounded_removed': report.get('ungrounded_before_fix'),
            'evaluative_cells': report.get('evaluative_cells'), 'timings_ms': rec.get('timings_ms'),
        })

    def record_event(self, kind, search_id=None, target=None, origin=None, reason=None, latency_s=None):
        if kind == 'rage_click':
            with self._lock:
                if self.task:
                    self.task['rage'] += 1
        c = self.collector()
        if c:
            c.log_search_event(kind, search_id, target, origin, reason, latency_s)

    def record_anticipation(self, entry):
        """Listener for Anticipator decisions (proposal/accept/dismiss/undo/...)."""
        self.record_event(entry.get('kind'), entry.get('search_id'), entry.get('target'),
                          entry.get('from'), entry.get('reason'), entry.get('latency_s'))

    # ------------------------------------------------------------- surveys --
    def record_survey(self, kind, answers, task_id=None, answer_text='', task_stats=None):
        """Score and store a questionnaire. Returns the computed scores."""
        scores = {}
        if kind == 'sus':
            items = answers.get('sus_items') or []
            if len(items) != SUS_LEN:
                raise ValueError('SUS needs 10 answers')
            scores['sus'] = compute_sus(items)
        elif kind == 'task' and task_stats:
            eff, effect = compute_iso_metrics(
                completed=bool(answers.get('completed')),
                task_accuracy=float(answers.get('success', 3) - 1) * 25.0,     # 1..5 -> 0..100
                error_count=0, time_sec=task_stats.get('duration_s', 0),
                clicks=max(1, task_stats.get('searches', 1)), rage_clicks=task_stats.get('rage', 0))
            scores.update(efficiency=eff, effectiveness=effect)
        c = self.collector()
        if c:
            c.log_survey(kind, task_id, answers, scores, answer_text)
        return scores
