"""Desktop-Einträge: Autostart (~/.config/autostart) und Starter im Anwendungsmenü."""
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")

DESKTOP_FILE = CONFIG_HOME / "autostart" / "g733-tray.desktop"
LAUNCHER_FILE = DATA_HOME / "applications" / "g733-tray.desktop"
SYSTEM_LAUNCHER_FILE = Path("/usr/share/applications/g733-tray.desktop")  # kommt mit dem .deb-Paket

# Beschreibung im Anwendungsmenü, je Sprache ("" = Standard/Englisch)
COMMENTS = {
    "": "Battery level and light control for the Logitech G733",
    "de": "Akkustand und Licht des Logitech G733",
    "es": "Nivel de batería y luz del Logitech G733",
    "fr": "Niveau de batterie et éclairage du Logitech G733",
    "it": "Livello della batteria e luce del Logitech G733",
    "pt": "Nível da bateria e luz do Logitech G733",
    "nl": "Accustand en verlichting van de Logitech G733",
    "pl": "Poziom baterii i podświetlenie Logitech G733",
    "ru": "Заряд и подсветка Logitech G733",
    "tr": "Logitech G733 pil seviyesi ve ışık denetimi",
    "zh_CN": "Logitech G733 的电量与灯光",
    "ja": "Logitech G733 のバッテリー残量とライト",
}
COMMENT_LINES = "".join(f"Comment[{lang}]={text}\n" if lang else f"Comment={text}\n" for lang, text in COMMENTS.items())


def _quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'


def _command():
    """(Exec, Path) - bevorzugt das installierte Skript `g733-tray`, sonst `python -m` aus dem Quellbaum."""
    script = Path(sys.executable).parent / "g733-tray"
    if script.exists():
        return _quote(script), None
    return f"{_quote(sys.executable)} -m g733_tray", PROJECT_DIR


def _entry(extra=""):
    exec_line, workdir = _command()
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=G733 Tray\n"
        + COMMENT_LINES
        + f"Exec={exec_line}\n"
        + (f"Path={workdir}\n" if workdir else "")
        + "Icon=audio-headset\n"
        "Terminal=false\n"
        + extra
    )


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def is_enabled():
    return DESKTOP_FILE.exists()


def enable():
    _write(DESKTOP_FILE, _entry("X-KDE-autostart-after=panel\n"))


def disable():
    DESKTOP_FILE.unlink(missing_ok=True)


def system_launcher_exists():
    return SYSTEM_LAUNCHER_FILE.exists()


def launcher_installed():
    return LAUNCHER_FILE.exists()


def install_launcher():
    _write(LAUNCHER_FILE, _entry("Categories=AudioVideo;Audio;\nKeywords=Headset;G733;Logitech;Akku;\n"))


def remove_launcher():
    LAUNCHER_FILE.unlink(missing_ok=True)
