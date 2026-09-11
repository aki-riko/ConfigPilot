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


def main() -> int:
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication(sys.argv)
    app.setApplicationName("ConfigPilotPet")
    app.setApplicationDisplayName("ConfigPilot 余额桌宠")

    from backend.newapi_pet import NewApiPet
    from backend.pet_config import resolve_pet_config_path

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("PetStandalone", True)
    try:
        pet = NewApiPet(str(resolve_pet_config_path()))
    except RuntimeError as exc:
        print(f"[ERROR] 桌宠初始化失败: {exc}", file=sys.stderr)
        return -1
    engine.rootContext().setContextProperty("NewApiPet", pet)

    qml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "qml", "pet", "PetWindow.qml"
    )
    engine.load(QUrl.fromLocalFile(qml_path))
    if not engine.rootObjects():
        print("[ERROR] 加载 PetWindow.qml 失败,检查组件路径或语法", file=sys.stderr)
        return -1

    if os.environ.get("SELFTEST"):
        print("[SELFTEST] PetWindow.qml 加载成功, rootObjects =", len(engine.rootObjects()))
        QTimer.singleShot(3000, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
