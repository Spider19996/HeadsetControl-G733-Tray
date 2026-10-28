"""Persistent configuration in ~/.config/g733-tray/config.json."""
import json
import logging
import os
from pathlib import Path

from .i18n import LANGUAGES

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "g733-tray"
CONFIG_PATH = CONFIG_DIR / "config.json"

log = logging.getLogger("g733.config")

DEFAULTS = {
    "usb_vendor_id": "046d",          # USB vendor ID of the dongle (hex), default: Logitech G733
    "usb_product_id": "0ab5",         # USB product ID of the dongle (hex)
    "language": "auto",               # "auto" (system language) or a language code, e.g. "de", "en"
    "light": True,                    # desired light state
    "sidetone": None,                 # None = do not manage, otherwise 0-128 (applied after power-on)
    "notifications": True,            # notifications for a low battery
    "full_charge_notification": True, # "fully charged" notification
    "warn_threshold": 20,             # percent, normal urgency
    "critical_threshold": 10,         # percent, high urgency
    "poll_interval_s": 60,            # reconciliation via headsetcontrol -b
    "relight_delay_ms": 1500,         # wait after power-on before light/sidetone are set
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
    """Four hex digits in lower case ("0x046D", "46d" -> "046d"); otherwise the default."""
    text = str(value).strip().lower().removeprefix("0x")
    try:
        number = int(text, 16)
    except ValueError:
        return default
    return f"{number:04x}" if 0 <= number <= 0xFFFF and len(text) <= 4 else default


class Config:
    def __init__(self, path=CONFIG_PATH, read_only=False):
        self.path = Path(path)
        self.read_only = read_only  # test mode: never write to disk
        self.data = dict(DEFAULTS)
        self._extra = {}
        if not self.reload() and not self.path.exists():
            self.save()

    def reload(self):
        """Re-reads the file. False if it is missing or unusable (the previous state is then kept)."""
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
                self._extra[key] = value  # keep unknown keys when saving
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
