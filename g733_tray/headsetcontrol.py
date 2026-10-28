"""Asynchroner Wrapper um das headsetcontrol-Kommando (QProcess, seriell abgearbeitet)."""
import json
import logging
from collections import deque
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, QProcess, QTimer

BINARY = "headsetcontrol"
TIMEOUT_MS = 10_000

# Fehlerarten für die Anzeige im Tray
MISSING = "missing"        # headsetcontrol ist nicht installiert
NO_DEVICE = "no_device"    # headsetcontrol läuft, findet aber das Gerät nicht (Dongle nicht eingesteckt?)
FAILED = "failed"          # sonstiger Fehler, Details im Log

log = logging.getLogger("g733.headsetcontrol")


@dataclass
class BatteryStatus:
    powered: bool
    level: Optional[int] = None
    charging: bool = False
    voltage_mv: Optional[int] = None
    time_to_empty_min: Optional[int] = None


def parse_battery(output):
    """Wertet `headsetcontrol -b -o json` aus. Ergebnis: (BatteryStatus, None) oder (None, Fehlerart)."""
    try:
        data = json.loads(output)
    except ValueError:
        return None, FAILED
    devices = data.get("devices") or []
    if not devices:
        return None, NO_DEVICE
    battery = devices[0].get("battery") or {}
    status = battery.get("status")
    if status in ("BATTERY_AVAILABLE", "BATTERY_CHARGING"):
        level = battery.get("level")
        level = level if isinstance(level, int) and level >= 0 else None
        voltage = battery.get("voltage_mv")
        voltage = voltage if isinstance(voltage, int) and voltage > 0 else None
        remaining = battery.get("time_to_empty_min")
        remaining = remaining if isinstance(remaining, int) and remaining > 0 else None
        charging = status == "BATTERY_CHARGING"
        return BatteryStatus(True, level, charging, voltage, None if charging else remaining), None
    if status == "BATTERY_UNAVAILABLE":
        return BatteryStatus(powered=False), None
    return None, FAILED


class Headsetcontrol(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = deque()
        self._proc = None
        self._device_args = []

    def set_device(self, vendor_id, product_id):
        """Alle weiteren Aufrufe auf dieses Gerät beschränken (-d VID:PID); IDs als Hex-Strings."""
        self._device_args = ["-d", f"{vendor_id}:{product_id}"]

    def battery(self, callback):
        """callback(BatteryStatus | None, Fehlerart | None)"""
        def done(ok, out, missing):
            if missing:
                callback(None, MISSING)
            else:
                callback(*parse_battery(out))  # auch bei Exit-Code 1: ohne Gerät kommt trotzdem gültiges JSON
        self._enqueue(["-b", "-o", "json"], done)

    def set_light(self, on, callback=None):
        """callback(bool erfolgreich)"""
        self._enqueue(["-l", "1" if on else "0"], lambda ok, _out, _missing: callback and callback(ok))

    def set_sidetone(self, level, callback=None):
        """level 0-128; callback(bool erfolgreich)"""
        self._enqueue(["-s", str(level)], lambda ok, _out, _missing: callback and callback(ok))

    def version(self, callback):
        """callback(Ausgabe von --version | None, wenn nicht installiert)"""
        self._enqueue(["--version"], lambda ok, out, missing: callback(out.strip() if ok else None),
                      with_device=False)

    def _enqueue(self, args, done, with_device=True):
        self._queue.append((self._device_args + args if with_device else args, done))
        if self._proc is None:
            self._next()

    def _next(self):
        if not self._queue:
            self._proc = None
            return
        args, done = self._queue.popleft()
        proc = self._proc = QProcess(self)
        proc.finished.connect(lambda code, status: self._finish(
            proc, done, args, code, status == QProcess.ExitStatus.NormalExit, missing=False))
        proc.errorOccurred.connect(lambda err: self._on_error(proc, done, args, err))
        watchdog = QTimer(proc)  # wird mit dem Prozess zusammen aufgeräumt
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(proc.kill)
        watchdog.start(TIMEOUT_MS)
        log.debug("running %s %s", BINARY, " ".join(args))
        proc.start(BINARY, args)

    def _on_error(self, proc, done, args, err):
        if err == QProcess.ProcessError.FailedToStart:
            log.error("could not start %s (not installed?)", BINARY)
            self._finish(proc, done, args, None, False, missing=True)

    def _finish(self, proc, done, args, code, normal_exit, missing):
        if proc is not self._proc:
            return  # schon abgeschlossen (Fehler- und finished-Signal)
        out = "" if missing else bytes(proc.readAllStandardOutput()).decode(errors="replace")
        proc.deleteLater()
        self._proc = None
        ok = normal_exit and code == 0
        if not missing:
            log.debug("%s -> exit code %s%s", " ".join(args), code, "" if normal_exit else " (aborted)")
        done(ok, out, missing)
        # Der Callback kann selbst schon den nächsten Aufruf gestartet haben (dann läuft self._proc):
        # diesen nicht überschreiben, sonst geht dessen Ergebnis verloren.
        if self._proc is None:
            self._next()
