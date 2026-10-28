"""Reads the dongle's hidraw node event-driven and reports power on/off.

Report `11 ff 08 .. VV VV FF ..`: bytes 4-5 are the battery voltage in mV, 0 = headset off.
Byte 6 is 0x01 in operation and 0x03 while charging (bit 1 = charging, derived from captures).
All other reports (e.g. `01 00 00 00 00` or the light acknowledgements `11 ff 04 ..`)
are ignored.
"""
import errno
import glob
import logging
import os
from typing import Optional

from PyQt6.QtCore import QObject, QSocketNotifier, QTimer, pyqtSignal

VENDOR_ID = 0x046D
PRODUCT_ID = 0x0AB5
RECONNECT_MS = 5000

log = logging.getLogger("g733.hid")


def parse_power(report: bytes) -> Optional[bool]:
    """True/False for a power report, None for everything else."""
    if len(report) < 6 or report[0] != 0x11 or report[1] != 0xFF or report[2] != 0x08:
        return None
    return ((report[4] << 8) | report[5]) != 0


def parse_charging(report: bytes) -> Optional[bool]:
    """True/False for the charging state of a power report, otherwise None."""
    if parse_power(report) is None or len(report) < 7:
        return None
    return bool(report[6] & 0x02)


def find_nodes(vendor=VENDOR_ID, product=PRODUCT_ID):
    """/dev/hidrawN paths via sysfs (HID_ID in uevent); the number is not stable."""
    nodes = []
    for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        try:
            with open(uevent) as f:
                lines = dict(l.strip().split("=", 1) for l in f if "=" in l)
            _bus, vid, pid = lines["HID_ID"].split(":")
            if int(vid, 16) == vendor and int(pid, 16) == product:
                nodes.append("/dev/" + uevent.split("/")[4])
        except (OSError, KeyError, ValueError):
            continue
    return nodes


class HidWatcher(QObject):
    power_changed = pyqtSignal(bool)  # only on a real change
    charging_changed = pyqtSignal(bool)  # only on a real change (not on the first report)

    def __init__(self, vendor=VENDOR_ID, product=PRODUCT_ID, parent=None):
        super().__init__(parent)
        self._vendor = vendor
        self._product = product
        self._notifiers = {}  # fd -> QSocketNotifier
        self._power = None
        self._charging = None
        self._retry = QTimer(self)
        self._retry.setInterval(RECONNECT_MS)
        self._retry.timeout.connect(self._open)

    def start(self):
        self._open()

    def retarget(self, vendor, product):
        """Watch another device (setting changed); the state starts over."""
        if (vendor, product) == (self._vendor, self._product):
            return
        log.info("now watching %04x:%04x instead of %04x:%04x", vendor, product, self._vendor, self._product)
        for fd in list(self._notifiers):
            self._close(fd, report=False)
        self._vendor, self._product = vendor, product
        self._power = self._charging = None
        self._open()

    def _open(self):
        for path in find_nodes(self._vendor, self._product):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as err:
                log.warning("%s not readable (%s) - udev rule installed?", path, err.strerror)
                continue
            log.info("reading %s (%04x:%04x)", path, self._vendor, self._product)
            notifier = QSocketNotifier(fd, QSocketNotifier.Type.Read, self)
            notifier.activated.connect(self._readable)
            self._notifiers[fd] = notifier
        if self._notifiers:
            self._retry.stop()
        elif not self._retry.isActive():
            self._retry.start()  # dongle missing: search again from time to time

    def _readable(self, fd):
        try:
            while True:
                self._handle(os.read(fd, 64))
        except BlockingIOError:
            pass
        except OSError as err:  # ENODEV when the dongle is unplugged
            log.warning("read error (%s), closing node", errno.errorcode.get(err.errno, err.errno))
            self._close(fd)

    def _handle(self, report):
        on = parse_power(report)
        if on is None:
            return
        log.debug("Report %s", report.hex(" "))
        if on != self._power:
            self._power = on
            self.power_changed.emit(on)
        charging = parse_charging(report) if on else None  # when switching off, this is 0
        if charging is not None and charging != self._charging:
            known = self._charging is not None
            self._charging = charging
            if known:
                self.charging_changed.emit(charging)

    def _close(self, fd, report=True):
        notifier = self._notifiers.pop(fd, None)
        if notifier:
            notifier.setEnabled(False)
            notifier.deleteLater()
        try:
            os.close(fd)
        except OSError:
            pass
        if report and not self._notifiers:
            if self._power is not False:  # without the dongle the headset is not reachable
                self._power = False
                self.power_changed.emit(False)
            self._retry.start()
