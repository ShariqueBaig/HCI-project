"""Explain a fuse() decision: every rule, every condition, and how close each mood came.

The fusion model is a priority-ordered rule list (overwhelmed > disoriented >
fatigued > energized > focused). This module rebuilds that list from the same
inputs fuse() used, so the explanation can never drift from the decision:
for each mood it reports each clause ("any of these"), each condition inside
it ("all of these"), the live value, the threshold and whether it was met,
plus a 0..1 closeness score so the UI can show how near the other moods were.
"""

PRIORITY = ('overwhelmed', 'disoriented', 'fatigued', 'energized', 'focused')


def _cond(label, value, op, threshold, unit=''):
    """One condition. value None means the signal is unavailable (never met)."""
    if value is None:
        met, prog = False, 0.0
    elif op == '>=':
        met = value >= threshold
        prog = 1.0 if met else (max(0.0, value) / threshold if threshold > 0 else 0.0)
    elif op == '>':
        met = value > threshold
        prog = 1.0 if met else (max(0.0, value) / threshold if threshold > 0 else 0.0)
    elif op == '<':
        met = value < threshold
        prog = 1.0 if met else (threshold / value if value > 0 else 0.0)
    elif op == 'is':
        met = bool(value) == bool(threshold)
        prog = 1.0 if met else 0.0
    else:
        raise ValueError(op)
    v = value if not isinstance(value, float) else round(value, 3)
    return {'label': label, 'value': v, 'op': op, 'threshold': threshold, 'unit': unit,
            'met': bool(met), 'progress': round(max(0.0, min(1.0, prog)), 3)}


def _clause(name, conds):
    met = all(c['met'] for c in conds)
    # a clause is only as close as its weakest condition (all must hold)
    closeness = min(c['progress'] for c in conds) if conds else 0.0
    return {'name': name, 'conditions': conds, 'met': met, 'closeness': round(closeness, 3)}


def explain(*, state, stress, tier, blocking, friction, hes, refs, typing_fresh, kps, dwell, err,
            cam, val, aro, load, parts,
            fatigued_kps_max=1.6, fatigued_dwell_min=0.14, energized_kps_min=4.0):
    """Build the explanation dict attached to fuse() output as `xai`."""
    s = stress
    cam_on = bool(cam)
    rules = {
        'overwhelmed': [
            _clause('High stress', [_cond('Fused stress', s, '>=', 60, '/100')]),
            _clause('Rising stress + friction', [_cond('Fused stress', s, '>=', 45, '/100'),
                                                 _cond('Rapid clicks / back-outs', friction, '>=', 2)]),
            _clause("Aura's Focus mode active", [_cond('Aura tier', tier, '>=', 2),
                                                 _cond('Notifications held', blocking, 'is', True)]),
            _clause('Tense face + stress', [_cond('Camera on', cam_on, 'is', True),
                                            _cond('Fused stress', s, '>=', 35, '/100'),
                                            _cond('Cognitive load (camera)', load if cam_on else None, '>=', 0.72)]),
        ],
        'disoriented': [
            _clause('Reworded searches', [_cond('Reformulations (3 min)', refs, '>=', 2)]),
            _clause('Interaction uncertainty', [_cond('Hesitations / scroll thrash', hes, '>=', 2),
                                                _cond('Fused stress', s, '<', 60, '/100')]),
        ],
        'fatigued': [
            _clause('Slow, heavy typing', [_cond('Query typing is fresh', typing_fresh, 'is', True),
                                           _cond('Fused stress', s, '<', 45, '/100'),
                                           _cond('Typing tempo', kps if typing_fresh else None, '<', fatigued_kps_max, 'keys/s'),
                                           _cond('Key hold time', dwell if typing_fresh else None, '>', fatigued_dwell_min, 's')]),
            _clause('Tired face', [_cond('Camera on', cam_on, 'is', True),
                                   _cond('Fused stress', s, '<', 45, '/100'),
                                   _cond('Mood (camera, negative = low)', -val if cam_on else None, '>', 0.18),
                                   _cond('Energy (camera, negative = low)', -aro if cam_on else None, '>', 0.20)]),
        ],
        'energized': [
            _clause('Fast, accurate typing', [_cond('Query typing is fresh', typing_fresh, 'is', True),
                                              _cond('Fused stress', s, '<', 30, '/100'),
                                              _cond('Typing tempo', kps if typing_fresh else None, '>=', energized_kps_min, 'keys/s'),
                                              _cond('Typo rate', err if typing_fresh else None, '<', 0.08)]),
            _clause('Upbeat face', [_cond('Camera on', cam_on, 'is', True),
                                    _cond('Fused stress', s, '<', 30, '/100'),
                                    _cond('Mood (camera)', val if cam_on else None, '>=', 0.32),
                                    _cond('Energy (camera)', aro if cam_on else None, '>=', 0.15)]),
        ],
    }
    # the 'tense face' clause also accepts negative valence + high arousal; fold it in
    if cam_on and val is not None and val < -0.28 and aro > 0.22 and s is not None and s >= 35:
        c = rules['overwhelmed'][3]
        c['conditions'][2] = _cond('Tense expression (camera)', True, 'is', True)
        c['met'] = all(x['met'] for x in c['conditions'])

    moods = []
    for name in PRIORITY[:-1]:
        clauses = rules[name]
        matched = any(c['met'] for c in clauses)
        closeness = max(c['closeness'] for c in clauses)
        moods.append({'state': name, 'clauses': clauses, 'matched': matched,
                      'closeness': round(1.0 if matched else closeness, 3)})
    others = max(m['closeness'] for m in moods)
    focused_ok = s is not None and not any(m['matched'] for m in moods)
    moods.append({'state': 'focused', 'matched': focused_ok or s is None,
                  'closeness': round(1.0 if focused_ok else max(0.0, 1.0 - others), 3),
                  'clauses': [_clause('Nothing else fired (default)',
                                      [_cond('No higher-priority rule matched', focused_ok, 'is', True)])]})
    for m in moods:
        m['chosen'] = m['state'] == state
        m['priority'] = PRIORITY.index(m['state']) + 1

    total_w = sum(w for _, w, _ in parts)
    breakdown = [{'source': src, 'value': round(v, 1), 'weight': w,
                  'share': round(w / total_w, 3) if total_w else 0.0} for v, w, src in parts]
    return {
        'model': 'priority rule list over fused signals (deterministic)',
        'priority': list(PRIORITY),
        'moods': moods,
        'stress_fusion': {'parts': breakdown, 'fused': round(s, 1) if s is not None else None,
                          'formula': 'weighted mean: aura x1.0 + query typing x0.6'},
    }
