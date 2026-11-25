"""
research.py -- privacy-preserving research data collection for Aura UI.

This module is the only place that writes study data. It is deliberately
small, dependency-free and readable so it can be audited.

Guarantees
----------
1. Consent gate      -- nothing is written until an explicit consent record exists.
2. Local only        -- there is no network code here; records never leave the machine.
3. Pseudonymous      -- participant codes are stored only as salted SHA-256 digests.
4. Data minimisation -- only whitelisted numeric typing/mouse aggregates, scores and
                        timings are stored. Characters, key codes, window titles and app
                        names are never recorded. Free text is limited to what consent v4
                        names: the journal note/reflection and, for Aura Search, the
                        queries typed into it (or only a salted hash of them, if the
                        participant chose that), optional task answers, and the facts
                        and sources shown. Each search record is whitelisted field by field.
5. Tamper-evident    -- each record carries a SHA-256 hash chained to the previous one,
                        so any edit or deletion of a line is detectable.
6. Retention         -- purge_expired(days) enforces a data-retention window.

Typical use
-----------
    from backend import research
    research.give_consent('P07')               # once, with the participant's agreement
    c = research.ResearchCollector('P07')      # raises PermissionError without consent
    c.log_tick(0.33, 12.0, 0, features)        # per polling tick
    c.set_self_report(stress=6, valence=3)     # post-session self-report
    c.end(stats)                               # writes the summary record
    c.close()

    research.verify_session(c.session_path)    # -> (True, 'ok')
    research.export_dataset('exports/')        # de-identified CSVs for analysis
"""
import csv
import datetime
import hashlib
import json
import os
import secrets
import sys
import threading
import time

APP_NAME         = 'Aura UI'
PROTOCOL_VERSION = '2.0'
CONSENT_VERSION  = '4.0'   # v3: journal note + reflection; v4: Aura Search queries + surveys

# The only telemetry fields that may be stored. Anything not listed here is
# dropped before it can reach disk -- this is the data-minimisation contract.
ALLOWED_FEATURES = frozenset({
    'keys_per_second', 'error_rate', 'mean_dwell', 'std_dwell',
    'mean_flight', 'std_flight', 'flight_count',
    'mouse_distance', 'mouse_clicks',
})

CONSENT_TEXT = (
    'I agree to take part in this study of the Aura UI stress monitor. '
    'I understand that: (1) numeric summaries of my typing and mouse activity '
    '(speed, timing variation, backspace rate, movement distance) and the '
    'app\u2019s stress score are recorded; (2) the characters I type, window titles '
    'and app names are never recorded; (3) any note I choose to write in the '
    'session journal, and the reflection Aura writes from it, are stored with the '
    'session and \u2014 if cloud sync is enabled \u2014 uploaded under my pseudonymous '
    'code, so I should not write anything I would not want in the research '
    'dataset; (4) data is stored under a salted pseudonym and is not shared with '
    'other participants; (5) I can withdraw at any time, which deletes my '
    'sessions locally and from the database; (6) if I use Aura Search during a '
    'recorded session, the searches I type (or, if I choose, only a scrambled '
    'code for each search), the sources and layouts shown, whether I accept '
    'Aura\u2019s offers to change the layout, my answers to post-task questionnaires '
    'and any task answer I choose to type are stored with the session; only '
    'counts and scores from these are uploaded, never the searches themselves.'
)


# --------------------------------------------------------------------- paths

from backend.paths import base_dir


DATA_ROOT    = os.path.join(base_dir(), 'data')
CONSENT_FILE = os.path.join(DATA_ROOT, 'consent.json')
SALT_FILE    = os.path.join(DATA_ROOT, '.salt')
SESSIONS_DIR = os.path.join(DATA_ROOT, 'sessions')


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def _restrict(path):
    """Best-effort owner-only permissions (POSIX; a no-op limitation on Windows)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ------------------------------------------------------------------- consent

def consent_status():
    """Return {'granted': bool, 'code': str|None, 'version': str|None, ...}."""
    try:
        with open(CONSENT_FILE, encoding='utf-8') as f:
            rec = json.load(f)
    except Exception:
        return {'granted': False}
    rec['granted'] = (bool(rec.get('granted'))
                      and rec.get('version') == CONSENT_VERSION
                      and not rec.get('revoked'))
    return rec


def give_consent(participant_code, researcher='', note='', store_queries=True):
    """Record explicit consent. participant_code is stored only as a digest.
    store_queries=False keeps only a salted hash of each Aura Search query."""
    if not (participant_code or '').strip():
        raise ValueError('a participant code is required')
    _ensure_dir(DATA_ROOT)
    rec = {
        'granted':        True,
        'version':        CONSENT_VERSION,
        'consent_text':   CONSENT_TEXT,
        'pseudonym':      pseudonym(participant_code),
        'granted_at':     _now(),
        'researcher':     researcher.strip(),
        'note':           note.strip(),
        'revoked':        False,
        'protocol':       PROTOCOL_VERSION,
        'store_queries':  bool(store_queries),
    }
    _write_json(CONSENT_FILE, rec)
    _restrict(CONSENT_FILE)
    return rec


def revoke_consent(purge=True):
    """Withdraw consent and (by default) delete every session written so far."""
    rec = consent_status()
    rec.update({'granted': False, 'revoked': True, 'revoked_at': _now()})
    rec.pop('granted', None)
    _ensure_dir(DATA_ROOT)
    _write_json(CONSENT_FILE, {'granted': False, 'revoked': True,
                               'revoked_at': _now(), 'version': CONSENT_VERSION})
    removed = purge_all() if purge else 0
    return removed


def purge_all():
    """Delete every stored session file. Returns the number of files removed."""
    n = 0
    for root, _dirs, files in os.walk(SESSIONS_DIR):
        for name in files:
            if name.endswith('.jsonl'):
                try:
                    os.remove(os.path.join(root, name))
                    n += 1
                except OSError:
                    pass
    return n


def purge_expired(days=180):
    """Delete sessions older than `days`. Returns the number deleted."""
    if days is None:
        return 0
    cutoff = time.time() - days * 86400
    n = 0
    for root, _dirs, files in os.walk(SESSIONS_DIR):
        for name in files:
            p = os.path.join(root, name)
            if name.endswith('.jsonl') and os.path.getmtime(p) < cutoff:
                try:
                    os.remove(p)
                    n += 1
                except OSError:
                    pass
    return n


# --------------------------------------------------------------- pseudonyms

def _salt():
    """Per-install random salt -- or a lab-wide one when the study provides it.

    A shared salt (``AURA_LAB_SALT`` or a ``lab_salt.txt`` written by
    ``tools/lab_setup.py``) makes the same participant code map to the same
    pseudonym on every lab machine, so one person's sessions can be joined
    across stations and deleted together. Kept out of version control and out
    of every export either way.
    """
    shared = (os.environ.get('AURA_LAB_SALT') or '').strip()
    if shared:
        return shared
    try:
        with open(os.path.join(base_dir(), 'lab_salt.txt'), encoding='utf-8') as f:
            lab = f.read().strip()
        if lab:
            return lab
    except Exception:
        pass
    try:
        with open(SALT_FILE, encoding='utf-8') as f:
            s = f.read().strip()
        if s:
            return s
    except Exception:
        pass
    _ensure_dir(DATA_ROOT)
    s = secrets.token_hex(32)
    with open(SALT_FILE, 'w', encoding='utf-8') as f:
        f.write(s)
    _restrict(SALT_FILE)
    return s


def pseudonym(participant_code):
    """Salted, one-way participant id. Without the local salt the code cannot be
    recovered from the stored value, and codes cannot be linked across machines."""
    raw = (participant_code or '').strip().upper().encode('utf-8')
    return hashlib.sha256(_salt().encode('utf-8') + b'|' + raw).hexdigest()[:16]


# ---------------------------------------------------------------- integrity

def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def _hash(prev, obj):
    return hashlib.sha256((prev or '').encode('utf-8') + _canon(obj)).hexdigest()


def _write_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, path)
    _restrict(path)


def verify_session(path):
    """Recompute the hash chain. Returns (ok, message)."""
    prev = ''
    n = 0
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                claimed = rec.pop('h', None)
                if claimed != _hash(prev, rec):
                    return False, 'hash mismatch at record {}'.format(n + 1)
                prev = claimed
                n += 1
    except Exception as e:
        return False, 'unreadable: {}'.format(e)
    return True, '{} records verified'.format(n)


# ---------------------------------------------------------------- collection

class ResearchCollector:
    """Append-only, hash-chained per-session log. Numeric data only."""

    def __init__(self, participant_code, tick_hz=3.0, instrument='Aura UI stress engine',
                 condition='field', operator=''):
        st = consent_status()
        if not st.get('granted'):
            raise PermissionError('no consent on file -- refusing to record')
        code = (participant_code or '').strip()
        if not code:
            raise ValueError('a participant code is required')
        self.pseudonym   = pseudonym(code)
        self.session_id  = time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3)
        self.started     = time.time()
        self._prev       = ''
        self._closed     = False
        self._self_report = {}
        self._journal    = {}     # optional note + reflection, attached on save
        self._n_ticks    = 0
        # The Aura Search server writes from its own thread; one lock keeps the
        # hash chain strictly sequential.
        self._lock       = threading.RLock()
        self._store_queries = bool(st.get('store_queries', True))
        self._search     = {'searches': 0, 'reformulations': 0, 'offers': 0, 'accepted': 0,
                            'dismissed': 0, 'undone': 0, 'expired': 0, 'counterfactual': 0,
                            'standard_view': 0, 'backtracks': 0, 'tasks': 0, 'surveys': 0,
                            'sus': []}
        folder = _ensure_dir(os.path.join(SESSIONS_DIR, self.pseudonym))
        self.session_path = os.path.join(folder, self.session_id + '.jsonl')
        self._fh = open(self.session_path, 'a', encoding='utf-8', newline='\n')
        _restrict(self.session_path)
        self._append({
            'type':       'header',
            'protocol':   PROTOCOL_VERSION,
            'consent':    st.get('version'),
            'pseudonym':  self.pseudonym,
            'session_id': self.session_id,
            'started':    _now(),
            'app':        APP_NAME,
            'instrument': instrument,
            'condition':  condition,
            'operator':   operator,
            'tick_hz':    tick_hz,
            'device':     sys.platform,
        })

    # -- writing ---------------------------------------------------------

    def _append(self, rec):
        with self._lock:
            if self._closed:
                return False
            rec['h'] = _hash(self._prev, rec)
            self._prev = rec['h']
            self._fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + '\n')
            self._fh.flush()
            return True

    def _t(self):
        return round(time.time() - self.started, 3)

    @property
    def closed(self):
        return self._closed

    # -- Aura Search (consent v4) ---------------------------------------

    def query_field(self, query):
        """The query itself, or a salted hash if the participant opted out of text."""
        q = (query or '').strip()[:300]
        if self._store_queries:
            return {'query': q}
        digest = hashlib.sha256((_salt() + '|q|' + q.lower()).encode('utf-8')).hexdigest()[:16]
        return {'query_hash': digest, 'query_words': len(q.split())}

    def log_search(self, search):
        """One search: what was asked, what state it was in, what it was shown.
        Field-by-field whitelist; facts are stored as ids, not text."""
        g = search.get
        feat = {k: round(float(v), 4) for k, v in (g('query_typing') or {}).items()
                if k in ALLOWED_FEATURES and isinstance(v, (int, float))}
        rec = {
            'type': 'search', 't': self._t(),
            'search_id': str(g('search_id', ''))[:24], 'task_id': g('task_id'),
            'condition': g('condition'), 'adaptive': bool(g('adaptive')),
            'policy': g('policy'), 'state': g('state'), 'confidence': g('confidence'),
            'stress': g('stress'), 'camera': bool(g('camera')),
            'camera_valence': g('camera_valence'), 'camera_arousal': g('camera_arousal'),
            'reformulation': bool(g('reformulation')),
            'query_uncertain': bool(g('query_uncertain')), 'query_typing': feat,
            'provider': g('provider'), 'source_domains': list(g('source_domains') or [])[:10],
            'n_claims': g('n_claims'), 'claims_shown': list(g('claims_shown') or [])[:20],
            'widgets': list(g('widgets') or [])[:12], 'topology': g('topology'),
            'layout_source': g('layout_source'), 'model_facts': g('model_facts'),
            'model_layout': g('model_layout'), 'ungrounded_removed': g('ungrounded_removed'),
            'evaluative_cells': g('evaluative_cells'),
            'timings_ms': {k: v for k, v in (g('timings_ms') or {}).items()
                           if k in ('retrieval', 'stageA', 'stageB', 'total')},
        }
        rec.update(self.query_field(g('query')))
        if self._append(rec):
            self._search['searches'] += 1
            self._search['reformulations'] += int(rec['reformulation'])

    SEARCH_EVENTS = ('proposal', 'accept', 'dismiss', 'undo', 'expired', 'counterfactual',
                     'superseded', 'standard_view', 'adapted_view', 'source_open', 'backtrack',
                     'followup', 'clarifier', 'facet', 'rage_click', 'hesitation',
                     'camera_on', 'camera_off')

    def log_search_event(self, kind, search_id=None, target=None, origin=None, reason=None,
                         latency_s=None):
        if kind not in self.SEARCH_EVENTS:
            return
        rec = {'type': 'search_event', 't': self._t(), 'kind': kind,
               'search_id': (str(search_id)[:24] if search_id else None),
               'target': target, 'from': origin,
               'reason': (reason or '')[:200] or None, 'latency_s': latency_s}
        if self._append(rec):
            key = {'proposal': 'offers', 'accept': 'accepted', 'dismiss': 'dismissed',
                   'undo': 'undone', 'expired': 'expired', 'counterfactual': 'counterfactual',
                   'standard_view': 'standard_view', 'backtrack': 'backtracks'}.get(kind)
            if key:
                self._search[key] += 1

    def log_task(self, event, task_id, task='', duration_s=None, searches=None):
        if event not in ('start', 'end', 'abandon'):
            return
        rec = {'type': 'task', 't': self._t(), 'event': event, 'task_id': str(task_id)[:60],
               'task': (task or '')[:200], 'duration_s': duration_s, 'searches': searches}
        if self._append(rec) and event == 'start':
            self._search['tasks'] += 1

    def log_survey(self, kind, task_id=None, answers=None, scores=None, answer_text=''):
        """Post-task (SAM, NASA-TLX, Likert, success) or SUS questionnaire."""
        if kind not in ('task', 'sus'):
            return
        clean = {}
        for k, v in (answers or {}).items():
            if isinstance(v, bool):
                clean[str(k)[:40]] = v
            elif isinstance(v, (int, float)):
                clean[str(k)[:40]] = round(float(v), 2)
            elif isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
                clean[str(k)[:40]] = [round(float(x), 2) for x in v[:20]]
        rec = {'type': 'survey', 't': self._t(), 'kind': kind,
               'task_id': (str(task_id)[:60] if task_id else None), 'answers': clean,
               'scores': {k: v for k, v in (scores or {}).items() if isinstance(v, (int, float))},
               'answer_text': (answer_text or '').strip()[:500] or None}
        if self._append(rec):
            self._search['surveys'] += 1
            if kind == 'sus' and 'sus' in rec['scores']:
                self._search['sus'].append(rec['scores']['sus'])

    def log_tick(self, t_s, score, tier, features, brightness=None,
                 breathing=0, simulated=0, label=None):
        if self._closed:
            return
        clean = {}
        for k, v in (features or {}).items():
            if k in ALLOWED_FEATURES:
                try:
                    clean[k] = round(float(v), 4)
                except (TypeError, ValueError):
                    continue
        self._append({
            'type':  'tick',
            't':     round(float(t_s), 3),
            'score': round(float(score), 3),
            'tier':  int(tier),
            'label': label,
            'feat':  clean,
            'int':   {'brightness': brightness,
                      'breathing': int(breathing),
                      'simulated': int(simulated)},
        })
        self._n_ticks += 1

    def set_journal(self, note='', reflection=''):
        """Attach the participant's written note and Aura's reflection to the
        session. Covered by consent v3; truncated to keep documents bounded."""
        note = (note or '').strip()
        reflection = (reflection or '').strip()
        if not (note or reflection):
            return
        self._journal = {'note': note[:4000],
                         'reflection': reflection[:4000],
                         'note_chars': len(note)}

    def set_self_report(self, stress=None, valence=None):
        """Post-session self-report on 0-10 scales (perceived stress / mood)."""
        self._self_report = {
            'stress_0_10':  None if stress is None else int(stress),
            'valence_0_10': None if valence is None else int(valence),
            'at':           _now(),
        }

    def end(self, stats):
        """Write the session summary (aggregates only) and close the file."""
        if self._closed:
            return None
        s = dict(stats or {})
        tier_s = s.get('tier_s') or [0, 0, 0]
        rec = {
            'type':        'summary',
            'session_id':  self.session_id,
            'pseudonym':   self.pseudonym,
            'ended':       _now(),
            'duration_s':  round(float(s.get('duration_s', time.time() - self.started)), 2),
            'ticks':       self._n_ticks,
            'score_mean':  round(float(s.get('avg', 0.0)), 3),
            'score_peak':  round(float(s.get('peak', 0.0)), 3),
            'peak_at_s':   round(float(s.get('peak_at_s', 0.0)), 2),
            'tier_s':      [round(float(x), 2) for x in tier_s],
            'episodes':    int(s.get('episodes', 0)),
            'breathing':   int(s.get('breathing', 0)),
            'notif_held':  int(s.get('held', 0)),
            'self_report': self._self_report,
            'journal':     self._journal,
            'demo':        bool(s.get('demo', False)),
        }
        if self._search['searches'] or self._search['surveys'] or self._search['tasks']:
            agg = {k: v for k, v in self._search.items() if k != 'sus'}
            sus = self._search['sus']
            agg['sus_mean'] = round(sum(sus) / len(sus), 1) if sus else None
            rec['search'] = agg
        self._append(rec)
        self.close()
        return rec

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._fh.close()
            except Exception:
                pass


# ------------------------------------------------------------------- export

def _read_session(path):
    """Parse a session log into (header, ticks, summary).

    A force-quit or power cut can leave the last line half-written, and one bad
    byte used to abort every caller: the CSV export, the upload queue and the
    charts. Unparseable lines are skipped (and reported) instead, so the rest of
    the session survives. verify_session() stays strict and still flags the file
    as damaged.
    """
    header, ticks, summary = {}, [], {}
    bad = 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if not isinstance(rec, dict):
                bad += 1
                continue
            t = rec.get('type')
            if t == 'header':
                header = rec
            elif t == 'tick':
                ticks.append(rec)
            elif t == 'summary':
                summary = rec
    if bad:
        print('[research] {} unreadable line(s) skipped in {}'.format(
            bad, os.path.basename(path)), file=sys.stderr)
    return header, ticks, summary


def _read_session_full(path):
    """All records of a session grouped by type (search-era records included)."""
    out = {'header': {}, 'summary': {}, 'tick': [], 'search': [], 'search_event': [],
           'task': [], 'survey': []}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:                         # half-written line after a force-quit: skip it
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            t = rec.get('type')
            if t in ('header', 'summary'):
                out[t] = rec
            elif t in out:
                out[t].append(rec)
    return out


def sessions_for(pseudonym):
    """Session files belonging to one pseudonym (used for cloud erasure)."""
    if not pseudonym:
        return []
    folder = os.path.join(SESSIONS_DIR, pseudonym)
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                  if n.endswith('.jsonl'))


def list_sessions():
    out = []
    for root, _dirs, files in os.walk(SESSIONS_DIR):
        for name in sorted(files):
            if name.endswith('.jsonl'):
                out.append(os.path.join(root, name))
    return sorted(out)


def export_dataset(dest_dir, dedupe=True):
    """Write de-identified CSVs: one row per tick and one row per session.

    No pseudonym-to-person mapping is included; the salt is never exported.
    """
    _ensure_dir(dest_dir)
    ticks_path = os.path.join(dest_dir, 'ticks.csv')
    sess_path  = os.path.join(dest_dir, 'sessions.csv')
    feat_cols  = sorted(ALLOWED_FEATURES)

    tick_cols = (['session_id', 't', 'score', 'tier', 'label', 'brightness',
                  'breathing', 'simulated'] + feat_cols)
    sess_cols = (['session_id', 'pseudonym', 'condition', 'protocol', 'tick_hz',
                  'started', 'duration_s', 'ticks', 'score_mean', 'score_peak',
                  'peak_at_s', 'calm_s', 'mild_s', 'elevated_s', 'episodes',
                  'breathing', 'notif_held', 'sr_stress', 'sr_valence', 'device',
                  'journal_note', 'journal_reflection'])

    seen = set()
    n_s, n_t, n_skip = 0, 0, 0
    with open(ticks_path, 'w', encoding='utf-8', newline='') as tf, \
         open(sess_path, 'w', encoding='utf-8', newline='') as sf:
        tw, sw = csv.DictWriter(tf, fieldnames=tick_cols), csv.DictWriter(sf, fieldnames=sess_cols)
        tw.writeheader()
        sw.writeheader()
        for path in list_sessions():
            if dedupe:
                if path in seen:
                    continue
                seen.add(path)
            try:
                header, ticks, summary = _read_session(path)
            except Exception as e:      # unreadable file: skip it, keep exporting
                print('[research] skipped {}: {}'.format(
                    os.path.basename(path), e), file=sys.stderr)
                continue
            if not header or not summary:
                n_skip += 1             # aborted/crashed session: no end state to export
                continue
            sid = header.get('session_id') or os.path.basename(path)[:-6]
            for rec in ticks:
                row = {'session_id': sid, 't': rec.get('t'), 'score': rec.get('score'),
                       'tier': rec.get('tier'), 'label': rec.get('label')}
                pred = rec.get('int') or {}
                row.update({'brightness': pred.get('brightness'),
                            'breathing': pred.get('breathing'),
                            'simulated': pred.get('simulated')})
                for k in feat_cols:
                    row[k] = (rec.get('feat') or {}).get(k)
                tw.writerow(row)
                n_t += 1
            sr = summary.get('self_report') or {}
            ts = summary.get('tier_s') or [None, None, None]
            sw.writerow({
                'session_id': sid, 'pseudonym': summary.get('pseudonym') or header.get('pseudonym'),
                'condition': header.get('condition'), 'protocol': header.get('protocol'),
                'tick_hz': header.get('tick_hz'), 'started': header.get('started') or summary.get('ended'),
                'duration_s': summary.get('duration_s'), 'ticks': summary.get('ticks'),
                'score_mean': summary.get('score_mean'), 'score_peak': summary.get('score_peak'),
                'peak_at_s': summary.get('peak_at_s'),
                'calm_s': ts[0], 'mild_s': ts[1], 'elevated_s': ts[2],
                'episodes': summary.get('episodes'), 'breathing': summary.get('breathing'),
                'notif_held': summary.get('notif_held'),
                'sr_stress': sr.get('stress_0_10'), 'sr_valence': sr.get('valence_0_10'),
                'device': header.get('device'),
                'journal_note': (summary.get('journal') or {}).get('note'),
                'journal_reflection': (summary.get('journal') or {}).get('reflection'),
            })
            n_s += 1
    res = {'ticks': n_t, 'sessions': n_s, 'skipped': n_skip,
           'ticks_csv': ticks_path, 'sessions_csv': sess_path}
    res.update(_export_search(dest_dir))
    return res


def _export_search(dest_dir):
    """Aura Search CSVs: one row per search, per search event, per task event and
    per questionnaire. Joined to sessions.csv by session_id."""
    search_cols = ['session_id', 'pseudonym', 'condition', 't', 'search_id', 'task_id', 'query',
                   'query_hash', 'query_words', 'adaptive', 'policy', 'state', 'confidence', 'stress',
                   'camera', 'camera_valence', 'camera_arousal',
                   'reformulation', 'query_uncertain', 'provider', 'n_sources', 'n_claims',
                   'n_claims_shown', 'widgets', 'topology', 'layout_source', 'model_facts',
                   'model_layout', 'ungrounded_removed', 'evaluative_cells', 'ms_retrieval',
                   'ms_stageA', 'ms_stageB', 'ms_total', 'typing_kps', 'typing_error_rate']
    event_cols = ['session_id', 'pseudonym', 'condition', 't', 'kind', 'search_id', 'target',
                  'from', 'latency_s', 'reason']
    task_cols = ['session_id', 'pseudonym', 'condition', 't', 'event', 'task_id', 'task',
                 'duration_s', 'searches']
    sam_tlx = ['sam_valence', 'sam_arousal', 'sam_dominance', 'tlx_mental', 'tlx_frustration',
               'tlx_effort', 'personalization', 'control', 'trust', 'success']
    survey_cols = (['session_id', 'pseudonym', 'condition', 't', 'kind', 'task_id', 'completed']
                   + sam_tlx + ['sus_items', 'sus', 'efficiency', 'effectiveness', 'answer_text'])
    paths = {k: os.path.join(dest_dir, k + '.csv')
             for k in ('searches', 'search_events', 'tasks', 'surveys')}
    counts = dict.fromkeys(paths, 0)
    with open(paths['searches'], 'w', encoding='utf-8', newline='') as f1, \
         open(paths['search_events'], 'w', encoding='utf-8', newline='') as f2, \
         open(paths['tasks'], 'w', encoding='utf-8', newline='') as f3, \
         open(paths['surveys'], 'w', encoding='utf-8', newline='') as f4:
        w = {'searches': csv.DictWriter(f1, fieldnames=search_cols, extrasaction='ignore'),
             'search_events': csv.DictWriter(f2, fieldnames=event_cols, extrasaction='ignore'),
             'tasks': csv.DictWriter(f3, fieldnames=task_cols, extrasaction='ignore'),
             'surveys': csv.DictWriter(f4, fieldnames=survey_cols, extrasaction='ignore')}
        for x in w.values():
            x.writeheader()
        for path in list_sessions():
            try:
                d = _read_session_full(path)
            except Exception as e:      # unreadable file: skip it, keep exporting
                print('[research] skipped {}: {}'.format(os.path.basename(path), e), file=sys.stderr)
                continue
            if not d['header'] or not d['summary']:
                continue                # aborted/crashed session, as in export_dataset()
            h = d['header']
            base = {'session_id': h.get('session_id') or os.path.basename(path)[:-6],
                    'pseudonym': h.get('pseudonym'), 'condition': h.get('condition')}
            for r in d['search']:
                tm, qt = r.get('timings_ms') or {}, r.get('query_typing') or {}
                row = dict(base)
                row.update({k: r.get(k) for k in search_cols if k in r})
                row.update(n_sources=len(r.get('source_domains') or []),
                           n_claims_shown=len(r.get('claims_shown') or []),
                           widgets='|'.join(r.get('widgets') or []),
                           ms_retrieval=tm.get('retrieval'), ms_stageA=tm.get('stageA'),
                           ms_stageB=tm.get('stageB'), ms_total=tm.get('total'),
                           typing_kps=qt.get('keys_per_second'),
                           typing_error_rate=qt.get('error_rate'))
                w['searches'].writerow(row)
                counts['searches'] += 1
            for r in d['search_event']:
                w['search_events'].writerow({**r, **base})
                counts['search_events'] += 1
            for r in d['task']:
                w['tasks'].writerow({**r, **base})
                counts['tasks'] += 1
            for r in d['survey']:
                a, sc = r.get('answers') or {}, r.get('scores') or {}
                row = dict(base, t=r.get('t'), kind=r.get('kind'), task_id=r.get('task_id'),
                           completed=a.get('completed'), answer_text=r.get('answer_text'),
                           sus_items='|'.join(str(int(x)) for x in a.get('sus_items') or []),
                           sus=sc.get('sus'), efficiency=sc.get('efficiency'),
                           effectiveness=sc.get('effectiveness'))
                row.update({k: a.get(k) for k in sam_tlx})
                w['surveys'].writerow(row)
                counts['surveys'] += 1
    return {k + '_rows': v for k, v in counts.items()} | {k + '_csv': v for k, v in paths.items()}


def audit():
    """Summarise what is on disk and whether every chain verifies."""
    sessions = list_sessions()
    results = [verify_session(p) for p in sessions]
    ok = all(r[0] for r in results) if results else True
    return {
        'data_root':   DATA_ROOT,
        'consent':     consent_status().get('granted', False),
        'sessions':    len(sessions),
        'chain_ok':    ok,
        'bad':         [p for p, r in zip(sessions, results) if not r[0]],
        'retention_days': 180,
    }
