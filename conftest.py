# coding: utf-8
"""pytest 全局配置。

必须在任何测试导入 PySide6 之前选定 Qt 平台插件(测试机可能没有可用显示),
并用 QGuiApplication 而不是 QCoreApplication —— 桌宠 QML 测试要创建 Window。
"""

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.text.font.db=false")

from PySide6.QtGui import QGuiApplication  # noqa: E402


if QGuiApplication.instance() is None:
    QGuiApplication([])
