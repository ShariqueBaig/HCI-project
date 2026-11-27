"""Open the Aura Search window.

Order of preference:
1. pywebview (optional dependency) in a child process -- a native window.
   pywebview must own its process's main thread, and Tk already owns Aura's,
   so it cannot run in-process.
2. Microsoft Edge in app mode (``--app=URL``): a chromeless window, available
   on every Windows 10/11 machine with no extra install.
3. The default browser.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import webbrowser

WINDOW_TITLE = 'Aura Search'
WIDTH, HEIGHT = 1120, 820


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


def open_search_window(url):
    """Open the window without blocking the caller. Returns the method used."""
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if _has_pywebview():
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, '--search-window', url]
        else:
            cmd = [sys.executable, '-m', 'backend.search.window', url]
        try:
            subprocess.Popen(cmd, creationflags=flags,
                             cwd=os.path.dirname(os.path.dirname(os.path.dirname(
                                 os.path.abspath(__file__)))))
            return 'pywebview'
        except Exception as e:
            print('[Aura Search] pywebview launch failed:', e)
    edge = _edge_path()
    if edge:
        try:
            subprocess.Popen([edge, '--app=' + url,
                              '--window-size={},{}'.format(WIDTH, HEIGHT)],
                             creationflags=flags)
            return 'edge-app'
        except Exception as e:
            print('[Aura Search] Edge app-mode launch failed:', e)
    webbrowser.open(url)
    return 'browser'


def run_pywebview(url):
    """Child-process entry point: blocks until the window is closed."""
    import webview
    webview.create_window(WINDOW_TITLE, url, width=WIDTH, height=HEIGHT, min_size=(720, 560))
    webview.start()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m backend.search.window URL')
    run_pywebview(sys.argv[1])
