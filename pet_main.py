# coding: utf-8
"""ConfigPilot 余额桌宠独立入口。

单独运行桌宠(不启动主窗口):
    <venv>/python.exe pet_main.py
自检:
    SELFTEST=1 <venv>/python.exe pet_main.py   # 3 秒后自动退出
"""

import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "qt.text.font.db=false")
os.environ.setdefault("QML_XHR_ALLOW_FILE_READ", "1")

# 正式打包程序沿用主程序的稳定身份;源码运行时让 PrismQML
# 按脚本路径生成独立身份,避免与主程序共用任务栏图标。
if "__compiled__" in globals():
    os.environ.setdefault("PRISMQML_APP_USER_MODEL_ID", "PrismQML.ConfigPilotPet")


def main() -> int:
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication(sys.argv)
    app.setApplicationName("ConfigPilotPet")
    app.setApplicationDisplayName("ConfigPilot 余额桌宠")

    # 与主程序同一份外观配置(prismqml.json):register_types 装配
    # ThemeManager/ConfigManager 并启用外观持久化,桌宠的主题/皮肤/主题色
    # 与主窗口保持一致,深浅色跟随 Enums 令牌自动切换。
    from prismqml import register_types

    from backend.app_settings import resolve_prismqml_config_path
    from backend.pet_bootstrap import install_pet

    engine = QQmlApplicationEngine()
    register_types(
        engine,
        config_path=resolve_prismqml_config_path(),
        persist_appearance=True,
    )

    app_dir = os.path.dirname(os.path.abspath(__file__))
    taskbar_icon_path = os.path.join(
        app_dir,
        "resources",
        "app_icon.ico" if sys.platform == "win32" else "app_icon.png",
    )
    taskbar_icon = QIcon(taskbar_icon_path)
    if not taskbar_icon.isNull():
        app.setWindowIcon(taskbar_icon)

    try:
        # 返回值同时充当保活引用;bootstrap 还会把装配对象挂到 engine 上。
        _pet_manager, _pet_controller = install_pet(
            engine, app_dir=app_dir, standalone=True
        )
    except RuntimeError as exc:
        print(f"[ERROR] 桌宠初始化失败: {exc}", file=sys.stderr)
        return -1

    if os.environ.get("SELFTEST"):
        print("[SELFTEST] 桌宠独立入口初始化完成")
        from PySide6.QtCore import QTimer

        QTimer.singleShot(3000, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
