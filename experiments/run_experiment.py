"""
run_experiment.py -- instrument-characterisation experiment for Aura UI.

Protocol
--------
Four controlled input conditions are replayed through the REAL scoring path
(`run.StressEngine`, unchanged) and recorded with the REAL privacy-hardened
collector (`backend.research`). Nothing here bypasses the production code:

    condition features -> StressEngine.update() -> score/tier -> ResearchCollector

Conditions are presented in a balanced, seeded order (5 rounds x 4 conditions),
20 s per block at the app's own 333 ms polling rate.

Ground truth per tick is the condition label:
    REST, CALM -> Calm tier      MILD -> Mild tier      ELEV -> Elevated tier

Run:  python experiments/run_experiment.py
Requires: matplotlib
"""
import csv
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from backend import research
from run import StressEngine, Settings

OUT      = os.path.join(ROOT, 'Phase_2_Submission')
FIGDIR   = os.path.join(OUT, 'figures')
DATADIR  = os.path.join(OUT, 'data')
TICK     = 1.0 / 3.0          # 333 ms, matches AmbientApp.POLL_MS
BLOCK_S  = 20.0
ROUNDS   = 5
SEED     = 20261114
PARTICIPANT = 'VALIDATION-01'

# condition -> (keys/s, error rate, mean dwell s, mean flight s, CoV, mouse px/5s, clicks)
CONDITIONS = {
    'REST': dict(kps=0.0,  err=0.00, dwell=0.000, flight=0.000, cov=0.00, mouse=0.0,   clicks=0),
    'CALM': dict(kps=4.2,  err=0.02, dwell=0.095, flight=0.140, cov=0.22, mouse=1800.0, clicks=3),
    'MILD': dict(kps=5.6,  err=0.08, dwell=0.160, flight=0.100, cov=0.45, mouse=5200.0, clicks=9),
    'ELEV': dict(kps=7.8,  err=0.19, dwell=0.240, flight=0.070, cov=0.62, mouse=14000.0, clicks=24),
}
EXPECTED_TIER = {'REST': 0, 'CALM': 0, 'MILD': 1, 'ELEV': 2}
TIER_NAME     = ['Calm', 'Mild', 'Elevated']
COLORS        = {'REST': '#b8cfc6', 'CALM': '#7fae9d', 'MILD': '#d9a054', 'ELEV': '#c97070'}


def features_for(cond, rng):
    """Draw one noisy feature sample for a condition (the instrument's input)."""
    c = CONDITIONS[cond]
    j = lambda v, lo=0.0: max(lo, v * (1 + rng.uniform(-0.08, 0.08)))
    mean_flight = j(c['flight'])
    cov         = j(c['cov'])
    return {
        'keys_per_second': j(c['kps']),
        'error_rate':      min(1.0, j(c['err'])),
        'mean_dwell':      j(c['dwell']),
        'mean_flight':     mean_flight,
        'std_flight':      cov * mean_flight,
        'flight_count':    14 if cond != 'REST' else 0,
        'mouse_distance':  j(c['mouse']),
        'mouse_clicks':    int(j(c['clicks'])),
    }


def run_protocol():
    """Replay the balanced protocol through the production engine and collector."""
    rng = random.Random(SEED)
    # Reproducible run: withdraw (which purges) then re-consent, so the exported
    # dataset contains exactly this run and nothing stale.
    research.revoke_consent(purge=True)
    research.give_consent(PARTICIPANT, researcher='automated run',
                          note='instrument validation, synthetic input protocol')
    settings = Settings()
    engine   = StressEngine(settings)
    # Arms-length assessment: no per-person calibration, as on a fresh install.
    settings['baseline_cov'] = 0.0
    settings['baseline_err'] = 0.0

    order = []
    for _ in range(ROUNDS):
        block = list(CONDITIONS)
        rng.shuffle(block)
        order.extend(block)

    collector = research.ResearchCollector(PARTICIPANT, tick_hz=3.0,
                                           condition='controlled-protocol',
                                           instrument='Aura UI StressEngine v' + research.PROTOCOL_VERSION)
    ticks, blocks = [], []
    t = 0.0
    for cond in order:
        start = t
        n = int(round(BLOCK_S / TICK))
        for _ in range(n):
            feats = features_for(cond, rng)
            engine.update(feats)
            score, tier = engine.score, engine.tier
            ticks.append({'t': t, 'cond': cond, 'score': score, 'tier': tier,
                          'expected': EXPECTED_TIER[cond], 'feat': feats})
            collector.log_tick(t, score, tier, feats, brightness=None,
                               simulated=1, label=cond)
            t += TICK
        blocks.append({'cond': cond, 'start': start, 'end': t})

    stats = {
        'duration_s': t,
        'avg': statistics.mean([x['score'] for x in ticks]),
        'peak': max(x['score'] for x in ticks),
        'peak_at_s': max(ticks, key=lambda x: x['score'])['t'],
        'tier_s': [
            sum(TICK for x in ticks if x['tier'] == 0),
            sum(TICK for x in ticks if x['tier'] == 1),
            sum(TICK for x in ticks if x['tier'] == 2),
        ],
        'episodes': sum(1 for a, b in zip(ticks, ticks[1:])
                        if b['tier'] == 2 and a['tier'] != 2),
        'breathing': 0, 'held': 0, 'demo': False,
    }
    collector.set_self_report(stress=None, valence=None)
    collector.end(stats)
    path = collector.session_path
    collector.close()
    return ticks, blocks, path, stats


# ------------------------------------------------------------------ analysis

def analyse(ticks, blocks):
    out = {}
    by = {c: [x for x in ticks if x['cond'] == c] for c in CONDITIONS}

    # 1. score distribution per condition
    dist = {}
    for c, xs in by.items():
        s = [x['score'] for x in xs]
        dist[c] = {'n': len(s), 'mean': statistics.mean(s),
                   'sd': statistics.stdev(s) if len(s) > 1 else 0.0,
                   'median': statistics.median(s),
                   'p95': sorted(s)[max(0, int(0.95 * len(s)) - 1)],
                   'min': min(s), 'max': max(s)}
    out['score_by_condition'] = dist

    # 2. typing features recovered from the recorded tick stream
    feat = {}
    for c, xs in by.items():
        rows = [x['feat'] for x in xs]
        cov = [r['std_flight'] / r['mean_flight'] for r in rows
               if r['mean_flight'] > 0 and r['flight_count'] >= 3]
        feat[c] = {
            'kps': statistics.mean([r['keys_per_second'] for r in rows]),
            'err': statistics.mean([r['error_rate'] for r in rows]),
            'dwell_ms': 1000 * statistics.mean([r['mean_dwell'] for r in rows]),
            'cov': statistics.mean(cov) if cov else 0.0,
            'mouse_px': statistics.mean([r['mouse_distance'] for r in rows]),
            'clicks': statistics.mean([r['mouse_clicks'] for r in rows]),
        }
    out['features_by_condition'] = feat

    # 3. confusion: ground-truth condition vs predicted tier
    labels = ['REST', 'CALM', 'MILD', 'ELEV']
    conf = {c: [0, 0, 0] for c in labels}
    for x in ticks:
        conf[x['cond']][x['tier']] += 1
    out['confusion'] = conf
    correct = sum(1 for x in ticks if x['tier'] == x['expected'])
    out['accuracy'] = correct / len(ticks)
    out['n_ticks'] = len(ticks)
    # worst-case severity: Elevated ticks during rest/calm conditions
    out['false_elevated_rate'] = (
        sum(1 for x in ticks if x['cond'] in ('REST', 'CALM') and x['tier'] == 2)
        / max(1, sum(1 for x in ticks if x['cond'] in ('REST', 'CALM'))))
    out['elev_recall'] = (
        sum(1 for x in ticks if x['cond'] == 'ELEV' and x['tier'] == 2)
        / max(1, sum(1 for x in ticks if x['cond'] == 'ELEV')))

    # 4. latency to detect, and recovery time back to Calm
    lat, rec = [], []
    for i, b in enumerate(blocks):
        if b['cond'] == 'ELEV':
            hit = next((x['t'] for x in ticks
                        if b['start'] <= x['t'] < b['end'] and x['tier'] == 2), None)
            lat.append(round(hit - b['start'], 2) if hit is not None else None)
        if b['cond'] == 'REST' and i > 0 and blocks[i - 1]['cond'] == 'ELEV':
            hit = next((x['t'] for x in ticks
                        if b['start'] <= x['t'] < b['end'] and x['tier'] == 0), None)
            rec.append(round(hit - b['start'], 2) if hit is not None else None)
    out['latency_elev_s'] = lat
    out['recovery_calm_s'] = rec

    # 5. ROC of the raw score as an ELEV detector (vs REST+CALM)
    pos = [x['score'] for x in ticks if x['cond'] == 'ELEV']
    neg = [x['score'] for x in ticks if x['cond'] in ('REST', 'CALM')]
    sweep = []
    for th in [i for i in range(0, 101, 5)]:
        tp = sum(1 for s in pos if s >= th) / max(1, len(pos))
        fp = sum(1 for s in neg if s >= th) / max(1, len(neg))
        sweep.append({'th': th, 'tpr': tp, 'fpr': fp})
    # Operating point by Youden's J (sensitivity + specificity - 1) -- the
    # degenerate corner (th=100, TPR=FPR=0) must not win.
    best = max(sweep, key=lambda r: (r['tpr'] - r['fpr'], -r['th']))
    out['roc'] = sweep
    out['deployed_rule'] = next(p for p in sweep if p['th'] == 60)   # app's tier-2 cut
    # AUC by trapezoid over FPR-sorted points
    pts = sorted(sweep, key=lambda r: r['fpr'])
    auc = 0.0
    for a, b in zip(pts, pts[1:]):
        auc += (b['fpr'] - a['fpr']) * (a['tpr'] + b['tpr']) / 2
    out['auc'] = auc
    out['operating_point'] = best
    return out


# ------------------------------------------------------------------- figures

INK, MUT, GRID = '#2a1a1c', '#6b5d5f', '#e6e1e3'


def _style(ax):
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for sp in ('left', 'bottom'):
        ax.spines[sp].set_color('#bbb')
    ax.tick_params(colors=MUT, labelsize=9)
    ax.yaxis.label.set_color(INK)
    ax.xaxis.label.set_color(INK)


def fig_timeline(ticks, out):
    t = [x['t'] for x in ticks]
    s = [x['score'] for x in ticks]
    fig, ax = plt.subplots(figsize=(11, 3.8), dpi=200)
    for lo, hi, c in [(0, 30, '#7fae9d'), (30, 60, '#d9a054'), (60, 100, '#c97070')]:
        ax.axhspan(lo, hi, color=c, alpha=0.13, lw=0)
    i = 0
    while i < len(ticks):
        j = i
        while j + 1 < len(ticks) and ticks[j + 1]['cond'] == ticks[i]['cond']:
            j += 1
        ax.axvspan(ticks[i]['t'], ticks[j]['t'] + TICK, color=COLORS[ticks[i]['cond']],
                   alpha=0.10, lw=0)
        ax.text((ticks[i]['t'] + ticks[j]['t']) / 2, 97, ticks[i]['cond'],
                ha='center', va='top', fontsize=7, color=MUT, fontweight='bold')
        i = j + 1
    ax.plot(t, s, color='#8B1A1F', lw=1.6)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 30, 60, 100])
    ax.set_ylabel('Stress score')
    ax.set_xlabel('Time (s)')
    ax.set_title('Score response to controlled input conditions', fontsize=11,
                 fontweight='bold', color=INK, loc='left')
    _style(ax)
    fig.tight_layout()
    fig.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def fig_box(ticks, out):
    order = ['REST', 'CALM', 'MILD', 'ELEV']
    data = [[x['score'] for x in ticks if x['cond'] == c] for c in order]
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=200)
    for lo, hi, c in [(0, 30, '#7fae9d'), (30, 60, '#d9a054'), (60, 100, '#c97070')]:
        ax.axhspan(lo, hi, color=c, alpha=0.10, lw=0)
    bp = ax.boxplot(data, patch_artist=True, widths=0.55, showfliers=False,
                    medianprops=dict(color=INK, lw=1.4))
    for patch, c in zip(bp['boxes'], order):
        patch.set_facecolor(COLORS[c])
        patch.set_alpha(0.65)
        patch.set_edgecolor('#7a6e70')
    ax.set_xticklabels(order)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 30, 60, 100])
    ax.set_ylabel('Stress score')
    ax.set_title('Score distribution per condition', fontsize=11,
                 fontweight='bold', color=INK, loc='left')
    _style(ax)
    fig.tight_layout()
    fig.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def fig_confusion(conf, out):
    labels = ['REST', 'CALM', 'MILD', 'ELEV']
    m = [[conf[c][k] / max(1, sum(conf[c])) for k in range(3)] for c in labels]
    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=200)
    im = ax.imshow(m, cmap='BuPu', vmin=0, vmax=1, aspect='auto')
    ax.set_xticks(range(3)); ax.set_xticklabels(TIER_NAME)
    ax.set_yticks(range(4)); ax.set_yticklabels(labels)
    ax.set_xlabel('Predicted tier'); ax.set_ylabel('Input condition')
    for i in range(4):
        for k in range(3):
            pct = 100 * m[i][k]
            if pct >= 1:
                ax.text(k, i, '{:.0f}%'.format(pct), ha='center', va='center',
                        fontsize=9, color='white' if m[i][k] > 0.6 else INK,
                        fontweight='bold')
    ax.set_title('Tier prediction by condition', fontsize=11,
                 fontweight='bold', color=INK, loc='left')
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label='row proportion')
    fig.tight_layout()
    fig.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def fig_features(feat, out):
    metrics = [('kps', 'Keys / s'), ('err', 'Error rate'),
               ('dwell_ms', 'Mean dwell (ms)'), ('cov', 'Flight-time CoV')]
    order = ['REST', 'CALM', 'MILD', 'ELEV']
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.6), dpi=200)
    for ax, (key, label) in zip(axes.flat, metrics):
        vals = [feat[c][key] for c in order]
        ax.bar(range(4), vals, color=[COLORS[c] for c in order], alpha=0.8, width=0.6)
        ax.set_xticks(range(4)); ax.set_xticklabels(order, fontsize=8)
        ax.set_title(label, fontsize=9, color=INK, loc='left')
        ax.set_ylim(0, max(vals) * 1.25 or 1)
        _style(ax)
    fig.suptitle('Typing and mouse features per condition', fontsize=11,
                 fontweight='bold', color=INK, x=0.02, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def fig_roc(res, out):
    pts = sorted(res['roc'], key=lambda r: r['fpr'])
    fig, ax = plt.subplots(figsize=(4.4, 3.8), dpi=200)
    ax.plot([p['fpr'] for p in pts], [p['tpr'] for p in pts],
            color='#8B1A1F', lw=2, marker='o', ms=3)
    ax.plot([0, 1], [0, 1], '--', color='#bbb', lw=1)
    op = res['operating_point']
    ax.scatter([op['fpr']], [op['tpr']], s=60, color='#d9a054', zorder=5,
               edgecolor='white', lw=1.2)
    ax.annotate('score >= {}'.format(op['th']), (op['fpr'], op['tpr']),
                xytext=(8, -12), textcoords='offset points', fontsize=8, color=INK)
    ax.set_xlabel('False-positive rate'); ax.set_ylabel('True-positive rate')
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
    ax.set_title('Elevated detection ROC (AUC {:.3f})'.format(res['auc']),
                 fontsize=10, fontweight='bold', color=INK, loc='left')
    _style(ax)
    fig.tight_layout()
    fig.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ---------------------------------------------------------------------- main

def main():
    os.makedirs(FIGDIR, exist_ok=True)
    os.makedirs(DATADIR, exist_ok=True)

    ticks, blocks, session_path, stats = run_protocol()
    res = analyse(ticks, blocks)

    ok, msg = research.verify_session(session_path)
    res['integrity'] = {'ok': ok, 'message': msg, 'session': os.path.basename(session_path)}
    res['audit'] = research.audit()

    # Prove the minimisation contract: a disallowed field never reaches disk.
    probe = research.ResearchCollector(PARTICIPANT, condition='whitelist-probe')
    probe.log_tick(0.0, 10.0, 0, {'keys_per_second': 1.0, 'key_char': 'a',
                                  'window_title': 'secret.docx'})
    probe.end({'duration_s': 0.0, 'avg': 10.0, 'peak': 10.0, 'peak_at_s': 0.0,
               'tier_s': [0, 0, 0], 'episodes': 0, 'breathing': 0, 'held': 0})
    probe.close()
    with open(probe.session_path, encoding='utf-8') as f:
        body = f.read()
    res['minimisation'] = {
        'key_char_stored': 'key_char' in body,
        'window_title_stored': 'window_title' in body or 'secret.docx' in body,
        'keys_stored': sorted(json.loads(body.splitlines()[1]).get('feat', {}).keys()),
    }
    try:
        os.remove(probe.session_path)    # probe is a test artefact, not study data
    except OSError:
        pass

    exported = research.export_dataset(DATADIR)
    res['export'] = exported
    res['protocol'] = {
        'conditions': list(CONDITIONS),
        'block_s': BLOCK_S, 'rounds': ROUNDS, 'tick_s': round(TICK, 4),
        'seed': SEED, 'blocks': len(blocks), 'ticks': len(ticks),
        'duration_s': round(stats['duration_s'], 1),
        'order': [b['cond'] for b in blocks],
    }

    fig_timeline(ticks, os.path.join(FIGDIR, 'f1_protocol_timeline.png'))
    fig_box(ticks, os.path.join(FIGDIR, 'f2_score_by_condition.png'))
    fig_confusion(res['confusion'], os.path.join(FIGDIR, 'f3_confusion.png'))
    fig_features(res['features_by_condition'], os.path.join(FIGDIR, 'f4_typing_features.png'))
    fig_roc(res, os.path.join(FIGDIR, 'f5_roc.png'))

    with open(os.path.join(OUT, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2, sort_keys=True)

    # ---- console summary -------------------------------------------------
    print('session   :', session_path)
    print('integrity :', ok, msg)
    print('ticks     :', res['n_ticks'], ' blocks:', len(blocks))
    print('accuracy  : {:.1%}'.format(res['accuracy']))
    print('elev rec  : {:.1%}   false-elevated: {:.1%}'.format(
        res['elev_recall'], res['false_elevated_rate']))
    print('AUC       : {:.3f}  youden: score>={} (TPR {:.2f}, FPR {:.2f})'.format(
        res['auc'], res['operating_point']['th'],
        res['operating_point']['tpr'], res['operating_point']['fpr']))
    dr = res['deployed_rule']
    print('deployed  : score>=60 (tier-2 rule) TPR {:.2f}, FPR {:.2f}'.format(
        dr['tpr'], dr['fpr']))
    print('latency s :', res['latency_elev_s'])
    print('recovery s:', res['recovery_calm_s'])
    for c in CONDITIONS:
        d = res['score_by_condition'][c]
        print('  {:4s} mean {:5.1f} sd {:4.1f} median {:5.1f} p95 {:5.1f}'.format(
            c, d['mean'], d['sd'], d['median'], d['p95']))
    print('minimisation:', res['minimisation'])
    print('export    :', exported)


if __name__ == '__main__':
    main()
