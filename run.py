#!/usr/bin/env python3
"""Aura UI -- Unified Ambient Computing & State-Aware Search Desktop App.

Headless Python ambient daemon + peripheral system tray icon + single-instance
native React shell (port 8765 by default; automatically picks the next free
port if another instance is already running).
"""
import argparse
import os
import sys
import threading
import time

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from backend.daemon_controller import AuraController
from backend.search.server import DEFAULT_PORT, SearchServer
from backend.search.window import open_search_window
from backend.stress_engine import StressEngine  # re-exported for compatibility

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_OK = True
except ImportError:
    TRAY_OK = False

TIER_COLORS = ('#7fb8a4', '#e2ac5f', '#e08282')


class AuraV2App:
    def __init__(self, port=DEFAULT_PORT, open_on_start=True, start_lab=False):
        self.controller = AuraController(standalone=False, persist=True, lab_unlocked=start_lab)
        self.server = SearchServer(
            self.controller.live_state,
            port=port,
            get_collector=lambda: self.controller._collector,
            controller=self.controller,
        )
        self.open_on_start = open_on_start
        self.start_lab = start_lab
        self._stop_event = threading.Event()
        self._tray = None
        self._hotkey = None
        self._last_tier = -1

    @staticmethod
    def _make_icon(tier=0):
        img = Image.new('RGB', (64, 64), '#0c0b12')
        d = ImageDraw.Draw(img)
        color = TIER_COLORS[max(0, min(2, int(tier)))]
        d.ellipse([10, 10, 54, 54], outline=color, width=6)
        d.ellipse([23, 23, 41, 41], fill=color)
        return img

    def open_window(self, view=None, lab=False):
        if not self.server.wait_started(timeout=3.0):
            return
        url = self.server.url
        params = []
        if view:
            params.append(f'view={view}')
        if lab or self.start_lab:
            params.append('lab=1')
        if params:
            url += '&' + '&'.join(params)
        open_search_window(url)

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem('Open Aura  (Ctrl+Shift+Space)', lambda i, it: self.open_window()),
            pystray.MenuItem('Wellness & Comfort', lambda i, it: self.open_window(view='wellness')),
            pystray.MenuItem('Researcher Lab Console', lambda i, it: self.open_window(lab=True)),
            pystray.MenuItem('Quit Aura', lambda i, it: self.quit()),
        )
        self._tray = pystray.Icon('Aura', self._make_icon(0), 'Aura — Calm', menu)
        self._tray.run_detached()

    def _tray_updater(self):
        while not self._stop_event.is_set():
            if self._tray is not None:
                tier = self.controller.engine.tier
                if tier != self._last_tier:
                    self._last_tier = tier
                    try:
                        self._tray.icon = self._make_icon(tier)
                        self._tray.title = f'Aura — {self.controller.engine.label}'
                    except Exception:
                        pass
            self._stop_event.wait(1.0)

    def _start_hotkey(self):
        try:
            from pynput import keyboard as _kb
            self._hotkey = _kb.GlobalHotKeys({'<ctrl>+<shift>+<space>': self.open_window})
            self._hotkey.daemon = True
            self._hotkey.start()
        except Exception as e:
            print('[Aura v2] global hotkey unavailable:', e)

    def quit(self):
        self._stop_event.set()
        if self._hotkey:
            try:
                self._hotkey.stop()
            except Exception:
                pass
        self.controller.stop()
        self.server.stop()
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass

    def run(self):
        self.controller.start()
        self.server.start()
        if not self.server.wait_started(timeout=6.0):
            raise SystemExit(f'[Aura v2] server failed to start: {self.server.error}')
        print('[Aura v2] running at:', self.server.url)
        if TRAY_OK:
            self._setup_tray()
            threading.Thread(target=self._tray_updater, name='aura-tray', daemon=True).start()
        self._start_hotkey()
        if self.open_on_start:
            self.open_window(lab=self.start_lab)
        try:
            while not self._stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.quit()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--search-window':
        from backend.search.window import run_pywebview
        run_pywebview(sys.argv[2])
        return
    ap = argparse.ArgumentParser(description='Aura v2 Unified App')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--no-window', action='store_true', help='start in tray without opening window')
    ap.add_argument('--lab', action='store_true', help='open with Researcher Lab Console unlocked')
    args = ap.parse_args()
    AuraV2App(port=args.port, open_on_start=not args.no_window, start_lab=args.lab).run()


if __name__ == '__main__':
    main()
