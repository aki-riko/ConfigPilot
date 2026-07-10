# coding: utf-8
"""从 SVG 源图标生成包含多种尺寸的 Windows ICO。"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"无法编码 {size}x{size} PNG")
    return bytes(buffer.data())


def write_ico(images: list[tuple[int, bytes]], output_path: Path) -> None:
    header_size = 6 + 16 * len(images)
    offset = header_size
    entries = []
    payloads = []

    for size, payload in images:
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        payloads.append(payload)
        offset += len(payload)

    output_path.write_bytes(
        struct.pack("<HHH", 0, 1, len(images))
        + b"".join(entries)
        + b"".join(payloads)
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source_path = root / "resources" / "app_icon.svg"
    output_path = root / "resources" / "app_icon.ico"

    if not source_path.is_file():
        print(f"[ERROR] 找不到源图标: {source_path}")
        return 1

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(source_path))
    if not renderer.isValid():
        print(f"[ERROR] SVG 无法解析: {source_path}")
        return 1

    write_ico(
        [(size, render_png(renderer, size)) for size in SIZES],
        output_path,
    )
    print(f"[OK] 已生成 {output_path}，包含 {len(SIZES)} 种尺寸")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
