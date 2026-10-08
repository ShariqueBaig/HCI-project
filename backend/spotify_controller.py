"""
SpotifyController — wraps spotipy for Aura UI.
Handles OAuth (first run opens a browser), then exposes
simple play/pause/skip/volume methods safe to call from any thread.
"""
import json
import os
import threading

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import sys

if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRETS_FILE  = os.path.join(DATA_DIR, 'secrets.json')
CACHE_PATH    = os.path.join(DATA_DIR, '.cache')
SCOPES        = 'user-read-playback-state user-modify-playback-state'


class SpotifyController:
    """
    Thread-safe Spotify controller.
    All public methods are safe to call from background threads.
    `available` is False until auth succeeds.
    """

    def __init__(self):
        self._sp        = None
        self.available  = False
        self._lock      = threading.Lock()
        self._init()

    # ------------------------------------------------------------------ init

    def _init(self):
        try:
            with open(SECRETS_FILE) as f:
                s = json.load(f)

            auth = SpotifyOAuth(
                client_id     = s['spotify_client_id'],
                client_secret = s['spotify_client_secret'],
                redirect_uri  = s['spotify_redirect_uri'],
                scope         = SCOPES,
                cache_path    = CACHE_PATH,
                open_browser  = True,
            )
            self._sp       = spotipy.Spotify(auth_manager=auth)
            self.available = True
            print('[Spotify] Connected.')
        except FileNotFoundError:
            print('[Spotify] secrets.json not found — music panel disabled.')
        except Exception as e:
            print(f'[Spotify] init failed: {e}')

    # ------------------------------------------------------------------ read

    def current_track(self):
        """
        Returns a dict or None.
        Keys: title, artist, is_playing, volume (0-100)
        """
        if not self.available:
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
        except Exception:
            return None

    # ------------------------------------------------------------------ control

    def play_pause(self):
        if not self.available:
            return
        try:
            with self._lock:
                pb = self._sp.current_playback()
                if pb and pb.get('is_playing'):
                    self._sp.pause_playback()
                else:
                    self._sp.start_playback()
        except Exception as e:
            print(f'[Spotify] play_pause: {e}')

    def next_track(self):
        if not self.available:
            return
        try:
            with self._lock:
                self._sp.next_track()
        except Exception as e:
            print(f'[Spotify] next: {e}')

    def prev_track(self):
        if not self.available:
            return
        try:
            with self._lock:
                self._sp.previous_track()
        except Exception as e:
            print(f'[Spotify] prev: {e}')

    def set_volume(self, level: int):
        """Set playback volume 0-100."""
        if not self.available:
            return
        try:
            with self._lock:
                self._sp.volume(max(0, min(100, int(level))))
        except Exception as e:
            print(f'[Spotify] volume: {e}')
