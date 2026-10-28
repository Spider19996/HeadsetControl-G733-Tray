# RPM for Fedora and openSUSE. Build with packaging/build-rpm.sh
Name:           g733-tray
Version:        1.0.3
Release:        1%{?dist}
Summary:        Tray application for the Logitech G733 (battery level, light)
# Translations of Summary and description (AI-generated, not reviewed by native speakers)
Summary(de):    Tray-Programm für das Logitech G733 (Akkustand, Licht)
Summary(es):    Aplicación de bandeja para el Logitech G733 (nivel de batería, luz)
Summary(fr):    Application de la zone de notification pour le Logitech G733 (niveau de batterie, éclairage)
Summary(it):    Applicazione per l'area di notifica per il Logitech G733 (livello della batteria, luce)
Summary(pt):    Aplicação de bandeja para o Logitech G733 (nível da bateria, luz)
Summary(nl):    Systeemvakprogramma voor de Logitech G733 (accustand, verlichting)
Summary(pl):    Aplikacja w zasobniku systemowym dla Logitech G733 (poziom baterii, podświetlenie)
Summary(ru):    Программа для области уведомлений для Logitech G733 (заряд, подсветка)
Summary(tr):    Logitech G733 için sistem tepsisi uygulaması (pil seviyesi, ışık)
Summary(zh_CN): Logitech G733 托盘程序（电量、灯光）
Summary(ja):    Logitech G733 用トレイアプリ（バッテリー残量、ライト）
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
Shows the battery level of the Logitech G733 (USB dongle) as a tray icon in KDE Plasma,
re-applies the saved light state after power-on and warns when the battery is low.
Requires headsetcontrol (4.2.0 or newer) at runtime.

%description -l de
Zeigt den Akkustand des Logitech G733 (USB-Dongle) als Tray-Icon in KDE Plasma, setzt den gespeicherten Lichtzustand nach dem Einschalten neu und warnt bei niedrigem Akkustand. Benötigt headsetcontrol (4.2.0 oder neuer) zur Laufzeit.

%description -l es
Muestra el nivel de batería del Logitech G733 (dongle USB) como icono de la bandeja en KDE Plasma, vuelve a aplicar el estado guardado de la luz al encender y avisa cuando la batería está baja. Requiere headsetcontrol (4.2.0 o posterior) en tiempo de ejecución.

%description -l fr
Affiche le niveau de batterie du Logitech G733 (dongle USB) sous forme d'icône dans la zone de notification de KDE Plasma, rétablit l'état enregistré de l'éclairage après l'allumage et avertit lorsque la batterie est faible. Nécessite headsetcontrol (version 4.2.0 ou plus récente) à l'exécution.

%description -l it
Mostra il livello della batteria del Logitech G733 (dongle USB) come icona nell'area di notifica di KDE Plasma, ripristina lo stato salvato della luce dopo l'accensione e avvisa quando la batteria è scarica. Richiede headsetcontrol (4.2.0 o successivo) in fase di esecuzione.

%description -l pt
Mostra o nível da bateria do Logitech G733 (dongle USB) como ícone na bandeja do KDE Plasma, reaplica o estado guardado da luz depois de ligar e avisa quando a bateria está fraca. Requer o headsetcontrol (4.2.0 ou superior) em tempo de execução.

%description -l nl
Toont de accustand van de Logitech G733 (USB-dongle) als pictogram in het systeemvak van KDE Plasma, stelt na het inschakelen de opgeslagen verlichtingsstatus opnieuw in en waarschuwt bij een lage accustand. Vereist headsetcontrol (4.2.0 of nieuwer) tijdens het uitvoeren.

%description -l pl
Pokazuje poziom baterii Logitech G733 (klucz USB) jako ikonę w zasobniku systemowym KDE Plasma, po włączeniu ponownie ustawia zapisany stan podświetlenia i ostrzega o niskim poziomie baterii. Do działania wymaga headsetcontrol (4.2.0 lub nowszy).

%description -l ru
Показывает заряд Logitech G733 (USB-приёмник) значком в области уведомлений KDE Plasma, после включения заново применяет сохранённое состояние подсветки и предупреждает о низком заряде. Для работы требуется headsetcontrol (4.2.0 или новее).

%description -l tr
Logitech G733'ün (USB alıcı) pil seviyesini KDE Plasma sistem tepsisinde simge olarak gösterir, kulaklık açıldıktan sonra kayıtlı ışık durumunu yeniden uygular ve pil azaldığında uyarır. Çalışma sırasında headsetcontrol (4.2.0 veya üstü) gerekir.

%description -l zh_CN
在 KDE Plasma 系统托盘中以图标显示 Logitech G733（USB 接收器）的电量，开机后重新应用已保存的灯光状态，并在电量低时发出警告。运行时需要 headsetcontrol（4.2.0 或更高版本）。

%description -l ja
Logitech G733（USBドングル）のバッテリー残量を KDE Plasma のシステムトレイにアイコンで表示し、電源オン後に保存したライト状態を再設定し、バッテリー残量が少ないときに警告します。実行時に headsetcontrol（4.2.0 以降）が必要です。

%prep
%setup -q

%build
# pure Python, nothing to compile

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
* Wed Oct 28 2026 Spider19996 <spider19996@users.noreply.github.com> - 1.0.3-1
- Launcher: StartupNotify=false (no busy cursor while the tray program starts)

* Wed Oct 28 2026 Spider19996 <spider19996@users.noreply.github.com> - 1.0.2-1
- Translations use text IDs instead of German source strings
- Code comments translated to English

* Wed Oct 28 2026 Spider19996 <spider19996@users.noreply.github.com> - 1.0.0-1
- First release
