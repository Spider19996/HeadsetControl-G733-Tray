#!/bin/sh
# Removes g733-tray, the launcher and the autostart entry. The configuration is kept.
set -eu

prefix="${XDG_DATA_HOME:-$HOME/.local/share}/g733-tray"

if [ -x "$prefix/venv/bin/g733-tray" ]; then
    "$prefix/venv/bin/g733-tray" --remove-launcher
    "$prefix/venv/bin/g733-tray" --remove-autostart
fi
rm -rf "$prefix"
rm -f "$HOME/.local/bin/g733-tray"

echo "Removed. Configuration: ${XDG_CONFIG_HOME:-$HOME/.config}/g733-tray (delete it manually if needed)."
[ -e /etc/udev/rules.d/70-g733-tray.rules ] && echo "Remove the udev rule manually: sudo rm /etc/udev/rules.d/70-g733-tray.rules"
true
