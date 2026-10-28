# RPM für Fedora und openSUSE. Bauen mit packaging/build-rpm.sh
Name:           g733-tray
Version:        1.0.0
Release:        1%{?dist}
Summary:        Tray-Programm für das Logitech G733 (Akkustand, Licht)
License:        MIT
URL:            https://github.com/Spider19996/HeadsetControl-G733-Tray
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
Requires:       python3 >= 3.9
%if 0%{?suse_version}
Requires:       python3-qt6
Recommends:     libnotify-tools
%else
Requires:       python3-pyqt6
Recommends:     libnotify
%endif
Recommends:     headsetcontrol

%description
Zeigt den Akkustand des Logitech G733 (USB-Dongle) als Tray-Icon in KDE Plasma,
setzt den gespeicherten Lichtzustand nach dem Einschalten neu und warnt bei
niedrigem Akkustand. Benötigt headsetcontrol (4.2.0 oder neuer) zur Laufzeit.

%prep
%setup -q

%build
# reines Python, nichts zu kompilieren

%install
install -d %{buildroot}%{python3_sitelib}/g733_tray
install -m 644 g733_tray/*.py %{buildroot}%{python3_sitelib}/g733_tray/
install -d %{buildroot}%{python3_sitelib}/g733_tray/lang
install -m 644 g733_tray/lang/*.py %{buildroot}%{python3_sitelib}/g733_tray/lang/
install -D -m 755 /dev/stdin %{buildroot}%{_bindir}/g733-tray <<'SCRIPT'
#!/usr/bin/python3
from g733_tray.app import run

run()
SCRIPT
install -D -m 644 packaging/g733-tray.desktop %{buildroot}%{_datadir}/applications/g733-tray.desktop
install -D -m 644 udev/70-g733-tray.rules %{buildroot}%{_prefix}/lib/udev/rules.d/70-g733-tray.rules

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/g733-tray.desktop

%post
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=hidraw >/dev/null 2>&1 || :

%postun
udevadm control --reload-rules >/dev/null 2>&1 || :

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/g733_tray/
%{_bindir}/g733-tray
%{_datadir}/applications/g733-tray.desktop
%{_prefix}/lib/udev/rules.d/70-g733-tray.rules

%changelog
* Wed Oct 28 2026 Spider19996 <spider19996@users.noreply.github.com> - 1.0.0-1
- Erstes Release
