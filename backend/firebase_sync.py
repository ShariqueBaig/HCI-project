"""
firebase_sync.py -- optional upload of pseudonymous session data to Firebase.

Design
------
* Zero dependencies: urllib + json only (no firebase-admin, no SDK).
* Off unless configured: reads `firebase_config.json` (or AURA_FIREBASE_CONFIG).
  Ship that file with the app and every instance auto-connects -- the end user
  does nothing.
* Per-install identity: each instance signs in to Firebase Auth ANONYMOUSLY,
  receiving its own uid with no interaction. The refresh token is cached in
  `data/firebase_identity.json` so the uid is stable across restarts.
* Rules-bound writes: Firestore Security Rules require
  `request.resource.data.uid == request.auth.uid`, so one install can only ever
  create its own documents.
* Data minimisation: only what `backend/research.py` already recorded is
  uploaded -- numeric typing/mouse aggregates, scores, timings, a salted
  pseudonym. The salt, the participant code, journal text and any keystroke
  content are never uploaded.
* Best-effort: failures never block the app; sessions stay queued locally until
  a push succeeds.

The Web API key in the config is public by design (Firebase ships it in every
web client). It identifies the project, not a user; access is decided by the
security rules, not by possession of the key.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

from backend import paths, research

SCHEMA_VERSION   = 2   # v2 adds the journal note + reflection
SIGNUP_URL       = 'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={key}'
REFRESH_URL      = 'https://securetoken.googleapis.com/v1/token?key={key}'
FIRESTORE_URL    = ('https://firestore.googleapis.com/v1/projects/{project}'
                    '/databases/(default)/documents/{path}')
DEFAULT_COLLECTION = 'aura_sessions'
TIMEOUT          = 20
MAX_CLOUD_TICKS  = 800   # cap REST payload well under Firestore's 1 MiB document limit


def _base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_FILE   = os.path.join(_base_dir(), 'firebase_config.json')
IDENTITY_FILE = os.path.join(research.DATA_ROOT, 'firebase_identity.json')


def load_config(path=None):
    """Resolve config: explicit file -> environment -> defaults bundled in the app.

    The bundled `aura_defaults.json` is what makes a fresh download work with no
    setup: it carries the public project id + Web API key.
    """
    path = path or os.environ.get('AURA_FIREBASE_CONFIG') or CONFIG_FILE
    cfg = {}
    try:
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    if not (cfg.get('project_id') and cfg.get('api_key')):
        bundled = (paths.bundled_json('aura_defaults.json').get('firebase') or {})
        for k in ('project_id', 'api_key', 'collection'):
            if not cfg.get(k) and bundled.get(k):
                cfg[k] = bundled[k]
    for k in ('project_id', 'api_key'):
        if not cfg.get(k) and os.environ.get('AURA_FIREBASE_' + k.upper()):
            cfg[k] = os.environ['AURA_FIREBASE_' + k.upper()]
    pid = (cfg.get('project_id') or '').strip()
    key = (cfg.get('api_key') or '').strip()
    cfg['project_id'] = pid
    cfg['api_key']    = key
    cfg['collection'] = (cfg.get('collection') or DEFAULT_COLLECTION).strip() or DEFAULT_COLLECTION
    cfg['enabled'] = bool(pid and key) and not str(pid).upper().startswith('YOUR_') \
                     and not str(key).upper().startswith('YOUR_')
    return cfg


def _fs_value(v):
    """Map a Python value to a Firestore REST Value object."""
    if v is None:
        return {'nullValue': None}
    if isinstance(v, bool):
        return {'booleanValue': v}
    if isinstance(v, int):
        return {'integerValue': str(v)}
    if isinstance(v, float):
        return {'doubleValue': v}
    if isinstance(v, (list, tuple)):
        return {'arrayValue': {'values': [_fs_value(x) for x in v]}}
    if isinstance(v, dict):
        return {'mapValue': {'fields': {k: _fs_value(x) for k, x in v.items()}}}
    return {'stringValue': str(v)}


def _fs_fields(d):
    return {k: _fs_value(v) for k, v in d.items() if v is not None}


class FirebaseSync:
    """Push locally recorded sessions to Cloud Firestore."""

    def __init__(self, config_path=None, identity_path=None, opener=None):
        self.config    = load_config(config_path)
        self.enabled   = self.config['enabled']
        self.identity_path = identity_path or IDENTITY_FILE
        self._opener   = opener or urllib.request.urlopen
        self._uid      = None
        self._token    = None
        self._expires  = 0.0
        self.status    = 'disabled' if not self.enabled else 'ready'
        self.last_error = ''          # most recent upload failure, shown in the UI
        self.last_success = None      # epoch seconds of the last confirmed write

    # ---------------------------------------------------------------- identity

    def _request(self, url, payload=None, headers=None, method=None):
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method or ('POST' if data else 'GET'))
        req.add_header('Content-Type', 'application/json')
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with self._opener(req, timeout=TIMEOUT) as r:
            body = r.read().decode('utf-8')
        return json.loads(body or '{}')

    def _load_identity(self):
        try:
            with open(self.identity_path, encoding='utf-8') as f:
                rec = json.load(f)
            if rec.get('api_key_fingerprint') != self.config['api_key'][-6:]:
                return None           # different project -- start a fresh identity
            return rec
        except Exception:
            return None

    def _save_identity(self, uid, refresh_token):
        os.makedirs(os.path.dirname(self.identity_path), exist_ok=True)
        tmp = self.identity_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'uid': uid, 'refresh_token': refresh_token,
                       'api_key_fingerprint': self.config['api_key'][-6:]}, f)
        os.replace(tmp, self.identity_path)
        try:
            os.chmod(self.identity_path, 0o600)
        except OSError:
            pass

    def token(self):
        """Return a valid ID token, signing in anonymously on first use."""
        if not self.enabled:
            raise RuntimeError('firebase sync is not configured')
        if self._token and time.time() < self._expires - 60:
            return self._token

        ident = self._load_identity()
        if ident and ident.get('refresh_token'):
            try:
                res = self._request(
                    REFRESH_URL.format(key=self.config['api_key']),
                    {'grant_type': 'refresh_token', 'refresh_token': ident['refresh_token']})
                self._token   = res['id_token']
                self._expires = time.time() + float(res.get('expires_in', 3600))
                self._uid     = res.get('user_id') or ident.get('uid')
                self._save_identity(self._uid, res.get('refresh_token', ident['refresh_token']))
                self.status = 'connected'
                return self._token
            except Exception as e:
                self.status = 'refresh failed: {}'.format(e)

        # Anonymous sign-in: one uid per install, no user interaction.
        res = self._request(SIGNUP_URL.format(key=self.config['api_key']),
                            {'returnSecureToken': True})
        self._token   = res['idToken']
        self._expires = time.time() + float(res.get('expiresIn', 3600))
        self._uid     = res['localId']
        self._save_identity(self._uid, res.get('refreshToken', ''))
        self.status = 'connected'
        return self._token

    @property
    def uid(self):
        if self._uid is None:
            self.token()
        return self._uid

    # ----------------------------------------------------------------- writing

    def build_document(self, header, ticks, summary):
        """Assemble the Firestore document body from already-recorded records."""
        h, s = header or {}, summary or {}
        sr = s.get('self_report') or {}
        jr = s.get('journal') or {}
        tier_s = s.get('tier_s') or [None, None, None]
        doc = {
            'schema_version': SCHEMA_VERSION,
            'app':            h.get('app'),
            'protocol':       h.get('protocol'),
            'consent_version': h.get('consent'),
            'session_id':     h.get('session_id'),
            'pseudonym':      h.get('pseudonym'),
            'condition':      h.get('condition'),
            'tick_hz':        h.get('tick_hz'),
            'started':        h.get('started'),
            'ended':          s.get('ended'),
            'device':         h.get('device'),
            'uid':            self.uid,
            'uploaded_at':    time.strftime('%Y-%m-%dT%H:%M:%S'),
            'duration_s':     s.get('duration_s'),
            'tick_count':     s.get('ticks'),
            'score_mean':     s.get('score_mean'),
            'score_peak':     s.get('score_peak'),
            'peak_at_s':      s.get('peak_at_s'),
            'calm_s':         tier_s[0],
            'mild_s':         tier_s[1],
            'elevated_s':     tier_s[2],
            'episodes':       s.get('episodes'),
            'breathing':      s.get('breathing'),
            'notif_held':     s.get('notif_held'),
            'sr_stress':      sr.get('stress_0_10'),
            'sr_valence':     sr.get('valence_0_10'),
            # Consent v3: the participant's own note and Aura's reflection.
            'journal_note':       jr.get('note'),
            'journal_reflection': jr.get('reflection'),
            'journal_note_chars': jr.get('note_chars'),
        }
        # Tick stream: numeric fields only, capped so long sessions stay < 1 MiB.
        # Local .jsonl files retain all 3 Hz ticks untouched.
        n_ticks = len(ticks)
        if n_ticks > MAX_CLOUD_TICKS:
            peak_idx = max(range(n_ticks), key=lambda i: float(ticks[i].get('score') or 0.0))
            idxs = {int(i * (n_ticks - 1) / (MAX_CLOUD_TICKS - 2)) for i in range(MAX_CLOUD_TICKS - 1)}
            idxs.update((0, n_ticks - 1, peak_idx))
            selected = [ticks[i] for i in sorted(idxs)]
            doc['tick_stride']  = round(n_ticks / len(selected), 3)
        else:
            selected = ticks
            doc['tick_stride']  = 1.0
        doc['tick_sampled'] = len(selected)

        stream = []
        for rec in selected:
            feat = rec.get('feat') or {}
            iface = rec.get('int') or {}
            stream.append({
                't':        rec.get('t'),
                'score':    rec.get('score'),
                'tier':     rec.get('tier'),
                'label':    rec.get('label'),
                'kps':      feat.get('keys_per_second'),
                'err':      feat.get('error_rate'),
                'dwell':    feat.get('mean_dwell'),
                'flight':   feat.get('mean_flight'),
                'cov':      (feat['std_flight'] / feat['mean_flight']
                             if feat.get('mean_flight') else None),
                'mouse':    feat.get('mouse_distance'),
                'clicks':   feat.get('mouse_clicks'),
                'bright':   iface.get('brightness'),
                'breath':   iface.get('breathing'),
            })
        doc['tick_data'] = stream
        return doc

    def push_session(self, path):
        """Upload one session file. Returns (ok, message)."""
        if not self.enabled:
            return False, 'disabled'
        # Everything, including the auth/sign-in attempt and document assembly,
        # is inside the guard: this method must never raise into the app.
        try:
            header, ticks, summary = research._read_session(path)
            if not header or not summary:
                return False, 'incomplete session (no summary yet)'
            doc_id = '{}_{}'.format(header.get('pseudonym') or 'unknown',
                                    header.get('session_id') or os.path.basename(path)[:-6])
            doc_id = ''.join(c for c in doc_id if c.isalnum() or c in '-_')
            body = self.build_document(header, ticks, summary)
            # Flag a damaged log (e.g. a torn line from a crash) instead of
            # uploading it as if it were intact.
            body['chain_ok'] = research.verify_session(path)[0]
            # Create on the COLLECTION, with the id in documentId. Putting the id in
            # both the path and the query is rejected with HTTP 400 by Firestore.
            url = FIRESTORE_URL.format(project=self.config['project_id'],
                                       path=self.config['collection'])
            url += '?documentId={}'.format(doc_id)
            self._request(url, {'fields': _fs_fields(body)},
                          headers={'Authorization': 'Bearer ' + self.token()})
        except urllib.error.HTTPError as e:
            if e.code == 409:                 # already uploaded -- treat as success
                self._mark(path)
                return True, 'already present'
            detail = ''
            try:
                detail = (json.loads(e.read().decode('utf-8'))
                          .get('error', {}).get('message', '') or '')
            except Exception:
                pass
            self.last_error = 'HTTP {}{}'.format(
                e.code, ' - ' + detail[:120] if detail else '')
            return False, 'HTTP {}{}'.format(e.code, ' - ' + detail[:200] if detail else '')
        except Exception as e:
            return False, str(e)
        self._mark(path)
        return True, 'ok'

    # ------------------------------------------------------------------ queue

    @staticmethod
    def _marker(path):
        return path + '.synced'

    def _mark(self, path):
        try:
            with open(self._marker(path), 'w', encoding='utf-8') as f:
                f.write(str(int(time.time())))
        except OSError:
            pass

    @staticmethod
    def _finalised(path):
        """True when the session ended and wrote its summary line.

        A session left behind by a force-quit or crash has no summary and can
        never be uploaded, so leaving it in the queue would show a permanent
        upload error. Cheap tail check - the summary is always the last line.
        """
        try:
            with open(path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 4096))
                return b'"summary"' in f.read()
        except OSError:
            return False

    def pending(self):
        return [p for p in research.list_sessions()
                if not os.path.exists(self._marker(p)) and self._finalised(p)]

    def push_pending(self, limit=None):
        """Upload every session not yet marked as synced. Never raises."""
        if not self.enabled:
            return {'uploaded': 0, 'failed': 0, 'skipped': 'disabled'}
        done = failed = 0
        errors = []
        for path in self.pending()[:limit or None]:
            ok, msg = self.push_session(path)
            if ok:
                done += 1
            else:
                failed += 1
                errors.append(msg)
                self.status = 'upload failed: ' + msg
        if failed:
            self.last_error = errors[0] if errors else self.last_error
        else:
            self.last_error = ''
        if done:
            self.status = 'connected · {} synced'.format(done)
            self.last_success = time.time()
        return {'uploaded': done, 'failed': failed, 'errors': errors[:3]}

    # ------------------------------------------------------------------ status

    def status_line(self):
        if not self.enabled:
            return 'cloud sync off (no firebase_config.json)'
        line = 'cloud sync {} · {} queued'.format(self.status, len(self.pending()))
        if self.last_error:
            line += ' · last error: {}'.format(self.last_error[:60])
        return line

    # ------------------------------------------------------------- erasure

    def delete_participant(self, pseudonym):
        """Erase this participant's uploaded documents from Firestore.

        Only documents whose IDs can be derived from the local session files are
        targeted, and the security rules additionally require
        `resource.data.uid == request.auth.uid`, so this install can erase only
        what it uploaded -- never another install's data.

        Returns {'deleted': n, 'failed': n, 'errors': [...]}. Never raises.
        """
        out = {'deleted': 0, 'failed': 0, 'errors': []}
        if not self.enabled or not pseudonym:
            return out
        for path in research.sessions_for(pseudonym):
            try:
                header, _ticks, _summary = research._read_session(path)
                sid = header.get('session_id') or os.path.basename(path)[:-6]
                doc_id = '{}_{}'.format(pseudonym, sid)
                doc_id = ''.join(c for c in doc_id if c.isalnum() or c in '-_')
                url = FIRESTORE_URL.format(
                    project=self.config['project_id'],
                    path='{}/{}'.format(self.config['collection'], doc_id))
                self._request(url, method='DELETE',
                              headers={'Authorization': 'Bearer ' + self.token()})
                out['deleted'] += 1
            except urllib.error.HTTPError as e:
                if e.code == 404:          # already gone -- erasure satisfied
                    out['deleted'] += 1
                    continue
                detail = ''
                try:
                    detail = (json.loads(e.read().decode('utf-8'))
                              .get('error', {}).get('message', '') or '')
                except Exception:
                    pass
                out['failed'] += 1
                out['errors'].append('HTTP {}{}'.format(
                    e.code, ' - ' + detail[:80] if detail else ''))
            except Exception as e:
                out['failed'] += 1
                out['errors'].append(str(e)[:80])
        if out['failed']:
            self.last_error = 'erase failed: ' + out['errors'][0]
        return out


# ---------------------------------------------------------------------- CLI
def _main(argv=None):
    """python -m backend.firebase_sync [--check] [--push] [--config PATH]"""
    import argparse
    ap = argparse.ArgumentParser(
        prog='python -m backend.firebase_sync',
        description='Verify the Firebase connection or push queued sessions.')
    ap.add_argument('--config', help='path to firebase_config.json')
    ap.add_argument('--check', action='store_true',
                    help='verify config + anonymous sign-in (no data written)')
    ap.add_argument('--push', action='store_true', help='upload every pending session')
    a = ap.parse_args(argv)

    s = FirebaseSync(a.config)
    print('config     :', a.config or CONFIG_FILE)
    print('project    :', s.config['project_id'] or '(missing)')
    print('collection :', s.config['collection'])
    print('enabled    :', s.enabled)
    if not s.enabled:
        print('\nSync is off. Copy firebase_config.example.json -> firebase_config.json, '
              'fill in project_id + api_key, then re-run. See FIREBASE_SETUP.md.')
        return 2
    print('pending    :', len(s.pending()))
    try:
        print('uid        :', s.uid)
        print('status     :', s.status)
    except Exception as e:
        print('sign-in failed:', e)
        print('Check: project_id, api_key, and that Anonymous sign-in is enabled.')
        return 1
    if a.push:
        print('push       :', s.push_pending())
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
