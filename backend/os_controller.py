import ctypes
import math
import struct
import sys

import screen_brightness_control as sbc

# Windows volume media-key codes (used when pycaw is not installed).
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP   = 0xAF
KEYEVENTF_KEYUP = 0x0002


class OSController:
    """
    Brightness control via screen_brightness_control (handles both
    built-in laptop panels and external DDC/CI monitors).
    WMI is no longer required.

    System volume has two paths, picked at runtime:
      1. Windows Core Audio through pycaw  -> exact, absolute percentages.
      2. The Windows volume media keys     -> approximate, no dependency.
    Neither is required for the app to run; ``volume_backend`` reports which
    one is live so the UI can say "system volume unavailable" instead of lying.
    """

    def __init__(self):
        self._vol       = None      # IAudioEndpointVolume when pycaw works
        self._vol_tried = False
        self._vol_estimate = 50     # media-key fallback only
        self.volume_backend = 'unavailable'

    # ------------------------------------------------------------- brightness

    def get_brightness(self) -> int:
        try:
            levels = sbc.get_brightness()
            if levels:
                return int(levels[0])
        except Exception as e:
            print(f"[brightness] get failed: {e}")
        return 100

    def set_brightness(self, level: int):
        try:
            level = max(0, min(100, int(level)))
            sbc.set_brightness(level)
        except Exception as e:
            print(f"[brightness] set failed: {e}")

    # --------------------------------------------------------- system volume

    def _volume_interface(self):
        """Open the default output device once; None when pycaw is missing."""
        if self._vol_tried:
            return self._vol
        self._vol_tried = True
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            speakers = AudioUtilities.GetSpeakers()
            iface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._vol = cast(iface, POINTER(IAudioEndpointVolume))
            self.volume_backend = 'Core Audio'
        except Exception:
            self._vol = None
            self.volume_backend = 'volume keys' if sys.platform == 'win32' else 'unavailable'
        return self._vol

    @property
    def volume_available(self):
        return self.volume_backend != 'unavailable'

    def get_volume(self):
        """Master output volume 0-100, or None when it cannot be read."""
        iface = self._volume_interface()
        if iface is None:
            return None
        try:
            return int(round(iface.GetMasterVolumeLevelScalar() * 100))
        except Exception as e:
            print(f"[volume] get failed: {e}")
            return None

    @staticmethod
    def _tap(vk, times=1):
        """Press a media key n times (Windows SendInput-free, keybd_event)."""
        try:
            user32 = ctypes.windll.user32
        except Exception:
            return
        for _ in range(max(0, min(int(times), 50))):
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def set_volume(self, level: int):
        """Set master output volume to 0-100 using the best available path."""
        level = max(0, min(100, int(level)))
        iface = self._volume_interface()
        if iface is not None:
            try:
                iface.SetMasterVolumeLevelScalar(level / 100.0, None)
                self._vol_estimate = level
                return
            except Exception as e:
                print(f"[volume] set failed: {e}")
                return
        if sys.platform != 'win32':
            print(f"[volume] unavailable on this platform (wanted {level}%)")
            return
        # Media keys move ~2 % per press; step from our last known target.
        delta = level - self._vol_estimate
        steps = int(round(abs(delta) / 2.0))
        if steps:
            self._tap(VK_VOLUME_UP if delta > 0 else VK_VOLUME_DOWN, steps)
            self._vol_estimate = level

    # ------------------------------------------------------ notifications etc

    def set_dnd(self, enabled: bool):
        # Use Windows Notification Facility (WNF) to toggle Focus Assist natively
        try:
            ntdll = ctypes.windll.ntdll
            state = 2 if enabled else 0  # 2 = Alarms only, 0 = Off
            state_name = ctypes.c_uint64(0x0d83063ea3bf1c75)
            buffer = ctypes.create_string_buffer(bytes([state, 0x00, 0x00, 0x00]))
            ntdll.ZwUpdateWnfStateData(ctypes.byref(state_name), buffer, 4, None, None, 0, 0)
            print(f"[DND] Focus Assist -> {'ON' if enabled else 'OFF'}")
        except Exception as e:
            print(f"[DND] set failed: {e}")

    def set_color_temp(self, temp_k: int):
        # Approximate mapping from K to RGB scaling
        temp = max(1000, min(40000, temp_k)) / 100.0

        if temp <= 66:
            r = 255
        else:
            r = temp - 60
            r = 329.698727446 * (r ** -0.1332047592)

        if temp <= 66:
            g = temp
            g = 99.4708025861 * math.log(g) - 161.1195681661
        else:
            g = temp - 60
            g = 288.1221695283 * (g ** -0.0755148492)

        if temp >= 66:
            b = 255
        elif temp <= 19:
            b = 0
        else:
            b = temp - 10
            b = 138.5177312231 * math.log(b) - 305.0447927307

        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))

        r_scale = r / 255.0
        g_scale = g / 255.0
        b_scale = b / 255.0

        try:
            gamma = bytearray(256 * 3 * 2)
            for i in range(256):
                val_r = int(i * 256 * r_scale)
                val_g = int(i * 256 * g_scale)
                val_b = int(i * 256 * b_scale)
                val_r = max(0, min(65535, val_r))
                val_g = max(0, min(65535, val_g))
                val_b = max(0, min(65535, val_b))

                struct.pack_into("H", gamma, i * 2, val_r)
                struct.pack_into("H", gamma, 512 + i * 2, val_g)
                struct.pack_into("H", gamma, 1024 + i * 2, val_b)

            hdc = ctypes.windll.user32.GetDC(None)
            ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, bytes(gamma))
            ctypes.windll.user32.ReleaseDC(None, hdc)
        except Exception as e:
            print(f"[color_temp] set failed: {e}")


if __name__ == "__main__":
    ctrl = OSController()
    current = ctrl.get_brightness()
    print(f"Current brightness: {current}%")
    print(f"Volume backend    : {ctrl.volume_backend}")
    print(f"Current volume    : {ctrl.get_volume()}")
