#!/usr/bin/env python3
"""
Aura UI -- background stress monitor
Run: python run.py
  Opens the desktop widget
"""
import sys, os, threading, time, json, csv, random
import tkinter as tk

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))

from backend.telemetry_daemon import TelemetryDaemon
from backend.os_controller import OSController
from backend.spotify_controller import SpotifyController
from backend.llm_controller import LLMController, OPENER
from backend import journal as journal_store

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_OK = True
except ImportError:
    TRAY_OK = False

# palette
BG     = '#0b0a10'
SURF   = '#15131d'
BORDER = '#2b263b'
TEXT   = '#e8e6ed'
MUTED  = '#9d98ab'
FAINT  = '#3a3550'
CALM   = '#7fae9d'
MILD   = '#d9a054'
ELEV   = '#c97070'

SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
DEFAULTS = {
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
    'baseline_cov': 0.0,   # calibrated resting CoV
    'baseline_err': 0.0,   # calibrated resting error rate
    'is_calibrated': 0,    # 0 = never done, 1 = done
}

class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE) as f:
                    self.data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def __getitem__(self, k):      return self.data[k]
    def __setitem__(self, k, v):   self.data[k] = v; self.save()


class StressEngine:
    TIER_LABELS = ['Calm', 'Mild', 'Elevated']
    TIER_COLORS = [CALM,   MILD,   ELEV]

    def __init__(self, settings):
        self.settings = settings
        self.smoothed = 10.0

    def update(self, features):
        kps = features.get('keys_per_second', 0)
        m_px = features.get('mouse_distance', 0)
        
        if kps < 0.2 and m_px < 3000:
            decay = self.settings['decay_speed']*1.5
            self.smoothed = max(0.0, self.smoothed - (decay if self.smoothed > 10 else decay * 0.2))
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
        if self.smoothed < 30: return 0
        if self.smoothed < 60: return 1
        return 2
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


class BreathingPopup:
    """Animated physiological sighing guide shown when stress is Elevated.
    Pattern: inhale (1.5s) → short top-up inhale (0.5s) → long exhale (6s).
    """
    PHASES = [
        ('Inhale',         1.5, CALM),   # first deep inhale — circle grows
        ('Inhale again',   0.5, CALM),   # short top-up — circle grows a bit more
        ('Exhale slowly',  6.0, MUTED),  # long slow exhale — circle shrinks
    ]
    CYCLES = 3   # auto-close after this many full breath cycles
    TICK   = 50  # ms between animation frames

    def __init__(self, parent):
        self._running = True
        self._phase   = 0
        self._elapsed = 0.0
        self._cycles  = 0

        win = tk.Toplevel(parent)
        win.title('Breathe')
        win.configure(bg=BG)
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.protocol('WM_DELETE_WINDOW', self.close)
        self._win = win

        tk.Label(win, text='Physiological sigh  ·  double inhale, long exhale',
                 bg=BG, fg=MUTED, font=('Arial', 8, 'italic')).pack(pady=(14, 0))

        self._canvas = tk.Canvas(win, width=220, height=220,
                                 bg=BG, highlightthickness=0)
        self._canvas.pack()

        self._phase_lbl = tk.Label(win, text='', bg=BG, fg=TEXT,
                                   font=('Georgia', 15))
        self._phase_lbl.pack(pady=(0, 2))

        self._time_lbl = tk.Label(win, text='', bg=BG, fg=MUTED,
                                  font=('Arial', 9))
        self._time_lbl.pack()

        tk.Button(win, text='Dismiss', command=self.close,
                  bg=SURF, fg=MUTED, relief='flat', font=('Arial', 9),
                  activebackground=BORDER, cursor='hand2', pady=4
                  ).pack(fill='x', padx=30, pady=(14, 18))

        # Center on screen
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry('+{}+{}'.format((sw - ww) // 2, (sh - wh) // 2))

        self._animate()

    def _animate(self):
        if not self._running:
            return
        name, dur, color = self.PHASES[self._phase]
        progress = min(self._elapsed / dur, 1.0)

        # R_MID is the size after the first inhale; R_MAX after the top-up
        R_MIN, R_MID, R_MAX, cx, cy = 28, 80, 92, 110, 110
        if name == 'Inhale':
            r = R_MIN + (R_MID - R_MIN) * progress
        elif name == 'Inhale again':
            r = R_MID + (R_MAX - R_MID) * progress
        else:  # Exhale slowly
            r = R_MAX - (R_MAX - R_MIN) * progress

        c = self._canvas
        c.delete('all')
        # soft glow ring
        c.create_oval(cx-r-10, cy-r-10, cx+r+10, cy+r+10,
                      outline=color, width=1)
        # main circle
        c.create_oval(cx-r, cy-r, cx+r, cy+r,
                      fill=color, outline='')
        # Soft rounded-rect pill behind the label.
        # Width adapts so 'Exhale slowly' is fully contained.
        pill_hw = 60 if name == 'Exhale slowly' else 46
        pill_hh, cr = 11, 8   # half-height, corner radius
        px1, py1 = cx - pill_hw, cy - pill_hh
        px2, py2 = cx + pill_hw, cy + pill_hh
        kw = dict(fill=color, outline='')
        c.create_arc(px1,        py1,        px1+2*cr, py1+2*cr, start= 90, extent=90, style='pieslice', **kw)
        c.create_arc(px2-2*cr,   py1,        px2,      py1+2*cr, start=  0, extent=90, style='pieslice', **kw)
        c.create_arc(px1,        py2-2*cr,   px1+2*cr, py2,      start=180, extent=90, style='pieslice', **kw)
        c.create_arc(px2-2*cr,   py2-2*cr,   px2,      py2,      start=270, extent=90, style='pieslice', **kw)
        c.create_rectangle(px1+cr, py1, px2-cr, py2, **kw)   # horizontal fill
        c.create_rectangle(px1, py1+cr, px2, py2-cr, **kw)   # vertical fill
        c.create_text(cx, cy, text=name, fill=BG,
                      font=('Georgia', 12, 'bold'))

        self._phase_lbl.config(text=name, fg=color)
        self._time_lbl.config(text='{}s'.format(int(dur - self._elapsed) + 1))

        self._elapsed += self.TICK / 1000.0
        if self._elapsed >= dur:
            self._elapsed = 0.0
            self._phase   = (self._phase + 1) % len(self.PHASES)
            if self._phase == 0:
                self._cycles += 1
                if self._cycles >= self.CYCLES:
                    self.close()
                    return

        self._win.after(self.TICK, self._animate)

    def alive(self):
        try:
            return self._running and self._win.winfo_exists()
        except Exception:
            return False

    def close(self):
        self._running = False
        try:
            self._win.destroy()
        except Exception:
            pass


class SessionStats:
    """Aggregate numbers for the journal -- no keystroke content."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.start     = time.time()
        self._last     = self.start
        self.tier_s    = [0.0, 0.0, 0.0]
        self._score_s  = 0.0
        self._total_s  = 0.0
        self.peak      = 0.0
        self.peak_at   = 0.0
        self.episodes  = 0
        self._prev     = 0
        self.breathing = 0
        self.held      = 0
        self.delivered = 0
        self.demo      = False

    def tick(self, score, tier, demo=False):
        now = time.time()
        dt = min(now - self._last, 2.0)
        self._last = now
        self.tier_s[tier] += dt
        self._score_s += score * dt
        self._total_s += dt
        if score > self.peak:
            self.peak, self.peak_at = score, now - self.start
        if tier == 2 and self._prev != 2:
            self.episodes += 1
        self._prev = tier
        self.demo = self.demo or demo

    def summary(self):
        return {'duration_s': time.time() - self.start,
                'avg': self._score_s / self._total_s if self._total_s else 0.0,
                'peak': self.peak, 'peak_at_s': self.peak_at,
                'tier_s': list(self.tier_s), 'episodes': self.episodes,
                'breathing': self.breathing, 'held': self.held,
                'delivered': self.delivered, 'demo': self.demo}


_toasts = []   # live toast windows, for stacking

def show_toast(root, title, text, kind='delivered', ms=3800):
    """Small always-on-top card, bottom-right. kind: delivered | blocked | digest."""
    accent, tag = {'delivered': (CALM, 'Delivered'),
                   'blocked':   (ELEV, 'Held back by Focus mode'),
                   'digest':    (MILD, 'Focus summary')}[kind]
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes('-topmost', True)
    win.configure(bg=accent)
    body = tk.Frame(win, bg=SURF)
    body.pack(fill='both', expand=True, padx=(5, 0))
    tk.Label(body, text=tag, bg=SURF, fg=accent,
             font=('Arial', 7, 'bold')).pack(anchor='w', padx=10, pady=(6, 0))
    tk.Label(body, text=title, bg=SURF, fg=TEXT if kind != 'blocked' else MUTED,
             font=('Arial', 10, 'bold')).pack(anchor='w', padx=10)
    tk.Label(body, text=text, bg=SURF, fg=MUTED, wraplength=270, justify='left',
             font=('Arial', 9)).pack(anchor='w', padx=10, pady=(0, 8))
    win.update_idletasks()
    w, h = 300, win.winfo_reqheight()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    y = sh - 110 - sum(t.winfo_reqheight() + 8 for t in _toasts if t.winfo_exists()) - h
    win.geometry('{}x{}+{}+{}'.format(w, h, sw - w - 20, max(20, y)))
    _toasts.append(win)

    def close():
        try: win.destroy()
        except Exception: pass
        if win in _toasts: _toasts.remove(win)
    win.after(ms, close)


class AmbientApp:
    POLL_MS = 333
    DEMO_NOTIFS = [('Slack', 'Ahmed: are you free for a quick call?'),
                   ('Mail', 'Your order has shipped'),
                   ('WhatsApp', 'Mum: dinner at 8?'),
                   ('Calendar', 'Team meeting in 10 minutes'),
                   ('Instagram', '12 new likes on your photo'),
                   ('Teams', 'New message in #project-hci')]

    def __init__(self):
        self.settings       = Settings()
        self.daemon         = TelemetryDaemon(window_size_seconds=5)
        self.os_ctrl        = OSController()
        self.engine         = StressEngine(self.settings)
        self._running            = True
        self._sim_ticks          = 0
        self._last_bright        = 100
        self._settings_win       = None
        self._breathing_popup    = None
        self._last_popup_time    = 0.0
        self.tray                = None
        # Spotify
        self.spotify             = SpotifyController()
        self._track_cache        = None
        self._sp_auto_vol        = False
        self._sp_saved_vol       = None
        self._vol_target         = None   # set by _refresh when auto_music is on
        self._vol_current        = None   # tracked by _spotify_loop for ramping
        # Calibration
        self._calibrating        = False
        self._calib_samples      = []    # list of (cov, err)
        self._calib_start        = 0.0
        self.CALIB_DURATION      = 30.0  # seconds
        self._dnd_active         = False # tracks notification muting
        # Focus mode / notifications / journal
        self.stats               = SessionStats()
        self._held               = []    # notifications held back while Elevated
        self._notif_n            = 0
        self._journal_win        = None
        self._demo_stage_start   = 0.0
        self._demo_fired         = 0
        # Aura chat (OpenRouter)
        self.llm                 = LLMController()
        self._chat_gen           = 0     # bumped when a chat is dismissed/restarted
        self._elevated_since     = None
        self._last_checkin       = 0.0
        # Demo mode (scripted presentation)
        self._demo_target        = None   # stress score the demo is steering toward
        self._demo_script        = []     # [(label, score, seconds, note)]
        self._demo_idx           = -1
        self._demo_end           = 0.0
        self._demo_win           = None
        self._demo_status        = None
        self._demo_note          = None
        # Session recording (CSV of numeric features only -- no keystroke content)
        self._log_fh             = None
        self._log_writer         = None
        self._log_start          = 0.0
        self._build_window()

    # ------- window ----------------------------------------------------------

    def _build_window(self):
        r = tk.Tk()
        r.title('Aura UI')
        r.configure(bg=BG)
        r.resizable(False, False)
        r.protocol('WM_DELETE_WINDOW', self._hide)
        self.root = r
        self.auto_bright = tk.BooleanVar(value=True)
        self.always_top  = tk.BooleanVar(value=False)
        self.always_top.trace_add('write', self._on_topmost)
        # two columns so the whole app fits on a laptop screen
        self._left  = tk.Frame(r, bg=BG)
        self._right = tk.Frame(r, bg=BG, width=300)
        self._left.pack(side='left', anchor='n')
        tk.Frame(r, bg=BORDER, width=1).pack(side='left', fill='y', pady=14)
        self._right.pack(side='left', anchor='n', fill='y')
        self._build_header()
        self._build_gauge()
        self._build_stats()
        self._build_controls()
        self._build_focus()
        self._build_music()
        self._build_chat()
        r.geometry('+80+80')

    def _build_header(self):
        row = tk.Frame(self._left, bg=BG)
        row.pack(fill='x', padx=20, pady=(14, 0))
        tk.Label(row, text='Aura UI', bg=BG, fg=TEXT,
                 font=('Georgia', 16)).pack(side='left')
        tk.Checkbutton(row, text='top', variable=self.always_top,
                       bg=BG, fg=FAINT, selectcolor=SURF,
                       activebackground=BG, activeforeground=CALM,
                       font=('Arial', 8), bd=0).pack(side='right', pady=4)
        self.dot = tk.Label(row, text='●', bg=BG, fg=CALM, font=('Arial', 10))
        self.dot.pack(side='right', pady=5, padx=2)
        tk.Label(self._left, text='background stress monitor  ·  Aura UI',
                 bg=BG, fg=MUTED, font=('Arial', 8)).pack(anchor='w', padx=20)

    def _build_gauge(self):
        self.canvas = tk.Canvas(self._left, width=180, height=155,
                                bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(10, 0))
        self._draw_gauge(0, CALM)
        self.tier_lbl = tk.Label(self._left, text='Calm', bg=BG, fg=CALM,
                                  font=('Georgia', 12, 'italic'))
        self.tier_lbl.pack(pady=(2, 8))

    def _draw_gauge(self, score, color):
        c = self.canvas
        c.delete('all')
        cx, cy, r = 90, 78, 60
        c.create_arc(cx-r, cy-r, cx+r, cy+r,
                     start=-45, extent=270, outline=FAINT, width=9, style='arc')
        if score > 0.5:
            ext = (score / 100.0) * 270
            c.create_arc(cx-r, cy-r, cx+r, cy+r,
                         start=-45, extent=ext, outline=color, width=9, style='arc')
        if self._sim_ticks > 0:
            c.create_text(cx, cy-22, text='SIM', fill=MILD, font=('Arial', 7, 'bold'))
        # Consolas has tabular (monospace) digits — prevents vertical jitter
        # as the number changes, unlike proportional fonts like Georgia.
        c.create_text(cx, cy-4,  text=str(int(score)), fill=TEXT,  font=('Consolas', 28, 'bold'))
        c.create_text(cx, cy+20, text='/ 100',         fill=MUTED, font=('Arial', 8))

    def _build_stats(self):
        f = tk.Frame(self._left, bg=SURF,
                     highlightbackground=BORDER, highlightthickness=1)
        f.pack(fill='x', padx=20, pady=(0, 8))
        self._sv = {}
        for idx, (lbl, key) in enumerate([('keys / s','kps'),('error rate','err'),
                                           ('dwell ms','dwell'),('flight ms','flight'),
                                           ('mouse px', 'mouse_px'), ('clicks', 'mouse_clicks')]):
            row, col = divmod(idx, 2)
            cell = tk.Frame(f, bg=SURF, padx=10, pady=6)
            cell.grid(row=row, column=col, sticky='nsew')
            f.columnconfigure(col, weight=1)
            tk.Label(cell, text=lbl, bg=SURF, fg=MUTED, font=('Arial', 7)).pack(anchor='w')
            v = tk.StringVar(value='--')
            self._sv[key] = v
            tk.Label(cell, textvariable=v, bg=SURF, fg=TEXT,
                     font=('Arial', 12, 'bold')).pack(anchor='w')

    def _build_controls(self):
        row = tk.Frame(self._left, bg=BG)
        row.pack(fill='x', padx=20, pady=(0, 2))
        tk.Label(row, text='Brightness', bg=BG, fg=MUTED, font=('Arial', 8)).pack(side='left')
        self.bright_var = tk.StringVar(value='--')
        tk.Label(row, textvariable=self.bright_var, bg=BG, fg=TEXT,
                 font=('Arial', 8, 'bold')).pack(side='right')

        row2 = tk.Frame(self._left, bg=BG)
        row2.pack(fill='x', padx=18, pady=(0, 6))
        tk.Checkbutton(row2, text='Auto-adjust brightness', variable=self.auto_bright,
                       bg=BG, fg=MUTED, selectcolor=SURF, activebackground=BG,
                       font=('Arial', 8)).pack(side='left')
        self.record_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row2, text='Record session', variable=self.record_var,
                       command=self._toggle_record,
                       bg=BG, fg=MUTED, selectcolor=SURF, activebackground=BG,
                       font=('Arial', 8)).pack(side='right')

        btn_row = tk.Frame(self._left, bg=BG)
        btn_row.pack(fill='x', padx=20, pady=(0, 4))
        self.sim_btn = tk.Button(btn_row, text='Simulate Stress',
                                  command=self._simulate,
                                  bg=SURF, fg=MILD, relief='flat',
                                  font=('Arial', 9), activebackground=BORDER,
                                  activeforeground=ELEV, cursor='hand2', pady=4)
        self.sim_btn.pack(side='left', fill='x', expand=True, padx=(0, 4))
        tk.Button(btn_row, text='Demo',
                  command=self._open_demo,
                  bg=SURF, fg=CALM, relief='flat',
                  font=('Arial', 9), activebackground=BORDER,
                  activeforeground=TEXT, cursor='hand2', pady=4).pack(side='right', padx=(0, 4))
        tk.Button(btn_row, text='Settings',
                  command=self._open_settings,
                  bg=SURF, fg=MUTED, relief='flat',
                  font=('Arial', 9), activebackground=BORDER,
                  activeforeground=TEXT, cursor='hand2', pady=4).pack(side='right')

        # Calibration row
        cal_row = tk.Frame(self._left, bg=BG)
        cal_row.pack(fill='x', padx=20, pady=(0, 10))
        calib_color = MUTED if self.settings['is_calibrated'] else ELEV
        self._calib_btn = tk.Button(cal_row, text='Calibrate',
                                    command=self._start_calibration,
                                    bg=SURF, fg=calib_color, relief='flat',
                                    font=('Arial', 9), activebackground=BORDER,
                                    cursor='hand2', pady=4)
        self._calib_btn.pack(side='left', fill='x', expand=True, padx=(0, 4))
        status = '✓ Calibrated' if self.settings['is_calibrated'] else 'Not calibrated'
        self._calib_lbl = tk.Label(cal_row, text=status, bg=BG,
                                   fg=MUTED if self.settings['is_calibrated'] else ELEV,
                                   font=('Arial', 8))
        self._calib_lbl.pack(side='right')

    # ------- focus mode ------------------------------------------------------

    def _build_focus(self):
        tk.Frame(self._right, bg=BORDER, height=1).pack(fill='x', padx=20, pady=(2, 6))
        wrap = tk.Frame(self._right, bg=BG)
        wrap.pack(fill='x', padx=20, pady=(0, 4))
        self.focus_mode = tk.BooleanVar(value=True)
        top = tk.Frame(wrap, bg=BG)
        top.pack(fill='x')
        tk.Checkbutton(top, text='Focus mode', variable=self.focus_mode,
                       bg=BG, fg=TEXT, selectcolor=SURF, activebackground=BG,
                       font=('Arial', 9, 'bold')).pack(side='left')
        self._focus_state = tk.Label(top, text='standing by', bg=BG, fg=MUTED,
                                     font=('Arial', 8))
        self._focus_state.pack(side='right')
        tk.Label(wrap, text='Holds back notifications while stress is Elevated, '
                 'then shows a summary when you calm down.',
                 bg=BG, fg=FAINT, font=('Arial', 7), wraplength=250,
                 justify='left').pack(anchor='w')
        row = tk.Frame(wrap, bg=BG)
        row.pack(fill='x', pady=(4, 0))
        self._notif_lbl = tk.Label(row, text='Delivered 0  ·  Held back 0', bg=BG,
                                   fg=MUTED, font=('Arial', 8))
        self._notif_lbl.pack(side='left')
        tk.Button(row, text='Journal', command=self._open_journal, bg=SURF, fg=CALM,
                  relief='flat', font=('Arial', 8), activebackground=BORDER,
                  cursor='hand2').pack(side='right')
        tk.Button(row, text='Test notification', command=self._send_test_notif, bg=SURF,
                  fg=MUTED, relief='flat', font=('Arial', 8), activebackground=BORDER,
                  cursor='hand2').pack(side='right', padx=(0, 4))

    def _blocking(self):
        return self.focus_mode.get() and self.engine.tier == 2

    def notify(self, app, text):
        """A (simulated) incoming notification: held back in focus mode, else delivered."""
        if self._blocking():
            self._held.append(app)
            self.stats.held += 1
            show_toast(self.root, app, text, 'blocked')
        else:
            self.stats.delivered += 1
            show_toast(self.root, app, text, 'delivered')
        self._update_notif_lbl()

    def _send_test_notif(self):
        app, text = self.DEMO_NOTIFS[self._notif_n % len(self.DEMO_NOTIFS)]
        self._notif_n += 1
        self.notify(app, text)

    def _update_notif_lbl(self):
        self._notif_lbl.config(text='Delivered {}  ·  Held back {}'.format(
            self.stats.delivered, self.stats.held))

    def _release_held(self):
        n = len(self._held)
        if n:
            names = ', '.join(dict.fromkeys(self._held))
            show_toast(self.root, '{} notification{} held back'.format(n, '' if n == 1 else 's'),
                       'While you were stressed: ' + names, 'digest', ms=6000)
        self._held = []

    def _start_breathing(self):
        self._last_popup_time = time.time()
        self._breathing_popup = BreathingPopup(self.root)
        self.stats.breathing += 1

    # ------- journal ---------------------------------------------------------

    def _open_journal(self):
        if self._journal_win and self._journal_win.winfo_exists():
            self._journal_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title('Aura UI  -  Journal')
        win.configure(bg=BG)
        win.resizable(False, False)
        self._journal_win = win
        tk.Label(win, text='Session journal', bg=BG, fg=TEXT,
                 font=('Georgia', 13)).pack(anchor='w', padx=16, pady=(14, 0))
        self._j_stats = tk.Label(win, text='', bg=BG, fg=MUTED, justify='left',
                                 font=('Arial', 8))
        self._j_stats.pack(anchor='w', padx=16, pady=(2, 8))

        tk.Label(win, text='How did this session feel? (optional)', bg=BG, fg=MUTED,
                 font=('Arial', 8)).pack(anchor='w', padx=16)
        tk_kw = dict(bg=SURF, fg=TEXT, relief='flat', wrap='word', font=('Arial', 9),
                     highlightbackground=BORDER, highlightthickness=1, padx=8, pady=6,
                     insertbackground=TEXT)
        self._j_note = tk.Text(win, height=3, width=48, **tk_kw)
        self._j_note.pack(padx=16, pady=(2, 8))

        btns = tk.Frame(win, bg=BG)
        btns.pack(fill='x', padx=16)
        self._j_reflect_btn = tk.Button(btns, text='Reflect with Aura', command=self._journal_reflect,
                                        bg=SURF, fg=CALM, relief='flat', font=('Arial', 9),
                                        activebackground=BORDER, cursor='hand2', pady=4)
        self._j_reflect_btn.pack(side='left', fill='x', expand=True, padx=(0, 4))
        tk.Button(btns, text='Save entry', command=self._journal_save, bg=SURF, fg=TEXT,
                  relief='flat', font=('Arial', 9), activebackground=BORDER,
                  cursor='hand2', pady=4).pack(side='left', fill='x', expand=True)

        self._j_refl = tk.Text(win, height=6, width=48, state='disabled', **tk_kw)
        self._j_refl.pack(padx=16, pady=(8, 8))

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x', padx=16)
        tk.Label(win, text='Past entries', bg=BG, fg=MUTED, font=('Arial', 8)
                 ).pack(anchor='w', padx=16, pady=(6, 2))
        self._j_list = tk.Listbox(win, height=4, bg=SURF, fg=TEXT, relief='flat',
                                  selectbackground=BORDER, highlightthickness=1,
                                  highlightbackground=BORDER, font=('Arial', 9),
                                  exportselection=False)
        self._j_list.pack(fill='x', padx=16)
        self._j_list.bind('<<ListboxSelect>>', self._journal_view)
        tk.Button(win, text='Close', command=win.destroy, bg=SURF, fg=MUTED, relief='flat',
                  font=('Arial', 9), activebackground=BORDER, cursor='hand2',
                  pady=4).pack(fill='x', padx=16, pady=(10, 14))

        self._journal_entries = []
        self._j_reflection = ''
        self._journal_refresh()
        win.geometry('+{}+{}'.format(self.root.winfo_x() + self.root.winfo_width() + 8,
                                     self.root.winfo_y()))

    def _journal_set_refl(self, text):
        self._j_refl.config(state='normal')
        self._j_refl.delete('1.0', 'end')
        self._j_refl.insert('1.0', text)
        self._j_refl.config(state='disabled')

    def _journal_refresh(self):
        self._j_stats.config(text=journal_store.stats_text(self.stats.summary()))
        self._journal_entries = journal_store.load()
        self._j_list.delete(0, 'end')
        for e in reversed(self._journal_entries):
            self._j_list.insert('end', '{}  ·  peak {:.0f}  ·  {}{}'.format(
                e.get('time', '?'), e['stats']['peak'],
                journal_store.fmt_duration(e['stats']['duration_s']),
                '  (demo)' if e['stats'].get('demo') else ''))

    def _journal_reflect(self):
        s = self.stats.summary()
        note = self._j_note.get('1.0', 'end')
        self._j_reflect_btn.config(state='disabled', text='Aura is writing...')
        self._journal_set_refl('')

        def work():
            try:
                text = self.llm.generate(journal_store.reflect_prompt(s, note),
                                         journal_store.REFLECT_SYSTEM)
            except Exception as e:
                print('[Aura UI] reflection fallback:', e)
                text = journal_store.local_reflection(s)
            def done():
                if not (self._journal_win and self._journal_win.winfo_exists()):
                    return
                self._j_reflection = text
                self._journal_set_refl(text)
                self._j_reflect_btn.config(state='normal', text='Reflect with Aura')
            self.root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def _journal_save(self):
        s = self.stats.summary()
        entry = {'time': time.strftime('%d %b %H:%M'), 'stats': s,
                 'note': self._j_note.get('1.0', 'end').strip(),
                 'reflection': self._j_reflection or journal_store.local_reflection(s)}
        try:
            journal_store.add(entry)
        except OSError as e:
            print('[Aura UI] could not save journal:', e)
            return
        self.stats.reset()
        self._update_notif_lbl()
        self._j_note.delete('1.0', 'end')
        self._j_reflection = ''
        self._journal_set_refl('Saved. A fresh session has started.')
        self._journal_refresh()

    def _journal_view(self, _event=None):
        sel = self._j_list.curselection()
        if not sel:
            return
        e = list(reversed(self._journal_entries))[sel[0]]
        text = e['reflection']
        if e.get('note'):
            text = 'Your note: ' + e['note'] + '\n\n' + text
        self._journal_set_refl(text)

    # ------- session recording ----------------------------------------------

    LOG_COLUMNS = ['t_s', 'score', 'tier', 'tier_label', 'keys_per_s', 'error_rate',
                   'dwell_ms', 'flight_ms', 'mouse_px', 'clicks', 'brightness_pct',
                   'breathing_open', 'simulated']

    def _toggle_record(self):
        if self.record_var.get():
            path = os.path.join(DATA_DIR, time.strftime('session_log_%Y%m%d_%H%M%S.csv'))
            try:
                self._log_fh = open(path, 'w', newline='', encoding='utf-8')
                self._log_writer = csv.writer(self._log_fh)
                self._log_writer.writerow(self.LOG_COLUMNS)
                self._log_start = time.time()
                print('[Aura UI] recording session ->', path)
            except OSError as e:
                print('[Aura UI] could not start recording:', e)
                self._log_fh = self._log_writer = None
                self.record_var.set(False)
        else:
            self._close_log()

    def _close_log(self):
        if self._log_fh:
            try: self._log_fh.close()
            except Exception: pass
        self._log_fh = self._log_writer = None

    def _log_tick(self, feats):
        if not self._log_writer:
            return
        try:
            popup = bool(self._breathing_popup and self._breathing_popup.alive())
            self._log_writer.writerow([
                round(time.time() - self._log_start, 2),
                round(self.engine.score, 2),
                self.engine.tier,
                self.engine.label,
                round(feats.get('keys_per_second', 0), 2),
                round(feats.get('error_rate', 0), 4),
                round(feats.get('mean_dwell', 0) * 1000, 1),
                round(feats.get('mean_flight', 0) * 1000, 1),
                round(feats.get('mouse_distance', 0)),
                feats.get('mouse_clicks', 0),
                self._last_bright,
                int(popup),
                int(self._sim_ticks > 0),
            ])
            self._log_fh.flush()
        except Exception:
            pass

    # ------- demo mode (for presentations) -----------------------------------

    DEMO_SCRIPT = [
        # (label, target score, seconds, note, [seconds into stage when a notification arrives])
        ('1/4  Normal working', 12, 7, 'Relaxed typing. Screen stays bright and cool. '
                                       'A notification is delivered normally.', [3.0]),
        ('2/4  Stress building', 48, 7, 'Erratic input. Brightness and colour temperature ease down.',
                                       [3.5]),
        ('3/4  Elevated stress', 85, 7, 'Focus mode is BLOCKING: notifications are held back (red cards). '
                                        'Dimmer, warmer screen, music lowered, breathing guide, Aura check-in.',
                                       [1.5, 3.0, 4.5]),
        ('4/4  Recovery', 8, 7, 'Stress falls: a summary of held notifications appears, '
                                'then new ones are delivered again.', [6.0]),
    ]
    DEMO_FEATS = [   # kps, error rate, dwell s, flight s, mouse px, clicks (per tier)
        (4.2, 0.02, 0.095, 0.140, 1800, 3),
        (5.6, 0.08, 0.150, 0.100, 5200, 9),
        (7.8, 0.19, 0.240, 0.070, 14000, 24),
    ]

    def _open_demo(self):
        if self._demo_win and self._demo_win.winfo_exists():
            self._demo_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title('Aura UI  -  Demo')
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.root)
        win.protocol('WM_DELETE_WINDOW', self._demo_close)
        self._demo_win = win
        tk.Label(win, text='Demo controller', bg=BG, fg=TEXT,
                 font=('Georgia', 13)).pack(anchor='w', padx=16, pady=(14, 0))
        tk.Label(win, text='drives the real app with simulated input', bg=BG, fg=FAINT,
                 font=('Arial', 7)).pack(anchor='w', padx=16, pady=(0, 8))

        bk = dict(relief='flat', font=('Arial', 10), cursor='hand2', pady=6,
                  activebackground=BORDER)
        tk.Button(win, text='Run full scripted demo', command=self._demo_run_script,
                  bg=SURF, fg=CALM, **bk).pack(fill='x', padx=16, pady=(0, 6))
        tk.Label(win, text='or set the state by hand', bg=BG, fg=MUTED,
                 font=('Arial', 8)).pack(anchor='w', padx=16, pady=(4, 2))
        row = tk.Frame(win, bg=BG)
        row.pack(fill='x', padx=16)
        for i, (txt, col, lvl) in enumerate([('Calm', CALM, 8), ('Mild', MILD, 48),
                                             ('Elevated', ELEV, 85)]):
            tk.Button(row, text=txt, command=lambda l=lvl: self._demo_manual(l),
                      bg=SURF, fg=col, **bk).pack(side='left', fill='x', expand=True,
                                                  padx=(0 if i == 0 else 4, 0))
        tk.Button(win, text='Show breathing guide', command=self._chat_breathe,
                  bg=SURF, fg=MUTED, **bk).pack(fill='x', padx=16, pady=(8, 0))
        tk.Button(win, text='Aura check-in (chat)', command=self._demo_checkin,
                  bg=SURF, fg=MUTED, **bk).pack(fill='x', padx=16, pady=(6, 0))
        tk.Button(win, text='Send test notification', command=self._send_test_notif,
                  bg=SURF, fg=MUTED, **bk).pack(fill='x', padx=16, pady=(6, 0))
        tk.Button(win, text='Stop demo (back to live sensing)', command=self._demo_stop,
                  bg=SURF, fg=ELEV, **bk).pack(fill='x', padx=16, pady=(10, 0))

        self._demo_status = tk.StringVar(value='Idle - using real keyboard/mouse input')
        tk.Label(win, textvariable=self._demo_status, bg=BG, fg=TEXT, wraplength=260,
                 justify='left', font=('Arial', 9, 'bold')).pack(anchor='w', padx=16, pady=(12, 0))
        self._demo_note = tk.StringVar(value='')
        tk.Label(win, textvariable=self._demo_note, bg=BG, fg=MUTED, wraplength=260,
                 justify='left', font=('Arial', 8)).pack(anchor='w', padx=16, pady=(2, 14))
        win.geometry('+{}+{}'.format(self.root.winfo_x() + self.root.winfo_width() + 8,
                                     self.root.winfo_y()))

    def _demo_reset_triggers(self):
        self._last_popup_time = 0.0
        self._last_checkin    = 0.0
        self._elevated_since  = None

    def _demo_manual(self, level):
        self._demo_script = []
        self._demo_idx = -1
        self._demo_reset_triggers()
        self._demo_target = level
        name = ['Calm', 'Mild', 'Elevated'][0 if level < 30 else 1 if level < 60 else 2]
        self._demo_status.set('Manual: ' + name)
        self._demo_note.set('Holding this state until you pick another.')

    def _demo_run_script(self):
        self._chat_dismiss()
        if self._breathing_popup and self._breathing_popup.alive():
            self._breathing_popup.close()
        self._demo_reset_triggers()
        self._demo_script = list(self.DEMO_SCRIPT)
        self._demo_idx = -1
        self._demo_end = 0.0
        self._demo_target = self.engine.score   # start from wherever we are

    def _demo_checkin(self):
        if self._demo_target is None:
            self._demo_target = self.engine.score
        self._chat_check_in()

    def _demo_stop(self):
        self._demo_target = None
        self._demo_script = []
        self._demo_idx = -1
        if self._demo_status:
            self._demo_status.set('Idle - using real keyboard/mouse input')
            self._demo_note.set('')

    def _demo_close(self):
        self._demo_stop()
        self._demo_win.destroy()

    def _demo_tick(self):
        """Advance the script, ease the engine toward the target, return fake features."""
        if self._demo_script and time.time() >= self._demo_end:
            self._demo_idx += 1
            if self._demo_idx >= len(self._demo_script):
                self._demo_stop()
                self._demo_status.set('Demo finished')
                self._demo_note.set('Press "Run full scripted demo" to repeat.')
                return None
            label, level, secs, note, _events = self._demo_script[self._demo_idx]
            self._demo_target = level
            self._demo_end = time.time() + secs
            self._demo_stage_start = time.time()
            self._demo_fired = 0
            self._demo_note.set(note)
            if level >= 60:
                self._demo_reset_triggers()
        if self._demo_script and self._demo_idx >= 0:
            left = int(max(0, self._demo_end - time.time()))
            self._demo_status.set('{}  ({}s)'.format(self._demo_script[self._demo_idx][0], left))
            events = self._demo_script[self._demo_idx][4]
            while (self._demo_fired < len(events)
                   and time.time() - self._demo_stage_start >= events[self._demo_fired]):
                self._demo_fired += 1
                self._send_test_notif()
        eng = self.engine
        eng.smoothed += (self._demo_target - eng.smoothed) * 0.18
        kps, err, dwell, flight, px, clicks = self.DEMO_FEATS[
            0 if self._demo_target < 30 else 1 if self._demo_target < 60 else 2]
        j = lambda v: v * (1 + random.uniform(-0.08, 0.08))
        return {'keys_per_second': j(kps), 'error_rate': j(err), 'mean_dwell': j(dwell),
                'mean_flight': j(flight), 'mouse_distance': j(px), 'mouse_clicks': int(j(clicks))}

    def _open_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title('Settings')
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.root)
        self._settings_win = win

        def make_slider(label, key, lo, hi, res, fmt='{:.2f}'):
            row = tk.Frame(win, bg=BG)
            row.pack(fill='x', padx=16, pady=(0, 5))
            val_var = tk.StringVar(value=fmt.format(self.settings[key]))
            tk.Label(row, text=label, bg=BG, fg=MUTED,
                     font=('Arial', 8), width=18, anchor='w').pack(side='left')
            tk.Label(row, textvariable=val_var, bg=BG, fg=TEXT,
                     font=('Arial', 8, 'bold'), width=6).pack(side='right')
            def on_change(v, k=key, vv=val_var, f=fmt):
                self.settings[k] = float(v)
                vv.set(f.format(float(v)))
            s = tk.Scale(row, from_=lo, to=hi, resolution=res,
                         orient='horizontal', showvalue=False,
                         bg=BG, fg=TEXT, troughcolor=SURF,
                         highlightthickness=0, bd=0, activebackground=CALM,
                         command=on_change)
            s.set(self.settings[key])
            s.pack(side='left', fill='x', expand=True)

        def section(title, sub=''):
            tk.Frame(win, bg=BORDER, height=1).pack(fill='x', padx=16, pady=(10, 4))
            tk.Label(win, text=title, bg=BG, fg=TEXT,
                     font=('Georgia', 11)).pack(anchor='w', padx=16)
            if sub:
                tk.Label(win, text=sub, bg=BG, fg=MUTED,
                         font=('Arial', 7)).pack(anchor='w', padx=16, pady=(0, 4))

        tk.Label(win, text='Aura UI  ·  Settings', bg=BG, fg=TEXT,
                 font=('Georgia', 13)).pack(anchor='w', padx=16, pady=(14, 0))
        tk.Label(win, text='changes saved automatically',
                 bg=BG, fg=FAINT, font=('Arial', 7)).pack(anchor='w', padx=16, pady=(0, 4))

        section('Sensitivity', 'how the stress score is calculated')
        make_slider('CoV weight',    'cov_weight',   0.0,  1.0,  0.01)
        make_slider('Error weight',  'error_weight', 0.0,  1.0,  0.01)
        make_slider('Smoothing',     'smoothing',    0.05, 0.50, 0.01)
        make_slider('Sensitivity',   'sensitivity',  0.5,  3.0,  0.1)
        make_slider('Decay speed',   'decay_speed',  0.5,  8.0,  0.5)

        section('Brightness Targets', 'screen brightness per stress tier')
        make_slider('Calm  (score 0-29)',   'bright_calm', 10, 100, 1, '{:.0f}%')
        make_slider('Mild  (score 30-59)',  'bright_mild', 10, 100, 1, '{:.0f}%')
        make_slider('Elevated (score 60+)', 'bright_elev', 10, 100, 1, '{:.0f}%')

        section('Color Temperature', 'screen warmth per stress tier (in Kelvin)')
        make_slider('Calm  (score 0-29)',   'temp_calm', 2000, 6500, 100, '{:.0f}K')
        make_slider('Mild  (score 30-59)',  'temp_mild', 2000, 6500, 100, '{:.0f}K')
        make_slider('Elevated (score 60+)', 'temp_elev', 2000, 6500, 100, '{:.0f}K')

        section('Volume Targets', 'Spotify volume per stress tier  ·  requires Auto-lower')
        make_slider('Calm  (score 0-29)',   'vol_calm', 0, 100, 5, '{:.0f}%')
        make_slider('Mild  (score 30-59)',  'vol_mild', 0, 100, 5, '{:.0f}%')
        make_slider('Elevated (score 60+)', 'vol_elev', 0, 100, 5, '{:.0f}%')

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x', padx=16, pady=(12, 8))
        tk.Button(win, text='Close', command=win.destroy,
                  bg=SURF, fg=TEXT, relief='flat', font=('Arial', 9),
                  activebackground=BORDER, cursor='hand2', pady=4).pack(
                  fill='x', padx=16, pady=(0, 14))

        x = self.root.winfo_x() + self.root.winfo_width() + 8
        y = self.root.winfo_y()
        win.geometry('+{}+{}'.format(x, y))

    def _build_chat(self):
        tk.Frame(self._right, bg=BORDER, height=1).pack(fill='x', padx=20, pady=(8, 8))
        wrap = tk.Frame(self._right, bg=BG)
        wrap.pack(fill='x', padx=20, pady=(0, 14))
        hdr = tk.Frame(wrap, bg=BG)
        hdr.pack(fill='x', pady=(0, 4))
        tk.Label(hdr, text='Aura', bg=BG, fg=MUTED,
                 font=('Arial', 8, 'italic')).pack(side='left')
        tk.Button(hdr, text="I'm Good", command=self._chat_dismiss, bg=BG, fg=MUTED,
                  relief='flat', font=('Arial', 8), bd=0, activebackground=BG,
                  activeforeground=CALM, cursor='hand2').pack(side='right')
        tk.Button(hdr, text='Breathe', command=self._chat_breathe, bg=BG, fg=MUTED,
                  relief='flat', font=('Arial', 8), bd=0, activebackground=BG,
                  activeforeground=CALM, cursor='hand2').pack(side='right', padx=8)

        self.chat_log = tk.Text(wrap, height=7, width=30, bg=SURF, fg=TEXT, relief='flat',
                                wrap='word', font=('Arial', 9), state='disabled',
                                highlightbackground=BORDER, highlightthickness=1,
                                padx=8, pady=6)
        self.chat_log.pack(fill='x', pady=(0, 6))
        self.chat_log.tag_config('aura', foreground=CALM)
        self.chat_log.tag_config('user', foreground=MUTED, justify='right')
        self.chat_log.tag_config('note', foreground=FAINT)

        row = tk.Frame(wrap, bg=SURF, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill='x')
        self.chat_entry = tk.Entry(row, bg=SURF, fg=TEXT, insertbackground=TEXT,
                                   relief='flat', font=('Arial', 9))
        self.chat_entry.pack(side='left', fill='x', expand=True, padx=8, pady=5)
        self.chat_entry.bind('<Return>', lambda e: self._chat_send())
        self.chat_send_btn = tk.Button(row, text='Send', command=self._chat_send,
                                       bg=SURF, fg=CALM, relief='flat', font=('Arial', 8),
                                       activebackground=BORDER, cursor='hand2')
        self.chat_send_btn.pack(side='right', padx=6)

        if self.llm.available:
            self._chat_add('note', "Talk to Aura any time. It also checks in when you're stressed.")
        else:
            self._chat_add('note', 'Add "openrouter_api_key" to secrets.json to enable chat.')
            self.chat_entry.config(state='disabled')
            self.chat_send_btn.config(state='disabled')

    # ------- Aura chat (OpenRouter) ----------------------------------------------

    def _chat_add(self, tag, text):
        self.chat_log.config(state='normal')
        self.chat_log.insert('end', text + '\n\n', tag)
        self.chat_log.config(state='disabled')
        self.chat_log.see('end')

    def _stress_note(self):
        return 'stress score {:.0f}/100 ({}).'.format(self.engine.score, self.engine.label)

    def _chat_request(self, text, fallback):
        """Run an AI call off the UI thread; reply is posted back via after()."""
        self.chat_send_btn.config(state='disabled')
        note = self._stress_note()

        def work():
            try:
                reply, tag = self.llm.chat(text, note), 'aura'
            except Exception as e:
                print('[Aura UI] AI error:', e)
                reply, tag = fallback, 'note'
            def done():
                if self._chat_gen != gen:
                    return           # chat was dismissed while waiting
                self._chat_add(tag, reply)
                self.chat_send_btn.config(state='normal')
            self.root.after(0, done)
        gen = self._chat_gen
        threading.Thread(target=work, daemon=True).start()

    def _chat_send(self):
        text = self.chat_entry.get().strip()
        if not text or not self.llm.available:
            return
        self.chat_entry.delete(0, 'end')
        self._chat_add('user', text)
        self._chat_request(text, "I hear you. Take a moment to breathe.")

    def _chat_check_in(self):
        """Aura opens the conversation when the user has been Elevated for a while."""
        self._chat_gen += 1
        self.llm.reset()
        self._show()
        self._chat_add('note', 'Aura noticed you seem stressed.')
        self._chat_request(OPENER, "You seem a bit stuck. Want to talk about what's blocking you?")

    def _chat_dismiss(self):
        self._chat_gen += 1
        self.llm.reset()
        self.chat_log.config(state='normal')
        self.chat_log.delete('1.0', 'end')
        self.chat_log.config(state='disabled')
        if self.llm.available:
            self.chat_send_btn.config(state='normal')
        self._elevated_since = None
        self._last_checkin = time.time()

    def _chat_breathe(self):
        if not (self._breathing_popup and self._breathing_popup.alive()):
            self._start_breathing()

    def _build_music(self):
        tk.Frame(self._right, bg=BORDER, height=1).pack(fill='x', padx=20, pady=(8, 4))
        wrap = tk.Frame(self._right, bg=BG)
        wrap.pack(fill='x', padx=20, pady=(0, 4))

        # Header
        hdr = tk.Frame(wrap, bg=BG)
        hdr.pack(fill='x')
        tk.Label(hdr, text='Music', bg=BG, fg=MUTED,
                 font=('Arial', 8, 'italic')).pack(side='left')
        self._sp_dot = tk.Label(hdr, text='●', bg=BG, fg=FAINT, font=('Arial', 8))
        self._sp_dot.pack(side='right')

        # Now-playing
        self._track_var  = tk.StringVar(value='Nothing playing')
        self._artist_var = tk.StringVar(value='—')
        tk.Label(wrap, textvariable=self._track_var,  bg=BG, fg=TEXT,
                 font=('Arial', 10, 'bold'), anchor='w').pack(fill='x')
        tk.Label(wrap, textvariable=self._artist_var, bg=BG, fg=MUTED,
                 font=('Arial', 8), anchor='w').pack(fill='x')

        # Controls
        ctrl = tk.Frame(wrap, bg=BG)
        ctrl.pack(fill='x', pady=(6, 2))
        bkw = dict(bg=SURF, fg=TEXT, relief='flat', font=('Arial', 13),
                   activebackground=BORDER, cursor='hand2', width=3, pady=2)
        tk.Button(ctrl, text='⏮', command=lambda: threading.Thread(
                  target=self.spotify.prev_track, daemon=True).start(), **bkw
                  ).pack(side='left', padx=(0, 4))
        self._pp_btn = tk.Button(ctrl, text='⏵', command=self._sp_play_pause, **bkw)
        self._pp_btn.pack(side='left', padx=(0, 4))
        tk.Button(ctrl, text='⏭', command=lambda: threading.Thread(
                  target=self.spotify.next_track, daemon=True).start(), **bkw
                  ).pack(side='left')

        # Volume row
        vrow = tk.Frame(wrap, bg=BG)
        vrow.pack(fill='x', pady=(4, 2))
        tk.Label(vrow, text='Volume', bg=BG, fg=MUTED, font=('Arial', 8)).pack(side='left')
        self._vol_var = tk.StringVar(value='--')
        tk.Label(vrow, textvariable=self._vol_var, bg=BG, fg=TEXT,
                 font=('Arial', 8, 'bold')).pack(side='right')

        # Auto-lower checkbox
        self.auto_music = tk.BooleanVar(value=False)
        tk.Checkbutton(wrap, text='Auto-lower volume when Elevated',
                       variable=self.auto_music, bg=BG, fg=MUTED,
                       selectcolor=SURF, activebackground=BG,
                       font=('Arial', 8)).pack(anchor='w')

    # ------- callbacks -------------------------------------------------------

    def _on_topmost(self, *_):
        self.root.attributes('-topmost', self.always_top.get())

    def _simulate(self):
        self._sim_ticks = 25
        self.sim_btn.config(state='disabled', text='Simulating...')

    # ------- poll loop (runs on main thread via after) -----------------------

    def _start(self):
        self.daemon.start()
        threading.Thread(target=self._brightness_loop, daemon=True).start()
        threading.Thread(target=self._spotify_loop,    daemon=True).start()
        self._poll()

    def _spotify_loop(self):
        """Poll track info every 3 s; ramp volume toward _vol_target at 3 %/0.5 s."""
        VOL_STEP = 5
        TICK     = 0.5
        ticks    = 0
        while self._running:
            time.sleep(TICK)
            ticks += 1

            # Full track poll every 6 ticks (= 3 s)
            if ticks >= 6:
                ticks = 0
                self._track_cache = self.spotify.current_track()
                if self._track_cache and self._vol_current is None:
                    self._vol_current = float(self._track_cache['volume'])

            # Volume ramp
            if (self.auto_music.get() and self.spotify.available
                    and self._vol_target is not None
                    and self._vol_current is not None):
                target = float(self._vol_target)
                diff   = target - self._vol_current
                if abs(diff) > 0.5:
                    self._vol_current += VOL_STEP if diff > 0 else -VOL_STEP
                    # Don't overshoot
                    if abs(target - self._vol_current) < VOL_STEP:
                        self._vol_current = target
                    self.spotify.set_volume(int(round(self._vol_current)))
            elif self._track_cache and not self.auto_music.get():
                # Track actual volume when not in auto mode
                self._vol_current = float(self._track_cache['volume'])

    def _sp_play_pause(self):
        threading.Thread(target=self.spotify.play_pause, daemon=True).start()


    def _brightness_loop(self):
        STEP = 5          # percent per tick
        TEMP_STEP = 100   # Kelvin per tick
        TICK = 0.5        # seconds per tick  →  ~10 %/sec ramp rate
        current = float(self.os_ctrl.get_brightness())
        current_temp = 6500.0
        while self._running:
            time.sleep(TICK)
            if self.auto_bright.get():
                target = float(self.engine.target_brightness)
                if current != target:
                    # Step toward target without overshooting
                    delta = target - current
                    current += STEP if delta > 0 else -STEP
                    current = target if abs(target - current) < STEP else current
                    self.os_ctrl.set_brightness(int(round(current)))
                    
                target_tmp = float(self.engine.target_temp)
                if current_temp != target_tmp:
                    delta_t = target_tmp - current_temp
                    current_temp += TEMP_STEP if delta_t > 0 else -TEMP_STEP
                    current_temp = target_tmp if abs(target_tmp - current_temp) < TEMP_STEP else current_temp
                    self.os_ctrl.set_color_temp(int(round(current_temp)))
            else:
                # Manual mode — just read and track whatever the OS says
                current = float(self.os_ctrl.get_brightness())
                if current_temp != 6500.0:
                    current_temp = 6500.0
                    self.os_ctrl.set_color_temp(6500)
            self._last_bright = int(round(current))

    def _poll(self):
        if not self._running:
            return
        features = self.daemon.get_features()
        if self._demo_target is not None:
            features = self._demo_tick() or features   # engine steered by the demo
        elif self._calibrating:
            self._calibration_tick(features)
        elif self._sim_ticks > 0:
            self.engine.inject_stress(82)
            self._sim_ticks -= 1
            if self._sim_ticks == 0:
                self.sim_btn.config(state='normal', text='Simulate Stress')
        else:
            self.engine.update(features)

        self._refresh(features)
        self.root.after(self.POLL_MS, self._poll)

    def _start_calibration(self):
        if self._calibrating:
            return
        self._calibrating   = True
        self._calib_samples = []
        self._calib_start   = time.time()
        self._calib_btn.config(state='disabled', text='Calibrating... 30s')
        self._calib_lbl.config(text='Type normally', fg=CALM)

    def _calibration_tick(self, features):
        elapsed   = time.time() - self._calib_start
        remaining = max(0, int(self.CALIB_DURATION - elapsed))
        self._calib_btn.config(text=f'Calibrating... {remaining}s')

        mf  = features.get('mean_flight', 0)
        sf  = features.get('std_flight',  0)
        fc  = features.get('flight_count', 0)
        err = features.get('error_rate',  0)
        kps = features.get('keys_per_second', 0)
        if kps > 0.2 and fc >= 3:
            cov = min(sf / mf, 3.0) if mf > 0 else 0
            self._calib_samples.append((cov, err))

        if elapsed >= self.CALIB_DURATION:
            self._finish_calibration()

    def _finish_calibration(self):
        self._calibrating = False
        if self._calib_samples:
            covs = [c for c, _ in self._calib_samples]
            errs = [e for _, e in self._calib_samples]
            self.settings['baseline_cov'] = round(sum(covs) / len(covs), 4)
            self.settings['baseline_err'] = round(sum(errs) / len(errs), 4)
        self.settings['is_calibrated'] = 1
        self._calib_btn.config(state='normal', text='Calibrate', fg=MUTED)
        self._calib_lbl.config(text='✓ Calibrated', fg=MUTED)

    def _refresh(self, feats):
        score = self.engine.score
        color = self.engine.color
        self._draw_gauge(score, color)
        self.tier_lbl.config(text=self.engine.label, fg=color)
        self.dot.config(fg=color)
        kps   = feats.get('keys_per_second', 0)
        err   = feats.get('error_rate',      0)
        dwell = feats.get('mean_dwell',      0) * 1000
        flt   = feats.get('mean_flight',     0) * 1000
        self._sv['kps'].set   ('{:.1f}'.format(kps)   if kps   > 0 else '--')
        self._sv['err'].set   ('{:.0%}'.format(err)   if kps   > 0 else '--')
        self._sv['dwell'].set ('{:.0f}'.format(dwell) if dwell > 0 else '--')
        self._sv['flight'].set('{:.0f}'.format(flt)   if flt   > 0 else '--')
        
        m_px = feats.get('mouse_distance', 0)
        m_cl = feats.get('mouse_clicks', 0)
        self._sv['mouse_px'].set('{:.0f}'.format(m_px) if m_px > 0 else '--')
        self._sv['mouse_clicks'].set(str(m_cl) if m_cl > 0 else '--')
        
        self.bright_var.set('{}%'.format(self._last_bright))
        self._log_tick(feats)

        # --- music panel update ----------------------------------------------
        t = self._track_cache
        if t:
            title  = t['title'][:28] + '…' if len(t['title'])  > 28 else t['title']
            artist = t['artist'][:30] + '…' if len(t['artist']) > 30 else t['artist']
            self._track_var.set(title or 'Unknown')
            self._artist_var.set(artist or '—')
            self._vol_var.set('{}%'.format(t['volume']))
            self._pp_btn.config(text='⏸' if t['is_playing'] else '⏵')
            self._sp_dot.config(fg=CALM)
        elif self.spotify.available:
            blocked = 'not added' in (self.spotify.status or '').lower()
            self._track_var.set(
                'Account not allowed' if blocked else 'Nothing playing')
            self._artist_var.set(self.spotify.status if blocked else '—')
            self._vol_var.set('--')
            self._sp_dot.config(fg=MILD)
        else:
            self._track_var.set('Not connected')
            self._artist_var.set(self.spotify.status or '—')
            self._vol_var.set('--')
            self._sp_dot.config(fg=FAINT)

        # Auto-volume: set target based on current tier, loop ramps smoothly
        if self.auto_music.get() and self.spotify.available and t:
            vol_keys = ['vol_calm', 'vol_mild', 'vol_elev']
            self._vol_target = self.settings[vol_keys[self.engine.tier]]
        else:
            self._vol_target = None

        # --- notification muting ---------------------------------------------
        self.stats.tick(self.engine.score, self.engine.tier, self._demo_target is not None)
        blocking = self._blocking()
        if blocking and not self._dnd_active:
            self.os_ctrl.set_dnd(True)
            self._dnd_active = True
        elif not blocking and self._dnd_active:
            self.os_ctrl.set_dnd(False)
            self._dnd_active = False
            self._release_held()
        self._focus_state.config(text='BLOCKING notifications' if blocking else
                                 ('standing by' if self.focus_mode.get() else 'off'),
                                 fg=ELEV if blocking else MUTED)

        # --- Aura check-in: Elevated for 10 s straight, then at most once per 5 min
        if self.engine.tier == 2:
            if self._elevated_since is None:
                self._elevated_since = time.time()
            elif ((self.llm.available or self._demo_target is not None)
                  and time.time() - self._elevated_since > (3 if self._demo_target is not None else 10)
                  and time.time() - self._last_checkin > 300):
                self._last_checkin = time.time()
                self._chat_check_in()
        else:
            self._elevated_since = None

        # --- breathing popup when Elevated -----------------------------------
        if self.engine.tier == 2:
            popup_gone  = not (self._breathing_popup and self._breathing_popup.alive())
            cooldown_ok = (time.time() - self._last_popup_time) > 120
            if popup_gone and cooldown_ok:
                self._start_breathing()

    # ------- tray ------------------------------------------------------------

    def _make_icon(self):
        img = Image.new('RGB', (64, 64), '#0b0a10')
        d = ImageDraw.Draw(img)
        d.ellipse([14, 14, 50, 50], fill='#7fae9d')
        return img

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem('Show / Hide', lambda i, it: self.root.after(0, self._toggle)),
            pystray.MenuItem('Quit',        lambda i, it: self.root.after(0, self._quit)),
        )
        self.tray = pystray.Icon('Aura UI', self._make_icon(), 'Aura UI', menu)
        self.tray.run_detached()

    def _hide(self):   self.root.withdraw()
    def _show(self):   self.root.deiconify(); self.root.lift()
    def _toggle(self):
        if self.root.state() == 'withdrawn': self._show()
        else: self._hide()

    def _quit(self):
        self._running = False
        self._close_log()
        if self.tray:
            try: self.tray.stop()
            except: pass
        self.root.destroy()

    def run(self):
        if TRAY_OK: self._setup_tray()
        else: print('[Aura UI] pip install pystray pillow for tray support')
        self._start()
        self.root.mainloop()


if __name__ == '__main__':
    AmbientApp().run()
