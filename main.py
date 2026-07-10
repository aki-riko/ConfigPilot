# coding: utf-8
"""
ConfigPilot 应用入口。

运行: <venv>/python.exe main.py
"""
import os
import sys

# 让 QML XHR 可读本地文件(Translator 加载 i18n 所需)
os.environ.setdefault("QT_LOGGING_RULES", "qt.text.font.db=false")
os.environ.setdefault("QML_XHR_ALLOW_FILE_READ", "1")

from PySide6.QtCore import QUrl
from prismqml import App


def main() -> int:
    # App 自动完成 DPI / 消息处理器 / register_types / 异步孵化控制器
    app = App(sys.argv)
    engine = app.engine

    # 指向 prismqml 包目录(其下 PrismQML/qmldir 提供 QML 模块)
    import prismqml
    pkg_dir = os.path.dirname(prismqml.__file__)
    engine.addImportPath(pkg_dir)

    # 图标目录 URL(供 QML 拼接导航图标路径)
    icons_dir = os.path.join(pkg_dir, "PrismQML", "controls", "icons", "fluent")
    engine.rootContext().setContextProperty(
        "FluentIconsDir", QUrl.fromLocalFile(icons_dir + os.sep).toString()
    )

    # 注册 svg 图片提供器(窗口图标走 image://svg/ 需要它)
    import prismqml as _fq
    try:
        engine.addImageProvider("svg", _fq.get_svg_provider())
    except Exception as exc:
        print(f"[WARN] 注册 SVG 图片提供器失败: {exc}", file=sys.stderr)

    # 应用图标 URL(窗口/任务栏)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(app_dir, "resources", "app_icon.svg")
    engine.rootContext().setContextProperty(
        "AppLogo",
        QUrl.fromLocalFile(logo_path).toString() if os.path.isfile(logo_path) else ""
    )

    # 注册 Codex 配置后端
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from backend.codex_config import CodexConfig
    codex = CodexConfig()
    engine.rootContext().setContextProperty("CodexConfig", codex)

    qml_main = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "main.qml")
    engine.load(QUrl.fromLocalFile(qml_main))

    if not engine.rootObjects():
        print("[ERROR] 加载 main.qml 失败,检查组件路径或语法")
        return -1

    # headless 自检:设了 SELFTEST 则加载成功后定时退出
    if os.environ.get("SELFTEST"):
        from PySide6.QtCore import QTimer
        print("[SELFTEST] QML 加载成功, rootObjects =", len(engine.rootObjects()))
        QTimer.singleShot(1500, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
