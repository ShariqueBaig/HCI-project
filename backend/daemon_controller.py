"""Unified headless controller for Aura v2 (zero Tkinter dependency).

Owns settings, telemetry polling, calibrated StressEngine, OS comfort controls
(brightness, color temp, Windows DND), Spotify/system audio, Silent Focus Mode,
tiered mixed-initiative nudges, Aura Chat, Session Journal, Consent/Calibration,
and Research Recording + Study Blinding.
"""
import copy
import json
import os
import random
import threading
import time

from backend import firebase_sync
from backend import journal as journal_store
from backend import research
from backend.llm_controller import LLMController, OPENER
from backend.os_controller import OSController, detect_screen_diagonal_px
from backend.paths import base_dir
from backend.search.live_state import LiveStateStore, build_snapshot
from backend.spotify_controller import SpotifyController
from backend.stress_engine import DEFAULT_SETTINGS, StressEngine
from backend.telemetry_daemon import TelemetryDaemon

DATA_DIR = base_dir()
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

V2_DEFAULTS = dict(
    DEFAULT_SETTINGS,
    is_calibrated=0,
    participant_code='',
    study_condition='intervention',  # 'intervention' (Active B) | 'control' (Control A)
    auto_bright=False,
    auto_music=False,
    focus_mode=True,
    theme='dark',                    # 'dark' | 'light'
    auto_adapt=True,
    view_mode_override='',
    onboarding_complete=False,
)


class Settings:
    def __init__(self, persist=True):
        self._persist = persist
        self.data = dict(V2_DEFAULTS)
        if persist:
            self._load()
        if not self.data.get('screen_diag_px'):
            self.data['screen_diag_px'] = detect_screen_diagonal_px()

    def _load(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, encoding='utf-8') as f:
                    self.data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        if not self._persist:
            return
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def get(self, k, default=None):
        return self.data.get(k, default)

    def update(self, mapping):
        self.data.update(mapping)
        self.save()


class SessionStats:
    """Aggregate numbers for journal and wrap-up — never keystroke content."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.start = time.time()
        self._last = self.start
        self.tier_s = [0.0, 0.0, 0.0]
        self._score_s = 0.0
        self._total_s = 0.0
        self.peak = 0.0
        self.peak_at = 0.0
        self.episodes = 0
        self._prev = 0
        self.breathing = 0
        self.held = 0
        self.delivered = 0
        self.demo = False

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
        return {
            'duration_s': time.time() - self.start,
            'avg': self._score_s / self._total_s if self._total_s else 0.0,
            'peak': self.peak,
            'peak_at_s': self.peak_at,
            'tier_s': list(self.tier_s),
            'episodes': self.episodes,
            'breathing': self.breathing,
            'held': self.held,
            'delivered': self.delivered,
            'demo': self.demo,
        }


class AuraController:
    """Headless orchestrator for Aura v2 ambient sensing, comfort, and study workflows."""

    POLL_S = 0.333
    CALIB_DURATION = 30.0
    NUDGE_DELAY_S = 15.0
    NUDGE_DEMO_DELAY_S = 4.0
    NUDGE_COOLDOWN_S = 300.0

    DEMO_NOTIFS = [
        ('Slack', 'Ahmed: are you free for a quick call?'),
        ('Mail', 'Your order has shipped'),
        ('WhatsApp', 'Mum: dinner at 8?'),
        ('Calendar', 'Team meeting in 10 minutes'),
        ('Instagram', '12 new likes on your photo'),
        ('Teams', 'New message in #project-hci'),
    ]

    DEMO_SCRIPT = [
        ('1/4  Normal working', 12, 7, 'Relaxed typing. Screen stays bright and cool.', [3.0]),
        ('2/4  Stress building', 48, 7, 'Erratic input. Screen comfort eases down.', [3.5]),
        ('3/4  Elevated stress', 85, 7, 'Focus mode holds notifications silently; corner nudge offered.', [1.5, 3.0, 4.5]),
        ('4/4  Recovery', 8, 7, 'Stress falls: calm digest banner summarizes held alerts.', [6.0]),
    ]

    DEMO_FEATS = [
        (4.2, 0.02, 0.095, 0.140, 1800, 3),
        (5.6, 0.08, 0.150, 0.100, 5200, 9),
        (7.8, 0.19, 0.240, 0.070, 14000, 24),
    ]

    def __init__(self, standalone=False, persist=True, live_state=None, lab_unlocked=True):
        self.standalone = standalone
        self._persist = persist
        self._lock = threading.Lock()
        self.settings = Settings(persist=persist)
        self.daemon = None if standalone else TelemetryDaemon(window_size_seconds=5)
        self.os_ctrl = OSController()
        self.engine = StressEngine(self.settings)
        self.spotify = SpotifyController() if persist else None
        self.llm = LLMController()
        self.sync = firebase_sync.FirebaseSync() if persist else None
        self.stats = SessionStats()
        self.live_state = live_state or LiveStateStore()
        self.search_server = None

        self._running = False
        self._started = False
        self._sim_ticks = 0
        self._last_bright = 80
        self._last_temp = 6500
        self._orig_bright = None
        self._display_touched = False
        self._dnd_active = False
        self._track_cache = None
        self._vol_target = None
        self._vol_current = None
        self._held = []
        self._focus_digest = None
        self._notif_n = 0
        self._breathing_active = False

        # Calibration state
        self._calibrating = False
        self._calib_status = 'idle'  # idle | running | done | insufficient
        self._calib_samples = []     # list of (cov, err, kps, dwell)
        self._calib_start = 0.0
        self._calib_duration = self.CALIB_DURATION
        self._calib_msg = ''

        # Tiered mixed-initiative nudge state
        self._elevated_since = None
        self._last_nudge_ts = 0.0
        self._nudge_snooze_until = 0.0
        self._active_nudge = None
        self._nudge_seq = 0

        # Chat state
        self._chat_messages = [
            {'id': 'sys-0', 'role': 'note', 'text': 'Talk to Aura anytime. Checks in gently only after sustained tension.', 'ts': time.time()}
        ]
        self._chat_busy = False

        # Demo state
        self._demo_target = None
        self._demo_script = []
        self._demo_idx = -1
        self._demo_end = 0.0
        self._demo_stage_start = 0.0
        self._demo_fired = 0
        self._demo_status = 'Idle — using real keyboard/mouse input'
        self._demo_note = ''

        # Research recording + blinding
        self._collector = None
        self._log_start = 0.0
        self._pending_finalize = False
        self._pending_summary = None
        self._sync_status = self.sync.status_line() if self.sync else 'off'
        self._pending_n = 0
        self.lab_unlocked = lab_unlocked

        # Keep live_state seeded when standalone controller owns it directly (not injected test store)
        if live_state is None and persist:
            self.publish_live_state({'keys_per_second': 0.0, 'error_rate': 0.0, 'mean_dwell': 0.0,
                                     'mean_flight': 0.0, 'std_flight': 0.0, 'flight_count': 0,
                                     'mouse_distance': 0.0, 'mouse_clicks': 0}, False)

    @property
    def blinded(self):
        """True during an active study recording unless the Researcher Lab is unlocked."""
        return bool((self._collector is not None or self._pending_finalize) and not self.lab_unlocked)

    def _is_control(self):
        return self.settings['study_condition'] == 'control'

    def _blocking(self):
        return (not self._is_control()) and bool(self.settings['focus_mode']) and self.engine.tier == 2

    # ------------------------------------------------------------ lifecycle --

    def start(self):
        if self._started:
            return self
        self._started = True
        self._running = True
        if self.daemon is not None:
            try:
                self.daemon.start()
            except Exception as e:
                print('[Aura] telemetry start failed:', e)
        threading.Thread(target=self._poll_loop, name='aura-poll', daemon=True).start()
        if not self.standalone:
            threading.Thread(target=self._display_loop, name='aura-display', daemon=True).start()
            threading.Thread(target=self._audio_loop, name='aura-audio', daemon=True).start()
        if self.sync and self.sync.enabled:
            self._sync_refresh()
            threading.Thread(target=self._sync_loop, name='aura-sync', daemon=True).start()
        return self

    def stop(self):
        self._running = False
        self._close_log()
        self._restore_display()
        if self._dnd_active:
            self.os_ctrl.set_dnd(False)
            self._dnd_active = False

    # ---------------------------------------------------------- main loops --

    def _poll_loop(self):
        while self._running:
            try:
                self.poll_once()
            except Exception as e:
                print('[Aura] poll error:', e)
            time.sleep(self.POLL_S)

    def poll_once(self, features=None, now=None):
        """Run a single telemetry + intervention tick (also callable deterministically in tests)."""
        now = now if now is not None else time.time()
        if features is None:
            if self._demo_target is not None:
                features = self._demo_tick(now)
            elif self.daemon is not None:
                features = self.daemon.get_features()
            else:
                features = {'keys_per_second': 2.5, 'error_rate': 0.03, 'mean_dwell': 0.10,
                            'std_dwell': 0.02, 'mean_flight': 0.16, 'std_flight': 0.04,
                            'flight_count': 8, 'mouse_distance': 400.0, 'mouse_clicks': 1}

        if self._demo_target is not None:
            pass  # _demo_tick already eased engine.smoothed
        elif self._calibrating:
            self._calibration_tick(features, now)
        elif self._sim_ticks > 0:
            self.engine.inject_stress(82)
            self._sim_ticks -= 1
        else:
            self.engine.update(features)

        score = self.engine.score
        tier = self.engine.tier
        if not self._pending_finalize:
            self.stats.tick(score, tier, self._demo_target is not None)

        blocking = self._blocking()
        if blocking and not self._dnd_active:
            if not self.standalone:
                self.os_ctrl.set_dnd(True)
            self._dnd_active = True
        elif not blocking and self._dnd_active:
            if not self.standalone:
                self.os_ctrl.set_dnd(False)
            self._dnd_active = False
            self._release_held(now)

        # Tiered mixed-initiative escalation:
        # 0-15s Elevated = silent peripheral adaptation only.
        # >=15s sustained Elevated (4s in demo/sim) = gentle non-focus-stealing corner nudge.
        if tier == 2 and not self._is_control():
            if self._elevated_since is None:
                self._elevated_since = now
            else:
                delay = self.NUDGE_DEMO_DELAY_S if (self._demo_target is not None or self._sim_ticks > 0) else self.NUDGE_DELAY_S
                if (now - self._elevated_since >= delay
                        and now >= self._nudge_snooze_until
                        and now - self._last_nudge_ts >= self.NUDGE_COOLDOWN_S
                        and self._active_nudge is None):
                    self._last_nudge_ts = now
                    self._nudge_seq += 1
                    self._active_nudge = {
                        'id': f'nudge-{self._nudge_seq}',
                        'ts': now,
                        'score': round(score),
                        'message': 'Your pace has been intense for a bit. Want a 20-second breather or quick check-in?',
                    }
        else:
            self._elevated_since = None

        # Audio volume target
        if (not self._is_control()) and self.settings['auto_music'] and self._audio_available():
            vol_keys = ['vol_calm', 'vol_mild', 'vol_elev']
            self._vol_target = self.settings[vol_keys[tier]]
        else:
            self._vol_target = None

        self._log_tick(features)
        self.publish_live_state(features, blocking)

    def publish_live_state(self, feats, blocking):
        self.live_state.set(build_snapshot(
            score=self.engine.score,
            tier=self.engine.tier,
            features=feats,
            condition=self.settings['study_condition'],
            calibrated=self.settings['is_calibrated'],
            baseline_cov=self.settings['baseline_cov'],
            baseline_err=self.settings['baseline_err'],
            baseline_kps=self.settings.get('baseline_kps', 0.0),
            baseline_dwell=self.settings.get('baseline_dwell', 0.0),
            dnd_active=self._dnd_active,
            focus_blocking=blocking,
            breathing_active=self._breathing_active,
            held_count=len(self._held),
            simulated=self._sim_ticks > 0,
            demo=self._demo_target is not None,
            recording=self._collector is not None,
            brightness=self._last_bright,
            color_temp=self._last_temp,
            session_stats=self.stats.summary(),
        ))

    # ------------------------------------------------------ silent focus ----

    def notify(self, app, text, now=None):
        """Incoming notification: held SILENTLY when Focus Mode is blocking."""
        now = now if now is not None else time.time()
        if self._blocking():
            self._held.append({'app': app, 'text': text, 'ts': now})
            self.stats.held += 1
            return {'status': 'held', 'held_count': len(self._held)}
        self.stats.delivered += 1
        return {'status': 'delivered', 'app': app, 'text': text}

    def _release_held(self, now=None):
        now = now if now is not None else time.time()
        if self._held:
            items = list(self._held)
            apps = list(dict.fromkeys(x['app'] for x in items))
            self._focus_digest = {
                'id': f'digest-{int(now * 1000)}',
                'count': len(items),
                'apps': apps,
                'items': items[-6:],
                'ts': now,
            }
        self._held = []

    def clear_focus_digest(self):
        self._focus_digest = None

    # -------------------------------------------------------- display/audio --

    def _restore_display(self):
        if not self.standalone and self._display_touched and self._orig_bright is not None:
            self.os_ctrl.set_brightness(self._orig_bright)
            self.os_ctrl.set_color_temp(6500)
        self._display_touched = False
        self._orig_bright = None
        self._last_temp = 6500

    def _display_loop(self):
        step, temp_step, tick = 5, 100, 0.5
        current = float(self.os_ctrl.get_brightness())
        current_temp = 6500.0
        idle_ticks = 0
        while self._running:
            time.sleep(tick)
            if self.settings['auto_bright'] and not self._is_control():
                idle_ticks = 0
                if self._orig_bright is None:
                    current = float(self.os_ctrl.get_brightness())
                    self._orig_bright = int(round(current))
                target = float(self.engine.target_brightness)
                if current != target:
                    delta = target - current
                    current += step if delta > 0 else -step
                    current = target if abs(target - current) < step else current
                    self.os_ctrl.set_brightness(int(round(current)))
                    self._display_touched = True
                target_tmp = float(self.engine.target_temp)
                if current_temp != target_tmp:
                    delta_t = target_tmp - current_temp
                    current_temp += temp_step if delta_t > 0 else -temp_step
                    current_temp = target_tmp if abs(target_tmp - current_temp) < temp_step else current_temp
                    self.os_ctrl.set_color_temp(int(round(current_temp)))
                    self._display_touched = True
            else:
                idle_ticks += 1
                if idle_ticks >= 20:
                    idle_ticks = 0
                    current = float(self.os_ctrl.get_brightness())
                current_temp = 6500.0
                if self._display_touched:
                    self._restore_display()
            self._last_bright = int(round(current))
            self._last_temp = int(round(current_temp))

    def _audio_available(self):
        return bool((self.spotify and self.spotify.available) or self.os_ctrl.volume_available)

    def _read_audio_volume(self):
        if self.spotify and self.spotify.available and self._track_cache:
            return float(self._track_cache.get('volume') or 0)
        return self.os_ctrl.get_volume()

    def _set_audio_volume(self, level):
        if self.spotify and self.spotify.available:
            self.spotify.set_volume(level)
        else:
            self.os_ctrl.set_volume(level)

    def _audio_loop(self):
        vol_step, tick, ticks = 5, 0.5, 0
        if self.spotify and self.spotify.configured:
            self.spotify.try_resume()
        while self._running:
            time.sleep(tick)
            ticks += 1
            if ticks >= 6:
                ticks = 0
                self._track_cache = self.spotify.current_track() if (self.spotify and self.spotify.connected) else None
                if self._track_cache and self._vol_current is None:
                    self._vol_current = float(self._track_cache['volume'])
            if self.settings['auto_music'] and self._vol_target is not None:
                cur = self._read_audio_volume()
                if cur is not None:
                    tgt = float(self._vol_target)
                    if abs(tgt - cur) >= vol_step:
                        cur += vol_step if tgt > cur else -vol_step
                    else:
                        cur = tgt
                    self._set_audio_volume(int(round(cur)))
                    self._vol_current = cur
            else:
                self._vol_current = self._read_audio_volume()

    def audio_action(self, action):
        if self.spotify is None:
            return {'ok': False, 'status': 'Audio disabled in memory-only mode'}
        if action == 'connect':
            threading.Thread(target=self.spotify.connect, daemon=True).start()
            return {'ok': True, 'status': 'Waiting for browser login...'}
        if action == 'disconnect':
            self.spotify.disconnect()
            self._track_cache = None
            return {'ok': True, 'status': self.spotify.status}
        if action == 'play_pause':
            threading.Thread(target=self.spotify.play_pause, daemon=True).start()
            return {'ok': True}
        if action == 'next':
            threading.Thread(target=self.spotify.next_track, daemon=True).start()
            return {'ok': True}
        if action == 'prev':
            threading.Thread(target=self.spotify.prev_track, daemon=True).start()
            return {'ok': True}
        raise ValueError(f'Unknown audio action: {action}')

    # --------------------------------------------------------- calibration --

    def start_calibration(self, duration_s=None):
        dur = float(duration_s or self.CALIB_DURATION)
        with self._lock:
            self._calibrating = True
            self._calib_status = 'running'
            self._calib_samples = []
            self._calib_start = time.time()
            self._calib_duration = max(5.0, min(60.0, dur))
            self._calib_msg = 'Type the passage at your relaxed pace.'
        return self.calibration_status()

    def cancel_calibration(self):
        with self._lock:
            self._calibrating = False
            self._calib_status = 'idle'
            self._calib_samples = []
            self._calib_msg = ''
        return self.calibration_status()

    def ingest_calibration_sample(self, features, now=None):
        """Accept typing timing features from the React calibration box (great for browser/standalone)."""
        if not self._calibrating:
            return self.calibration_status()
        self._record_calib_sample(features)
        return self.calibration_status(now)

    def _record_calib_sample(self, features):
        mf = features.get('mean_flight', 0) or 0
        sf = features.get('std_flight', 0) or 0
        fc = features.get('flight_count', 0) or 0
        err = features.get('error_rate', 0) or 0
        kps = features.get('keys_per_second', 0) or 0
        dwell = features.get('mean_dwell', 0) or 0
        if kps > 0.2 and fc >= 3:
            cov = min(sf / mf, 3.0) if mf > 0 else 0.0
            self._calib_samples.append((cov, err, kps, dwell))

    def _calibration_tick(self, features, now=None):
        now = now if now is not None else time.time()
        elapsed = now - self._calib_start
        self._record_calib_sample(features)
        if elapsed >= self._calib_duration:
            self._finish_calibration()

    def _finish_calibration(self):
        self._calibrating = False
        if len(self._calib_samples) >= 3:
            covs = [s[0] for s in self._calib_samples]
            errs = [s[1] for s in self._calib_samples]
            kpss = [s[2] for s in self._calib_samples]
            dwells = [s[3] for s in self._calib_samples if s[3] > 0]
            self.settings.update({
                'baseline_cov': round(sum(covs) / len(covs), 4),
                'baseline_err': round(sum(errs) / len(errs), 4),
                'baseline_kps': round(sum(kpss) / len(kpss), 3),
                'baseline_dwell': round(sum(dwells) / len(dwells), 4) if dwells else 0.0,
                'is_calibrated': 1,
            })
            self._calib_status = 'done'
            self._calib_msg = 'Personal baseline saved ({} samples).'.format(len(self._calib_samples))
        else:
            self._calib_status = 'insufficient'
            self._calib_msg = 'Not enough typing detected — click Retry to try again.'

    def calibration_status(self, now=None):
        now = now if now is not None else time.time()
        elapsed = (now - self._calib_start) if self._calibrating else 0.0
        remaining = max(0.0, self._calib_duration - elapsed) if self._calibrating else 0.0
        return {
            'active': self._calibrating,
            'status': self._calib_status,
            'duration_s': self._calib_duration,
            'remaining_s': round(remaining, 1),
            'progress': round(min(1.0, elapsed / self._calib_duration), 3) if self._calibrating else (1.0 if self._calib_status == 'done' else 0.0),
            'samples': len(self._calib_samples),
            'message': self._calib_msg,
            'calibrated': bool(self.settings['is_calibrated']),
            'baselines': {
                'cov': self.settings['baseline_cov'],
                'err': self.settings['baseline_err'],
                'kps': self.settings.get('baseline_kps', 0.0),
                'dwell': self.settings.get('baseline_dwell', 0.0),
            },
        }

    # ---------------------------------------------------- nudges & chat ------

    def nudge_action(self, action, snooze_minutes=30):
        now = time.time()
        if action == 'dismiss':
            self._active_nudge = None
            return {'ok': True}
        if action == 'snooze':
            self._active_nudge = None
            self._nudge_snooze_until = now + max(1, int(snooze_minutes)) * 60
            return {'ok': True, 'snoozed_until': self._nudge_snooze_until}
        if action == 'breathe':
            self._active_nudge = None
            self.stats.breathing += 1
            return {'ok': True, 'open': 'breathe'}
        if action == 'chat':
            self._active_nudge = None
            self.trigger_chat_checkin()
            return {'ok': True, 'open': 'chat'}
        raise ValueError(f'Unknown nudge action: {action}')

    def set_breathing_active(self, active: bool):
        if active and not self._breathing_active:
            self.stats.breathing += 1
        self._breathing_active = bool(active)

    def trigger_chat_checkin(self):
        self.llm.reset()
        note = 'stress score {:.0f}/100 ({}).'.format(self.engine.score, self.engine.label)
        reply = self.llm.chat(OPENER, note)
        self._chat_messages.append({'id': f'aura-{time.time()}', 'role': 'aura', 'text': reply, 'ts': time.time()})
        return self.chat_history()

    def chat_send(self, text):
        msg = (text or '').strip()
        if not msg:
            raise ValueError('Empty message')
        self._chat_messages.append({'id': f'u-{time.time()}', 'role': 'user', 'text': msg, 'ts': time.time()})
        note = 'stress score {:.0f}/100 ({}).'.format(self.engine.score, self.engine.label)
        reply = self.llm.chat(msg, note)
        self._chat_messages.append({'id': f'a-{time.time()}', 'role': 'aura', 'text': reply, 'ts': time.time()})
        return self.chat_history()

    def chat_reset(self):
        self.llm.reset()
        self._chat_messages = [
            {'id': f'sys-{time.time()}', 'role': 'note', 'text': 'Conversation cleared. Ready whenever you want to reflect.', 'ts': time.time()}
        ]
        self._elevated_since = None
        return self.chat_history()

    def chat_history(self):
        return {'messages': list(self._chat_messages[-40:]), 'llm_status': self.llm.status}

    # ---------------------------------------------------- journal & study ----

    def journal_list(self):
        entries = journal_store.load() if self._persist else []
        return {
            'entries': list(reversed(entries)),
            'current_stats': self.stats.summary(),
            'current_stats_text': journal_store.stats_text(self.stats.summary()),
            'recording': self._collector is not None,
        }

    def journal_reflect(self, note=''):
        s = self.stats.summary()
        try:
            text = self.llm.generate(journal_store.reflect_prompt(s, note), journal_store.REFLECT_SYSTEM)
        except Exception:
            text = journal_store.local_reflection(s, note)
        return {'reflection': text}

    def save_journal_note(self, note='', reflection=''):
        """Save a note to journal.json ONLY — never stops an active recording."""
        s = self.stats.summary()
        note_txt = (note or '').strip()
        refl_txt = (reflection or '').strip() or journal_store.local_reflection(s, note_txt)
        entry = {
            'time': time.strftime('%d %b %H:%M'),
            'stats': s,
            'note': note_txt,
            'reflection': refl_txt,
        }
        if self._persist:
            journal_store.add(entry)
        return {'saved': True, 'entry': entry, 'recording_still_active': self._collector is not None}

    def consent_info(self):
        st = research.consent_status() if self._persist else {'granted': False}
        n = len(research.list_sessions()) if self._persist else 0
        cloud_on = bool(self.sync and self.sync.enabled)
        return {
            'granted': bool(st.get('granted')),
            'version': st.get('version'),
            'required_version': research.CONSENT_VERSION,
            'granted_at': st.get('granted_at'),
            'store_queries': bool(st.get('store_queries', True)),
            'participant_code': self.settings.get('participant_code', ''),
            'local_sessions': n,
            'cloud_sync_enabled': cloud_on,
            'cloud_status': self._sync_status,
            'pending_uploads': self._pending_n,
            'storage_summary': (
                'Stored locally on this computer and synced pseudonymously to Firebase when recorded.'
                if cloud_on else
                'Stored only on this computer (cloud sync is off).'
            ),
            'consent_text': research.CONSENT_TEXT,
        }

    def grant_consent(self, participant_code, store_queries=True):
        code = (participant_code or '').strip()
        if not code:
            raise ValueError('Participant code is required')
        if self._persist:
            research.give_consent(code, note='consent given in Aura v2', store_queries=bool(store_queries))
        self.settings['participant_code'] = code
        return self.consent_info()

    def withdraw_consent(self, confirm=False):
        if confirm is not True:
            raise ValueError('Explicit confirmation is required to withdraw and delete data')
        st = research.consent_status() if self._persist else {}
        pseudo = st.get('pseudonym')
        self._pending_finalize = False
        self._pending_summary = None
        self._close_log(sync=False)
        cloud_deleted = 0
        if pseudo and self.sync and self.sync.enabled:
            res = self.sync.delete_participant(pseudo)
            cloud_deleted = res.get('deleted', 0)
        removed = research.revoke_consent(purge=True) if self._persist else 0
        self._sync_refresh()
        return {'withdrawn': True, 'local_deleted': removed, 'cloud_deleted': cloud_deleted}

    def start_recording(self):
        if self._collector is not None:
            return self.recording_status()
        if not research.consent_status().get('granted'):
            raise PermissionError('Consent v4 must be saved before recording.')
        code = (self.settings.get('participant_code') or '').strip()
        if not code:
            raise PermissionError('Participant code is required before recording.')
        cond = self.settings.get('study_condition') or 'intervention'
        self.stats.reset()
        self._pending_finalize = False
        self._pending_summary = None
        self._collector = research.ResearchCollector(code, tick_hz=1.0 / self.POLL_S, condition=cond)
        self._log_start = time.time()
        # Automatically enforce participant blinding when a recording begins
        self.lab_unlocked = False
        return self.recording_status()

    def stop_recording(self):
        if self._collector is None:
            return {'recording': False, 'pending_finalize': False}
        self._pending_finalize = True
        self._pending_summary = self.stats.summary()
        return self.recording_status()

    def resume_recording(self):
        if self._collector is not None:
            self._pending_finalize = False
            self._pending_summary = None
        return self.recording_status()

    def finalize_recording(self, perceived_stress=None, mood=None, note='', reflection='', skip_ratings=False):
        summary = self._pending_summary or self.stats.summary()
        if self._collector is not None:
            if note or reflection:
                refl = (reflection or '').strip() or journal_store.local_reflection(summary, note)
                self._collector.set_journal(note, refl)
                if self._persist:
                    journal_store.add({
                        'time': time.strftime('%d %b %H:%M'),
                        'stats': summary,
                        'note': (note or '').strip(),
                        'reflection': refl,
                    })
            if not skip_ratings and perceived_stress is not None and mood is not None:
                self._collector.set_self_report(int(perceived_stress), int(mood))
            self._close_log(sync=True)
        self._pending_finalize = False
        self._pending_summary = None
        self.stats.reset()
        return self.recording_status()

    def _close_log(self, sync=True):
        if self._collector is not None:
            try:
                self._collector.end(self._pending_summary or self.stats.summary())
            except Exception as e:
                print('[Aura] close session error:', e)
            self._collector = None
            if sync and self.sync and self.sync.enabled:
                self._sync_refresh()
                threading.Thread(target=self._sync_once, daemon=True).start()

    def _log_tick(self, feats):
        if not self._collector or self._pending_finalize:
            return
        try:
            self._collector.log_tick(
                time.time() - self._log_start,
                self.engine.score,
                self.engine.tier,
                feats,
                brightness=self._last_bright,
                breathing=self._breathing_active,
                simulated=int(self._sim_ticks > 0),
                label='demo' if self._demo_target is not None else 'live',
            )
        except Exception:
            pass

    def recording_status(self):
        elapsed = int(max(0, time.time() - self._log_start)) if self._collector else 0
        return {
            'recording': self._collector is not None,
            'pending_finalize': self._pending_finalize,
            'elapsed_s': elapsed,
            'summary': self._pending_summary or self.stats.summary(),
        }

    # ---------------------------------------------------- lab, demo, sim ----

    def lock_lab(self):
        self.lab_unlocked = False
        return {'lab_unlocked': self.lab_unlocked, 'blinded': self.blinded}

    def unlock_lab(self):
        self.lab_unlocked = True
        return {'lab_unlocked': self.lab_unlocked, 'blinded': self.blinded}

    def simulate_mood(self, state, duration_s=45.0):
        if self.blinded:
            raise PermissionError('Simulation is locked during a blinded study recording. Unlock Researcher Lab first.')
        hub = getattr(self.search_server, 'hub', None) if self.search_server else None
        st = hub.simulate(state, duration_s) if hub else None
        if state == 'overwhelmed':
            self._sim_ticks = 30
            self._elevated_since = None
        elif state is None:
            self._sim_ticks = 0
        return st

    def demo_action(self, action, level=None):
        if self.blinded:
            raise PermissionError('Demo mode is locked during a blinded study recording.')
        if action == 'script':
            self._demo_script = list(self.DEMO_SCRIPT)
            self._demo_idx = -1
            self._demo_end = 0.0
            self._demo_target = self.engine.score
            self._elevated_since = None
            self._active_nudge = None
            return {'ok': True, 'status': 'Scripted demo started'}
        if action == 'manual':
            lvl = float(level if level is not None else 48)
            self._demo_script = []
            self._demo_idx = -1
            self._demo_target = lvl
            self._demo_status = f'Manual hold ({int(lvl)})'
            self._demo_note = 'Holding state until stopped.'
            return {'ok': True, 'status': self._demo_status}
        if action == 'stop':
            self._demo_target = None
            self._demo_script = []
            self._demo_idx = -1
            self._demo_status = 'Idle — using real keyboard/mouse input'
            self._demo_note = ''
            return {'ok': True, 'status': self._demo_status}
        if action == 'notify':
            app, text = self.DEMO_NOTIFS[self._notif_n % len(self.DEMO_NOTIFS)]
            self._notif_n += 1
            return self.notify(app, text)
        raise ValueError(f'Unknown demo action: {action}')

    def _demo_tick(self, now=None):
        now = now if now is not None else time.time()
        if self._demo_script and now >= self._demo_end:
            self._demo_idx += 1
            if self._demo_idx >= len(self._demo_script):
                self._demo_target = None
                self._demo_script = []
                self._demo_idx = -1
                self._demo_status = 'Demo finished'
                self._demo_note = ''
                return None
            label, level, secs, note, _events = self._demo_script[self._demo_idx]
            self._demo_target = level
            self._demo_end = now + secs
            self._demo_stage_start = now
            self._demo_fired = 0
            self._demo_note = note
        if self._demo_script and self._demo_idx >= 0:
            left = int(max(0, self._demo_end - now))
            self._demo_status = '{} ({}s)'.format(self._demo_script[self._demo_idx][0], left)
            events = self._demo_script[self._demo_idx][4]
            while self._demo_fired < len(events) and now - self._demo_stage_start >= events[self._demo_fired]:
                self._demo_fired += 1
                app, text = self.DEMO_NOTIFS[self._notif_n % len(self.DEMO_NOTIFS)]
                self._notif_n += 1
                self.notify(app, text, now=now)
        self.engine.smoothed += (self._demo_target - self.engine.smoothed) * 0.18
        kps, err, dwell, flight, px, clicks = self.DEMO_FEATS[
            0 if self._demo_target < 30 else 1 if self._demo_target < 60 else 2]
        j = lambda v: v * (1 + random.uniform(-0.08, 0.08))
        return {
            'keys_per_second': j(kps),
            'error_rate': j(err),
            'mean_dwell': j(dwell),
            'mean_flight': j(flight),
            'mouse_distance': j(px),
            'mouse_clicks': int(j(clicks)),
        }

    # --------------------------------------------------------- sync & state --

    def _sync_refresh(self):
        if not self.sync or not self.sync.enabled:
            self._pending_n = 0
            return
        try:
            self._pending_n = len(self.sync.pending())
        except Exception:
            self._pending_n = 0

    def _sync_once(self):
        if not self.sync or not self.sync.enabled:
            return
        try:
            self.sync.push_pending()
            self._sync_status = self.sync.status_line()
        except Exception:
            pass
        finally:
            self._sync_refresh()

    def _sync_loop(self):
        while self._running:
            self._sync_once()
            time.sleep(300)

    def set_comfort(self, **kwargs):
        allowed = ('auto_bright', 'focus_mode', 'auto_music', 'theme', 'auto_adapt',
                   'view_mode_override', 'onboarding_complete')
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if updates:
            self.settings.update(updates)
        if 'auto_bright' in updates and not updates['auto_bright']:
            self._restore_display()
        if 'focus_mode' in updates and not updates['focus_mode'] and self._dnd_active:
            if not self.standalone:
                self.os_ctrl.set_dnd(False)
            self._dnd_active = False
            self._release_held()
        return self.app_status()

    def update_engine_settings(self, values: dict):
        if self.blinded:
            raise PermissionError('Study condition and engine settings are locked during a blinded recording.')
        if 'study_condition' in values and values['study_condition'] in ('control', 'intervention'):
            cond = values['study_condition']
            self.settings['study_condition'] = cond
            if cond == 'control':
                self._restore_display()
                if self._dnd_active:
                    if not self.standalone:
                        self.os_ctrl.set_dnd(False)
                    self._dnd_active = False
                    self._release_held()
                self._active_nudge = None
            cur = self.live_state.get()
            if cur is not None:
                self.publish_live_state(cur.get('features') or {}, self._blocking())
        numeric_keys = ('cov_weight', 'error_weight', 'smoothing', 'sensitivity', 'decay_speed',
                        'bright_calm', 'bright_mild', 'bright_elev',
                        'temp_calm', 'temp_mild', 'temp_elev',
                        'vol_calm', 'vol_mild', 'vol_elev')
        updates = {}
        for k in numeric_keys:
            if k in values:
                updates[k] = float(values[k])
        if updates:
            self.settings.update(updates)
        return self.engine_settings()

    def engine_settings(self):
        return copy.deepcopy(self.settings.data)

    def app_status(self):
        t = self._track_cache
        sysvol = self._vol_current if self._vol_current is not None else (
            None if self.standalone else self.os_ctrl.get_volume())
        return {
            'comfort': {
                'auto_bright': bool(self.settings['auto_bright']),
                'focus_mode': bool(self.settings['focus_mode']),
                'auto_music': bool(self.settings['auto_music']),
                'theme': self.settings.get('theme', 'dark'),
                'auto_adapt': bool(self.settings.get('auto_adapt', True)),
                'view_mode_override': self.settings.get('view_mode_override', ''),
                'onboarding_complete': bool(self.settings.get('onboarding_complete', False)),
                'brightness': self._last_bright,
                'color_temp': self._last_temp,
                'focus_blocking': self._blocking(),
                'held_count': len(self._held),
                'delivered_count': self.stats.delivered,
                'held_total': self.stats.held,
            },
            'audio': {
                'spotify_configured': bool(self.spotify and self.spotify.configured),
                'spotify_connected': bool(self.spotify and self.spotify.connected),
                'spotify_status': self.spotify.status if self.spotify else 'Standalone mode',
                'track': t,
                'volume': t['volume'] if t else sysvol,
                'backend': 'Spotify' if (self.spotify and self.spotify.available) else (
                    self.os_ctrl.volume_backend if not self.standalone else 'simulated'),
            },
            'nudge': self._active_nudge,
            'focus_digest': self._focus_digest,
            'calibration': self.calibration_status(),
            'recording': self.recording_status(),
            'consent': self.consent_info(),
            'study': {
                'condition': self.settings['study_condition'],
                'blinded': self.blinded,
                'lab_unlocked': self.lab_unlocked,
            },
            'demo': {
                'active': self._demo_target is not None,
                'status': self._demo_status,
                'note': self._demo_note,
            },
        }
