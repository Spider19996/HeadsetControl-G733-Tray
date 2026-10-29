import os
import unittest

from g733_tray.hidwatch import HidWatcher
from tests import qt

ON = bytes.fromhex("11ff08000eee0100000000000000000000000000")        # on, discharging
CHARGING = bytes.fromhex("11ff080a0efe0300000000000000000000000000")  # on, charging
OFF = bytes.fromhex("11ff08000000000000000000000000000000000000")
LIGHT_ACK = bytes.fromhex("11ff043c010200b6ff0fa000640000000000")    # not a power report


class Watcher(unittest.TestCase):
    def setUp(self):
        qt.app()
        self.watcher = HidWatcher()
        self.power, self.charging = [], []
        self.watcher.power_changed.connect(self.power.append)
        self.watcher.charging_changed.connect(self.charging.append)

    def tearDown(self):
        self.watcher._retry.stop()

    def test_power_changes_are_reported_once(self):
        for report in (ON, ON, OFF, OFF, ON):
            self.watcher._handle(report)
        self.assertEqual(self.power, [True, False, True])

    def test_other_reports_are_ignored(self):
        for report in (LIGHT_ACK, b"", bytes.fromhex("0100000000")):
            self.watcher._handle(report)
        self.assertEqual(self.power, [])
        self.assertEqual(self.charging, [])

    def test_first_charging_state_is_not_a_change(self):
        self.watcher._handle(ON)        # first report: the state becomes known, nothing is emitted
        self.assertEqual(self.charging, [])
        self.watcher._handle(CHARGING)
        self.watcher._handle(CHARGING)
        self.watcher._handle(ON)
        self.assertEqual(self.charging, [True, False])

    def test_switching_off_while_charging_reports_power_only(self):
        self.watcher._handle(CHARGING)
        self.watcher._handle(OFF)
        self.assertEqual(self.power, [True, False])
        self.assertEqual(self.charging, [])

    def test_unplugging_the_dongle_reports_off(self):
        self.watcher._power = True
        read_fd, write_fd = os.pipe()   # stands in for the hidraw node
        self.watcher._close(read_fd)
        os.close(write_fd)
        self.assertEqual(self.power, [False])

    def test_default_device_comes_from_the_config_defaults(self):
        from g733_tray.config import DEFAULTS
        self.assertEqual((self.watcher._vendor, self.watcher._product),
                         (int(DEFAULTS["usb_vendor_id"], 16), int(DEFAULTS["usb_product_id"], 16)))


if __name__ == "__main__":
    unittest.main()
