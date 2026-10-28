"""Tray-Icons werden zur Laufzeit gezeichnet (Akku-Symbol mit Prozentzahl, keine Bilddateien nötig)."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QApplication

SIZE = 64
GREEN, ORANGE, RED = QColor("#3dd68c"), QColor("#f5a623"), QColor("#e5484d")
BLUE, GREY = QColor("#4aa3ff"), QColor("#8a8a8a")
BODY = QRectF(3, 16, 53, 36)


def _draw_number(p, text):
    """Zahl mit dunklem Rand, damit sie auf Füllung und leerem Bereich lesbar bleibt."""
    font = QFont()
    font.setBold(True)
    font.setPixelSize(30 if len(text) < 3 else 24)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    box = path.boundingRect()
    path.translate(BODY.center().x() - box.center().x(), BODY.center().y() - box.center().y())
    p.setPen(QPen(QColor("#101010"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("white"))
    p.drawPath(path)


def level_color(level, warn, critical):
    shown = 100 if level is None else level
    return RED if shown <= critical else ORANGE if shown <= warn else GREEN


def status_color(level, charging, powered, warn, critical):
    """Farbe für Statustext: grün/orange/rot nach Stand, blau beim Laden, grau wenn aus oder unbekannt."""
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


def battery_icon(level, charging, powered, warn, critical):
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
        p.drawLine(QPointF(8, 60), QPointF(56, 6))  # durchgestrichen = ausgeschaltet
    elif charging:
        # Der Prozentwert ist beim Laden unzuverlässig, daher nur ein großer Blitz.
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
        _draw_number(p, "?" if level is None else str(level))
    p.end()
    return QIcon(pix)
