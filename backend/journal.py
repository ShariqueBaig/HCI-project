"""
Journal -- stores saved session reflections in journal.json next to the app.
Only aggregate numbers and the user's own text are stored, never keystrokes.
"""
import json
import os
import sys

if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JOURNAL_FILE = os.path.join(DATA_DIR, 'journal.json')

REFLECT_SYSTEM = (
    "You are Aura, a gentle metacognitive mirror. Write a short journal reflection "
    "(3-4 sentences, second person) about the user's work session from the stats given. "
    "Mention when stress peaked and what seemed to help, and end with one small, kind "
    "suggestion for next time. Do not give medical advice. Plain text only."
)


def load():
    try:
        with open(JOURNAL_FILE, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def add(entry):
    entries = load()
    entries.append(entry)
    with open(JOURNAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(entries, f, indent=2)
    return entries


def fmt_duration(sec):
    sec = int(sec)
    return '{}m {:02d}s'.format(sec // 60, sec % 60)


def stats_text(s):
    return ('Duration {}  |  avg stress {:.0f}  |  peak {:.0f} at {}\n'
            'Calm {}  |  Mild {}  |  Elevated {}  ({} episode{})\n'
            'Breathing guides {}  |  notifications held back {}'.format(
                fmt_duration(s['duration_s']), s['avg'], s['peak'], fmt_duration(s['peak_at_s']),
                fmt_duration(s['tier_s'][0]), fmt_duration(s['tier_s'][1]),
                fmt_duration(s['tier_s'][2]), s['episodes'], '' if s['episodes'] == 1 else 's',
                s['breathing'], s['held']))


def reflect_prompt(s, note):
    p = 'Session stats:\n' + stats_text(s)
    if note.strip():
        p += '\nThe user wrote: ' + note.strip()
    return p


def local_reflection(s):
    """Fallback when OpenRouter is unavailable."""
    if s['episodes'] == 0:
        body = 'You stayed out of the Elevated zone this session. '
    else:
        body = ('Stress reached Elevated {} time{} and peaked at {:.0f} around minute {}. '
                .format(s['episodes'], '' if s['episodes'] == 1 else 's', s['peak'],
                        int(s['peak_at_s'] // 60)))
    if s['breathing']:
        body += 'The breathing guide opened {} time{}. '.format(
            s['breathing'], '' if s['breathing'] == 1 else 's')
    if s['held']:
        body += 'Focus mode kept {} notification{} out of the way. '.format(
            s['held'], '' if s['held'] == 1 else 's')
    return body + 'Next time, try a short break as soon as the score starts climbing.'
