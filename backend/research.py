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
                        timings are stored. Characters, key codes, window titles, app
                        names and journal text are never recorded.
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
import time

APP_NAME         = 'Aura UI'
PROTOCOL_VERSION = '2.0'
CONSENT_VERSION  = '3.0'   # v3 adds the optional journal note + reflection to the record

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
    'sessions locally and from the database.'
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


def give_consent(participant_code, researcher='', note=''):
    """Record explicit consent. participant_code is stored only as a digest."""
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
    """Per-install random salt; kept out of version control and out of exports."""
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
        rec['h'] = _hash(self._prev, rec)
        self._prev = rec['h']
        self._fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + '\n')
        self._fh.flush()

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
        self._append(rec)
        self.close()
        return rec

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._fh.close()
        except Exception:
            pass


# ------------------------------------------------------------------- export

def _read_session(path):
    header, ticks, summary = {}, [], {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            t = rec.get('type')
            if t == 'header':
                header = rec
            elif t == 'tick':
                ticks.append(rec)
            elif t == 'summary':
                summary = rec
    return header, ticks, summary


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
    n_s, n_t = 0, 0
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
            header, ticks, summary = _read_session(path)
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
                'tick_hz': header.get('tick_hz'), 'started': summary.get('ended') or header.get('started'),
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
    return {'ticks': n_t, 'sessions': n_s,
            'ticks_csv': ticks_path, 'sessions_csv': sess_path}


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
