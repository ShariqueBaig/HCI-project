import screen_brightness_control as sbc
import ctypes
import math
import struct

class OSController:
    """
    Brightness control via screen_brightness_control (handles both
    built-in laptop panels and external DDC/CI monitors).
    WMI is no longer required.
    """

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

    # TODO: pycaw implementation for system volume
    def set_volume(self, level: int):
        print(f"[MOCK] System volume -> {level}%")

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
