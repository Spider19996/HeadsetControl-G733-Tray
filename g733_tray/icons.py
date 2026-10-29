"""Tray icons are drawn at runtime (battery symbol with percentage, no image files needed)."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QApplication

SIZE = 64
GREEN, ORANGE, RED = QColor("#3dd68c"), QColor("#f5a623"), QColor("#e5484d")
BLUE, GREY = QColor("#4aa3ff"), QColor("#8a8a8a")
BODY = QRectF(3, 16, 53, 36)


def _outline_for(color):
    """Outline that contrasts with the text color: dark around light text, light around dark text."""
    luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return QColor("#101010") if luminance > 128 else QColor("#f0f0f0")


def _draw_number(p, text, color):
    """Number with a contrasting outline so it stays readable on the fill and on the empty area."""
    font = QFont()
    font.setBold(True)
    font.setPixelSize(30 if len(text) < 3 else 24)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    box = path.boundingRect()
    path.translate(BODY.center().x() - box.center().x(), BODY.center().y() - box.center().y())
    p.setPen(QPen(_outline_for(color), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(path)


def level_band(level, warn, critical):
    """"critical", "warning" or "normal" for the level (an unknown level counts as normal)."""
    shown = 100 if level is None else level
    return "critical" if shown <= critical else "warning" if shown <= warn else "normal"


def level_color(level, warn, critical):
    return {"critical": RED, "warning": ORANGE, "normal": GREEN}[level_band(level, warn, critical)]


def status_color(level, charging, powered, warn, critical):
    """Colour for status text: green/orange/red by level, blue while charging, grey if off or unknown."""
    if powered is not True:
        return GREY
    return BLUE if charging else level_color(level, warn, critical)


def status_dot(color):
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QRectF(4, 4, 24, 24))
    p.end()
    return QIcon(pix)


def battery_icon(level, charging, powered, warn, critical, text_color="#ffffff"):
    text = QApplication.palette().windowText().color()
    pix = QPixmap(SIZE, SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    outline = QColor(text) if powered else QColor(text.red(), text.green(), text.blue(), 110)
    p.setPen(QPen(outline, 4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(BODY, 6, 6)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(outline)
    p.drawRoundedRect(QRectF(57, 27, 6, 14), 2, 2)

    if not powered:
        p.setPen(QPen(RED, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(8, 60), QPointF(56, 6))  # crossed out = switched off
    elif charging:
        # The percentage is unreliable while charging, so only a large bolt.
        bolt = QPolygonF([QPointF(33, 18), QPointF(18, 36), QPointF(27, 36),
                          QPointF(23, 50), QPointF(41, 30), QPointF(32, 30)])
        p.setPen(QPen(QColor("#101010"), 2))
        p.setBrush(QColor("#ffd23f"))
        p.drawPolygon(bolt)
    else:
        shown = 100 if level is None else level
        color = level_color(level, warn, critical)
        inner = BODY.adjusted(5, 5, -5, -5)
        inner.setWidth(inner.width() * max(shown, 4) / 100)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(inner, 2, 2)
        _draw_number(p, "?" if level is None else str(level), QColor(text_color))
    p.end()
    return QIcon(pix)
