"""
SpotifyController -- PKCE-based Spotify linking for Aura UI.

Why PKCE
--------
The desktop app is distributed to other people, so a client *secret* cannot be
kept secret. Spotify's Authorization Code with PKCE flow needs only the app's
public Client ID: each user signs into **their own** Spotify account in their
browser and the token is cached locally per user.

Behaviour
---------
* Nothing touches the network at import/construct time, and no browser opens on
  launch. `try_resume()` silently reuses a cached token; `connect()` is only
  called from the explicit Connect button.
* `connected` is False until a token is verified with `current_user()`, so a
  half-finished or stale auth never leaves the UI pretending to be connected.

Notes
-----
* Spotify rejects `localhost` as a redirect URI; an explicit loopback IP is
  required (`http://127.0.0.1:8080`). Legacy configs using `localhost` are
  rewritten automatically, and the same URI must be registered in the Spotify
  dashboard.
* Development Mode apps are limited to 5 allowlisted Spotify users and require
  the owner to have Premium; a non-allowlisted user gets HTTP 403 by design.
"""
import json
import os
import sys
import threading

import spotipy
from spotipy.oauth2 import SpotifyPKCE

from backend.paths import base_dir

DATA_DIR = base_dir()
SECRETS_FILE = os.path.join(DATA_DIR, 'secrets.json')
CACHE_PATH   = os.path.join(DATA_DIR, '.cache')
SCOPES       = 'user-read-playback-state user-modify-playback-state'
DEFAULT_REDIRECT = 'http://127.0.0.1:8080'


def _configured(value):
    """True only for a real value; blank and YOUR_... placeholders are not."""
    value = (value or '').strip()
    return bool(value) and not value.upper().startswith('YOUR_')


def _normalise_redirect(uri):
    """Spotify no longer accepts 'localhost' -- force an explicit loopback IP."""
    uri = (uri or '').strip() or DEFAULT_REDIRECT
    if '//localhost' in uri:
        print('[Spotify] redirect_uri uses localhost, which Spotify rejects; '
              'using 127.0.0.1 instead.')
        uri = uri.replace('//localhost', '//127.0.0.1')
    return uri


class SpotifyController:
    """Thread-safe Spotify controller. All public methods are safe off-UI-thread."""

    def __init__(self):
        self._sp          = None
        self._auth        = None
        self.configured   = False
        self.connected    = False
        self.status       = 'Not connected'
        self._lock        = threading.Lock()
        self._busy        = threading.Event()
        self._init()

    @property
    def available(self):
        """Backwards-compatible alias: the music panel is usable when connected."""
        return self.connected

    # ------------------------------------------------------------------ setup

    def _init(self):
        try:
            with open(SECRETS_FILE) as f:
                s = json.load(f)
        except FileNotFoundError:
            self.status = 'secrets.json not found'
            print('[Spotify] secrets.json not found - music panel disabled.')
            return
        except Exception as e:
            self.status = 'could not read secrets.json'
            print('[Spotify] could not read secrets.json:', e)
            return

        client_id = (s.get('spotify_client_id') or '').strip()
        if not _configured(client_id):
            self.status = 'Add spotify_client_id to secrets.json'
            print('[Spotify] no client_id (or placeholder) - music panel disabled.')
            return

        try:
            self._auth = SpotifyPKCE(
                client_id    = client_id,
                redirect_uri = _normalise_redirect(s.get('spotify_redirect_uri')),
                scope        = SCOPES,
                cache_path   = CACHE_PATH,
                open_browser = True,
            )
            self._sp         = spotipy.Spotify(auth_manager=self._auth)
            self.configured  = True
            self.status      = 'Not connected - click Connect'
        except Exception as e:
            self.configured = False
            self.status     = 'init failed: {}'.format(e)
            print('[Spotify] init failed:', e)

    # ------------------------------------------------------------------- auth

    def cached_token(self):
        try:
            return self._auth.cache_handler.get_cached_token()
        except Exception:
            return None

    def try_resume(self):
        """Reuse a cached token without opening a browser. Safe to call at startup."""
        if not self.configured or self.connected:
            return self.connected
        if not self.cached_token():
            return False
        try:
            me = self._sp.current_user()
            self.connected = True
            self.status = 'Connected as {}'.format(
                me.get('display_name') or me.get('id') or 'user')
        except Exception as e:
            self.connected = False
            self.status = 'Saved login expired - click Connect'
            print('[Spotify] cached token unusable:', e)
        return self.connected

    def connect(self):
        """Interactive PKCE grant. Blocks while the browser flow is open -- call
        from a background thread. Returns True when connected."""
        if not self.configured:
            self.status = 'Spotify not configured'
            return False
        if not self._busy.acquire(blocking=False):
            return self.connected
        try:
            self.status = 'Waiting for browser...'
            # check_cache=False forces a real consent screen for this account.
            self._auth.get_access_token(check_cache=False)
            me = self._sp.current_user()
            self.connected = True
            self.status = 'Connected as {}'.format(
                me.get('display_name') or me.get('id') or 'user')
            print('[Spotify] connected as', me.get('id'))
        except Exception as e:
            self.connected = False
            self.status = 'Connect failed: {}'.format(str(e)[:90])
            print('[Spotify] connect failed:', e)
        finally:
            self._busy.clear()
        return self.connected

    def disconnect(self):
        """Forget the local token (does not revoke it at Spotify)."""
        self.connected = False
        self.status = 'Not connected'
        try:
            os.remove(CACHE_PATH)
        except OSError:
            pass
        try:
            if self._auth:
                self._auth.cache_handler.save_token_to_cache(None)
        except Exception:
            pass

    # ------------------------------------------------------------------- read

    def current_track(self):
        """dict(title, artist, is_playing, volume) or None. Never starts auth."""
        if not self.connected:
            return None
        try:
            with self._lock:
                pb = self._sp.current_playback()
            if not pb:
                return None
            item    = pb.get('item') or {}
            artists = ', '.join(a['name'] for a in item.get('artists', []))
            return {
                'title':      item.get('name', ''),
                'artist':     artists,
                'is_playing': pb.get('is_playing', False),
                'volume':     (pb.get('device') or {}).get('volume_percent', 50),
            }
        except Exception as e:
            self._error(e)
            return None

    def _error(self, e):
        msg = str(e)
        low = msg.lower()
        if 'not registered' in low or '403' in msg:
            self.connected = False
            self.status = ('This Spotify account must be added as a test user '
                           '(Dashboard > Settings > User Management)')
            print('[Spotify] 403 - account not allowlisted for this app.')
        elif '401' in msg or 'expired' in low:
            self.connected = False
            self.status = 'Session expired - click Connect'
        else:
            self.status = msg[:90]
            print('[Spotify]', msg)

    # ---------------------------------------------------------------- control

    def play_pause(self):
        if not self.connected:
            return
        try:
            with self._lock:
                pb = self._sp.current_playback()
                if pb and pb.get('is_playing'):
                    self._sp.pause_playback()
                else:
                    self._sp.start_playback()
        except Exception as e:
            self._error(e)

    def next_track(self):
        if not self.connected:
            return
        try:
            with self._lock:
                self._sp.next_track()
        except Exception as e:
            self._error(e)

    def prev_track(self):
        if not self.connected:
            return
        try:
            with self._lock:
                self._sp.previous_track()
        except Exception as e:
            self._error(e)

    def set_volume(self, level):
        """Set playback volume 0-100."""
        if not self.connected:
            return
        try:
            with self._lock:
                self._sp.volume(max(0, min(100, int(level))))
        except Exception as e:
            self._error(e)
