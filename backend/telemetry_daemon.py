import time
import threading
from pynput import keyboard, mouse
from collections import deque
import statistics
import math

# Keys that signal a keyboard shortcut when held.
# Any keypress while one of these is down is excluded from stress scoring.
SHORTCUT_MODS = frozenset({
    keyboard.Key.ctrl,  keyboard.Key.ctrl_l,  keyboard.Key.ctrl_r,
    keyboard.Key.alt,   keyboard.Key.alt_l,   keyboard.Key.alt_r,
    keyboard.Key.cmd,   keyboard.Key.cmd_l,   keyboard.Key.cmd_r,
})

class TelemetryDaemon:
    def __init__(self, window_size_seconds=5):
        self.window_size_seconds = window_size_seconds
        
        # State tracking for the time window
        self.key_press_times = {} # key_id -> press timestamp
        self.dwell_times = deque()
        self.flight_times = deque()
        self.last_release_time = None
        
        # Cumulative error tracking within the window
        self.backspace_count = 0
        self.total_keys = 0
        
        self.lock = threading.Lock()
        self._mods_down = set()  # currently held shortcut-modifier keys

        # Mouse tracking
        self.mouse_distances = deque()
        self.mouse_clicks = deque()
        self.last_mouse_pos = None
        
    def on_press(self, key):
        current_time = time.time()
        with self.lock:
            # Track modifier state; don't count modifiers themselves
            if key in SHORTCUT_MODS:
                self._mods_down.add(key)
                return
            # Skip shortcut combo keys (e.g. the 'C' in Ctrl+C)
            if self._mods_down:
                if key not in (keyboard.Key.backspace, keyboard.Key.delete):
                    return

            key_id = id(key)
            is_auto_repeat = key_id in self.key_press_times
            if not is_auto_repeat:
                self.key_press_times[key_id] = current_time
            elif key == keyboard.Key.backspace or key == keyboard.Key.delete:
                # If they hold backspace (auto-repeat), penalize heavily
                self.backspace_count += 2
                
            if key == keyboard.Key.backspace or key == keyboard.Key.delete:
                if self._mods_down:
                    self.backspace_count += 4  # modified delete (e.g. word delete) has higher penalty
                else:
                    self.backspace_count += 1
            self.total_keys += 1

    def on_release(self, key):
        current_time = time.time()
        key_id = id(key)
        with self.lock:
            was_in_shortcut = bool(self._mods_down)
            self._mods_down.discard(key)

            if key in SHORTCUT_MODS:
                # When all modifiers are finally released, reset the flight timer
                # so the next real keystroke doesn't measure from end-of-shortcut.
                if not self._mods_down:
                    self.last_release_time = None
                return

            # Skip release processing for keys pressed during a shortcut
            if was_in_shortcut:
                if key not in (keyboard.Key.backspace, keyboard.Key.delete):
                    return

            if key_id in self.key_press_times:
                press_time = self.key_press_times.pop(key_id)
                dwell_time = current_time - press_time
                self.dwell_times.append((current_time, dwell_time))

            if self.last_release_time is not None:
                flight_time = current_time - self.last_release_time
                # Ignore gaps > 2 s — that's a typing pause, not a flight time.
                if flight_time < 2.0:
                    self.flight_times.append((current_time, flight_time))
                else:
                    self.last_release_time = None

            self.last_release_time = current_time

            # Clean up old data outside the time window
            cutoff = current_time - self.window_size_seconds
            while self.dwell_times and self.dwell_times[0][0] < cutoff:
                self.dwell_times.popleft()
            while self.flight_times and self.flight_times[0][0] < cutoff:
                self.flight_times.popleft()

    def on_move(self, x, y):
        current_time = time.time()
        with self.lock:
            if self.last_mouse_pos:
                dx = x - self.last_mouse_pos[0]
                dy = y - self.last_mouse_pos[1]
                dist = math.hypot(dx, dy)
                self.mouse_distances.append((current_time, dist))
            self.last_mouse_pos = (x, y)
            
            cutoff = current_time - self.window_size_seconds
            while self.mouse_distances and self.mouse_distances[0][0] < cutoff:
                self.mouse_distances.popleft()

    def on_click(self, x, y, button, pressed):
        if not pressed:
            return
        current_time = time.time()
        with self.lock:
            self.mouse_clicks.append(current_time)
            cutoff = current_time - self.window_size_seconds
            while self.mouse_clicks and self.mouse_clicks[0] < cutoff:
                self.mouse_clicks.popleft()

    def get_features(self):
        with self.lock:
            current_time = time.time()
            cutoff = current_time - self.window_size_seconds
            
            active_dwells = [d for t, d in self.dwell_times if t >= cutoff]
            active_flights = [f for t, f in self.flight_times if t >= cutoff]
            active_distances = [d for t, d in self.mouse_distances if t >= cutoff]
            active_clicks = [t for t in self.mouse_clicks if t >= cutoff]
            
            features = {
                "mean_dwell": statistics.mean(active_dwells) if active_dwells else 0.0,
                "std_dwell": statistics.stdev(active_dwells) if len(active_dwells) > 1 else 0.0,
                "mean_flight": statistics.mean(active_flights) if active_flights else 0.0,
                "std_flight": statistics.stdev(active_flights) if len(active_flights) > 1 else 0.0,
                "error_rate": self.backspace_count / max(self.total_keys, 1),
                "keys_per_second": len(active_dwells) / self.window_size_seconds,
                "flight_count": len(active_flights),  # used to suppress CoV on thin samples
                "mouse_distance": sum(active_distances),
                "mouse_clicks": len(active_clicks),
            }
            
            # Reset counts for the next extraction
            self.backspace_count = 0
            self.total_keys = 0
            
            return features

    def start(self):
        self.kb_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        self.kb_listener.start()
        
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click)
        self.mouse_listener.start()
        
if __name__ == "__main__":
    daemon = TelemetryDaemon()
    daemon.start()
    print("Telemetry daemon started. Monitoring keystroke dynamics silently (no characters logged).")
    try:
        while True:
            time.sleep(5)
            features = daemon.get_features()
            print(f"Extracted Features: {features}")
    except KeyboardInterrupt:
        pass
