# g733-tray

🇬🇧 [English version](README.md)

Akkustand und Licht des Logitech-G733-Headsets (USB-Dongle `046d:0ab5`) im System-Tray von KDE Plasma 6. Gebaut mit PyQt6 auf Basis von [headsetcontrol](https://github.com/Sapd/HeadsetControl) ab Version 4.2.0.

## Funktionen

- **Akku im Tray-Icon:** Prozentzahl im Icon, bei niedrigem Stand orange/rot, bei ausgeschaltetem Headset durchgestrichen. Der Tooltip nennt zusätzlich die geschätzte Restlaufzeit.
- **Benachrichtigungen:** bei niedrigem Akkustand (Warnung und kritisch) und bei "voll geladen".
- **Licht und Sidetone werden gemerkt:** Das Headset vergisst sie beim Ausschalten, deshalb setzt das Programm sie ca. 1,5 s nach dem Einschalten neu.
- **Laden:** Der Prozentwert des Headsets ist beim Laden unzuverlässig (er springt binnen Sekunden auf ~100 %). Das Icon zeigt dann einen Blitz, der Tooltip nennt den Stand vor dem Laden.
- **Menü:** Statuszeile (farbiger Punkt, Klick fragt neu ab), Licht an/aus, Sidetone, Einstellungen, Beenden.
- **12 Sprachen**, Änderungen in den Einstellungen wirken sofort.

<p>
  <img src="screenshots/TrayIcon.png" alt="Tray-Icon mit Prozentzahl" height="80">
  <img src="screenshots/Menu.png" alt="Tray-Menü" height="200">
</p>
<p>
  <img src="screenshots/Settings.png" alt="Einstellungsdialog" width="600">
</p>

## Installation

1. [headsetcontrol](https://github.com/Sapd/HeadsetControl) ab 4.2.0 installieren (es muss im `PATH` liegen).
2. Das Paket für deine Distribution von der [Releases-Seite](https://github.com/Spider19996/HeadsetControl-G733-Tray/releases) laden und installieren:

   | Distribution | Installation |
   |---|---|
   | Debian, Ubuntu, PikaOS und Ableger | `sudo apt install ./g733-tray_<version>_all.deb` |
   | Fedora | `sudo dnf install ./g733-tray-<version>-1.fc*.noarch.rpm` |
   | openSUSE | `sudo zypper install ./g733-tray-<version>-1.*.noarch.rpm` |
   | Arch, Manjaro, EndeavourOS | `cd packaging/arch && makepkg -si` |
   | alle anderen | siehe *Andere Distributionen* unten |

3. Den Dongle einmal abziehen und wieder einstecken (damit die udev-Regel greift), dann "G733 Tray" im Anwendungsmenü starten.

Zum Start beim Login schaltest du *Einstellungen → System → Beim Login starten* ein.

Die Pakete holen alles Weitere automatisch (PyQt6 aus der Distribution, udev-Regel, Starter im Anwendungsmenü). Das PyQt6 aus pip wird bewusst nicht verwendet: Es bringt ein eigenes Qt mit, das nur den Fusion-Stil kennt, und der Einstellungsdialog würde nicht zu deinem Plasma-Stil passen.

### Andere Distributionen

Du brauchst Python ≥ 3.9 mit `venv` (entwickelt und getestet nur mit 3.14) und **PyQt6 als Systempaket** (`python3-pyqt6` bei Debian und Fedora, `python-pyqt6` bei Arch). Optional: `notify-send` (`libnotify`), damit die kritische Meldung eine höhere Dringlichkeit bekommt.

```sh
git clone https://github.com/Spider19996/HeadsetControl-G733-Tray.git
cd HeadsetControl-G733-Tray
./install.sh --udev --autostart
```

Das Skript legt ein eigenes venv unter `~/.local/share/g733-tray/venv` an, verlinkt `~/.local/bin/g733-tray` und legt den Starter im Anwendungsmenü an. Danach darf der Ordner gelöscht werden.

| Option | Wirkung |
|---|---|
| `--udev` | installiert die udev-Regel nach `/etc/udev/rules.d/` (fragt per `sudo`) |
| `--autostart` | startet das Programm beim Login |
| `--no-launcher` | legt keinen Starter im Anwendungsmenü an |

Deinstallation: `./uninstall.sh` (die Konfiguration bleibt erhalten, die udev-Regel entfernst du manuell).

Die **udev-Regel** gibt dem angemeldeten Benutzer Lesezugriff auf den Dongle, damit kein `sudo` nötig ist. Auf vielen Systemen reicht schon die Regel `70-headsets.rules` von headsetcontrol.

## Benutzung

`g733-tray` starten oder "G733 Tray" im Anwendungsmenü. Eine zweite Instanz beendet sich sofort.

Licht und Sidetone stellst du direkt im Tray-Menü ein. Alles andere steht unter *Einstellungen …*: Benachrichtigungen und Schwellen, Autostart, Sprache, Intervalle, Geräteauswahl sowie die Reiter *Info* und *Log*.

Bei Problemen meldet sich das Tray selbst: "headsetcontrol nicht gefunden" (installieren), "Dongle nicht gefunden" (einstecken) oder "headsetcontrol-Fehler" (siehe Reiter *Log*).

## Konfiguration

Die meisten Optionen stehen im Einstellungsdialog. Die Datei `~/.config/g733-tray/config.json` lässt sich auch von Hand bearbeiten, Änderungen werden automatisch übernommen.

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `language` | `auto` | `auto` (Systemsprache) oder ein Sprachcode (`de`, `en`, `es`, `fr`, `it`, `pt`, `nl`, `pl`, `ru`, `tr`, `zh`, `ja`) |
| `usb_vendor_id` / `usb_product_id` | `046d` / `0ab5` | USB-IDs des Dongles (hex), siehe *Anderes Headset* |
| `light` | `true` | gespeicherter Lichtzustand |
| `sidetone` | `null` | `null` = nicht verwalten, sonst 0-128 (im Menü: Aus/Niedrig/Mittel/Hoch) |
| `notifications` | `true` | Benachrichtigungen bei niedrigem Akkustand an/aus |
| `warn_threshold` | `20` | Warnung bei ≤ diesem Prozentwert |
| `critical_threshold` | `10` | kritische Meldung (hohe Dringlichkeit) |
| `full_charge_notification` | `true` | Meldung "voll geladen" |
| `poll_interval_s` | `60` | wie oft der Stand abgefragt wird (min. 5) |
| `relight_delay_ms` | `1500` | Wartezeit nach dem Einschalten bis zum Setzen des Lichts |

Jede Schwelle meldet sich pro Entladevorgang einmal und wird wieder scharf, wenn das Headset lädt oder der Stand wieder darüber liegt. Liegt der Stand direkt unter beiden Schwellen, kommt nur die kritische Meldung.

**Voll geladen** ist eine Schätzung über die Spannung, weil der Prozentwert beim Laden nichts taugt: Steigt sie über 10 Minuten um höchstens 5 mV und liegt über 4100 mV, kommt einmal pro Ladevorgang die Meldung. Diese Grenzen sind Erfahrungswerte und noch nicht über einen vollständigen Ladevorgang validiert.

Die Meldungen gehen über `notify-send` an den Plasma-Benachrichtigungsdienst (nur so lässt sich die Dringlichkeit setzen). Fehlt es, wird `QSystemTrayIcon.showMessage` benutzt.

## Anderes Headset

Standard ist das Logitech G733. Unter *Einstellungen → Gerät* wählst du dein Headset aus einer Liste aller von headsetcontrol erkannten Geräte (Dongle eingesteckt, das Headset darf aus sein). *Neu suchen* aktualisiert die Liste, *Auf G733 zurücksetzen* stellt das Standardgerät wieder ein.

Taucht das Gerät nicht auf, wählst du *Andere IDs manuell eingeben …* und trägst Hersteller- und Produkt-ID ein. Du findest sie mit `lsusb`, z. B. `ID 046d:0ab5 Logitech, Inc. G733 Gaming Headset` (Hersteller-ID vor, Produkt-ID nach dem Doppelpunkt).

Das Headset muss von headsetcontrol unterstützt werden, und dein Benutzer braucht Lesezugriff auf den Dongle (udev-Regel, bei unterstützten Geräten bringt headsetcontrol sie mit). Das sofortige Erkennen des Einschaltens ist nur für das G733 geprüft, bei anderen Modellen greift die Abfrage alle 60 s.

## Logdatei

Das Log liegt in `~/.local/state/g733-tray/g733-tray.log` (bzw. `$XDG_STATE_HOME`). Es wird bei **jedem Programmstart geleert** und auf ca. 1 MB begrenzt. Der Reiter *Log* in den Einstellungen zeigt es direkt an (mit *Alles kopieren* und *Logdatei öffnen*). Für Fehlerberichte reichen meist der Kopieren-Button im Reiter *Info* und das Log.

```sh
g733-tray --verbose    # DEBUG-Meldungen im Terminal und in der Logdatei
```

---

# Für Entwickler

## Funktionsweise

Das Einschalten wird ereignisgesteuert über den hidraw-Knoten des Dongles erkannt (`11 ff 08 …`: Bytes 4-5 = Akkuspannung, 0 = aus). Zusätzlich gleicht alle 60 s `headsetcontrol -b -o json` Akkustand und Zustand ab.

## Aus dem Quellbaum starten

```sh
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -t .
```

## Testmodus

Ersetzt Headset und HID-Wächter durch einen künstlichen Akkustand. Die Konfiguration wird nicht geschrieben, eine laufende normale Instanz stört nicht, und das Log geht nach `g733-tray-test.log`.

```sh
g733-tray --fake-battery 15                 # Tooltip/Icon/Warnung
g733-tray --fake-battery off                # "ausgeschaltet"
g733-tray --fake-battery 80 --fake-charging
g733-tray --fake-battery 25 --simulate-drain --drain-interval 1   # fällt 1 % pro Sekunde
```

## Übersetzungen

Jeder Text im Code ist eine kurze ID, z. B. `tr("menu.quit")`. Jede Sprache, auch Deutsch und Englisch, ist eine Datei `g733_tray/lang/<code>.py` mit einem Wörterbuch von ID zu Text. Fehlt ein Eintrag, wird der englische Text angezeigt. Bis auf Deutsch wurden die Übersetzungen von einer KI erstellt und sind nicht von Muttersprachlern geprüft, Korrekturen sind willkommen.

Eine neue Sprache anlegen: `en.py` kopieren und die Werte übersetzen (IDs und `{Platzhalter}` bleiben), den Code in `LANGUAGES` in `g733_tray/i18n.py` eintragen. Einen neuen Text anlegen: im Code `tr("bereich.name")` schreiben und die ID in jede Sprachdatei eintragen. Der Test `tests/test_i18n.py` prüft für jede Sprache, dass alle IDs vorhanden sind, keine unbenutzten übrig bleiben und die Platzhalter (z. B. `{level}`) stimmen.

Die Logdatei und die Ausgabe von `--help` sind immer englisch, damit Fehlerberichte für alle lesbar sind.

## Pakete bauen und Releases

```sh
./packaging/build-deb.sh   # braucht nur dpkg-deb, Ergebnis: dist/g733-tray_<version>_all.deb
./packaging/build-rpm.sh   # braucht rpmbuild, Ergebnis: dist/*.rpm
```

Die Version steht nur in `g733_tray/__init__.py` (`__version__`) und wird von pyproject, den Build-Skripten und dem Reiter *Info* gelesen. Bei einem Git-Tag `vX.Y.Z` baut die GitHub Action [release.yml](.github/workflows/release.yml) beide Pakete und hängt sie an ein Release. Vor dem Tag die Version dort, in `packaging/g733-tray.spec` und als `pkgver` im PKGBUILD anheben.

Das Arch-Paket und die Release-Action sind noch nicht getestet. Das RPM baut und installiert sich unter Fedora (im Container geprüft).

## Lizenz

MIT, siehe [LICENSE](LICENSE).
