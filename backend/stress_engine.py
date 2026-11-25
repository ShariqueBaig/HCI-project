"""Aura stress scoring engine (moved verbatim from run.py so the search
server and tests can import it without pulling in tkinter).

`settings` is anything with __getitem__ for the keys used below: run.Settings,
or a plain dict such as backend.stress_engine.DEFAULT_SETTINGS.
"""

CALM = '#7fae9d'
MILD = '#d9a054'
ELEV = '#c97070'

DEFAULT_SETTINGS = {
    'cov_weight': 0.65, 'error_weight': 0.35, 'smoothing': 0.18,
    'sensitivity': 1.0, 'decay_speed': 1.0,
    'bright_calm': 80, 'bright_mild': 65, 'bright_elev': 50,
    'temp_calm': 6500, 'temp_mild': 5000, 'temp_elev': 3500,
    'baseline_cov': 0.0, 'baseline_err': 0.0,
}


class StressEngine:
    TIER_LABELS = ['Calm', 'Mild', 'Elevated']
    TIER_COLORS = [CALM,   MILD,   ELEV]

    def __init__(self, settings):
        self.settings = settings
        self.smoothed = 10.0
        self._tier    = 0

    def update(self, features):
        kps = features.get('keys_per_second', 0)
        m_px = features.get('mouse_distance', 0)
        
        if kps < 0.2 and m_px < 3000:
            speed = self.settings['decay_speed']
            # Proportional + linear release so Elevated stress recovers in ~3-4s instead of 15.3s
            step = (self.smoothed * 0.14 + 2.2) * speed if self.smoothed > 10 else 0.4 * speed
            self.smoothed = max(0.0, self.smoothed - step)
            return
            
        mf  = features.get('mean_flight', 0)
        sf  = features.get('std_flight',  0)
        err = features.get('error_rate',  0)
        # Require ≥3 flight samples before trusting CoV — fewer samples produce
        # wildly unstable std/mean ratios right after resuming from a long pause.
        fc  = features.get('flight_count', 0)
        cov = min(sf / mf, 3.0) if (mf > 0 and fc >= 3) else 0

        cov_adj = max(0.0, cov - self.settings['baseline_cov'])
        err_adj = max(0.0, err - self.settings['baseline_err'])

        # Long press penalty: dwell times > 150ms indicate heavy/long presses.
        # Scales up to a 40% raw stress boost at 400ms dwell.
        md = features.get('mean_dwell', 0)
        dwell_penalty = min(max(0.0, md - 0.15) / 0.25, 1.0)

        # Mouse jitter penalty: Excessive mouse movement indicates agitation.
        # Rapid shaking > 10000px in 5s boosts stress heavily.
        mouse_penalty = min(max(0.0, m_px - 10000) / 6000.0, 1.0)

        cw    = self.settings['cov_weight']
        ew    = self.settings['error_weight']
        total = (cw + ew) or 1.0  
        raw_score = min(
            (cw / total) * min(cov_adj / 1.0, 1.0) +
            (ew / total) * min(err_adj / 0.15, 1.0) +
            0.4 * dwell_penalty +
            0.8 * mouse_penalty,
            1.0
        ) * self.settings['sensitivity']
        raw_score = min(raw_score, 1.0)

        alpha = self.settings['smoothing']
        raw   = 100.0 * (raw_score ** 1.1)
        self.smoothed = self.smoothed * (1 - alpha) + raw * alpha

    def inject_stress(self, level=82):
        self.smoothed = self.smoothed * 0.4 + level * 0.6

    @property
    def score(self):             return self.smoothed
    @property
    def tier(self):
        s = self.smoothed
        # Hysteresis prevents flickering around tier boundaries:
        # Enter Mild at >=30, exit at <26; enter Elevated at >=60, exit at <52.
        if self._tier == 2:
            if s < 26:
                self._tier = 0
            elif s < 52:
                self._tier = 1
        elif self._tier == 1:
            if s >= 60:
                self._tier = 2
            elif s < 26:
                self._tier = 0
        else:
            if s >= 60:
                self._tier = 2
            elif s >= 30:
                self._tier = 1
        return self._tier
    @property
    def label(self):             return self.TIER_LABELS[self.tier]
    @property
    def color(self):             return self.TIER_COLORS[self.tier]
    @property
    def target_brightness(self):
        keys = ['bright_calm', 'bright_mild', 'bright_elev']
        return int(self.settings[keys[self.tier]])

    @property
    def target_temp(self):
        keys = ['temp_calm', 'temp_mild', 'temp_elev']
        return int(self.settings[keys[self.tier]])
