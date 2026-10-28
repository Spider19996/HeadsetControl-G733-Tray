#!/bin/sh
# Entfernt g733-tray, den Starter und den Autostart-Eintrag. Die Konfiguration bleibt erhalten.
set -eu

prefix="${XDG_DATA_HOME:-$HOME/.local/share}/g733-tray"

if [ -x "$prefix/venv/bin/g733-tray" ]; then
    "$prefix/venv/bin/g733-tray" --remove-launcher
    "$prefix/venv/bin/g733-tray" --remove-autostart
fi
rm -rf "$prefix"
rm -f "$HOME/.local/bin/g733-tray"

echo "Entfernt. Konfiguration: ${XDG_CONFIG_HOME:-$HOME/.config}/g733-tray (bei Bedarf manuell löschen)."
[ -e /etc/udev/rules.d/70-g733-tray.rules ] && echo "udev-Regel manuell entfernen: sudo rm /etc/udev/rules.d/70-g733-tray.rules"
true
