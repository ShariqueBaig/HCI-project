"""System-volume fallback (merged from the barkhi branch). Never changes the real volume."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.os_controller import OSController


class VolumeKeysFallbackTests(unittest.TestCase):
    def make(self):
        c = OSController()
        c._vol_tried, c._vol, c.volume_backend = True, None, 'volume keys'   # as if pycaw were missing
        c.taps = []
        c._tap = lambda vk, times=1: c.taps.append((vk, times))             # no real key presses
        return c

    def test_fallback_reports_its_estimate_so_the_ramp_runs(self):
        c = self.make()
        self.assertEqual(c.get_volume(), 50)
        c.set_volume(40)
        self.assertEqual(c.get_volume(), 40)
        self.assertEqual(c.taps, [(0xAE, 5)])          # five volume-down presses of ~2 %

    def test_unavailable_still_reports_none(self):
        c = OSController()
        c._vol_tried, c._vol, c.volume_backend = True, None, 'unavailable'
        self.assertIsNone(c.get_volume())


if __name__ == '__main__':
    unittest.main()
