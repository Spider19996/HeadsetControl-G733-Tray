"""Tray-Anwendung: verbindet HID-Wächter, headsetcontrol, Icon und Benachrichtigungen."""
import argparse
import logging
import os
import signal
import sys
import tempfile
import time

from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QFileSystemWatcher, QLockFile, QObject, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import __version__, autostart, logsetup
from .about import MIN_HEADSETCONTROL, headsetcontrol_too_old, install_kind
from .alerts import CRITICAL, WARNING, FullChargeDetector, LowBatteryAlerts
from .config import Config
from .i18n import N_, set_language, tr
from .headsetcontrol import FAILED, MISSING, NO_DEVICE, BatteryStatus, Headsetcontrol
from .hidwatch import HidWatcher
from .icons import battery_icon, status_color, status_dot
from .notifier import Notifier
from .settings import SettingsDialog

NAME = "G733"
log = logging.getLogger("g733.app")
PROBLEMS = {  # Anzeige per tr(PROBLEMS[...])
    MISSING: N_("headsetcontrol nicht gefunden"),
    NO_DEVICE: N_("Dongle nicht gefunden"),
    FAILED: N_("headsetcontrol-Fehler (siehe Logdatei)"),
}
RETRY_POLL_MS = 3000
HID_GRACE_S = 8  # so lange wird ein "aus" vom Abgleich nach einem HID-"an" nicht geglaubt
TRAY_WAIT_MS = 2000
TRAY_WAIT_MAX_MS = 120_000
SIDETONE_PRESETS = [(N_("Unverändert"), None), (N_("Aus"), 0), (N_("Niedrig"), 32), (N_("Mittel"), 64), (N_("Hoch"), 96)]


class FakeBattery(QObject):
    """Testmodus: ersetzt headsetcontrol -b und den HID-Wächter durch einen künstlichen Stand."""

    def __init__(self, status, drain_interval_s, drain, on_status, parent=None):
        super().__init__(parent)
        self._status = status
        self._on_status = on_status
        self._timer = QTimer(self)
        self._timer.setInterval(int(drain_interval_s * 1000))
        self._timer.timeout.connect(self._drain)
        self._drain_enabled = drain

    def start(self):
        self._on_status(self._status)
        if self._drain_enabled and self._status.powered:
            self._timer.start()

    def _drain(self):
        if self._status.level is None or self._status.level <= 0:
            self._timer.stop()
            return
        self._status.level -= 1
        log.info("[test] battery level %s %%", self._status.level)
        self._on_status(self._status)


class TrayApp(QObject):
    def __init__(self, config, fake=None):
        super().__init__()
        self.config = config
        self.fake = fake  # (BatteryStatus, drain, drain_interval_s) oder None
        self.alerts = LowBatteryAlerts(config["warn_threshold"], config["critical_threshold"])
        self.full_detector = FullChargeDetector()
        self.powered = None  # None = unbekannt
        self.level = None
        self.charging = False
        self.level_before_charge = None  # beim Laden ist der gemeldete Prozentwert unzuverlässig
        self.time_to_empty_min = None
        self.problem = None  # Text, wenn headsetcontrol fehlt/scheitert oder der Dongle fehlt
        self._hid_on_at = None  # Zeitpunkt des letzten "an" vom HID-Wächter

        self.hc = Headsetcontrol(self)
        self._apply_device_ids()
        self.tray = QSystemTrayIcon(self)
        self.notifier = Notifier(self.tray)
        self._build_menu()

        self._relight = QTimer(self)
        self._relight.setSingleShot(True)
        self._relight.timeout.connect(self._apply_saved_settings)
        self._relight_tries = 0
        self._retry_poll = QTimer(self)
        self._retry_poll.setSingleShot(True)
        self._retry_poll.timeout.connect(self.poll)

        self._refresh_ui()
        self.tray.show()

        if self.fake:
            status, drain, interval = self.fake
            self.source = FakeBattery(status, interval, drain, self.on_battery, self)
            self.source.start()
        else:
            self.hid = HidWatcher(*self._device_ids(), parent=self)
            self.hid.power_changed.connect(lambda on: self.on_power(on, from_hid=True))
            self.hid.charging_changed.connect(lambda _charging: self.poll())  # Stand sofort holen
            self.hid.start()
            self._poll = QTimer(self)
            self._poll.setInterval(config["poll_interval_s"] * 1000)
            self._poll.timeout.connect(self.poll)
            self._poll.start()
            self.poll()
            self.hc.version(self._check_headsetcontrol_version)
            self._watch_config()

    # ---- Menü -------------------------------------------------------------
    def _build_menu(self):
        menu = QMenu()
        # Plasma zeigt das Menü über DBusMenu: Widgets und Farben im Text gehen dort verloren,
        # ein farbiger Punkt als Icon kommt an. Klick = Status neu abfragen.
        self.status_action = menu.addAction(NAME, self._refresh_status)
        menu.addSeparator()
        self.light_action = self._checkable(menu, tr("Licht an"), self.config["light"], self._toggle_light)
        self._build_sidetone_menu(menu)
        menu.addSeparator()
        menu.addAction(tr("Einstellungen …"), self._open_settings)
        menu.addSeparator()
        menu.addAction(tr("Beenden"), QApplication.quit)
        self.menu = menu  # Referenz halten, das Tray besitzt das Menü nicht
        self.tray.setContextMenu(menu)

    def _build_sidetone_menu(self, menu):
        sub = menu.addMenu(tr("Sidetone (Mikrofon-Rückhörung)"))
        self.sidetone_group = QActionGroup(sub)
        self.sidetone_group.setExclusive(True)
        for label, value in SIDETONE_PRESETS:
            action = sub.addAction(tr(label))
            action.setCheckable(True)
            action.setData(value)
            action.setChecked(value == self.config["sidetone"])
            self.sidetone_group.addAction(action)
            action.triggered.connect(lambda _checked, v=value: self._set_sidetone(v))
        self.sidetone_menu = sub

    @staticmethod
    def _checkable(menu, text, checked, slot):
        action = QAction(text, menu)
        action.setCheckable(True)
        action.setChecked(checked)
        action.toggled.connect(slot)
        menu.addAction(action)
        return action

    def _toggle_light(self, on):
        self.config.set("light", on)  # im Testmodus ist die Config schreibgeschützt
        if self.powered is not False:  # ist das Headset aus, wird es beim Einschalten gesetzt
            self.hc.set_light(on)

    def _set_sidetone(self, value):
        self.config.set("sidetone", value)
        if value is not None and self.powered is not False:
            self.hc.set_sidetone(value)

    def _open_settings(self):
        has_system_launcher = autostart.system_launcher_exists()
        dialog = SettingsDialog(self.config, autostart.is_enabled(),
                                None if has_system_launcher else autostart.launcher_installed())
        if not dialog.exec():
            return
        old = dict(self.config.data)
        self.config.update(dialog.values())
        self.apply_config(old)
        self._sync_entry(dialog.autostart.isChecked(), autostart.is_enabled, autostart.enable, autostart.disable)
        if not has_system_launcher:
            self._sync_entry(dialog.launcher.isChecked(), autostart.launcher_installed,
                             autostart.install_launcher, autostart.remove_launcher)

    @staticmethod
    def _sync_entry(wanted, exists, create, remove):
        if wanted == exists():
            return
        try:
            create() if wanted else remove()
        except OSError as err:
            log.warning("desktop entry: %s", err)

    # ---- Konfiguration ----------------------------------------------------
    def _device_ids(self):
        return int(self.config["usb_vendor_id"], 16), int(self.config["usb_product_id"], 16)

    def _apply_device_ids(self):
        self.hc.set_device(self.config["usb_vendor_id"], self.config["usb_product_id"])

    def _watch_config(self):
        """Änderungen an der config.json (Editor, Einstellungsdialog) ohne Neustart übernehmen.

        Beobachtet Datei und Verzeichnis: Speichern per Umbenennen (die meisten Editoren, unser eigenes Speichern)
        ändert nur das Verzeichnis, direktes Überschreiben nur die Datei.
        """
        directory = self.config.path.parent
        if not directory.is_dir():
            return
        self._config_watcher = QFileSystemWatcher([str(directory)], self)
        self._config_debounce = QTimer(self)
        self._config_debounce.setSingleShot(True)
        self._config_debounce.setInterval(300)
        self._config_debounce.timeout.connect(self._reload_config)
        self._config_watcher.directoryChanged.connect(lambda _path: self._config_debounce.start())
        self._config_watcher.fileChanged.connect(lambda _path: self._config_debounce.start())
        self._watch_config_file()

    def _watch_config_file(self):
        """Nach dem Ersetzen der Datei (Umbenennen) ist die alte Beobachtung weg: neu eintragen."""
        path = str(self.config.path)
        if self.config.path.exists() and path not in self._config_watcher.files():
            self._config_watcher.addPath(path)

    def _reload_config(self):
        self._watch_config_file()
        old = dict(self.config.data)
        if self.config.reload() and self.config.data != old:
            log.info("Configuration reloaded")
            self.apply_config(old)

    def apply_config(self, old):
        """Wendet geänderte Werte an; `old` ist der Stand davor."""
        cfg = self.config
        self.alerts.warn, self.alerts.critical = cfg["warn_threshold"], cfg["critical_threshold"]
        if cfg["language"] != old["language"]:
            self._apply_language()
        if not self.fake:
            self._poll.setInterval(cfg["poll_interval_s"] * 1000)
            if (cfg["usb_vendor_id"], cfg["usb_product_id"]) != (old["usb_vendor_id"], old["usb_product_id"]):
                log.info("Device ID changed: %s:%s", cfg["usb_vendor_id"], cfg["usb_product_id"])
                self._apply_device_ids()
                self.hid.retarget(*self._device_ids())
                self.powered, self.level, self.charging = None, None, False
                self.time_to_empty_min = None
                self.poll()
        self._set_checked(self.light_action, cfg["light"])
        for action in self.sidetone_group.actions():
            self._set_checked(action, action.data() == cfg["sidetone"])
        if self.powered is not False:
            if cfg["light"] != old["light"]:
                self.hc.set_light(cfg["light"])
            if cfg["sidetone"] != old["sidetone"] and cfg["sidetone"] is not None:
                self.hc.set_sidetone(cfg["sidetone"])
        self._refresh_ui()

    def _apply_language(self):
        """Sprache wechseln: Menü neu aufbauen (die Texte stehen schon im Menü), Anzeige neu erzeugen."""
        code = set_language(self.config["language"])
        log.info("Language: %s (setting: %s)", code, self.config["language"])
        self._build_menu()
        self._refresh_ui()

    @staticmethod
    def _set_checked(action, checked):
        action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(False)

    # ---- Zustand ----------------------------------------------------------
    def _refresh_status(self):
        if not self.fake:
            self.poll()

    def poll(self):
        self.hc.battery(self._poll_result)

    def _poll_result(self, status, error):
        problem = PROBLEMS.get(error)
        if problem != self.problem:
            self.problem = problem
            if problem:
                log.warning("Problem: %s", error)
            else:
                log.info("Problem resolved")
        if status is not None:
            self.on_battery(status)
        elif error == NO_DEVICE:
            self.on_power(False)  # ohne Dongle ist das Headset nicht erreichbar
            self._refresh_ui()
        else:
            self._refresh_ui()  # Zustand sonst unverändert lassen

    def _check_headsetcontrol_version(self, text):
        log.info("headsetcontrol: %s", text or "not found")
        if headsetcontrol_too_old(text):
            wanted = ".".join(map(str, MIN_HEADSETCONTROL))
            log.warning("headsetcontrol too old (%s), at least %s is required", text, wanted)
            self.notifier.send(tr("{name}: headsetcontrol zu alt").format(name=NAME),
                               tr("Installiert: {installed}. Benötigt wird mindestens {wanted}, "
                                  "sonst fehlen Funktionen oder die Anzeige ist falsch.").format(
                                      installed=text, wanted=wanted))

    def on_battery(self, status: BatteryStatus):
        if not status.powered and self._hid_on_recently():
            # Direkt nach dem Einschalten antwortet headsetcontrol evtl. noch mit "nicht verfügbar":
            # das Ergebnis verwerfen, aber bald erneut fragen (sonst fehlt der Stand bis zum nächsten Abgleich).
            log.debug("Query reports 'off' right after HID reported 'on': ignored, querying again in %d s", RETRY_POLL_MS // 1000)
            self._retry_poll.start(RETRY_POLL_MS)
            return
        self.on_power(status.powered)
        if not status.powered:
            return
        if status.charging != self.charging:
            log.info("Charging: %s (reported: %s %%)", "yes" if status.charging else "no", status.level)
        if status.charging:
            log.debug("Charging voltage: %s mV", status.voltage_mv)
        if status.charging and not self.charging:
            self.level_before_charge = self.level
        elif not status.charging:
            self.level_before_charge = None
        self.level, self.charging = status.level, status.charging
        self.time_to_empty_min = status.time_to_empty_min
        if self.config["notifications"]:
            self._alert(self.alerts.update(self.level, self.charging))
        else:
            self.alerts.update(self.level, self.charging)  # Schwellen trotzdem nachführen
        if self.full_detector.update(time.monotonic(), status.voltage_mv, status.charging) \
                and self.config["full_charge_notification"]:
            self.notifier.send(tr("{name}: Akku voll").format(name=NAME), tr("Der Akku ist voll geladen."))
        self._refresh_ui()

    def _hid_on_recently(self):
        return self._hid_on_at is not None and time.monotonic() - self._hid_on_at < HID_GRACE_S

    def on_power(self, on, from_hid=False):
        if on and from_hid:
            self._hid_on_at = time.monotonic()
        if on == self.powered:
            return
        was_on = self.powered is True
        self.powered = on
        log.info("Headset %s", "on" if on else "off")
        if not on:
            self._relight.stop()
            self.charging = False
        elif not was_on and not self.fake:
            # Das Headset braucht kurz, bis es Befehle annimmt (auch beim Programmstart mit eingeschaltetem
            # Headset). Danach wird auch der Akkustand geholt.
            self._relight_tries = 0
            self._relight.start(self.config["relight_delay_ms"])
        self._refresh_ui()

    def _apply_saved_settings(self):
        want = self.config["light"]
        log.info("Applying saved light state: %s", "on" if want else "off")
        self.hc.set_light(want, self._light_done)
        if self.config["sidetone"] is not None:
            log.info("Applying saved sidetone: %s", self.config["sidetone"])
            self.hc.set_sidetone(self.config["sidetone"])

    def _light_done(self, ok):
        log.info("Setting light: %s", "ok" if ok else "failed")
        if not ok and self.powered and self._relight_tries < 2:
            self._relight_tries += 1
            self._relight.start(self.config["relight_delay_ms"])  # Headset evtl. noch nicht bereit
        elif self.powered:
            self.poll()

    def _alert(self, kind):
        if kind == CRITICAL:
            self.notifier.send(tr("{name}: Akku kritisch").format(name=NAME),
                               tr("Nur noch {level} % - bitte sofort laden.").format(level=self.level), critical=True)
        elif kind == WARNING:
            self.notifier.send(tr("{name}: Akku niedrig").format(name=NAME),
                               tr("Noch {level} % Akku.").format(level=self.level))

    # ---- Anzeige ----------------------------------------------------------
    def _refresh_ui(self):
        extra = None  # Zusatzangabe; Plasma stellt im Tooltip keine Zeilenumbrüche dar, daher alles in einer Zeile
        if self.problem:
            main = f"{NAME}: {tr(self.problem)}"
        elif self.powered is False:
            main = f"{NAME}: {tr('ausgeschaltet')}"
        elif self.powered is None:
            main = f"{NAME}: {tr('Status wird ermittelt …')}"
        elif self.charging:
            # Die Ladespannung verfälscht den Prozentwert (springt binnen Sekunden auf ~100 %).
            main = f"{NAME}: {tr('lädt (Prozentwert beim Laden ungenau)')}"
            if self.level_before_charge is not None:
                extra = tr("Vor dem Laden: {level} %").format(level=self.level_before_charge)
        else:
            main = f"{NAME}: {'?' if self.level is None else f'{self.level} %'}"
            if self.time_to_empty_min:
                extra = tr("noch ca. {duration}").format(duration=format_duration(self.time_to_empty_min))
        warn, critical = self.config["warn_threshold"], self.config["critical_threshold"]
        color = status_color(self.level, self.charging, None if self.problem else self.powered, warn, critical)
        charging_menu = self.powered and self.charging and not self.problem
        if charging_menu:
            menu_text = f"{NAME}: {tr('lädt')}"
        else:
            menu_text = f"{main} ({extra})" if extra else main
        self.status_action.setText(menu_text)
        self.status_action.setIcon(status_dot(color))
        self.tray.setToolTip(f"{main} · {extra}" if extra else main)
        shown_on = self.powered is not False and not self.problem
        self.tray.setIcon(battery_icon(self.level, self.charging, shown_on, warn, critical))


def format_duration(minutes):
    """459 -> "7 h 39 min", 45 -> "45 min"."""
    hours, rest = divmod(int(minutes), 60)
    if hours:
        return tr("{hours} h {minutes:02d} min").format(hours=hours, minutes=rest)
    return tr("{minutes} min").format(minutes=rest)


def lock_path():
    """Sperrdatei je Benutzer: ein gemeinsamer Pfad in /tmp würde andere Benutzer aussperren."""
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return os.path.join(base, f"g733-tray-{os.getuid()}.lock")


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="g733_tray", description="Tray application for the Logitech G733")
    ap.add_argument("--fake-battery", metavar="PERCENT|off",
                    help="test mode: fake battery level (0-100) or 'off' for powered off")
    ap.add_argument("--fake-charging", action="store_true", help="test mode: headset is charging")
    ap.add_argument("--simulate-drain", action="store_true",
                    help="test mode: level drops step by step (starts at --fake-battery, default 25)")
    ap.add_argument("--drain-interval", type=float, default=2.0, metavar="SEC",
                    help="seconds per percentage point for --simulate-drain (default: 2)")
    ap.add_argument("--verbose", action="store_true",
                    help="verbose output (DEBUG) in the terminal and the log file")
    ap.add_argument("--install-launcher", action="store_true", help="create the application menu launcher and exit")
    ap.add_argument("--remove-launcher", action="store_true", help="remove the application menu launcher and exit")
    ap.add_argument("--install-autostart", action="store_true", help="create the autostart entry and exit")
    ap.add_argument("--remove-autostart", action="store_true", help="remove the autostart entry and exit")
    args = ap.parse_args(argv)
    args.test_mode = args.fake_battery is not None or args.simulate_drain or args.fake_charging
    if args.fake_battery is not None and args.fake_battery.lower() != "off":
        try:
            level = int(args.fake_battery)
        except ValueError:
            ap.error("--fake-battery expects 0-100 or 'off'")
        if not 0 <= level <= 100:
            ap.error("--fake-battery expects 0-100 or 'off'")
    return args


def fake_status(args):
    if args.fake_battery is not None and args.fake_battery.lower() == "off":
        return BatteryStatus(powered=False)
    level = int(args.fake_battery) if args.fake_battery is not None else 25
    return BatteryStatus(True, level, args.fake_charging)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.install_launcher:
        autostart.install_launcher()
        print(f"Launcher created: {autostart.LAUNCHER_FILE}")
        return 0
    if args.remove_launcher:
        autostart.remove_launcher()
        print("Launcher removed")
        return 0
    if args.install_autostart:
        autostart.enable()
        print(f"Autostart entry created: {autostart.DESKTOP_FILE}")
        return 0
    if args.remove_autostart:
        autostart.disable()
        print("Autostart entry removed")
        return 0

    app = QApplication(sys.argv[:1])
    app.setApplicationName("g733-tray")
    app.setQuitOnLastWindowClosed(False)
    app.setDesktopFileName("g733-tray")  # ordnet Fenster dem Starter (und seinem Icon) in der Taskleiste zu
    app.setWindowIcon(QIcon.fromTheme("audio-headset", battery_icon(None, False, True, 20, 10)))
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QTimer()  # lässt den Python-Signalhandler regelmäßig laufen
    keepalive.start(500)
    keepalive.timeout.connect(lambda: None)

    lock = None
    if not args.test_mode:  # Testläufe dürfen neben der echten Instanz laufen
        lock = QLockFile(lock_path())
        if not lock.tryLock(0):
            print("g733-tray is already running")
            return 1

    logsetup.setup(verbose=args.verbose, test_mode=args.test_mode)  # erst nach dem Lock: leert die Logdatei
    log.info("g733-tray %s starting (test mode: %s)", __version__, args.test_mode)
    log.info("Install type: %s | Python %s | Qt %s | PyQt %s | Style: %s", install_kind(),
             sys.version.split()[0], QT_VERSION_STR, PYQT_VERSION_STR, app.style().name())
    config = Config(read_only=args.test_mode)
    language = set_language(config["language"])
    log.info("Language: %s (setting: %s)", language, config["language"])
    fake = (fake_status(args), args.simulate_drain, args.drain_interval) if args.test_mode else None
    holder = []  # hält Qt-Objekte am Leben

    def start():
        holder.append(TrayApp(config, fake))

    if QSystemTrayIcon.isSystemTrayAvailable():
        start()
    else:
        # Beim Login ist das Panel oft noch nicht bereit: regelmäßig erneut prüfen.
        log.warning("No system tray available, waiting for it ...")
        waiter = QTimer()
        tries = [0]

        def check():
            tries[0] += 1
            if QSystemTrayIcon.isSystemTrayAvailable():
                waiter.stop()
                start()
            elif tries[0] * TRAY_WAIT_MS >= TRAY_WAIT_MAX_MS:
                log.error("No system tray available, giving up")
                app.exit(1)

        waiter.timeout.connect(check)
        waiter.start(TRAY_WAIT_MS)
        holder.append(waiter)
    return app.exec()


def run():
    sys.exit(main())
