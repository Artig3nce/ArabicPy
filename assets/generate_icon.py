"""Generate the الباء application icon using Qt (run before packaging)."""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication


assets = Path(__file__).resolve().parent
app = QApplication.instance() or QApplication([])
image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)

painter = QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
painter.setPen(Qt.PenStyle.NoPen)
painter.setBrush(QColor("#007ACC"))
painter.drawRoundedRect(QRectF(18, 18, 220, 220), 54, 54)
painter.setPen(QColor("#FFFFFF"))
font = QFont("Tahoma", 132, QFont.Weight.Bold)
painter.setFont(font)
painter.drawText(QRectF(18, 4, 220, 220), Qt.AlignmentFlag.AlignCenter, "ب")
painter.end()

if not image.save(str(assets / "albaa.png"), "PNG"):
    raise SystemExit("Could not save PNG icon")
if not image.save(str(assets / "albaa.ico"), "ICO"):
    raise SystemExit("Could not save ICO icon")
