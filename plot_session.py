"""Turn an AuraUI session log into the poster chart.

Usage:  python plot_session.py [session_log_xxx.csv] [--start 5 --end 65]
With no file, the newest session_log_*.csv next to this script is used.
Requires:  pip install matplotlib
"""
import csv, glob, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith('--')]
opts = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith('--')}
path = args[0] if args else max(glob.glob(os.path.join(HERE, 'session_log_*.csv')), key=os.path.getmtime)
rows = list(csv.DictReader(open(path, encoding='utf-8')))
t0, t1 = float(opts.get('--start', 0)), float(opts.get('--end', 1e9))
rows = [r for r in rows if t0 <= float(r['t_s']) <= t1]
off = float(rows[0]['t_s'])
t  = [float(r['t_s']) - off for r in rows]
sc = [float(r['score']) for r in rows]
tr = [int(r['tier']) for r in rows]
br = [float(r['brightness_pct']) for r in rows]
bo = [int(r['breathing_open']) for r in rows]

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
    xmax = t[-1]
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
    a2.set_ylim(min(br) - 10, max(br) + 10); a2.set_yticks([round(min(br)), round(max(br))])
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
