#!/usr/bin/env python3
"""Build a standalone AuraUI.exe for development and testing.

    python build_exe.py            # -> dist/AuraUI.exe

This is the *developer / quick-test* build script.  It produces a single
self-contained exe you can double-click to launch Aura UI.  Config files
(settings.json, secrets.json, lab_salt.txt …) are read from beside the exe
at runtime, so drop whatever you need next to it.

For producing ready-to-run per-participant distribution packages, use:
    python tools/stamp_exe.py --help

What goes in
~~~~~~~~~~~~
  * run.py + backend/           stress engine, interventions, research, search
  * aura_defaults.json          public Firebase / Spotify ids (no secrets)
  * search_ui/dist              built search window (auto-built if missing)
  * search_fixtures/            recorded study tasks
  * pycaw + comtypes            Windows system-volume control
  * uvicorn submodules          Aura Search local server

What stays out
~~~~~~~~~~~~~~
  * secrets.json                put beside the exe if you need OpenRouter / Tavily
  * webcam sensor               opencv + onnxruntime (~150 MB); use `pip install ".[vision]"`
  * matplotlib                  only needed for plot_session.py
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SEP = ';' if os.name == 'nt' else ':'
SEARCH_UI_DIR = os.path.join(ROOT, 'search_ui')
SEARCH_UI_DIST = os.path.join(SEARCH_UI_DIR, 'dist', 'index.html')
FIXTURES_DIR = os.path.join(ROOT, 'search_fixtures')


def ensure_search_ui():
    """Build search_ui if its dist/ is missing."""
    if os.path.isfile(SEARCH_UI_DIST):
        print('[ok] search_ui/dist already built')
        return True

    if not os.path.isfile(os.path.join(SEARCH_UI_DIR, 'package.json')):
        print('[warn] search_ui/package.json not found — building without search UI')
        return False

    npm = shutil.which('npm')
    if not npm:
        print('[warn] npm not found on PATH — building without search UI')
        return False

    print('[build] npm install && npm run build  (search_ui)')
    subprocess.run([npm, 'install'], cwd=SEARCH_UI_DIR, check=True)
    subprocess.run([npm, 'run', 'build'], cwd=SEARCH_UI_DIR, check=True)

    if not os.path.isfile(SEARCH_UI_DIST):
        print('[warn] search_ui build did not produce dist/index.html — continuing without it')
        return False
    print('[ok] search_ui built')
    return True


def main():
    print('=' * 60)
    print('  Aura UI — Standalone EXE Build (dev / test)')
    print('=' * 60)

    # ---- pre-flight: search UI ----
    has_search_ui = ensure_search_ui()

    # ---- assemble PyInstaller command ----
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--onefile', '--noconsole',
        '--name', 'AuraUI',
        '--add-data', 'aura_defaults.json' + SEP + '.',
    ]

    if has_search_ui:
        cmd += ['--add-data', os.path.join('search_ui', 'dist') + SEP + os.path.join('search_ui', 'dist')]

    if os.path.isdir(FIXTURES_DIR):
        cmd += ['--add-data', 'search_fixtures' + SEP + 'search_fixtures']

    cmd += [
        # uvicorn picks loop / protocol implementations at runtime
        '--collect-submodules', 'uvicorn',
        '--hidden-import', 'backend.search.server',
        '--hidden-import', 'backend.search.window',
        # Windows system volume (pycaw is lazy-imported)
        '--hidden-import', 'pycaw',
        '--hidden-import', 'comtypes',
        # heavy / optional — stay out of the exe
        '--exclude-module', 'cv2',
        '--exclude-module', 'onnxruntime',
        '--exclude-module', 'backend.vision.vision_engine',
        '--exclude-module', 'backend.vision.model_manager',
        '--exclude-module', 'backend.vision.affective_engine',
        '--exclude-module', 'matplotlib',
        'run.py',
    ]

    print('\n[build] ' + ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    exe = os.path.join(ROOT, 'dist', 'AuraUI.exe' if os.name == 'nt' else 'AuraUI')
    if os.path.isfile(exe):
        mb = os.path.getsize(exe) / 1e6
        print('\n[ok] built {} ({:.1f} MB)'.format(exe, mb))
        print('     Drop secrets.json beside it if you need OpenRouter / Tavily keys.')
        print('     Run:  dist\\AuraUI.exe')
    else:
        print('\n[FAIL] PyInstaller did not produce {}'.format(exe))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
