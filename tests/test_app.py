import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PyQt6.QtGui import QColor, QIcon

from g733_tray import i18n, settings
from g733_tray.app import TrayApp
from g733_tray.config import Config
from g733_tray.headsetcontrol import BatteryStatus
from tests import qt


class StubHeadsetcontrol:
    """Records the commands instead of starting headsetcontrol."""

    def __init__(self):
        self.calls = []

    def battery(self, callback):
        self.calls.append(("battery",))

    def set_light(self, on, callback=None):
        self.calls.append(("light", on))

    def set_sidetone(self, level, callback=None):
        self.calls.append(("sidetone", level))

    def version(self, callback):
        self.calls.append(("version",))


class StubNotifier:
    def __init__(self):
        self.sends = []

    def send(self, title, text, critical=False):
        self.sends.append((title, text, critical))


class TrayLogic(unittest.TestCase):
    def setUp(self):
        qt.app()
        i18n.set_language("en")
        self.dir = tempfile.TemporaryDirectory()
        self.config = Config(Path(self.dir.name) / "c.json", read_only=True)
        # The fake battery needs no hardware; 80 % is above the thresholds, so nothing is notified while starting.
        self.app = TrayApp(self.config, (BatteryStatus(True, 80, False), False, 2.0))
        self.app.fake = None  # from here on behave like the real program
        self.app.hc = StubHeadsetcontrol()
        self.app.notifier = StubNotifier()

    def tearDown(self):
        self.app._relight.stop()
        self.app._retry_poll.stop()
        self.dir.cleanup()

    def test_off_answer_right_after_hid_on_is_ignored(self):
        self.app.on_power(True, from_hid=True)
        self.app.on_battery(BatteryStatus(powered=False))
        self.assertTrue(self.app.powered)
        self.assertTrue(self.app._retry_poll.isActive())  # asks again soon

    def test_off_answer_without_recent_hid_on_is_believed(self):
        self.app.on_battery(BatteryStatus(powered=False))
        self.assertIs(self.app.powered, False)

    def test_power_on_applies_the_saved_settings_after_the_delay(self):
        self.config.update({"light": False, "sidetone": 64})
        self.app.on_power(False)
        self.app.on_power(True, from_hid=True)
        self.assertTrue(self.app._relight.isActive())
        self.app._apply_saved_settings()  # what the timer calls after relight_delay_ms
        self.assertIn(("light", False), self.app.hc.calls)
        self.assertIn(("sidetone", 64), self.app.hc.calls)

    def test_power_off_stops_the_pending_relight_and_clears_charging(self):
        self.app.on_battery(BatteryStatus(True, 100, True))
        self.app.on_power(False)
        self.app.on_power(True, from_hid=True)
        self.assertTrue(self.app._relight.isActive())
        self.app.on_power(False)
        self.assertFalse(self.app._relight.isActive())
        self.assertFalse(self.app.charging)

    def test_level_before_charge_is_remembered_and_shown(self):
        self.app.on_battery(BatteryStatus(True, 55, False))
        self.app.on_battery(BatteryStatus(True, 100, True))
        self.assertEqual(self.app.level_before_charge, 55)
        self.assertIn("55 %", self.app.tray.toolTip())
        self.app.on_battery(BatteryStatus(True, 100, False))
        self.assertIsNone(self.app.level_before_charge)

    def test_low_battery_notifies_once_per_threshold(self):
        self.app.on_battery(BatteryStatus(True, 15, False))
        self.app.on_battery(BatteryStatus(True, 14, False))
        self.assertEqual([critical for _t, _x, critical in self.app.notifier.sends], [False])
        self.app.on_battery(BatteryStatus(True, 9, False))
        self.assertEqual([critical for _t, _x, critical in self.app.notifier.sends], [False, True])

    def test_no_notifications_when_switched_off(self):
        self.config.update({"notifications": False})
        self.app.on_battery(BatteryStatus(True, 5, False))
        self.assertEqual(self.app.notifier.sends, [])

    def test_icon_text_color_follows_the_level(self):
        self.config.update({"text_color": "#111111", "text_color_warning": "#222222", "text_color_critical": "#333333"})
        for level, expected in ((80, "#111111"), (15, "#222222"), (5, "#333333")):
            with mock.patch("g733_tray.app.battery_icon", return_value=QIcon()) as icon:
                self.app.on_battery(BatteryStatus(True, level, False))
                self.assertEqual(icon.call_args.args[-1], expected, level)


class SettingsColors(unittest.TestCase):
    def setUp(self):
        qt.app()
        i18n.set_language("en")
        self.dir = tempfile.TemporaryDirectory()
        self.config = Config(Path(self.dir.name) / "c.json", read_only=True)
        for name, result in (("detect_devices", []), ("headsetcontrol_version", "HeadsetControl 4.2.0")):
            patcher = mock.patch.object(settings, name, return_value=result)  # no calls to the real headsetcontrol
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.dir.cleanup()

    def colors(self, dialog):
        values = dialog.values()
        return values["text_color"], values["text_color_warning"], values["text_color_critical"]

    def test_values_contain_the_three_colors(self):
        self.config.update({"text_color_warning": "#ff8800"})
        self.assertEqual(self.colors(settings.SettingsDialog(self.config, False, False)),
                         ("#ffffff", "#ff8800", "#ffffff"))

    def test_choosing_a_color_changes_only_that_color(self):
        dialog = settings.SettingsDialog(self.config, False, False)
        with mock.patch.object(settings.QColorDialog, "getColor", return_value=QColor("#00ff00")):
            dialog._choose_text_color("text_color_critical")
        self.assertEqual(self.colors(dialog), ("#ffffff", "#ffffff", "#00ff00"))
        self.assertEqual(dialog.text_color_buttons["text_color_critical"].text(), "#00ff00")

    def test_cancelling_the_color_dialog_keeps_the_color(self):
        dialog = settings.SettingsDialog(self.config, False, False)
        with mock.patch.object(settings.QColorDialog, "getColor", return_value=QColor()):  # invalid = cancelled
            dialog._choose_text_color("text_color")
        self.assertEqual(self.colors(dialog), ("#ffffff", "#ffffff", "#ffffff"))

    def test_defaults_button_resets_the_colors(self):
        self.config.update({"text_color": "#123456", "text_color_critical": "#654321"})
        dialog = settings.SettingsDialog(self.config, False, False)
        dialog._restore_defaults()
        self.assertEqual(self.colors(dialog), ("#ffffff", "#ffffff", "#ffffff"))
        self.assertEqual(dialog.text_color_buttons["text_color"].text(), "#ffffff")


if __name__ == "__main__":
    unittest.main()
