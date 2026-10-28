"""Einstellungsdialog: Werte der config.json, Sprache, Autostart/Starter, Geräteauswahl, Info und Log."""
from PyQt6.QtCore import QRegularExpression, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QFontDatabase, QRegularExpressionValidator, QTextCursor
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
                             QWidget)

from . import __version__
from . import logsetup
from .about import (GITHUB_URL, LICENSE, MIN_HEADSETCONTROL, headsetcontrol_too_old, headsetcontrol_version,
                    install_kind)
from .config import DEFAULTS
from .devices import detect_devices
from .i18n import AUTO, LANGUAGES, tr

MANUAL = "manual"  # Datenwert des Listeneintrags "Andere IDs manuell eingeben"


class SettingsDialog(QDialog):
    def __init__(self, config, autostart_enabled, launcher_installed, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("G733 Tray - Einstellungen"))
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Benachrichtigungen
        form = self._page(tabs, tr("Benachrichtigungen"))
        self.notifications = QCheckBox(tr("Bei niedrigem Akkustand benachrichtigen"))
        self.notifications.setChecked(config["notifications"])
        form.addRow(self.notifications)
        self.warn = self._spin(config["warn_threshold"], 0, 100, " %")
        self.critical = self._spin(config["critical_threshold"], 0, 100, " %")
        form.addRow(tr("Warnung ab:"), self.warn)
        form.addRow(tr("Kritisch ab:"), self.critical)
        self.notifications.toggled.connect(self.warn.setEnabled)
        self.notifications.toggled.connect(self.critical.setEnabled)
        self.warn.setEnabled(config["notifications"])
        self.critical.setEnabled(config["notifications"])
        self.full = QCheckBox(tr("Melden, wenn voll geladen (Schätzung über die Spannung)"))
        self.full.setChecked(config["full_charge_notification"])
        form.addRow(self.full)

        # --- System
        form = self._page(tabs, tr("System"))
        self.autostart = QCheckBox(tr("Beim Login starten"))
        self.autostart.setChecked(autostart_enabled)
        self.launcher = QCheckBox(tr("Starter im Anwendungsmenü"))
        self.launcher.setChecked(bool(launcher_installed))
        form.addRow(self.autostart)
        if launcher_installed is not None:  # None: Starter kommt schon systemweit mit dem Paket
            form.addRow(self.launcher)
        self.language = QComboBox()
        self.language.addItem(tr("Automatisch (Systemsprache)"), AUTO)
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)  # Eigenname, damit man die Sprache auch im Fremdsprachigen findet
        self.language.setCurrentIndex(max(0, self.language.findData(config["language"])))
        form.addRow(tr("Sprache:"), self.language)

        # --- Erweitert
        form = self._page(tabs, tr("Erweitert"))
        self.poll = self._spin(config["poll_interval_s"], 5, 3600, " s")
        self.relight = self._spin(config["relight_delay_ms"], 0, 10000, " ms")
        form.addRow(tr("Akkustand abgleichen alle:"), self.poll)
        form.addRow(tr("Wartezeit nach dem Einschalten:"), self.relight)

        # --- Gerät
        self._device_page(tabs, config)

        # --- Info
        self._about_page(tabs)

        # --- Log
        self._log_page(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("OK"))  # unabhängig von Qts eigenen Übersetzungen
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Abbrechen"))
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText(tr("Standardwerte"))
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setToolTip(
            tr("Setzt alle Felder dieses Dialogs auf die Standardwerte (gilt erst nach OK)"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore_defaults)
        layout.addWidget(buttons)

    @staticmethod
    def _page(tabs, title):
        """Neuer Reiter mit Formularlayout; Aussehen kommt vom Anwendungsstil des Benutzers."""
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(page, title)
        return form

    def _device_page(self, tabs, config):
        form = self._page(tabs, tr("Gerät"))
        hint = QLabel(tr("Wähle dein Headset aus der Liste. Angezeigt werden alle von headsetcontrol erkannten "
                         "Geräte (Dongle eingesteckt, das Headset darf aus sein)."))
        hint.setWordWrap(True)
        form.addRow(hint)

        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self._device_choice_changed)
        refresh = QPushButton(tr("Neu suchen"))
        refresh.clicked.connect(lambda: self._fill_devices(self._current_ids()))
        reset = QPushButton(tr("Auf G733 zurücksetzen"))
        reset.setToolTip(tr("Stellt das Standardgerät (Logitech G733, 046d:0ab5) wieder ein"))
        reset.clicked.connect(self._reset_device_ids)
        row = QHBoxLayout()
        row.addWidget(self.device_combo, 1)
        row.addWidget(refresh)
        row.addWidget(reset)
        form.addRow(tr("Headset:"), row)

        # Ausweichmöglichkeit, falls das Gerät nicht in der Liste auftaucht
        self.manual_box = QWidget()
        manual = QFormLayout(self.manual_box)
        manual.setContentsMargins(0, 0, 0, 0)
        manual.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        manual_hint = QLabel(tr(
            "<b>IDs selbst ermitteln:</b> Im Terminal <tt>lsusb</tt> ausführen und die Zeile deines Dongles "
            "suchen, z. B. <tt>ID 046d:0ab5 Logitech, Inc. G733 Gaming Headset</tt>. Vor dem Doppelpunkt steht "
            "die Hersteller-ID, danach die Produkt-ID. Das Headset muss von headsetcontrol unterstützt werden "
            "und der Dongle braucht eine udev-Regel für den Lesezugriff (headsetcontrol bringt sie mit)."))
        manual_hint.setWordWrap(True)
        manual.addRow(manual_hint)
        hex_input = QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]{1,4}"))
        self.vendor_id = QLineEdit(config["usb_vendor_id"])
        self.product_id = QLineEdit(config["usb_product_id"])
        for field, example in ((self.vendor_id, DEFAULTS["usb_vendor_id"]),
                               (self.product_id, DEFAULTS["usb_product_id"])):
            field.setValidator(hex_input)
            field.setMaxLength(4)
            field.setPlaceholderText(example)
            field.setMaximumWidth(110)
        manual.addRow(tr("Hersteller-ID (hex):"), self.vendor_id)
        manual.addRow(tr("Produkt-ID (hex):"), self.product_id)
        form.addRow(self.manual_box)

        self.device_note = QLabel(tr("Das sofortige Erkennen des Einschaltens ist nur für das Logitech G733 "
                                     "geprüft; bei anderen Modellen greift der regelmäßige Abgleich."))
        self.device_note.setWordWrap(True)
        form.addRow(self.device_note)
        self._fill_devices((config["usb_vendor_id"], config["usb_product_id"]))

    def _fill_devices(self, wanted):
        """Liste neu aufbauen: erkannte Geräte, ggf. das eingestellte (nicht gefunden), dann "manuell"."""
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        devices = detect_devices()
        for device in devices:
            self.device_combo.addItem(device.label, device.ids)
        if f"{wanted[0]}:{wanted[1]}" not in [d.ids for d in devices]:
            known = "Logitech G733 Gaming Headset" if wanted == (DEFAULTS["usb_vendor_id"], DEFAULTS["usb_product_id"]) \
                else tr("Eingestelltes Gerät")
            self.device_combo.addItem(tr("{name} ({ids}) - nicht gefunden").format(name=known, ids=f"{wanted[0]}:{wanted[1]}"),
                                      f"{wanted[0]}:{wanted[1]}")
        self.device_combo.addItem(tr("Andere IDs manuell eingeben …"), MANUAL)
        self.device_combo.setCurrentIndex(self.device_combo.findData(f"{wanted[0]}:{wanted[1]}"))
        self.device_combo.blockSignals(False)
        self._device_choice_changed()

    def _device_choice_changed(self):
        chosen = self.device_combo.currentData()
        self.manual_box.setVisible(chosen == MANUAL)
        if chosen != MANUAL:  # Felder spiegeln die Auswahl, damit "manuell" mit sinnvollen Werten startet
            self.vendor_id.setText(chosen.split(":")[0])
            self.product_id.setText(chosen.split(":")[1])

    def _current_ids(self):
        chosen = self.device_combo.currentData()
        if chosen == MANUAL:
            return self.vendor_id.text(), self.product_id.text()
        return tuple(chosen.split(":"))

    def _reset_device_ids(self):
        self._fill_devices((DEFAULTS["usb_vendor_id"], DEFAULTS["usb_product_id"]))

    def _log_page(self, tabs):
        page = QWidget()
        layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        refresh = QPushButton(tr("Aktualisieren"))
        refresh.clicked.connect(lambda: self._load_log(full=True))
        self._log_copy_button = QPushButton(tr("Alles kopieren"))
        self._log_copy_button.setToolTip(tr("Das ganze Log in die Zwischenablage kopieren (Teile: markieren und Strg+C)"))
        self._log_copy_button.clicked.connect(self._copy_log)
        open_log = QPushButton(tr("Logdatei öffnen"))
        log_file = logsetup.log_path()
        open_log.setEnabled(log_file is not None)
        if log_file is not None:
            open_log.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_file))))
        self._log_live = QCheckBox(tr("Automatisch aktualisieren"))
        self._log_live.setChecked(True)
        for widget in (refresh, self._log_copy_button, open_log, self._log_live):
            bar.addWidget(widget)
        bar.addStretch()
        layout.addLayout(bar)

        path_label = QLabel(f"{tr('Logdatei')}: {log_file if log_file else tr('nicht verfügbar')}")
        self._selectable(path_label)  # Pfad markier- und kopierbar
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)  # markier- und kopierbar, aber nicht änderbar
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.log_view.setMinimumSize(640, 280)
        layout.addWidget(self.log_view, 1)
        tabs.addTab(page, tr("Log"))

        self._log_offset = 0  # bis hierhin (Bytes) ist die Datei schon angezeigt
        self._load_log(full=True)
        timer = QTimer(self)  # hängt am Dialog und endet mit ihm
        timer.timeout.connect(lambda: self._log_live.isChecked() and self._load_log())
        timer.start(1500)

    def _load_log(self, full=False):
        """Zeigt das Log. Normalerweise wird nur Neues angehängt, damit Auswahl und Scrollposition bleiben."""
        path = logsetup.log_path()
        if path is None:
            self.log_view.setPlainText(tr("Keine Logdatei verfügbar."))
            return
        try:
            size = path.stat().st_size
            if full or size < self._log_offset:  # neu gelesen oder die Datei wurde geleert/rotiert
                self._log_offset = 0
                self.log_view.clear()
            if size == self._log_offset:
                return
            with open(path, "rb") as f:
                f.seek(self._log_offset)
                chunk = f.read(size - self._log_offset)
        except OSError as err:
            self.log_view.setPlainText(tr("Logdatei nicht lesbar: {error}").format(error=err))
            return
        self._log_offset += len(chunk)
        bar = self.log_view.verticalScrollBar()
        at_bottom = full or bar.value() >= bar.maximum() - 4  # nur mitlaufen, wenn man unten ist
        cursor = QTextCursor(self.log_view.document())  # eigener Cursor: berührt die Auswahl des Benutzers nicht
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk.decode("utf-8", errors="replace"))
        if at_bottom:
            bar.setValue(bar.maximum())

    def _copy_log(self):
        QApplication.clipboard().setText(self.log_view.toPlainText())
        self._log_copy_button.setText(tr("Kopiert"))
        QTimer.singleShot(1500, lambda: self._log_copy_button.setText(tr("Alles kopieren")))

    def _restore_defaults(self):
        """Alle Felder auf Standard; Autostart/Starter sind keine Config-Werte und bleiben unberührt."""
        self.notifications.setChecked(DEFAULTS["notifications"])
        self.full.setChecked(DEFAULTS["full_charge_notification"])
        self.warn.setValue(DEFAULTS["warn_threshold"])
        self.critical.setValue(DEFAULTS["critical_threshold"])
        self.poll.setValue(DEFAULTS["poll_interval_s"])
        self.relight.setValue(DEFAULTS["relight_delay_ms"])
        self.language.setCurrentIndex(self.language.findData(DEFAULTS["language"]))
        self._reset_device_ids()

    def _about_page(self, tabs):
        form = self._page(tabs, tr("Info"))
        name = QLabel("G733 Tray")
        font = name.font()
        font.setBold(True)
        name.setFont(font)
        header = QWidget()  # Titel links, Kopieren-Button oben rechts
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(name)
        header_layout.addStretch()
        form.addRow(header)

        headsetcontrol = headsetcontrol_version()
        headsetcontrol_text = headsetcontrol or tr("nicht gefunden")
        if headsetcontrol_too_old(headsetcontrol):
            headsetcontrol_text += tr(" (zu alt, benötigt: {version} oder neuer)").format(
                version=".".join(map(str, MIN_HEADSETCONTROL)))
        log_file = logsetup.log_path()
        rows = [
            (tr("Version"), __version__),
            (tr("Installationsart"), tr(install_kind())),
            ("headsetcontrol", headsetcontrol_text),
            (tr("Lizenz"), LICENSE),
            (tr("Logdatei"), str(log_file) if log_file else tr("nicht verfügbar")),
        ]
        for label, value in rows:
            form.addRow(f"{label}:", self._selectable(QLabel(value)))
        link = QLabel(f'<a href="{GITHUB_URL}">{GITHUB_URL}</a>')
        link.setOpenExternalLinks(True)
        self._selectable(link)
        form.addRow("GitHub:", link)
        rows.append(("GitHub", GITHUB_URL))

        self._info_text = "G733 Tray\n" + "\n".join(f"{label}: {value}" for label, value in rows)
        self._copy_button = QPushButton(tr("Kopieren"))
        self._copy_button.setToolTip(tr("Alle Angaben in die Zwischenablage kopieren (z. B. für Fehlerberichte)"))
        self._copy_button.clicked.connect(self._copy_info)
        header_layout.addWidget(self._copy_button)

    @staticmethod
    def _selectable(label):
        """Text per Maus markierbar (Strg+C) und Links weiter anklickbar."""
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                      | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        return label

    def _copy_info(self):
        QApplication.clipboard().setText(self._info_text)
        self._copy_button.setText(tr("Kopiert"))
        QTimer.singleShot(1500, lambda: self._copy_button.setText(tr("Kopieren")))

    @staticmethod
    def _spin(value, low, high, suffix):
        box = QSpinBox()
        box.setRange(low, high)
        box.setValue(value)
        box.setSuffix(suffix)
        box.setMinimumWidth(110)  # einheitliche Feldbreite auf allen Reitern
        return box

    def values(self):
        """Werte für die config.json."""
        warn, critical = self.warn.value(), self.critical.value()
        return {
            "language": self.language.currentData(),
            "notifications": self.notifications.isChecked(),
            "full_charge_notification": self.full.isChecked(),
            "warn_threshold": max(warn, critical),
            "critical_threshold": min(warn, critical),
            "poll_interval_s": self.poll.value(),
            "relight_delay_ms": self.relight.value(),
            "usb_vendor_id": self._current_ids()[0],  # leer/ungültig -> Config fällt auf Standard zurück
            "usb_product_id": self._current_ids()[1],
        }
