#!/usr/bin/env python3
"""lab_setup.py -- set up Aura UI stations for a multi-participant lab study.

Why this exists
---------------
A lab session has to be correct, every time, on several machines:

  * one **lab-wide salt**, so the same participant code maps to the same
    pseudonym on every station (otherwise the same person is two records);
  * consent + participant code pre-seeded, so a participant sits down and only
    has to press Record;
  * no leftovers from the previous participant (journal, Spotify login);
  * proof that the station really reaches Firestore before the clock starts.

Usage (from the project folder, or next to AuraUI.exe)
    python tools/lab_setup.py salt-init            # ONCE per lab, then copy lab_salt.txt everywhere
    python tools/lab_setup.py status               # is this station ready?
    python tools/lab_setup.py check                # is it NAMED and does it reach the database? (real write test)
    python tools/lab_setup.py prepare --code P01   # before each participant
    python tools/lab_setup.py verify               # after the session: did it upload?
    python tools/lab_setup.py reset                # between participants

Exit codes: 0 ok, 1 problem (see message), 2 usage error.
"""
import argparse
import json
import os
import secrets
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend import journal, research                      # noqa: E402
from backend import firebase_sync                           # noqa: E402
from backend.paths import base_dir                          # noqa: E402

DATA_DIR    = base_dir()
SALT_FILE   = os.path.join(DATA_DIR, 'lab_salt.txt')
SETTINGS    = os.path.join(DATA_DIR, 'settings.json')
SPOTIFY_CACHE = os.path.join(DATA_DIR, '.cache')
DEFAULT_SETTINGS = {'participant_code': '', 'study_condition': 'intervention'}

DB_ENDPOINT = ('https://firestore.googleapis.com/v1/projects/{project}'
               '/databases/(default)/documents/{collection}')
DB_CONSOLE  = 'https://console.firebase.google.com/project/{project}/firestore'


# --------------------------------------------------------------------- helpers

def ok(msg):   print('  [ok]   ' + msg)
def warn(msg): print('  [warn] ' + msg)
def bad(msg):  print('  [FAIL] ' + msg)


def load_settings():
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS, encoding='utf-8') as f:
            data.update(json.load(f))
    except Exception:
        pass
    return data


def save_settings(data):
    tmp = SETTINGS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, SETTINGS)


def lab_salt():
    """Read the shared salt, if this station has one yet."""
    try:
        with open(SALT_FILE, encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return ''


def sync():
    return firebase_sync.FirebaseSync()


def clear_spotify_login():
    for p in (SPOTIFY_CACHE,):
        try:
            os.remove(p)
            return True
        except OSError:
            pass
    return False


def session_rows():
    rows = []
    for path in research.list_sessions():
        try:
            _h, ticks, summary = research._read_session(path)
        except Exception:
            ticks, summary = [], {}
        rows.append((path, len(ticks), bool(summary),
                     os.path.exists(path + '.synced')))
    return rows


# ------------------------------------------------------------------- commands

def cmd_salt_init(args):
    print('Lab salt')
    existing = lab_salt()
    if existing and not args.force:
        ok('already present: ' + SALT_FILE)
        print('\nCopy this file to the same place on every station.')
        return 0
    os.makedirs(DATA_DIR, exist_ok=True)
    salt = secrets.token_hex(32)
    with open(SALT_FILE, 'w', encoding='utf-8') as f:
        f.write(salt)
    try:
        os.chmod(SALT_FILE, 0o600)
    except OSError:
        pass
    ok('written: ' + SALT_FILE)
    print('\n  COPY lab_salt.txt TO EVERY STATION (same folder as AuraUI.exe / project root).')
    print('  Without it each machine invents its own salt and the same participant')
    print('  code becomes a DIFFERENT pseudonym on each machine.')
    return 0


def cmd_status(args):
    print('Aura UI lab station')
    print('  data dir   :', DATA_DIR)
    salt = lab_salt()
    print('  lab salt   :', 'shared (' + SALT_FILE + ')' if salt
          else 'NOT SET - run: python tools/lab_setup.py salt-init')

    st = research.consent_status()
    print('  consent    :', 'granted ' + st.get('granted_at', '') if st.get('granted') else 'NOT GRANTED')
    code = (load_settings().get('participant_code') or '').strip()
    print('  participant:', code or '(none - set with "prepare --code ...")')
    print('  condition  :', load_settings().get('study_condition'))
    if code:
        print('  pseudonym  :', research.pseudonym(code))

    s = sync()
    print('  firebase   :', s.config['project_id'] or '(none)', '/', s.config['collection'],
          '| enabled' if s.enabled else '| DISABLED')
    if s.enabled:
        try:
            print('  station uid:', s.uid)
            print('  pending    :', len(s.pending()), 'session(s) waiting to upload')
        except Exception as e:
            bad('sign-in failed: {}'.format(e))
            print('           -> check internet, api_key and Anonymous sign-in')
    try:
        from backend.spotify_controller import SpotifyController
        sp = SpotifyController()
        print('  spotify    :', 'configured' if sp.configured else 'not configured',
              '|', 'connected' if sp.connected else 'not linked')
    except Exception as e:
        warn('spotify check failed: {}'.format(e))
    try:
        from backend.os_controller import OSController
        print('  audio      :', 'system volume via ' + OSController().volume_backend)
    except Exception as e:
        warn('audio check failed: {}'.format(e))
    return 0


def cmd_check(args):
    """Answer the two questions that ruin a session if they are wrong:

      * is this station NAMED (participant code, consent, pseudonym)?
      * does it actually reach the database (a real write, not a ping)?
    """
    settings = load_settings()
    code = (settings.get('participant_code') or '').strip()
    st = research.consent_status()
    salt = lab_salt()
    named = True

    print('Station name')
    if not salt:
        bad('no lab_salt.txt - this station invents its own salt, so its '
            'pseudonyms will not match the other machines')
        named = False
    else:
        ok('shared lab salt: ' + SALT_FILE)
    if code:
        ok('participant code: ' + code)
        ok('pseudonym: ' + research.pseudonym(code))
    else:
        bad('no participant code - run: python tools/lab_setup.py prepare --code P01')
        named = False
    if st.get('granted'):
        ok('consent on file ({}), pseudonym {}'.format(st.get('granted_at', ''),
                                                       st.get('pseudonym', '?')))
        if code and st.get('pseudonym') != research.pseudonym(code):
            bad('consent pseudonym does not match this code - re-run prepare')
            named = False
    else:
        bad('consent NOT on file - run: python tools/lab_setup.py prepare --code ...')
        named = False
    print('  condition  :', settings.get('study_condition'))
    try:
        from backend.os_controller import OSController
        o = OSController()
        if o.volume_available:
            ok('audio: Windows system volume via ' + o.volume_backend)
        else:
            warn('audio: no system volume ({}) - install pycaw on Windows'.format(o.volume_backend))
    except Exception as e:
        warn('audio check failed: {}'.format(e))

    print('\nDatabase')
    s = sync()
    cfg = s.config
    print('  service    : Firebase Cloud Firestore (REST API, Anonymous sign-in)')
    print('  project    :', cfg['project_id'] or '(none)')
    print('  collection :', cfg['collection'])
    if cfg['project_id']:
        print('  console    :', DB_CONSOLE.format(project=cfg['project_id']))
    if not s.enabled:
        bad('cloud sync is DISABLED - sessions stay on this machine only')
        return 1
    try:
        print('  station uid:', s.uid)
    except Exception as e:
        bad('anonymous sign-in failed: {}'.format(e))
        print('           -> check internet, api_key and that Anonymous sign-in is enabled')
        return 1
    wrote, msg = s.probe()
    if wrote:
        ok('write test: ' + msg)
    else:
        bad('write test: ' + msg)
        print('           -> usually unpublished Firestore rules or no internet')
    try:
        print('  pending    :', len(s.pending()), 'session(s) waiting to upload')
    except Exception:
        pass

    rows = sorted(session_rows(), key=lambda r: os.path.getmtime(r[0]), reverse=True)[:5]
    print('\nSessions recorded on this station')
    if not rows:
        print('  (none yet)')
    for path, n_ticks, finished, synced in rows:
        name = os.path.basename(os.path.dirname(path)) or '?'
        state = ('named, uploaded' if synced else
                 ('named, NOT uploaded' if finished else 'named, unfinished'))
        print('  {}  {:>6} ticks  {}'.format(name, n_ticks, state))

    if named and wrote:
        print('\n[ok] this station is named and can write to Firestore')
        return 0
    print('\n[FAIL] fix the items marked above before the participant arrives')
    return 1


def cmd_prepare(args):
    print('Preparing station for participant', args.code)
    code = args.code.strip().upper()
    if not code:
        bad('empty participant code')
        return 2

    salt = lab_salt()
    if not salt:
        warn('no lab_salt.txt - creating one for this machine')
        cmd_salt_init(argparse.Namespace(force=False))
        warn('remember to copy lab_salt.txt to the other stations')

    # Refuse to walk over sessions that never reached the database.
    s = sync()
    if s.enabled:
        try:
            pending = s.pending()
        except Exception as e:
            warn('could not reach Firestore: {}'.format(e))
            pending = []
        if pending:
            bad('{} session(s) still waiting to upload'.format(len(pending)))
            for p in pending[:5]:
                print('           ' + os.path.basename(p))
            if not args.force:
                print('\n  Run: python tools/lab_setup.py verify')
                print('  (or re-run with --force to prepare anyway)')
                return 1

    # Previous participant's leftovers.
    removed_cache = clear_spotify_login()
    try:
        if os.path.exists(journal.JOURNAL_FILE):
            os.remove(journal.JOURNAL_FILE)
            journal_cleared = True
        else:
            journal_cleared = False
    except OSError:
        journal_cleared = False
    ok('cleared previous journal' if journal_cleared else 'journal already empty')
    ok('forgot previous Spotify login' if removed_cache else 'no Spotify login to clear')

    try:
        research.give_consent(code, note='lab station prepared')
        ok('consent on file for ' + code)
    except Exception as e:
        bad('could not write consent: {}'.format(e))
        return 1

    settings = load_settings()
    settings['participant_code'] = code
    settings['study_condition'] = args.condition
    save_settings(settings)
    ok('settings: participant {} · condition {}'.format(code, args.condition))

    pseudo = research.pseudonym(code)
    print('\n  pseudonym  :', pseudo)
    if s.enabled and not args.skip_sync_check:
        try:
            print('  station uid:', s.uid, '(anonymous, per station)')
            ok('Firestore reachable')
        except Exception as e:
            bad('Firestore check failed: {}'.format(e))
            return 1
    print('\n  Hand the machine over. Participant checklist:')
    print('    1. Launch Aura UI.')
    print('    2. Tick "Record session" when the task starts.')
    print('    3. Windows system volume is already the audio path - only link')
    print('       Spotify if this participant asked to and the account is allowlisted.')
    print('    4. Finish: Journal -> ratings -> Save entry.')
    print('    5. Then run: python tools/lab_setup.py verify')
    return 0


def cmd_verify(args):
    print('Verifying upload queue for', DATA_DIR)
    rows = session_rows()
    if not rows:
        warn('no sessions recorded on this station yet')
    for path, n_ticks, finished, synced in rows:
        state = 'uploaded' if synced else ('finished, NOT uploaded' if finished
                                           else 'INCOMPLETE (no summary)')
        print('  {:<44} {:>6} ticks  {}'.format(os.path.basename(path), n_ticks, state))

    s = sync()
    if not s.enabled:
        bad('cloud sync is disabled - sessions stay local only')
        return 1
    try:
        pending = s.pending()
        print('\n  station uid:', s.uid)
        print('  pending    :', len(pending))
    except Exception as e:
        bad('could not reach Firestore: {}'.format(e))
        return 1
    if pending:
        bad('{} session(s) not uploaded yet'.format(len(pending)))
        print('  Retry: python -m backend.firebase_sync --push')
        return 1
    ok('every finished session is in Firestore')
    return 0


def cmd_reset(args):
    print('Resetting station between participants')
    settings = load_settings()
    settings['participant_code'] = ''
    save_settings(settings)
    ok('participant code cleared')
    ok('Spotify login forgotten' if clear_spotify_login() else 'no Spotify login to clear')
    try:
        os.remove(journal.JOURNAL_FILE)
        ok('journal cleared')
    except OSError:
        ok('journal already empty')
    if args.wipe_sessions:
        n = 0
        for path in research.list_sessions():
            try:
                os.remove(path)
                n += 1
                for extra in (path + '.synced',):
                    try:
                        os.remove(extra)
                    except OSError:
                        pass
            except OSError:
                pass
        ok('{} local session file(s) deleted'.format(n))
    else:
        ok('session archive kept ({} file(s))'.format(len(research.list_sessions())))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='lab_setup.py',
        description='Prepare and check Aura UI stations for a lab study.')
    sub = ap.add_subparsers(dest='cmd')

    p = sub.add_parser('salt-init', help='create the shared lab salt (run once, copy to all stations)')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_salt_init)

    p = sub.add_parser('status', help='show whether this station is ready')
    p.set_defaults(func=cmd_status)

    p = sub.add_parser('check', help='test the participant name + a real database write')
    p.set_defaults(func=cmd_check)

    p = sub.add_parser('prepare', help='set up this station for one participant')
    p.add_argument('--code', required=True, help='participant code, e.g. P01')
    p.add_argument('--condition', default='intervention', choices=['intervention', 'control'],
                   help='study arm recorded with the session')
    p.add_argument('--force', action='store_true', help='prepare even if uploads are pending')
    p.add_argument('--skip-sync-check', action='store_true', help='do not test Firestore now')
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser('verify', help='check that finished sessions reached Firestore')
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser('reset', help='remove the participant code, journal and Spotify login')
    p.add_argument('--wipe-sessions', action='store_true', help='also delete local session files')
    p.set_defaults(func=cmd_reset)

    args = ap.parse_args(argv)
    if not getattr(args, 'func', None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
