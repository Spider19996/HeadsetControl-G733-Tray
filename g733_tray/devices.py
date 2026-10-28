"""Erkennt angeschlossene, von headsetcontrol unterstützte Headsets (für die Geräteauswahl)."""
import json
import shutil
import subprocess
from dataclasses import dataclass

from .config import normalize_usb_id
from .i18n import tr


@dataclass(frozen=True)
class Device:
    name: str
    vendor_id: str   # 4 Hex-Ziffern, klein
    product_id: str

    @property
    def ids(self):
        return f"{self.vendor_id}:{self.product_id}"

    @property
    def label(self):
        return f"{self.name} ({self.ids})"


def parse_devices(output):
    """Liest `headsetcontrol -o json` (ohne -d) und liefert die erkannten Geräte."""
    try:
        data = json.loads(output)
    except ValueError:
        return []
    devices = []
    for entry in data.get("devices") or []:
        vendor = normalize_usb_id(entry.get("id_vendor", ""), None)
        product = normalize_usb_id(entry.get("id_product", ""), None)
        if vendor is None or product is None:
            continue
        name = " ".join(part for part in (entry.get("vendor"), entry.get("product")) if part) \
            or entry.get("device") or tr("device.unknown")
        device = Device(name, vendor, product)
        if device not in devices:
            devices.append(device)
    return devices


def detect_devices():
    """Fragt headsetcontrol nach allen angeschlossenen Geräten. Leer, wenn es fehlt oder nichts findet."""
    binary = shutil.which("headsetcontrol")
    if not binary:
        return []
    try:
        result = subprocess.run([binary, "-o", "json"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return parse_devices(result.stdout)
