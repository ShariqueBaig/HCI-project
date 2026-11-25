#!/usr/bin/env python3
"""Build the single-file AuraUI.exe, including Aura Search.

    python build_exe.py            # -> dist/AuraUI.exe

What goes in:
  * run.py + backend/ (stress engine, interventions, research, search server)
  * aura_defaults.json        public Firebase / Spotify ids (no secrets)
  * search_ui/dist            the built search window (run `npm run build` in search_ui/ first)
  * search_fixtures/          recorded study tasks (same sources for every participant)
What stays out:
  * secrets.json (OpenRouter / Tavily keys) -- put it beside the exe; without it,
    search falls back to Wikipedia + extractive answers and the chat to the offline coach
  * the webcam sensor (OpenCV + onnxruntime, ~150 MB) -- Phase 6 camera support is for
    `python run.py` installs with `pip install ".[vision]"`; the exe hides the toggle
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SEP = ';' if os.name == 'nt' else ':'


def main():
    ui = os.path.join(ROOT, 'search_ui', 'dist', 'index.html')
    if not os.path.isfile(ui):
        sys.exit('search_ui is not built: run `npm install && npm run build` in search_ui/ first')
    cmd = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--noconsole',
        '--name', 'AuraUI',
        '--add-data', 'aura_defaults.json' + SEP + '.',
        '--add-data', os.path.join('search_ui', 'dist') + SEP + os.path.join('search_ui', 'dist'),
        '--add-data', 'search_fixtures' + SEP + 'search_fixtures',
        # uvicorn picks its loop / protocol implementations at runtime
        '--collect-submodules', 'uvicorn',
        '--hidden-import', 'backend.search.server',
        '--hidden-import', 'backend.search.window',
        # optional, heavy: camera support stays out of the exe
        '--exclude-module', 'cv2',
        '--exclude-module', 'onnxruntime',
        '--exclude-module', 'backend.vision.vision_engine',
        '--exclude-module', 'backend.vision.model_manager',
        '--exclude-module', 'backend.vision.affective_engine',
        '--exclude-module', 'matplotlib',
        'run.py',
    ]
    print(' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)
    exe = os.path.join(ROOT, 'dist', 'AuraUI.exe' if os.name == 'nt' else 'AuraUI')
    print('built {} ({:.1f} MB)'.format(exe, os.path.getsize(exe) / 1e6))


if __name__ == '__main__':
    main()
