#!/bin/sh
# Baut ein RPM nach dist/ (Fedora, openSUSE). Benötigt rpmbuild (Paket rpm-build bzw. rpm-build/rpmbuild).
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
version=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$here/g733_tray/__init__.py")
spec_version=$(sed -n 's/^Version:[[:space:]]*//p' "$here/packaging/g733-tray.spec")
[ "$version" = "$spec_version" ] || { echo "Version in g733_tray/__init__.py ($version) und .spec ($spec_version) unterscheiden sich." >&2; exit 1; }

top="$here/dist/rpmbuild"
rm -rf "$top"
mkdir -p "$top/SOURCES"

tar -C "$here" --transform "s,^,g733-tray-$version/," -czf "$top/SOURCES/g733-tray-$version.tar.gz" \
    g733_tray udev packaging/g733-tray.desktop LICENSE README.md
rpmbuild -bb --define "_topdir $top" "$here/packaging/g733-tray.spec" >/dev/null
find "$top/RPMS" -name '*.rpm' -exec cp {} "$here/dist/" \;
ls "$here"/dist/*.rpm
