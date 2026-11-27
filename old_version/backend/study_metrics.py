"""Standard HCI study instruments, ported from the webcam app
(HCI Mood assignment/backend/research_logger.py) so Aura Search sessions can be
scored the same way. Pure functions, no I/O.

* SUS        -- System Usability Scale, 10 items on 1..5 -> 0..100 (Brooke 1996).
* ISO 9241-11 -- efficiency and effectiveness proxies, 0..100.
* SAM        -- Self-Assessment Manikin, 1..9 (valence, arousal, dominance).
* NASA-TLX   -- raw (unweighted) subscales, here 1..7 for mental demand,
                frustration and effort (the three the webcam app used).
"""

SUS_ITEMS = (
    'I think that I would like to use this search often.',
    'I found the search unnecessarily complex.',
    'I thought the search was easy to use.',
    'I think that I would need the support of a technical person to use this search.',
    'I found the various parts of this search well integrated.',
    'I thought there was too much inconsistency in this search.',
    'I would imagine that most people would learn to use this search very quickly.',
    'I found the search very cumbersome to use.',
    'I felt very confident using the search.',
    'I needed to learn a lot of things before I could get going with this search.',
)


def compute_sus(answers):
    """10 item scores (1..5) -> SUS 0..100. Odd items positive, even items negative."""
    if len(answers) != 10:
        raise ValueError('SUS requires exactly 10 item scores (1..5).')
    total = 0
    for idx, raw in enumerate(answers):
        val = max(1, min(5, int(raw)))
        total += (val - 1) if idx % 2 == 0 else (5 - val)
    return round(total * 2.5, 1)


def compute_iso_metrics(completed, task_accuracy, error_count, time_sec, clicks, rage_clicks):
    """ISO 9241-11 efficiency and effectiveness (0..100), as in the webcam app.

    effectiveness = accuracy (x0.4 if not completed) - 5 per error
    efficiency    = 75 * 45/max(45, time) + 25 * 8/max(8, clicks) - 4 per rage click
    """
    acc = max(0.0, min(100.0, float(task_accuracy)))
    effectiveness = round(max(0.0, min(100.0, (acc if completed else acc * 0.4)
                                       - max(0, error_count) * 5.0)), 1)
    t_norm = 45.0 / max(45.0, float(time_sec))
    c_norm = 8.0 / max(8.0, float(clicks))
    efficiency = round(max(0.0, min(100.0, t_norm * 75.0 + c_norm * 25.0
                                    - max(0, rage_clicks) * 4.0)), 1)
    return efficiency, effectiveness


def sam_valence_to_unit(sam_valence):
    """SAM 1..9 -> -1..+1 (5 = neutral)."""
    return (max(1, min(9, int(sam_valence))) - 5.0) / 4.0


def compute_cv_sam_alignment(mean_valence, sam_valence):
    """Agreement (0..100%) between a sensed valence (-1..+1) and self-reported SAM."""
    return round(max(0.0, (1.0 - abs(float(mean_valence) - sam_valence_to_unit(sam_valence)) / 2.0) * 100.0), 1)


def stress_sam_alignment(mean_stress_0_100, sam_arousal):
    """Agreement (0..100%) between Aura's mean stress and SAM arousal (both scaled 0..1)."""
    s = max(0.0, min(100.0, float(mean_stress_0_100))) / 100.0
    a = (max(1, min(9, int(sam_arousal))) - 1) / 8.0
    return round((1.0 - abs(s - a)) * 100.0, 1)
