# coding: utf-8
"""用真实应用截图生成 ConfigPilot 社交预览图。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)


CANVAS_SIZE = (1280, 640)


def rounded_path(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def render_icon(source_path, size):
    source = QImage(str(source_path))
    if source.isNull():
        raise RuntimeError(f"PNG 无法解析: {source_path}")
    return source.scaled(
        size,
        size,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def paint_background(painter):
    gradient = QLinearGradient(0, 0, CANVAS_SIZE[0], CANVAS_SIZE[1])
    gradient.setColorAt(0, QColor("#10192B"))
    gradient.setColorAt(1, QColor("#17233B"))
    painter.fillRect(0, 0, *CANVAS_SIZE, gradient)
    painter.setPen(QPen(QColor("#5D8EF7"), 4))
    painter.drawLine(72, 84, 222, 84)


def paint_copy(painter, icon):
    painter.drawImage(QRectF(72, 112, 68, 68), icon)
    painter.setPen(QColor("#F8FAFC"))
    painter.setFont(QFont("Segoe UI Variable Display", 47, QFont.Weight.Bold))
    painter.drawText(QRectF(160, 105, 350, 80), int(Qt.AlignmentFlag.AlignVCenter), "ConfigPilot")

    painter.setPen(QColor("#C8D4E6"))
    painter.setFont(QFont("Segoe UI Variable Text", 22))
    painter.drawText(72, 232, "AI tool configuration and automation")

    painter.setFont(QFont("Segoe UI Variable Text", 24))
    lines = (
        "Manage Codex providers, models,",
        "API keys, and context settings",
        "from one desktop app.",
    )
    for index, line in enumerate(lines):
        painter.drawText(72, 302 + index * 36, line)

    badge = QRectF(72, 500, 344, 54)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#5D8EF7"))
    painter.drawRoundedRect(badge, 27, 27)
    painter.setPen(QColor("#0E1A2E"))
    painter.setFont(QFont("Segoe UI Variable Text", 20, QFont.Weight.DemiBold))
    painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), "QML  ·  PySide6  ·  Desktop")


def paint_app_preview(painter, screenshot):
    shadow = QRectF(562, 82, 650, 476)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 70))
    painter.drawRoundedRect(shadow.translated(0, 10), 24, 24)
    painter.setBrush(QColor("#F8FAFC"))
    painter.drawRoundedRect(shadow, 24, 24)

    target = QRectF(578, 98, 618, 444)
    painter.save()
    painter.setClipPath(rounded_path(target, 14))
    painter.drawImage(target, screenshot)
    painter.restore()


def main():
    root = Path(__file__).resolve().parents[1]
    screenshot_path = root / "docs" / "images" / "configpilot-main.png"
    icon_path = root / "resources" / "app_icon.png"
    output_path = root / "docs" / "images" / "social-preview.png"
    if not screenshot_path.is_file():
        raise FileNotFoundError(f"找不到应用截图: {screenshot_path}")

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    canvas = QImage(*CANVAS_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(QColor("#10192B"))
    screenshot = QImage(str(screenshot_path))
    icon = render_icon(icon_path, 68)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    paint_background(painter)
    paint_copy(painter, icon)
    paint_app_preview(painter, screenshot)
    painter.end()

    if not canvas.save(str(output_path), "PNG"):
        raise RuntimeError(f"保存失败: {output_path}")
    print(f"[OK] 已生成 {output_path}")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
