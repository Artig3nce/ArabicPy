"""Al-Baa Design System -- a small built-in icon set.

Icons are drawn live with QPainter into a QPixmap -- no binary asset
files, so this stays safe to copy into a new project with no path to
resolve. Self-contained: standard library + PySide6 only.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap

ICON_NAMES = ("home", "settings", "chat", "menu", "back", "close")


def _draw_home(painter, rect, pen):
    painter.setPen(pen)
    w, h = rect.width(), rect.height()
    roof = QPainterPath()
    roof.moveTo(rect.left(), rect.top() + h * 0.5)
    roof.lineTo(rect.center().x(), rect.top())
    roof.lineTo(rect.right(), rect.top() + h * 0.5)
    painter.drawPath(roof)
    body = QRectF(rect.left() + w * 0.18, rect.top() + h * 0.48, w * 0.64, h * 0.42)
    painter.drawRect(body)


def _draw_settings(painter, rect, pen):
    painter.setPen(pen)
    painter.drawEllipse(rect.center(), rect.width() * 0.32, rect.height() * 0.32)
    painter.drawEllipse(rect.center(), rect.width() * 0.12, rect.height() * 0.12)


def _draw_chat(painter, rect, pen):
    painter.setPen(pen)
    bubble = QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.72)
    painter.drawRoundedRect(bubble, 3, 3)
    tail = QPainterPath()
    tail.moveTo(rect.left() + rect.width() * 0.25, bubble.bottom())
    tail.lineTo(rect.left() + rect.width() * 0.2, rect.bottom())
    tail.lineTo(rect.left() + rect.width() * 0.42, bubble.bottom())
    painter.drawPath(tail)


def _draw_menu(painter, rect, pen):
    painter.setPen(pen)
    for fraction in (0.22, 0.5, 0.78):
        y = rect.top() + rect.height() * fraction
        painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))


def _draw_back(painter, rect, pen):
    painter.setPen(pen)
    mid_y = rect.center().y()
    painter.drawLine(QPointF(rect.right(), mid_y), QPointF(rect.left(), mid_y))
    painter.drawLine(QPointF(rect.left(), mid_y), QPointF(rect.left() + rect.width() * 0.4, rect.top()))
    painter.drawLine(QPointF(rect.left(), mid_y), QPointF(rect.left() + rect.width() * 0.4, rect.bottom()))


def _draw_close(painter, rect, pen):
    painter.setPen(pen)
    painter.drawLine(rect.topLeft(), rect.bottomRight())
    painter.drawLine(rect.topRight(), rect.bottomLeft())


_DRAWERS = {
    "home": _draw_home,
    "settings": _draw_settings,
    "chat": _draw_chat,
    "menu": _draw_menu,
    "back": _draw_back,
    "close": _draw_close,
}


def icon(name: str, *, color: str = "#000000", size: int = 20) -> QIcon:
    """Return a small vector-drawn QIcon for one of `ICON_NAMES`."""
    draw = _DRAWERS.get(name)
    if draw is None:
        raise ValueError(f"Unknown icon name: {name!r} (expected one of {ICON_NAMES})")
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color)
    pen.setWidthF(max(1.4, size * 0.08))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    margin = size * 0.15
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    draw(painter, rect, pen)
    painter.end()
    return QIcon(pixmap)
