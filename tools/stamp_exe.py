#!/usr/bin/env python3
"""Stamp pre-registered, ready-to-run AuraUI distribution packages.

Run with NO arguments for interactive mode (with code hints & prompts),
or pass CLI flags directly for scripted/one-shot use:

    python tools/stamp_exe.py                                   # interactive mode
    python tools/stamp_exe.py --range P01-P12 --counterbalance  # scripted
    python tools/stamp_exe.py --participants P01 P02 --condition control
    python tools/stamp_exe.py --range P01-P12 --update          # after rebuilding exe

Produces one self-contained folder per participant under dist/:

    dist/
    ├── AuraUI.exe                    (master build — kept as template)
    ├── AuraUI_P01/
    │   ├── AuraUI.exe                (copy of master)
    │   ├── aura_defaults.json
    │   ├── lab_salt.txt
    │   ├── settings.json             (pre-filled: code=P01, condition, defaults)
    │   └── data/
    │       └── consent.json          (consent pre-granted)
    ├── AuraUI_P02/
    │   └── ...
    ├── QUICK_START.md
    ├── TROUBLESHOOTING.md
    └── requirements_check.bat
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'dist')
MASTER_EXE = os.path.join(DIST, 'AuraUI.exe')
DEFAULTS_JSON = os.path.join(ROOT, 'aura_defaults.json')
SALT_FILE = os.path.join(ROOT, 'lab_salt.txt')

# Same defaults as run.py — kept in sync so stamped settings match the app.
APP_DEFAULTS = {
    'cov_weight':   0.65,
    'error_weight': 0.35,
    'smoothing':    0.18,
    'sensitivity':  1.0,
    'decay_speed':  1.0,
    'bright_calm':  80,
    'bright_mild':  65,
    'bright_elev':  50,
    'vol_calm':     70,
    'vol_mild':     55,
    'vol_elev':     35,
    'temp_calm':    6500,
    'temp_mild':    5000,
    'temp_elev':    3500,
    'baseline_cov': 0.0,
    'baseline_err': 0.0,
    'is_calibrated': 0,
    'participant_code': '',
    'study_condition': 'intervention',
}


def ok(msg):   print('  [ok]   ' + msg)
def warn(msg): print('  [warn] ' + msg)
def bad(msg):  print('  [FAIL] ' + msg)


def parse_range(spec):
    """Parse 'P01-P12' into ['P01', 'P02', ..., 'P12']."""
    m = re.match(r'^([A-Za-z]*)(\d+)\s*-\s*([A-Za-z]*)(\d+)$', spec.strip())
    if not m:
        raise ValueError('invalid range: {} (expected e.g. P01-P12)'.format(spec))
    prefix = m.group(1) or m.group(3)
    start, end = int(m.group(2)), int(m.group(4))
    width = max(len(m.group(2)), len(m.group(4)))
    if start > end:
        raise ValueError('range start ({}) > end ({})'.format(start, end))
    return ['{}{}'.format(prefix, str(i).zfill(width)) for i in range(start, end + 1)]


def parse_participant_input(raw):
    """Parse either 'P01-P12' or 'P01 P02, P03' into a list of codes."""
    raw = raw.strip()
    if not raw:
        return []
    if re.match(r'^[A-Za-z]*\d+\s*-\s*[A-Za-z]*\d+$', raw):
        return parse_range(raw)
    parts = [p.strip().upper() for p in re.split(r'[\s,;]+', raw) if p.strip()]
    return parts


def existing_participant_folders():
    """Return sorted list of existing participant codes found in dist/AuraUI_*."""
    if not os.path.isdir(DIST):
        return []
    found = []
    for name in sorted(os.listdir(DIST)):
        full = os.path.join(DIST, name)
        if os.path.isdir(full) and name.startswith('AuraUI_'):
            found.append(name[len('AuraUI_'):])
    return found


def pseudonym(code, salt):
    """Salted SHA-256 pseudonym — same algorithm as backend/research.py."""
    return hashlib.sha256((salt + code.strip().upper()).encode()).hexdigest()[:16]


def ensure_salt(salt_path):
    """Read or create a lab salt."""
    if os.path.isfile(salt_path):
        with open(salt_path, encoding='utf-8') as f:
            salt = f.read().strip()
        if salt:
            return salt
    salt = secrets.token_hex(32)
    os.makedirs(os.path.dirname(salt_path) or '.', exist_ok=True)
    with open(salt_path, 'w', encoding='utf-8') as f:
        f.write(salt)
    ok('generated new lab salt: {}'.format(salt_path))
    return salt


def stamp_participant(code, condition, salt, master_exe, defaults_json, update=False):
    """Create or update one participant folder."""
    folder_name = 'AuraUI_{}'.format(code.upper())
    folder = os.path.join(DIST, folder_name)
    data_dir = os.path.join(folder, 'data')
    is_update = os.path.isdir(folder)

    os.makedirs(data_dir, exist_ok=True)

    # --- copy / update the exe ---
    dest_exe = os.path.join(folder, 'AuraUI.exe')
    if not is_update or update or not os.path.isfile(dest_exe):
        shutil.copy2(master_exe, dest_exe)

    # --- aura_defaults.json ---
    if defaults_json and os.path.isfile(defaults_json):
        shutil.copy2(defaults_json, os.path.join(folder, 'aura_defaults.json'))

    # --- lab_salt.txt ---
    salt_dest = os.path.join(folder, 'lab_salt.txt')
    with open(salt_dest, 'w', encoding='utf-8') as f:
        f.write(salt)

    # --- settings.json ---
    settings_path = os.path.join(folder, 'settings.json')
    settings = dict(APP_DEFAULTS)
    if is_update and os.path.isfile(settings_path):
        try:
            with open(settings_path, encoding='utf-8') as f:
                existing = json.load(f)
            for key in ('baseline_cov', 'baseline_err', 'is_calibrated',
                        'cov_weight', 'error_weight', 'smoothing',
                        'sensitivity', 'decay_speed'):
                if key in existing and existing[key] != APP_DEFAULTS.get(key):
                    settings[key] = existing[key]
        except Exception:
            pass
    settings['participant_code'] = code.upper()
    settings['study_condition'] = condition
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    # --- consent.json (pre-grant) ---
    consent_path = os.path.join(data_dir, 'consent.json')
    if not os.path.isfile(consent_path) or not update:
        pseudo = pseudonym(code, salt)
        consent = {
            'granted': True,
            'granted_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'pseudonym': pseudo,
            'version': '3.0',
            'store_queries': True,
            'note': 'pre-registered by stamp_exe.py',
        }
        with open(consent_path, 'w', encoding='utf-8') as f:
            json.dump(consent, f, indent=2)

    # --- .salt (the data-dir salt used by research.py at runtime) ---
    data_salt_path = os.path.join(data_dir, '.salt')
    with open(data_salt_path, 'w', encoding='utf-8') as f:
        f.write(salt)

    action = 'updated' if is_update else 'created'
    pseudo = pseudonym(code, salt)
    return folder_name, action, pseudo


def run_stamp(codes, condition_mode, salt_path, master_exe, update=False):
    """Execute stamping for a list of codes and print summary."""
    if not os.path.isfile(master_exe):
        bad('master exe not found: {}'.format(master_exe))
        print('     Build it first:  python build_exe.py')
        return 1

    master_mb = os.path.getsize(master_exe) / 1e6
    print()
    print('=' * 60)
    print('  Aura UI — Stamp Distribution Packages')
    print('=' * 60)
    print('  master exe  : {} ({:.1f} MB)'.format(master_exe, master_mb))
    print('  participants: {} ({})'.format(len(codes), ', '.join(codes)))
    print('  mode        : {}'.format('update' if update else 'create'))

    salt = ensure_salt(salt_path)
    print('  salt        : {} ({}...)'.format(salt_path, salt[:12]))

    if condition_mode == 'counterbalance':
        conditions = ['intervention' if (i % 2 == 0) else 'control' for i in range(len(codes))]
        print('  conditions  : counterbalanced (odd=intervention, even=control)')
    else:
        conditions = [condition_mode] * len(codes)
        print('  condition   : {}'.format(condition_mode))

    defaults = DEFAULTS_JSON if os.path.isfile(DEFAULTS_JSON) else None
    if not defaults:
        warn('aura_defaults.json not found — packages will use built-in defaults')

    print()
    results = []
    for code, cond in zip(codes, conditions):
        folder_name, action, pseudo = stamp_participant(
            code, cond, salt, master_exe, defaults, update=update)
        ok('{:16s}  {:8s}  condition={:14s}  pseudo={}'.format(
            folder_name, action, cond, pseudo))
        results.append((folder_name, action, cond))

    check_bat_src = os.path.join(ROOT, 'tools', 'requirements_check.bat')
    check_bat_dst = os.path.join(DIST, 'requirements_check.bat')
    if os.path.isfile(check_bat_src) and not os.path.isfile(check_bat_dst):
        shutil.copy2(check_bat_src, check_bat_dst)

    created = sum(1 for _, a, _ in results if a == 'created')
    updated = sum(1 for _, a, _ in results if a == 'updated')
    print()
    print('  {} folder(s) created, {} updated (~{:.0f} MB each)'.format(
        created, updated, master_mb + 0.1))
    print()
    print('  Next steps:')
    print('    1. Copy each dist\\AuraUI_Pxx\\ folder to its lab station (or USB)')
    print('    2. On the station, double-click AuraUI.exe')
    print('    3. Participant just presses "Record session" to start')
    return 0


def show_status():
    """Print current dist/ packages and their settings."""
    print()
    print('  Current dist/ status:')
    if os.path.isfile(MASTER_EXE):
        mb = os.path.getsize(MASTER_EXE) / 1e6
        print('    Master EXE : {} ({:.1f} MB)'.format(MASTER_EXE, mb))
    else:
        print('    Master EXE : NOT BUILT (run: python build_exe.py)')

    if os.path.isfile(SALT_FILE):
        with open(SALT_FILE, encoding='utf-8') as f:
            s = f.read().strip()
        print('    Lab salt   : {} ({}...)'.format(SALT_FILE, s[:12]))
    else:
        print('    Lab salt   : NOT SET (will auto-generate on first stamp)')

    existing = existing_participant_folders()
    if not existing:
        print('    Packages   : (none yet)')
    else:
        print('    Packages   : {} folder(s)'.format(len(existing)))
        for code in existing:
            sp = os.path.join(DIST, 'AuraUI_' + code, 'settings.json')
            cond = '?'
            cal = ''
            if os.path.isfile(sp):
                try:
                    with open(sp, encoding='utf-8') as f:
                        d = json.load(f)
                    cond = d.get('study_condition', '?')
                    cal = ' | calibrated' if d.get('is_calibrated') else ''
                except Exception:
                    pass
            print('      - AuraUI_{:<8s} condition={}{}'.format(code, cond, cal))


def print_banner_and_hints():
    """Print top header, current status, and CLI code hints."""
    print()
    print('=' * 66)
    print('  AURA UI — Distribution Package Builder & Stamper')
    print('=' * 66)
    print('  CODE HINTS (for scripted / command-line use):')
    print('    Rebuild standalone exe:')
    print('      python build_exe.py')
    print('    Stamp range with alternating A/B conditions:')
    print('      python tools/stamp_exe.py --range P01-P12 --counterbalance')
    print('    Stamp specific participants as control:')
    print('      python tools/stamp_exe.py --participants P01 P02 --condition control')
    print('    Update existing folders after a code change (keeps logs/cal):')
    print('      python tools/stamp_exe.py --range P01-P12 --update')
    print('=' * 66)
    show_status()


def interactive_mode():
    """Interactive prompt loop when launched without CLI arguments."""
    print_banner_and_hints()

    while True:
        print()
        print('  What would you like to do?')
        print('    [1] Create / stamp participant folders  (e.g. AuraUI_P01 ...)')
        print('    [2] Update existing folders with latest AuraUI.exe')
        print('    [3] Rebuild master AuraUI.exe first  (runs build_exe.py)')
        print('    [4] Refresh / show current dist/ status')
        print('    [q] Quit')
        choice = input('\n  Enter choice [1/2/3/4/q]: ').strip().lower()

        if choice in ('q', 'quit', 'exit'):
            break

        if choice == '4':
            show_status()
            continue

        if choice == '3':
            print('\n  Running build_exe.py ...')
            subprocess.run([sys.executable, os.path.join(ROOT, 'build_exe.py')], cwd=ROOT)
            continue

        if choice not in ('1', '2'):
            print('  Invalid choice. Enter 1, 2, 3, 4, or q.')
            continue

        is_update = (choice == '2')
        if not os.path.isfile(MASTER_EXE):
            ans = input('\n  Master AuraUI.exe is missing. Build it now? [Y/n]: ').strip().lower()
            if ans in ('', 'y', 'yes'):
                rc = subprocess.run([sys.executable, os.path.join(ROOT, 'build_exe.py')], cwd=ROOT).returncode
                if rc != 0 or not os.path.isfile(MASTER_EXE):
                    bad('Build failed — cannot stamp without master exe.')
                    continue
            else:
                continue

        # Participants input
        existing = existing_participant_folders()
        if is_update and existing:
            hint = 'Press Enter for all existing ({}) or enter range/codes'.format(', '.join(existing))
        else:
            hint = 'e.g. P01-P12  or  P01 P02 P03'
        raw_codes = input('\n  Participants ({}): '.format(hint)).strip()
        if not raw_codes and is_update and existing:
            codes = existing
        else:
            try:
                codes = parse_participant_input(raw_codes)
            except ValueError as e:
                bad(str(e))
                continue

        if not codes:
            bad('No participant codes entered.')
            continue

        # Condition mode
        print('\n  Study condition:')
        print('    [1] Counterbalanced  (odd = intervention, even = control)')
        print('    [2] All intervention (Mode B — Aura Active)')
        print('    [3] All control      (Mode A — Baseline)')
        c_choice = input('  Choose condition [1/2/3, default=1]: ').strip() or '1'
        cond_map = {'1': 'counterbalance', '2': 'intervention', '3': 'control'}
        if c_choice not in cond_map:
            bad('Invalid condition choice.')
            continue
        cond_mode = cond_map[c_choice]

        # Salt path
        salt_in = input('\n  Lab salt path [Enter for default: {}]: '.format(SALT_FILE)).strip()
        salt_path = salt_in or SALT_FILE

        # Confirm
        print('\n  Ready to {} {} package(s): {}'.format(
            'update' if is_update else 'create', len(codes), ', '.join(codes)))
        confirm = input('  Proceed? [Y/n]: ').strip().lower()
        if confirm not in ('', 'y', 'yes'):
            print('  Cancelled.')
            continue

        run_stamp(codes, cond_mode, salt_path, MASTER_EXE, update=is_update)

        again = input('\n  Do something else? [y/N]: ').strip().lower()
        if again not in ('y', 'yes'):
            break

    return 0


def main():
    if len(sys.argv) == 1:
        return interactive_mode()

    ap = argparse.ArgumentParser(
        prog='stamp_exe.py',
        description='Stamp pre-registered AuraUI distribution packages for each participant.\n'
                    'Run with no arguments for interactive mode.',
        epilog='Example:\n'
               '  python tools/stamp_exe.py --range P01-P12 --counterbalance\n'
               '  python tools/stamp_exe.py --participants P01 P02 P03 --condition control\n'
               '  python tools/stamp_exe.py --range P01-P12 --update   # after rebuilding exe',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--participants', nargs='+', metavar='CODE',
                       help='explicit list of participant codes (e.g. P01 P02 P03)')
    group.add_argument('--range', metavar='P01-P12', dest='code_range',
                       help='range shorthand (e.g. P01-P12)')
    ap.add_argument('--condition', choices=['intervention', 'control'], default='intervention',
                    help='study condition for all participants (default: intervention)')
    ap.add_argument('--counterbalance', action='store_true',
                    help='alternate conditions: odd=intervention, even=control')
    ap.add_argument('--salt', metavar='PATH',
                    help='path to shared lab_salt.txt (default: project root)')
    ap.add_argument('--update', action='store_true',
                    help='update existing folders: refresh exe and settings defaults, '
                         'preserve calibration and session data')
    ap.add_argument('--exe', metavar='PATH',
                    help='path to master AuraUI.exe (default: dist/AuraUI.exe)')

    args = ap.parse_args()

    codes = parse_range(args.code_range) if args.code_range else [c.strip().upper() for c in args.participants]
    if not codes:
        bad('no participant codes')
        return 1

    cond_mode = 'counterbalance' if args.counterbalance else args.condition
    salt_path = args.salt or SALT_FILE
    master = args.exe or MASTER_EXE

    return run_stamp(codes, cond_mode, salt_path, master, update=args.update)


if __name__ == '__main__':
    raise SystemExit(main())
