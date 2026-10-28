"""Asynchronous wrapper around the headsetcontrol command (QProcess, processed serially)."""
import json
import logging
from collections import deque
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, QProcess, QTimer

BINARY = "headsetcontrol"
TIMEOUT_MS = 10_000

# kinds of error shown in the tray
MISSING = "missing"        # headsetcontrol is not installed
NO_DEVICE = "no_device"    # headsetcontrol runs but does not find the device (dongle not plugged in?)
FAILED = "failed"          # any other error, details in the log

log = logging.getLogger("g733.headsetcontrol")


@dataclass
class BatteryStatus:
    powered: bool
    level: Optional[int] = None
    charging: bool = False
    voltage_mv: Optional[int] = None
    time_to_empty_min: Optional[int] = None


def parse_battery(output):
    """Parses `headsetcontrol -b -o json`. Result: (BatteryStatus, None) or (None, error kind)."""
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
        """Restrict all further calls to this device (-d VID:PID); IDs as hex strings."""
        self._device_args = ["-d", f"{vendor_id}:{product_id}"]

    def battery(self, callback):
        """callback(BatteryStatus | None, error kind | None)"""
        def done(ok, out, missing):
            if missing:
                callback(None, MISSING)
            else:
                callback(*parse_battery(out))  # also with exit code 1: without a device, valid JSON still comes back
        self._enqueue(["-b", "-o", "json"], done)

    def set_light(self, on, callback=None):
        """callback(bool success)"""
        self._enqueue(["-l", "1" if on else "0"], lambda ok, _out, _missing: callback and callback(ok))

    def set_sidetone(self, level, callback=None):
        """level 0-128; callback(bool success)"""
        self._enqueue(["-s", str(level)], lambda ok, _out, _missing: callback and callback(ok))

    def version(self, callback):
        """callback(output of --version | None if not installed)"""
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
        watchdog = QTimer(proc)  # is cleaned up together with the process
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
            return  # already finished (error and finished signal)
        out = "" if missing else bytes(proc.readAllStandardOutput()).decode(errors="replace")
        proc.deleteLater()
        self._proc = None
        ok = normal_exit and code == 0
        if not missing:
            log.debug("%s -> exit code %s%s", " ".join(args), code, "" if normal_exit else " (aborted)")
        done(ok, out, missing)
        # The callback may already have started the next call itself (then self._proc is running):
        # do not overwrite that one, otherwise its result is lost.
        if self._proc is None:
            self._next()
