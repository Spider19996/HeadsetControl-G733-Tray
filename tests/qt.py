"""Shared Qt setup: one QApplication on the offscreen platform for all test modules, whatever their order."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.core.qobject.connect=false")  # no tray on the offscreen platform

from PyQt6.QtWidgets import QApplication  # noqa: E402  (after the platform is chosen)

_app = None  # keeps the QApplication alive: without a reference Python destroys it again


def app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app
