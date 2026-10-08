#!/usr/bin/env python3
"""
Aura UI -- background stress monitor
Run: python run.py
  Opens the desktop widget
"""
import sys, os, threading, time, json
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
    APP_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = APP_DIR

sys.path.insert(0, os.path.join(APP_DIR, 'backend'))
from telemetry_daemon import TelemetryDaemon
from os_controller import OSController
from spotify_controller import SpotifyController

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


class AmbientApp:
    POLL_MS = 333

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
        self._build_header()
        self._build_gauge()
        self._build_stats()
        self._build_controls()
        self._build_music()
        self._build_chat()
        r.geometry('+80+80')

    def _build_header(self):
        row = tk.Frame(self.root, bg=BG)
        row.pack(fill='x', padx=20, pady=(14, 0))
        tk.Label(row, text='Aura UI', bg=BG, fg=TEXT,
                 font=('Georgia', 16)).pack(side='left')
        tk.Checkbutton(row, text='top', variable=self.always_top,
                       bg=BG, fg=FAINT, selectcolor=SURF,
                       activebackground=BG, activeforeground=CALM,
                       font=('Arial', 8), bd=0).pack(side='right', pady=4)
        self.dot = tk.Label(row, text='●', bg=BG, fg=CALM, font=('Arial', 10))
        self.dot.pack(side='right', pady=5, padx=2)
        tk.Label(self.root, text='background stress monitor  ·  Aura UI',
                 bg=BG, fg=MUTED, font=('Arial', 8)).pack(anchor='w', padx=20)

    def _build_gauge(self):
        self.canvas = tk.Canvas(self.root, width=180, height=155,
                                bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(10, 0))
        self._draw_gauge(0, CALM)
        self.tier_lbl = tk.Label(self.root, text='Calm', bg=BG, fg=CALM,
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
        f = tk.Frame(self.root, bg=SURF,
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
        row = tk.Frame(self.root, bg=BG)
        row.pack(fill='x', padx=20, pady=(0, 2))
        tk.Label(row, text='Brightness', bg=BG, fg=MUTED, font=('Arial', 8)).pack(side='left')
        self.bright_var = tk.StringVar(value='--')
        tk.Label(row, textvariable=self.bright_var, bg=BG, fg=TEXT,
                 font=('Arial', 8, 'bold')).pack(side='right')

        row2 = tk.Frame(self.root, bg=BG)
        row2.pack(fill='x', padx=18, pady=(0, 6))
        tk.Checkbutton(row2, text='Auto-adjust brightness', variable=self.auto_bright,
                       bg=BG, fg=MUTED, selectcolor=SURF, activebackground=BG,
                       font=('Arial', 8)).pack(side='left')

        btn_row = tk.Frame(self.root, bg=BG)
        btn_row.pack(fill='x', padx=20, pady=(0, 4))
        self.sim_btn = tk.Button(btn_row, text='Simulate Stress',
                                  command=self._simulate,
                                  bg=SURF, fg=MILD, relief='flat',
                                  font=('Arial', 9), activebackground=BORDER,
                                  activeforeground=ELEV, cursor='hand2', pady=4)
        self.sim_btn.pack(side='left', fill='x', expand=True, padx=(0, 4))
        tk.Button(btn_row, text='Settings',
                  command=self._open_settings,
                  bg=SURF, fg=MUTED, relief='flat',
                  font=('Arial', 9), activebackground=BORDER,
                  activeforeground=TEXT, cursor='hand2', pady=4).pack(side='right')

        # Calibration row
        cal_row = tk.Frame(self.root, bg=BG)
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
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x', padx=20, pady=(8, 8))
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill='x', padx=20, pady=(0, 14))
        tk.Label(wrap, text='Aura  |  coming soon', bg=BG, fg=FAINT,
                 font=('Arial', 8, 'italic')).pack(anchor='w', pady=(0, 4))
        row = tk.Frame(wrap, bg=SURF, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill='x')
        tk.Entry(row, bg=SURF, fg=FAINT, state='disabled', relief='flat',
                 font=('Arial', 9), disabledforeground=FAINT,
                 disabledbackground=SURF).pack(side='left', fill='x', expand=True, padx=8, pady=5)
        tk.Button(row, text='Send', state='disabled', bg=SURF, fg=FAINT,
                  relief='flat', font=('Arial', 8),
                  disabledforeground=FAINT).pack(side='right', padx=6)

    def _build_music(self):
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x', padx=20, pady=(8, 4))
        wrap = tk.Frame(self.root, bg=BG)
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
        if self._calibrating:
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
            self._track_var.set('Nothing playing')
            self._artist_var.set('—')
            self._vol_var.set('--')
            self._sp_dot.config(fg=MILD)
        else:
            self._track_var.set('Not connected')
            self._artist_var.set('—')
            self._vol_var.set('--')
            self._sp_dot.config(fg=FAINT)

        # Auto-volume: set target based on current tier, loop ramps smoothly
        if self.auto_music.get() and self.spotify.available and t:
            vol_keys = ['vol_calm', 'vol_mild', 'vol_elev']
            self._vol_target = self.settings[vol_keys[self.engine.tier]]
        else:
            self._vol_target = None

        # --- notification muting ---------------------------------------------
        if self.engine.tier == 2 and not self._dnd_active:
            self.os_ctrl.set_dnd(True)
            self._dnd_active = True
        elif self.engine.tier < 2 and self._dnd_active:
            self.os_ctrl.set_dnd(False)
            self._dnd_active = False

        # --- breathing popup when Elevated -----------------------------------
        if self.engine.tier == 2:
            popup_gone  = not (self._breathing_popup and self._breathing_popup.alive())
            cooldown_ok = (time.time() - self._last_popup_time) > 120
            if popup_gone and cooldown_ok:
                self._last_popup_time = time.time()
                self._breathing_popup = BreathingPopup(self.root)

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
