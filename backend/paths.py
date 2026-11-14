"""
paths.py -- the single place that decides where Aura UI keeps its files.

Resolution order
----------------
1. ``AURA_DATA_DIR`` environment variable (explicit override).
2. The executable's folder, when frozen (PyInstaller build) -- so a shipped
   ``AuraUI.exe`` keeps its ``secrets.json`` / ``firebase_config.json`` beside it.
3. The project folder, when running from a source checkout.
4. ``%APPDATA%\\AuraUI`` (or ``~/.local/share/AuraUI``), when installed as a
   package -- a pip install must never write into site-packages.

Everything user-specific lives here: ``secrets.json``, ``settings.json``,
``journal.json``, ``.cache``, and the ``data/`` research store.
"""
import json
import os
import sys


def _is_installed(path):
    return ('site-packages' in path) or ('dist-packages' in path)


def resource_dirs():
    """Where read-only bundled resources may live, most specific first."""
    dirs = []
    if getattr(sys, 'frozen', False):
        dirs.append(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)))
        dirs.append(os.path.dirname(sys.executable))
    dirs.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return dirs


def bundled_json(name):
    """Read a JSON resource shipped inside the build (see aura_defaults.json)."""
    for folder in resource_dirs():
        path = os.path.join(folder, name)
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
    return {}


def base_dir():
    """Return the writable directory that holds this installation's files."""
    env = os.environ.get('AURA_DATA_DIR')
    if env:
        os.makedirs(env, exist_ok=True)
        return env

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        # Prefer files beside the exe so a copied folder stays self-contained;
        # fall back to APPDATA when that location is not writable
        # (e.g. the exe was dropped into Program Files).
        if os.access(exe_dir, os.W_OK):
            return exe_dir

    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _is_installed(project):
        appdata = os.environ.get('APPDATA') or os.path.expanduser('~/.local/share')
        target = os.path.join(appdata, 'AuraUI')
        os.makedirs(target, exist_ok=True)
        return target

    return project
