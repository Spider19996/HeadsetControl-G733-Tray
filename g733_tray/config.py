"""Persistente Konfiguration unter ~/.config/g733-tray/config.json."""
import json
import logging
import os
from pathlib import Path

from .i18n import LANGUAGES

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "g733-tray"
CONFIG_PATH = CONFIG_DIR / "config.json"

log = logging.getLogger("g733.config")

DEFAULTS = {
    "usb_vendor_id": "046d",          # USB-Hersteller-ID des Dongles (hex), Standard: Logitech G733
    "usb_product_id": "0ab5",         # USB-Produkt-ID des Dongles (hex)
    "language": "auto",               # "auto" (Systemsprache) oder ein Sprachcode, z. B. "de", "en"
    "light": True,                    # gewünschter Lichtzustand
    "sidetone": None,                 # None = nicht verwalten, sonst 0-128 (wird nach dem Einschalten gesetzt)
    "notifications": True,            # Benachrichtigungen bei niedrigem Akkustand
    "full_charge_notification": True, # Meldung "voll geladen"
    "warn_threshold": 20,             # Prozent, normale Dringlichkeit
    "critical_threshold": 10,         # Prozent, hohe Dringlichkeit
    "poll_interval_s": 60,            # Abgleich per headsetcontrol -b
    "relight_delay_ms": 1500,         # Wartezeit nach dem Einschalten, bis Licht/Sidetone gesetzt werden
}


def _int_or(value, default, low=None, high=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if low is not None:
        number = max(low, number)
    if high is not None:
        number = min(high, number)
    return number


def normalize_usb_id(value, default):
    """Vier Hex-Ziffern in Kleinbuchstaben ("0x046D", "46d" -> "046d"); sonst der Standardwert."""
    text = str(value).strip().lower().removeprefix("0x")
    try:
        number = int(text, 16)
    except ValueError:
        return default
    return f"{number:04x}" if 0 <= number <= 0xFFFF and len(text) <= 4 else default


class Config:
    def __init__(self, path=CONFIG_PATH, read_only=False):
        self.path = Path(path)
        self.read_only = read_only  # Testmodus: nie auf die Platte schreiben
        self.data = dict(DEFAULTS)
        self._extra = {}
        if not self.reload() and not self.path.exists():
            self.save()

    def reload(self):
        """Liest die Datei neu ein. False, wenn sie fehlt oder unbrauchbar ist (Stand bleibt dann erhalten)."""
        try:
            raw = json.loads(self.path.read_text())
        except FileNotFoundError:
            return False
        except (OSError, ValueError) as err:
            log.warning("%s not readable (%s), keeping previous values", self.path, err)
            return False
        if not isinstance(raw, dict):
            return False
        data = dict(DEFAULTS)
        self._extra = {}
        for key, value in raw.items():
            if key in DEFAULTS:
                data[key] = value
            else:
                self._extra[key] = value  # unbekannte Schlüssel beim Speichern erhalten
        self.data = self._validated(data)
        return True

    @staticmethod
    def _validated(data):
        data["usb_vendor_id"] = normalize_usb_id(data["usb_vendor_id"], DEFAULTS["usb_vendor_id"])
        data["usb_product_id"] = normalize_usb_id(data["usb_product_id"], DEFAULTS["usb_product_id"])
        language = str(data["language"]).strip().lower()
        data["language"] = language if language in LANGUAGES or language == "auto" else DEFAULTS["language"]
        data["light"] = bool(data["light"])
        data["notifications"] = bool(data["notifications"])
        data["full_charge_notification"] = bool(data["full_charge_notification"])
        sidetone = data["sidetone"]
        data["sidetone"] = None if sidetone is None else _int_or(sidetone, None, 0, 128)
        warn = _int_or(data["warn_threshold"], DEFAULTS["warn_threshold"], 0, 100)
        crit = _int_or(data["critical_threshold"], DEFAULTS["critical_threshold"], 0, 100)
        data["critical_threshold"], data["warn_threshold"] = sorted((crit, warn))
        data["poll_interval_s"] = _int_or(data["poll_interval_s"], 60, 5)
        data["relight_delay_ms"] = _int_or(data["relight_delay_ms"], 1500, 0)
        return data

    def __getitem__(self, key):
        return self.data[key]

    def set(self, key, value):
        self.update({key: value})

    def update(self, values):
        self.data = self._validated({**self.data, **values})
        self.save()

    def save(self):
        if self.read_only:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({**self.data, **self._extra}, indent=2) + "\n")
            tmp.replace(self.path)
        except OSError as err:
            log.warning("Saving failed: %s", err)
