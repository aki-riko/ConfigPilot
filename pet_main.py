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
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent

    app = QGuiApplication(sys.argv)
    app.setApplicationName("ConfigPilotPet")
    app.setApplicationDisplayName("ConfigPilot 余额桌宠")

    from backend.newapi_pet import NewApiPet
    from backend.pet_config import resolve_pet_config_path
    from backend.pet_manager import PetManager

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("PetStandalone", True)
    try:
        pet = NewApiPet(str(resolve_pet_config_path()))
    except RuntimeError as exc:
        print(f"[ERROR] 桌宠初始化失败: {exc}", file=sys.stderr)
        return -1
    engine.rootContext().setContextProperty("NewApiPet", pet)

    pet_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "pet")

    def _make_qml_window(qml_name):
        component = QQmlComponent(engine)
        component.loadUrl(QUrl.fromLocalFile(os.path.join(pet_dir, qml_name)))
        if component.isError():
            for err in component.errors():
                print(f"[ERROR] {qml_name}: {err.toString()}", file=sys.stderr)
            return None
        window = component.create()
        if window is None:
            return None
        # 保活 component,避免其回收时销毁窗口。
        window._pet_component = component
        return window

    manager = PetManager(
        pet,
        lambda: _make_qml_window("PetWindow.qml"),
        lambda: _make_qml_window("PetSettingsDialog.qml"),
        standalone=True,
    )
    engine.rootContext().setContextProperty("PetManager", manager)
    manager.show_at_startup()

    if os.environ.get("SELFTEST"):
        print("[SELFTEST] 桌宠独立入口初始化完成")
        QTimer.singleShot(3000, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
