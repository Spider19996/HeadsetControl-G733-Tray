#!/bin/sh
# Installs g733-tray for the current user (no sudo needed, except for --udev).
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
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

command -v python3 >/dev/null || { echo "python3 is missing." >&2; exit 1; }
python3 -c 'import venv, ensurepip' 2>/dev/null || {
    echo "The venv module is missing (Debian/Ubuntu/PikaOS: sudo apt install python3-venv)." >&2; exit 1; }
command -v headsetcontrol >/dev/null || echo "Warning: headsetcontrol (>= 4.2.0) is not installed, the program needs it at runtime." >&2
command -v notify-send >/dev/null || echo "Note: notify-send (libnotify-bin) is missing, so critical notifications will not have a raised urgency." >&2

# PyQt6 must be installed as a system package: only its Qt knows the user's Plasma style (Breeze).
# PyQt6 from pip ships its own Qt, which only knows "Fusion" and "Windows".
python3 -c 'import PyQt6.QtWidgets' 2>/dev/null || {
    cat >&2 <<'MSG'
PyQt6 is not installed as a system package. Install it and run ./install.sh again:
  Debian/Ubuntu/PikaOS: sudo apt install python3-pyqt6
  Fedora:               sudo dnf install python3-pyqt6
  Arch:                 sudo pacman -S python-pyqt6
MSG
    exit 1
}

echo "Installing to $prefix ..."
rm -rf "$prefix/venv"  # create it fresh: an old venv might still contain PyQt6 from pip, which would shadow the system Qt
python3 -m venv --system-site-packages "$prefix/venv"
"$prefix/venv/bin/pip" install --quiet --upgrade pip
"$prefix/venv/bin/pip" install --quiet --upgrade "$here"

mkdir -p "$bindir"
ln -sf "$prefix/venv/bin/g733-tray" "$bindir/g733-tray"

[ "$launcher" -eq 1 ] && "$prefix/venv/bin/g733-tray" --install-launcher
[ "$autostart" -eq 1 ] && "$prefix/venv/bin/g733-tray" --install-autostart

if [ "$udev" -eq 1 ]; then
    echo "Installing udev rule (sudo) ..."
    sudo cp "$here/udev/70-g733-tray.rules" /etc/udev/rules.d/
    sudo udevadm control --reload
    sudo udevadm trigger --subsystem-match=hidraw
fi

echo "Done. Start: g733-tray (or 'G733 Tray' in the application menu)."
case ":$PATH:" in *":$bindir:"*) ;; *) echo "Note: $bindir is not in the PATH." ;; esac
