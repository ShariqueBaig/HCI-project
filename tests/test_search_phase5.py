"""Phase 5 tests for Aura Search: consent v4, search records in Aura's research
store, study tasks, questionnaires, exports, and a full mock trial.

All research I/O is redirected to a temporary folder -- the real data/ folder is
never touched.

Run:  python -m unittest discover -s tests -v
"""
import csv
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend import research
from backend.study_metrics import compute_iso_metrics, compute_sus, stress_sam_alignment

TOKEN = 't'


class TempResearchDir:
    """Point backend.research at a throwaway folder for one test."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix='aura_research_')
        self.saved = {k: getattr(research, k) for k in ('DATA_ROOT', 'CONSENT_FILE', 'SALT_FILE', 'SESSIONS_DIR')}
        research.DATA_ROOT = os.path.join(self.dir, 'data')
        research.CONSENT_FILE = os.path.join(research.DATA_ROOT, 'consent.json')
        research.SALT_FILE = os.path.join(research.DATA_ROOT, '.salt')
        research.SESSIONS_DIR = os.path.join(research.DATA_ROOT, 'sessions')
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(research, k, v)
        shutil.rmtree(self.dir, ignore_errors=True)


def read_csv(path):
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


class MetricsTests(unittest.TestCase):
    def test_sus(self):
        self.assertEqual(compute_sus([5, 1] * 5), 100.0)
        self.assertEqual(compute_sus([3] * 10), 50.0)
        with self.assertRaises(ValueError):
            compute_sus([3] * 9)

    def test_iso_and_alignment(self):
        eff, effect = compute_iso_metrics(True, 100, 0, 45, 8, 0)
        self.assertEqual((eff, effect), (100.0, 100.0))
        self.assertLess(compute_iso_metrics(False, 100, 0, 180, 20, 2)[0], 50)
        self.assertEqual(stress_sam_alignment(0, 1), 100.0)


class ConsentTests(unittest.TestCase):
    def test_v3_consent_no_longer_valid(self):
        with TempResearchDir():
            os.makedirs(research.DATA_ROOT)
            research._write_json(research.CONSENT_FILE, {'granted': True, 'version': '3.0'})
            self.assertFalse(research.consent_status()['granted'])
            with self.assertRaises(PermissionError):
                research.ResearchCollector('P1')
            research.give_consent('P1')
            self.assertTrue(research.consent_status()['granted'])
            self.assertIn('Aura Search', research.CONSENT_TEXT)

    def test_hashed_queries_when_opted_out(self):
        with TempResearchDir():
            research.give_consent('P2', store_queries=False)
            c = research.ResearchCollector('P2')
            c.log_search({'search_id': 'x', 'query': 'my private worry about exams'})
            c.end({})
            with open(c.session_path, encoding='utf-8') as f:
                text = f.read()
            self.assertNotIn('worry', text)
            self.assertIn('query_hash', text)
            self.assertTrue(research.verify_session(c.session_path)[0])

    def test_search_record_whitelist(self):
        with TempResearchDir():
            research.give_consent('P3')
            c = research.ResearchCollector('P3')
            c.log_search({'search_id': 'x', 'query': 'q', 'query_typing': {'keys_per_second': 3, 'secret': 9},
                          'evil_field': 'should not be stored', 'source_domains': ['a.com']})
            c.log_search_event('keystroke_dump', 'x')          # unknown kind -> dropped
            c.log_survey('task', 't1', {'success': 4, 'note': 'free text in answers'}, {'x': 1})
            c.end({})
            with open(c.session_path, encoding='utf-8') as f:
                recs = [json.loads(l) for l in f]
            s = next(r for r in recs if r['type'] == 'search')
            self.assertNotIn('evil_field', s)
            self.assertEqual(s['query_typing'], {'keys_per_second': 3.0})
            self.assertFalse(any(r['type'] == 'search_event' for r in recs))
            sv = next(r for r in recs if r['type'] == 'survey')
            self.assertNotIn('note', sv['answers'])                # strings are not accepted as answers

    def test_mood_simulation_is_logged(self):
        with TempResearchDir():
            research.give_consent('P5')
            c = research.ResearchCollector('P5')
            c.log_search_event('mood_sim_start', None, 'fatigued')
            c.log_search_event('mood_sim_stop')
            c.end({})
            with open(c.session_path, encoding='utf-8') as f:
                ev = [json.loads(l) for l in f]
            ev = [(r['kind'], r['target']) for r in ev if r['type'] == 'search_event']
            self.assertEqual(ev, [('mood_sim_start', 'fatigued'), ('mood_sim_stop', None)])

    def test_concurrent_writers_keep_chain_valid(self):
        with TempResearchDir():
            research.give_consent('P4')
            c = research.ResearchCollector('P4')

            def ticks():
                for i in range(200):
                    c.log_tick(i / 3, 20, 0, {'keys_per_second': 1})

            def searches():
                for i in range(100):
                    c.log_search_event('proposal', 's{}'.format(i), 'overwhelmed')
            ts = [threading.Thread(target=ticks), threading.Thread(target=searches)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            c.end({})
            ok, msg = research.verify_session(c.session_path)
            self.assertTrue(ok, msg)
            self.assertIn('302 records', msg)                      # header + 200 + 100 + summary

    def test_writes_after_close_are_ignored(self):
        with TempResearchDir():
            research.give_consent('P5')
            c = research.ResearchCollector('P5')
            c.end({})
            c.log_search({'search_id': 'late', 'query': 'q'})
            self.assertTrue(research.verify_session(c.session_path)[0])
            with open(c.session_path, encoding='utf-8') as f:
                self.assertNotIn('late', f.read())


class DamagedLogTests(unittest.TestCase):
    def test_half_written_line_does_not_break_search_export(self):
        with TempResearchDir() as tmp:
            research.give_consent('P6')
            c = research.ResearchCollector('P6')
            c.log_search({'search_id': 's1', 'query': 'q'})
            c.end({})
            with open(c.session_path, 'a', encoding='utf-8') as f:
                f.write('{"type": "search", "half-writ')            # force-quit mid-line
            self.assertFalse(research.verify_session(c.session_path)[0])   # still flagged
            out = research.export_dataset(os.path.join(tmp.dir, 'exports'))
            self.assertEqual(out['searches_rows'], 1)
            self.assertEqual(out['sessions'], 1)


class MockTrialTests(unittest.TestCase):
    """The Phase 5 acceptance test: consent -> Record -> 3 tasks -> surveys -> Journal."""

    def test_full_mock_trial(self):
        from backend.firebase_sync import FirebaseSync
        from backend.search import anticipation as ant
        from backend.search.composer import Composer
        from backend.search.hub import StateHub
        from backend.search.live_state import LiveStateStore, build_snapshot
        from backend.search.providers import FixtureProvider, ProviderChain
        from backend.search.research_bridge import ResearchBridge
        from backend.search.server import create_app
        from backend.search.synthesis import StageA

        with TempResearchDir() as tmp:
            fx_dir = os.path.join(tmp.dir, 'fixtures')
            os.makedirs(fx_dir)
            tasks = {
                'ssd-vs-hdd': ('solid state drive vs hard disk drive', 'Compare: choose storage for a laptop',
                               [('SSD', 'SSDs are fast, have no moving parts and cost more per gigabyte.'),
                                ('HDD', 'Hard disk drives use spinning platters and offer large cheap capacity.')]),
                'caffeine': ('how does caffeine affect sleep', 'Explain: how caffeine changes sleep',
                             [('Caffeine', 'Caffeine blocks adenosine receptors and delays sleep onset.'),
                              ('Sleep', 'Caffeine late in the day reduces deep sleep in adults.')]),
                'compost': ('how to start composting at home', 'How-to: list the steps to begin composting',
                            [('Compost', 'Collect kitchen scraps. Add dry brown material. Keep the pile moist.'),
                             ('Home composting', 'Turn the pile every few days so it gets air.')]),
            }
            for tid, (q, task, srcs) in tasks.items():
                with open(os.path.join(fx_dir, tid + '.json'), 'w', encoding='utf-8') as f:
                    json.dump({'query': q, 'task': task, 'sources': [
                        {'id': '', 'title': t, 'url': 'https://example.org/' + t.replace(' ', '_'),
                         'snippet': c[:60], 'content': c, 'published': '', 'provider': 'wikipedia'}
                        for t, c in srcs]}, f)

            # 1. consent (Aura's Privacy dialog) and 2. Record session
            research.give_consent('P42')
            collector = research.ResearchCollector('P42', condition='intervention')
            for i in range(30):                                  # Aura's own 3 Hz ticks
                collector.log_tick(i / 3, 20 + i, 0 if i < 20 else 1, {'keys_per_second': 2.0})

            class NoTavily:
                available = False

            class NoWiki:
                def search(self, q, k=5):
                    raise AssertionError('study tasks must use recorded sources')

            store = LiveStateStore()
            store.set(build_snapshot(score=20, tier=0, features={}, condition='intervention', calibrated=True,
                                     recording=True))
            hub = StateHub(store)
            bridge = ResearchBridge(lambda: collector)
            client = TestClient(create_app(store, TOKEN, ui_dist=None,
                                           chain=ProviderChain(FixtureProvider([fx_dir]), NoTavily(), NoWiki()),
                                           stage_a=StageA(None), hub=hub, composer=Composer(None), research=bridge))
            h = {'X-Aura-Token': TOKEN}

            study = client.get('/api/study', headers=h).json()
            self.assertTrue(study['recording'])
            self.assertEqual(len(study['tasks']), 3)
            self.assertEqual(len(study['sus_items']), 10)

            saved = (ant.READ_GRACE_S, ant.SUSTAIN_S)
            ant.READ_GRACE_S, ant.SUSTAIN_S = 0.0, 0.0
            try:
                # 3. three tasks, each searched in the participant's own words
                wordings = {'ssd-vs-hdd': ['ssd or hdd for my laptop', 'which is better ssd hdd'],
                            'caffeine': ['does coffee ruin sleep'],
                            'compost': ['composting for beginners']}
                for tid, queries in wordings.items():
                    r = client.post('/api/study/task/start', json={'task_id': tid}, headers=h)
                    self.assertEqual(r.status_code, 200, r.text)
                    for q in queries:
                        d = client.post('/api/search', json={'query': q}, headers=h).json()
                        self.assertEqual(d['provider'], 'fixture')
                        self.assertEqual(d['task_id'], tid)
                    if tid == 'ssd-vs-hdd':
                        client.post('/api/behavior', json={'type': 'backtrack'}, headers=h)
                        # stress rises and stays -> one offer -> accept
                        store.set(build_snapshot(score=85, tier=2, features={}, condition='intervention',
                                                 calibrated=True, recording=True))
                        base = time.time()
                        snap = None
                        for i in range(1, 12):
                            snap = hub.tick(now=base + i)
                        p = snap['anticipation']['proposal']
                        self.assertIsNotNone(p)
                        client.post('/api/search/{}/proposal'.format(d['search_id']),
                                    json={'proposal_id': p['id'], 'action': 'accept'}, headers=h)
                        store.set(build_snapshot(score=20, tier=0, features={}, condition='intervention',
                                                 calibrated=True, recording=True))
                    end = client.post('/api/study/task/end', headers=h).json()['task']
                    self.assertEqual(end['searches'], len(queries))
                    sv = client.post('/api/study/survey', headers=h, json={
                        'kind': 'task', 'task_id': tid, 'answer_text': 'my answer for ' + tid,
                        'answers': {'completed': True, 'success': 4, 'sam_valence': 6, 'sam_arousal': 4,
                                    'sam_dominance': 6, 'tlx_mental': 3, 'tlx_frustration': 2,
                                    'tlx_effort': 3, 'personalization': 6, 'control': 5, 'trust': 6}}).json()
                    self.assertTrue(sv['recorded'])
                    self.assertIn('efficiency', sv['scores'])
            finally:
                ant.READ_GRACE_S, ant.SUSTAIN_S = saved

            sus = client.post('/api/study/survey', headers=h,
                              json={'kind': 'sus', 'answers': {'sus_items': [4, 2, 4, 2, 4, 2, 4, 2, 4, 2]}}).json()
            self.assertEqual(sus['scores']['sus'], 75.0)
            bad = client.post('/api/study/survey', headers=h, json={'kind': 'sus', 'answers': {'sus_items': [4]}})
            self.assertEqual(bad.status_code, 422)

            # 4. Journal (Aura's Save entry) ends the session
            collector.set_journal('felt rushed on the second task', 'You noticed the pressure.')
            collector.set_self_report(stress=5, valence=6)
            summary = collector.end({'duration_s': 600, 'avg': 30, 'peak': 85, 'tier_s': [400, 150, 50]})

            # 5. integrity + exports
            ok, msg = research.verify_session(collector.session_path)
            self.assertTrue(ok, msg)
            agg = summary['search']
            self.assertEqual((agg['searches'], agg['tasks'], agg['surveys']), (4, 3, 4))
            self.assertEqual((agg['offers'], agg['accepted']), (1, 1))
            self.assertEqual(agg['sus_mean'], 75.0)

            out = research.export_dataset(os.path.join(tmp.dir, 'exports'))
            self.assertEqual((out['sessions'], out['ticks']), (1, 30))
            searches = read_csv(out['searches_csv'])
            self.assertEqual(len(searches), 4)
            self.assertEqual({r['task_id'] for r in searches}, set(tasks))
            self.assertEqual(searches[0]['query'], 'ssd or hdd for my laptop')
            self.assertTrue(all(r['provider'] == 'fixture' for r in searches))
            self.assertEqual(searches[1]['reformulation'], 'True')
            events = read_csv(out['search_events_csv'])
            kinds = [e['kind'] for e in events]
            for k in ('backtrack', 'proposal', 'accept'):
                self.assertIn(k, kinds)
            accept = next(e for e in events if e['kind'] == 'accept')
            self.assertEqual((accept['target'], accept['from']), ('overwhelmed', 'focused'))
            task_rows = read_csv(out['tasks_csv'])
            self.assertEqual([r['event'] for r in task_rows], ['start', 'end'] * 3)
            surveys = read_csv(out['surveys_csv'])
            self.assertEqual([r['kind'] for r in surveys], ['task'] * 3 + ['sus'])
            self.assertEqual(surveys[-1]['sus'], '75.0')
            self.assertEqual(surveys[0]['sam_valence'], '6.0')
            # every search shows only facts from its own Stage A
            for r in searches:
                self.assertGreater(int(r['n_claims_shown']), 0)
                self.assertLessEqual(int(r['n_claims_shown']), int(r['n_claims']))

            # 6. cloud document: aggregates only, never the searches themselves
            header, ticks, summ = research._read_session(collector.session_path)
            doc = FirebaseSync.__new__(FirebaseSync)
            doc._uid = 'test-uid'                              # no network sign-in in tests
            body = json.dumps(doc.build_document(header, ticks, summ))
            self.assertIn('"search_searches": 4', body)
            for secret in ('ssd or hdd', 'coffee', 'my answer for'):
                self.assertNotIn(secret, body)


class NotRecordingTests(unittest.TestCase):
    def test_nothing_written_without_a_recording(self):
        from backend.search.research_bridge import ResearchBridge
        with TempResearchDir():
            b = ResearchBridge(lambda: None)
            self.assertFalse(b.recording)
            b.record_event('proposal', 's1', 'overwhelmed')
            self.assertEqual(b.record_survey('sus', {'sus_items': [3] * 10})['sus'], 50.0)
            self.assertFalse(os.path.exists(research.SESSIONS_DIR))


if __name__ == '__main__':
    unittest.main()
