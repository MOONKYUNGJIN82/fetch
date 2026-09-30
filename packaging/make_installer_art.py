"""Render the existing Fetch icon onto installer panels."""
from pathlib import Path
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QFontDatabase, QGuiApplication
from PySide6.QtCore import Qt, QRect
root = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
font_id = QFontDatabase.addApplicationFont(str(root / "assets/fonts/PretendardVariable.ttf"))
family = QFontDatabase.applicationFontFamilies(font_id)[0]
icon = QImage(str(root / "assets/fetch_icon_clean.png"))
for width, height, name in ((328, 628, "fetch-wizard.bmp"), (110, 110, "fetch-wizard-small.bmp")):
    canvas = QImage(width, height, QImage.Format_RGB32)
    canvas.fill(QColor("#11151b"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    size = 184 if height > 200 else 84
    top = 155 if height > 200 else 13
    painter.drawImage(QRect((width-size)//2, top, size, size), icon)
    if height > 200:
        painter.setPen(QColor("#f4f5f7"))
        painter.setFont(QFont(family, 30, QFont.Bold))
        painter.drawText(QRect(0, 360, width, 65), Qt.AlignCenter, "Fetch")
        painter.setPen(QColor("#b6bdc7"))
        painter.setFont(QFont(family, 10))
        painter.drawText(QRect(0, 420, width, 35), Qt.AlignCenter, "CONTENTS DOWNLOADER")
    painter.end()
    canvas.save(str(root / "build" / name), "BMP")
