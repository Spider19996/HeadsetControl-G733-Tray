"""Notifications through the Plasma service org.freedesktop.Notifications."""
import shutil

from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QSystemTrayIcon

APP_NAME = "G733 Tray"


class Notifier:
    """Uses notify-send (talks to the default service) because of the urgency hint;
    without notify-send it falls back to QSystemTrayIcon.showMessage."""

    def __init__(self, tray: QSystemTrayIcon):
        self._tray = tray
        self._notify_send = shutil.which("notify-send")

    def send(self, title, text, critical=False):
        if self._notify_send:
            args = ["-a", APP_NAME, "-u", "critical" if critical else "normal",
                    "-i", "battery-caution" if not critical else "battery-empty",
                    "-t", "10000", title, text]
            if QProcess.startDetached(self._notify_send, args):
                return
        icon = QSystemTrayIcon.MessageIcon.Critical if critical else QSystemTrayIcon.MessageIcon.Warning
        self._tray.showMessage(title, text, icon, 10000)
