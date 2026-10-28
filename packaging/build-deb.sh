#!/bin/sh
# Builds dist/g733-tray_<version>_all.deb (Debian, Ubuntu, PikaOS, ...). Needs only dpkg-deb.
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
version=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$here/g733_tray/__init__.py")
[ -n "$version" ] || { echo "__version__ not found in g733_tray/__init__.py." >&2; exit 1; }

stage="$here/dist/g733-tray_${version}_all"
rm -rf "$stage"
mkdir -p "$stage/DEBIAN"

# Program goes into the system Python (that is also where the system package python3-pyqt6 lives)
pydir="$stage/usr/lib/python3/dist-packages/g733_tray"
mkdir -p "$pydir"
for f in "$here"/g733_tray/*.py; do install -m 644 "$f" "$pydir/"; done
mkdir -p "$pydir/lang"
for f in "$here"/g733_tray/lang/*.py; do install -m 644 "$f" "$pydir/lang/"; done

install -D -m 755 /dev/stdin "$stage/usr/bin/g733-tray" <<'SCRIPT'
#!/usr/bin/python3
from g733_tray.app import run

run()
SCRIPT

install -D -m 644 "$here/packaging/g733-tray.desktop" "$stage/usr/share/applications/g733-tray.desktop"
install -D -m 644 "$here/udev/70-g733-tray.rules" "$stage/usr/lib/udev/rules.d/70-g733-tray.rules"
install -D -m 644 "$here/README.md" "$stage/usr/share/doc/g733-tray/README.md"
install -D -m 644 /dev/stdin "$stage/usr/share/doc/g733-tray/copyright" <<COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: g733-tray
Source: https://github.com/Spider19996/HeadsetControl-G733-Tray

Files: *
Copyright: 2026 Spider19996
License: MIT
$(sed -n '3,$p' "$here/LICENSE" | sed 's/^$/./; s/^/ /')
COPYRIGHT

size=$(du -sk "$stage" | cut -f1)
cat > "$stage/DEBIAN/control" <<CONTROL
Package: g733-tray
Version: $version
Section: sound
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-pyqt6
Recommends: libnotify-bin, headsetcontrol
Installed-Size: $size
Maintainer: Spider19996 <spider19996@users.noreply.github.com>
Homepage: https://github.com/Spider19996/HeadsetControl-G733-Tray
Description: Tray application for the Logitech G733 (battery level, light)
 Shows the battery level of the Logitech G733 (USB dongle) as a tray icon in KDE Plasma,
 re-applies the saved light state after power-on and warns when the battery is low.
 Requires headsetcontrol (4.2.0 or newer) at runtime.
CONTROL

for script in postinst postrm; do
    cat > "$stage/DEBIAN/$script" <<'HOOK'
#!/bin/sh
set -e
# make the udev rule (hidraw access for the logged-in user) take effect immediately
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger --subsystem-match=hidraw || true
fi
exit 0
HOOK
    chmod 755 "$stage/DEBIAN/$script"
done

find "$stage" -type d -exec chmod 755 {} +
dpkg-deb --root-owner-group --build "$stage" "$here/dist/g733-tray_${version}_all.deb" >/dev/null
echo "Gebaut: dist/g733-tray_${version}_all.deb"
