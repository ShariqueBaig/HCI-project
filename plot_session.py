"""Turn an AuraUI session log (.jsonl or .csv) into the poster chart.

Usage:  python plot_session.py [path/to/session.jsonl | session_log_xxx.csv] [--start 5 --end 65]
With no file, the newest non-empty research .jsonl or session_log_*.csv is used.
Requires:  pip install matplotlib
"""
import csv, glob, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from backend import research

HERE = os.path.dirname(os.path.abspath(__file__))

args, opts = [], {}
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a.startswith('--') and i + 1 < len(sys.argv):
        opts[a] = sys.argv[i + 1]
        i += 2
    else:
        args.append(a)
        i += 1


def _load_rows(p):
    if p.lower().endswith('.jsonl'):
        _hdr, ticks, _sum = research._read_session(p)
        return [
            {
                't': float(rec.get('t') or 0.0),
                'score': float(rec.get('score') or 0.0),
                'tier': int(rec.get('tier') or 0),
                'br': float((rec.get('int') or {}).get('brightness') or 80.0),
                'bo': int((rec.get('int') or {}).get('breathing') or 0),
            }
            for rec in ticks
        ]
    with open(p, encoding='utf-8') as f:
        return [
            {
                't': float(r.get('t_s') or r.get('t') or 0.0),
                'score': float(r.get('score') or 0.0),
                'tier': int(r.get('tier') or 0),
                'br': float(r.get('brightness_pct') or r.get('brightness') or 80.0),
                'bo': int(r.get('breathing_open') or r.get('breathing') or 0),
            }
            for r in csv.DictReader(f)
        ]


if args:
    path = args[0]
    rows = _load_rows(path)
else:
    candidates = sorted(
        research.list_sessions()
        + glob.glob(os.path.join(HERE, 'session_log_*.csv'))
        + glob.glob(os.path.join(HERE, 'Phase_1_Submission', 'session_log_*.csv')),
        key=os.path.getmtime,
        reverse=True,
    )
    path, rows = None, []
    for cand in candidates:
        cand_rows = _load_rows(cand)
        if cand_rows:
            path, rows = cand, cand_rows
            break
    if not path:
        raise SystemExit('No non-empty session .jsonl or session_log_*.csv found to plot.')

t0, t1 = float(opts.get('--start', 0)), float(opts.get('--end', 1e9))
rows = [r for r in rows if t0 <= r['t'] <= t1]
if not rows:
    raise SystemExit('No telemetry ticks found in {} within [{}, {}].'.format(path, t0, t1))

off = rows[0]['t']
t  = [r['t'] - off for r in rows]
sc = [r['score'] for r in rows]
tr = [r['tier'] for r in rows]
br = [r['br'] for r in rows]
bo = [r['bo'] for r in rows]

MAR, INK, MUT = '#8B1A1F', '#2a1a1c', '#6b5d5f'
CALM, MILD, ELEV = '#7fae9d', '#d9a054', '#c97070'
nxt = lambda cond: next((i for i, x in enumerate(cond) if x), None)
i_soothe = nxt([k >= 1 for k in tr])
i_prompt = nxt([b == 1 for b in bo]) if any(bo) else nxt([k >= 2 for k in tr])
peak = max(range(len(sc)), key=sc.__getitem__)
i_back = next((i for i in range(peak, len(tr)) if tr[i] == 0), None)

plt.rcParams['font.family'] = 'DejaVu Sans'

def draw(figsize, fs, out, title, lw, compact):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=figsize, dpi=300, sharex=True,
                                 gridspec_kw=dict(height_ratios=[3.2, 1], hspace=0.10))
    xmax = t[-1] or 1.0
    for lo, hi, c, l in [(0, 30, CALM, 'Calm'), (30, 60, MILD, 'Mild'), (60, 100, ELEV, 'Elevated')]:
        a1.axhspan(lo, hi, color=c, alpha=0.16, lw=0)
        a1.text(xmax * 0.99, (lo + hi) / 2, l, ha='right', va='center', color=MUT, fontsize=fs, fontweight='bold')
    a1.plot(t, sc, color=MAR, lw=lw, solid_capstyle='round')
    a1.set_ylim(0, 100); a1.set_xlim(0, xmax); a1.set_yticks([0, 30, 60, 100])
    a1.set_ylabel('Frustration score', fontsize=fs, color=INK)
    def note(i, txt, dx, y, col):
        if i is None: return
        a1.scatter([t[i]], [sc[i]], color=col, s=40 if compact else 70, zorder=5, edgecolor='white', lw=1.2)
        a1.annotate(txt, (t[i], sc[i]), xytext=(t[i] + dx * xmax, y), fontsize=fs, color=INK,
                    fontweight='bold', ha='left', arrowprops=dict(arrowstyle='->', color=INK, lw=1))
    if compact:
        note(i_soothe, '1 SOOTHE\nscreen dims,\nmusic lowers', -0.30, 62, MILD)
        note(i_prompt, '2 PROMPT\nbreathing guide', 0.04, 82, ELEV)
        note(i_back, '3 RECOVERY', 0.05, 45, CALM)
    else:
        note(i_soothe, '① SOOTHE\nscreen dims, colour\nwarms, music lowers', -0.17, 64, MILD)
        note(i_prompt, '② PROMPT\nbreathing guide opens', 0.03, 84, ELEV)
        note(i_back, '③ RECOVERY\nback to Calm', 0.05, 48, CALM)
    a2.step(t, br, where='post', color=MAR, lw=lw * 0.85)
    a2.set_ylim(min(br) - 10, max(br) + 10)
    b_lo, b_hi = round(min(br)), round(max(br))
    a2.set_yticks([b_lo] if b_lo == b_hi else [b_lo, b_hi])
    a2.set_ylabel('Brightness %', fontsize=fs, color=INK)
    a2.set_xlabel('Time (seconds)', fontsize=fs, color=INK)
    for a in (a1, a2):
        for sp in ('top', 'right'): a.spines[sp].set_visible(False)
        for sp in ('left', 'bottom'): a.spines[sp].set_color('#bbb')
        a.tick_params(colors=MUT, labelsize=fs)
    if title:
        fig.suptitle(title, fontsize=fs + 3, fontweight='bold', color=MAR, x=0.07, ha='left', y=0.97)
    fig.savefig(out, bbox_inches='tight', facecolor='white', pad_inches=0.08)
    plt.close(fig)
    print('saved', out)

draw((10, 6.4), 10.5, os.path.join(HERE, 'aura_session_chart_real.png'),
     'Live AuraUI session: frustration sensed and regulated in real time', 3, False)
# poster-sized version (about 5.4 x 2.9 in at print size, fonts stay readable)
draw((5.4, 3.0), 8.5, os.path.join(HERE, 'aura_session_chart_poster.png'), None, 2.2, True)
