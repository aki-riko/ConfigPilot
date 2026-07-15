# coding: utf-8
"""
把 resources/app_icon.png 缩放为 macOS 应用图标 resources/app_icon.icns。

用项目已有的 PySide6 生成各尺寸 PNG 到 .iconset 目录,
再调用 macOS 自带的 iconutil 合成 .icns,无需额外 brew 依赖。
仅在 macOS 上可用(依赖 iconutil)。
"""
import os
import shutil
import subprocess
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage

# iconutil 需要的标准命名: (像素边长, 文件名)
SPECS = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]


def render_png(source: QImage, size: int, out_path: str) -> None:
    img = source.scaled(
        QSize(size, size),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not img.save(out_path, "PNG"):
        raise RuntimeError(f"保存 PNG 失败: {out_path}")


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source_path = os.path.join(root, "resources", "app_icon.png")
    icns_path = os.path.join(root, "resources", "app_icon.icns")
    iconset_dir = os.path.join(root, "resources", "app_icon.iconset")

    if not os.path.isfile(source_path):
        print(f"[ERROR] 找不到源图标: {source_path}")
        return 1

    # 离屏渲染,无需真实显示
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _app = QGuiApplication(sys.argv)

    source = QImage(source_path)
    if source.isNull():
        print(f"[ERROR] PNG 无法解析: {source_path}")
        return 1

    if os.path.isdir(iconset_dir):
        shutil.rmtree(iconset_dir)
    os.makedirs(iconset_dir)

    for size, name in SPECS:
        render_png(source, size, os.path.join(iconset_dir, name))
    print(f"[OK] 已生成 {len(SPECS)} 个 PNG -> {iconset_dir}")

    # iconutil 只在 macOS 上存在
    if shutil.which("iconutil") is None:
        print("[ERROR] 未找到 iconutil,本脚本只能在 macOS 上生成 .icns")
        return 2

    subprocess.run(
        ["iconutil", "-c", "icns", iconset_dir, "-o", icns_path],
        check=True,
    )
    print(f"[OK] 已生成 {icns_path}")

    shutil.rmtree(iconset_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
