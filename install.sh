#!/bin/sh
# Installiert g733-tray für den aktuellen Benutzer (kein sudo nötig, außer für --udev).
#   ./install.sh [--udev] [--autostart] [--no-launcher]
set -eu

here=$(cd "$(dirname "$0")" && pwd)
prefix="${XDG_DATA_HOME:-$HOME/.local/share}/g733-tray"
bindir="$HOME/.local/bin"
udev=0 autostart=0 launcher=1

for arg in "$@"; do
    case "$arg" in
        --udev) udev=1 ;;
        --autostart) autostart=1 ;;
        --no-launcher) launcher=0 ;;
        -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
        *) echo "Unbekannte Option: $arg" >&2; exit 2 ;;
    esac
done

command -v python3 >/dev/null || { echo "python3 fehlt." >&2; exit 1; }
python3 -c 'import venv, ensurepip' 2>/dev/null || {
    echo "Das venv-Modul fehlt (Debian/Ubuntu/PikaOS: sudo apt install python3-venv)." >&2; exit 1; }
command -v headsetcontrol >/dev/null || echo "Warnung: headsetcontrol (>= 4.2.0) ist nicht installiert, das Programm braucht es zur Laufzeit." >&2
command -v notify-send >/dev/null || echo "Hinweis: notify-send (libnotify-bin) fehlt, kritische Meldungen haben dann keine erhöhte Dringlichkeit." >&2

# PyQt6 muss als Systempaket vorhanden sein: nur dessen Qt kennt den Plasma-Stil (Breeze) des Benutzers.
# Das PyQt6 aus pip bringt ein eigenes Qt mit, das nur "Fusion" und "Windows" kennt.
python3 -c 'import PyQt6.QtWidgets' 2>/dev/null || {
    cat >&2 <<'MSG'
PyQt6 ist nicht als Systempaket installiert. Installiere es und starte ./install.sh erneut:
  Debian/Ubuntu/PikaOS: sudo apt install python3-pyqt6
  Fedora:               sudo dnf install python3-pyqt6
  Arch:                 sudo pacman -S python-pyqt6
MSG
    exit 1
}

echo "Installiere nach $prefix ..."
rm -rf "$prefix/venv"  # frisch anlegen: ein altes venv könnte noch ein PyQt6 aus pip enthalten, das das System-Qt überdeckt
python3 -m venv --system-site-packages "$prefix/venv"
"$prefix/venv/bin/pip" install --quiet --upgrade pip
"$prefix/venv/bin/pip" install --quiet --upgrade "$here"

mkdir -p "$bindir"
ln -sf "$prefix/venv/bin/g733-tray" "$bindir/g733-tray"

[ "$launcher" -eq 1 ] && "$prefix/venv/bin/g733-tray" --install-launcher
[ "$autostart" -eq 1 ] && "$prefix/venv/bin/g733-tray" --install-autostart

if [ "$udev" -eq 1 ]; then
    echo "Installiere udev-Regel (sudo) ..."
    sudo cp "$here/udev/70-g733-tray.rules" /etc/udev/rules.d/
    sudo udevadm control --reload
    sudo udevadm trigger --subsystem-match=hidraw
fi

echo "Fertig. Start: g733-tray (oder 'G733 Tray' im Anwendungsmenü)."
case ":$PATH:" in *":$bindir:"*) ;; *) echo "Hinweis: $bindir ist nicht im PATH." ;; esac
