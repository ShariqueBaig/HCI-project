"""Open or focus the unified Aura window (single-instance).

Order of preference:
1. Focus existing Aura window if already open.
2. pywebview (optional dependency) in a child process -- a native window.
3. Microsoft Edge in app mode (``--app=URL``): a chromeless window.
4. The default browser.
"""
import ctypes
import importlib.util
import os
import shutil
import subprocess
import sys
import webbrowser

WINDOW_TITLE = 'Aura'
WIDTH, HEIGHT = 1180, 840
_proc = None


def _focus_existing_window(title=WINDOW_TITLE):
    """If a window titled `title` is already open on Windows, bring it to front."""
    if sys.platform != 'win32':
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return True
    except Exception:
        pass
    return False


def _edge_path():
    candidates = [shutil.which('msedge')]
    for env in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA'):
        root = os.environ.get(env)
        if root:
            candidates.append(os.path.join(root, 'Microsoft', 'Edge', 'Application', 'msedge.exe'))
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _has_pywebview():
    try:
        return importlib.util.find_spec('webview') is not None
    except Exception:
        return False


def open_search_window(url, force_new=False):
    """Open or focus the unified Aura window without blocking. Returns method used."""
    global _proc
    if not force_new:
        if _proc is not None and _proc.poll() is None and _focus_existing_window(WINDOW_TITLE):
            return 'focused'
        if _focus_existing_window(WINDOW_TITLE):
            return 'focused'

    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if _has_pywebview():
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, '--search-window', url]
        else:
            cmd = [sys.executable, '-m', 'backend.search.window', url]
        try:
            _proc = subprocess.Popen(
                cmd, creationflags=flags,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            )
            return 'pywebview'
        except Exception as e:
            print('[Aura] pywebview launch failed:', e)
    edge = _edge_path()
    if edge:
        try:
            _proc = subprocess.Popen(
                [edge, '--app=' + url, '--window-size={},{}'.format(WIDTH, HEIGHT)],
                creationflags=flags,
            )
            return 'edge-app'
        except Exception as e:
            print('[Aura] Edge app-mode launch failed:', e)
    webbrowser.open(url)
    return 'browser'


def run_pywebview(url):
    """Child-process entry point: blocks until the window is closed."""
    import webview
    webview.create_window(WINDOW_TITLE, url, width=WIDTH, height=HEIGHT, min_size=(760, 580))
    webview.start()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m backend.search.window URL')
    run_pywebview(sys.argv[1])
