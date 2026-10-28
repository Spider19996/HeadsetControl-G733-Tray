import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from g733_tray import __version__
from g733_tray.about import headsetcontrol_too_old, install_kind, parse_version
from g733_tray.app import format_duration, lock_path
from g733_tray.alerts import CRITICAL, WARNING, FullChargeDetector, LowBatteryAlerts
from g733_tray.config import Config
from g733_tray.devices import parse_devices
from g733_tray.headsetcontrol import FAILED, NO_DEVICE, parse_battery
from g733_tray.hidwatch import parse_charging, parse_power


class PowerParsing(unittest.TestCase):
    def test_off(self):
        self.assertIs(parse_power(bytes.fromhex("11ff08000000000000000000000000000000000000")), False)

    def test_on(self):
        self.assertIs(parse_power(bytes.fromhex("11ff08000eee0100000000000000000000000000")), True)

    def test_ignored(self):
        self.assertIsNone(parse_power(bytes.fromhex("0100000000")))
        self.assertIsNone(parse_power(bytes.fromhex("11ff043c0102 00b6ff0fa000640000000000")))
        self.assertIsNone(parse_power(b""))


class ChargingParsing(unittest.TestCase):
    def test_flag(self):
        self.assertIs(parse_charging(bytes.fromhex("11ff080a0efe0300000000000000000000000000")), True)
        self.assertIs(parse_charging(bytes.fromhex("11ff080a0eec0100000000000000000000000000")), False)

    def test_off_and_other_reports(self):
        self.assertIs(parse_charging(bytes.fromhex("11ff08000000000000000000000000000000000000")), False)
        self.assertIsNone(parse_charging(bytes.fromhex("0100000000")))


class Alerts(unittest.TestCase):
    def test_once_per_discharge(self):
        a = LowBatteryAlerts(20, 10)
        self.assertIsNone(a.update(30, False))
        self.assertEqual(a.update(19, False), WARNING)
        self.assertIsNone(a.update(18, False))
        self.assertEqual(a.update(10, False), CRITICAL)
        self.assertIsNone(a.update(5, False))

    def test_rearm_by_charging_and_level(self):
        a = LowBatteryAlerts(20, 10)
        self.assertEqual(a.update(5, False), CRITICAL)
        self.assertIsNone(a.update(5, True))
        self.assertEqual(a.update(8, False), CRITICAL)
        a.update(50, False)
        self.assertEqual(a.update(15, False), WARNING)

    def test_jump_below_both_gives_only_critical(self):
        a = LowBatteryAlerts(20, 10)
        self.assertEqual(a.update(8, False), CRITICAL)
        self.assertIsNone(a.update(7, False))


class FullCharge(unittest.TestCase):
    def feed(self, detector, samples):
        return [detector.update(t, mv, True) for t, mv in samples]

    def test_plateau_reports_once(self):
        d = FullChargeDetector(window_s=600, max_rise_mv=5, min_mv=4100)
        samples = [(t, 4150 + t // 300) for t in range(0, 1300, 60)]  # +1 mV je 5 min
        results = self.feed(d, samples)
        self.assertEqual(results.count(True), 1)
        self.assertTrue(results.index(True) >= 9)  # erst nach annähernd vollem Fenster

    def test_rising_voltage_is_not_full(self):
        d = FullChargeDetector()
        self.assertNotIn(True, self.feed(d, [(t, 4100 + t // 20) for t in range(0, 1300, 60)]))

    def test_low_plateau_is_not_full(self):
        d = FullChargeDetector()
        self.assertNotIn(True, self.feed(d, [(t, 3900) for t in range(0, 1300, 60)]))

    def test_reset_when_not_charging(self):
        d = FullChargeDetector()
        self.feed(d, [(t, 4150) for t in range(0, 700, 60)])
        self.assertFalse(d.update(700, 4150, False))
        self.assertFalse(d.update(760, 4150, True))  # neuer Ladevorgang, Fenster leer


class AboutTest(unittest.TestCase):
    def test_install_kinds(self):
        with tempfile.TemporaryDirectory() as d:
            tree = Path(d) / "repo"
            (tree / "g733_tray").mkdir(parents=True)
            (tree / "pyproject.toml").write_text("")
            self.assertEqual(install_kind(tree / "g733_tray"), "Quellbaum (Entwicklung)")
        user = "/home/x/.local/share/g733-tray/venv/lib/python3.14/site-packages/g733_tray"
        self.assertEqual(install_kind(user, user_venv=Path("/home/x/.local/share/g733-tray/venv")),
                         "install.sh (Benutzer-Installation)")
        custom = "/data/g733-tray/venv/lib/python3.14/site-packages/g733_tray"  # abweichendes XDG_DATA_HOME
        self.assertEqual(install_kind(custom, user_venv=Path("/data/g733-tray/venv")),
                         "install.sh (Benutzer-Installation)")
        system = "/usr/lib/python3/dist-packages/g733_tray"
        deb = install_kind(system, lambda cmd, path: cmd[0] == "dpkg", lambda b: b)
        self.assertEqual(deb, "Debian-Paket (.deb)")
        rpm = install_kind(system, lambda cmd, path: cmd[0] == "rpm", lambda b: b)
        self.assertEqual(rpm, "RPM-Paket")
        self.assertEqual(install_kind(system, lambda *_: False, lambda b: None), "Systeminstallation")
        self.assertEqual(install_kind("/opt/venv/lib/python3.12/site-packages/g733_tray",
                                      lambda *_: False, lambda b: None), "pip")

    def test_headsetcontrol_version_check(self):
        self.assertEqual(parse_version("HeadsetControl 4.2.0"), (4, 2, 0))
        self.assertTrue(headsetcontrol_too_old("HeadsetControl 3.1.0"))
        self.assertFalse(headsetcontrol_too_old("HeadsetControl 4.2.0"))
        self.assertFalse(headsetcontrol_too_old("HeadsetControl 4.10.1"))
        self.assertFalse(headsetcontrol_too_old(None))  # unbekannt: nicht warnen

    def test_duration(self):
        self.assertEqual(format_duration(459), "7 h 39 min")
        self.assertEqual(format_duration(45), "45 min")
        self.assertEqual(format_duration(120), "2 h 00 min")

    def test_lock_path_is_per_user(self):
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/1000"}):
            self.assertEqual(lock_path(), f"/run/user/1000/g733-tray-{os.getuid()}.lock")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(lock_path().endswith(f"g733-tray-{os.getuid()}.lock"))

    def test_version_is_semver(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")


class DevicesTest(unittest.TestCase):
    def test_parse_detected_devices(self):
        out = json.dumps({"device_count": 2, "devices": [
            {"vendor": "Logitech", "product": "G733 Gaming Headset", "id_vendor": "0x046d", "id_product": "0x0ab5"},
            {"vendor": "SteelSeries", "product": "Arctis 7", "id_vendor": "0x1038", "id_product": "0x12AD"},
            {"vendor": "Kaputt", "product": "Ohne IDs"},
        ]})
        devices = parse_devices(out)
        self.assertEqual([d.ids for d in devices], ["046d:0ab5", "1038:12ad"])
        self.assertEqual(devices[0].label, "Logitech G733 Gaming Headset (046d:0ab5)")

    def test_parse_nothing(self):
        self.assertEqual(parse_devices("kein json"), [])
        self.assertEqual(parse_devices(json.dumps({"device_count": 0, "devices": []})), [])


class Battery(unittest.TestCase):
    def test_states(self):
        def doc(status, level):
            return json.dumps({"devices": [{"battery": {"status": status, "level": level}}]})
        self.assertTrue(parse_battery(doc("BATTERY_AVAILABLE", 51))[0].powered)
        self.assertTrue(parse_battery(doc("BATTERY_CHARGING", 51))[0].charging)
        self.assertFalse(parse_battery(doc("BATTERY_UNAVAILABLE", -1))[0].powered)
        self.assertEqual(parse_battery("kein json"), (None, FAILED))
        self.assertEqual(parse_battery(json.dumps({"device_count": 0, "devices": []})), (None, NO_DEVICE))

    def test_time_to_empty_only_when_discharging(self):
        def doc(status):
            return json.dumps({"devices": [{"battery": {"status": status, "level": 50, "time_to_empty_min": 459}}]})
        self.assertEqual(parse_battery(doc("BATTERY_AVAILABLE"))[0].time_to_empty_min, 459)
        self.assertIsNone(parse_battery(doc("BATTERY_CHARGING"))[0].time_to_empty_min)

    def test_voltage(self):
        out = json.dumps({"devices": [{"battery": {"status": "BATTERY_CHARGING", "level": 100, "voltage_mv": 4150}}]})
        self.assertEqual(parse_battery(out)[0].voltage_mv, 4150)


class ConfigTest(unittest.TestCase):
    def test_roundtrip_and_validation(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            path.write_text(json.dumps({"warn_threshold": 5, "critical_threshold": 15, "foo": 1}))
            c = Config(path)
            self.assertEqual((c["critical_threshold"], c["warn_threshold"]), (5, 15))  # sortiert
            c.set("light", False)
            self.assertEqual(json.loads(path.read_text())["foo"], 1)

    def test_reload_and_sidetone(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            c = Config(path)
            self.assertIsNone(c["sidetone"])
            path.write_text(json.dumps({"sidetone": 500, "warn_threshold": 33}))
            self.assertTrue(c.reload())
            self.assertEqual((c["sidetone"], c["warn_threshold"]), (128, 33))
            path.write_text("{kaputt")
            self.assertFalse(c.reload())
            self.assertEqual(c["warn_threshold"], 33)  # bisheriger Stand bleibt

    def test_usb_ids_normalized(self):
        from g733_tray.config import normalize_usb_id
        self.assertEqual(normalize_usb_id("0x046D", "dflt"), "046d")
        self.assertEqual(normalize_usb_id("46d", "dflt"), "046d")
        self.assertEqual(normalize_usb_id("", "dflt"), "dflt")
        self.assertEqual(normalize_usb_id("12345", "dflt"), "dflt")
        self.assertEqual(normalize_usb_id("zz", "dflt"), "dflt")
        with tempfile.TemporaryDirectory() as d:
            c = Config(Path(d) / "c.json")
            c.update({"usb_vendor_id": "1038", "usb_product_id": "kaputt"})
            self.assertEqual((c["usb_vendor_id"], c["usb_product_id"]), ("1038", "0ab5"))

    def test_read_only_never_writes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            Config(path, read_only=True).set("light", False)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
