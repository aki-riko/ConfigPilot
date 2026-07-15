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

# 正式打包程序沿用安装器快捷方式的稳定身份；源码运行时让 PrismQML
# 按脚本路径生成独立身份，避免与本机旧安装版快捷方式共用任务栏图标。
if "__compiled__" in globals():
    os.environ.setdefault("PRISMQML_APP_USER_MODEL_ID", "PrismQML.ConfigPilot")

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from prismqml import App


def main() -> int:
    # App 自动完成 DPI / 消息处理器 / register_types / 异步孵化控制器
    app = App(sys.argv)
    engine = app.engine

    # 在创建 QML Window 前设置应用级图标，避免 Windows 任务栏先缓存通用图标。
    app_dir = os.path.dirname(os.path.abspath(__file__))
    taskbar_icon_path = os.path.join(
        app_dir,
        "resources",
        "app_icon.ico" if sys.platform == "win32" else "app_icon.png",
    )
    taskbar_icon = QIcon(taskbar_icon_path)
    if taskbar_icon.isNull():
        print(f"[WARN] 应用图标加载失败: {taskbar_icon_path}", file=sys.stderr)
    else:
        app.setWindowIcon(taskbar_icon)

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
    logo_path = os.path.join(app_dir, "resources", "app_icon.png")
    engine.rootContext().setContextProperty(
        "AppLogo",
        QUrl.fromLocalFile(logo_path).toString() if os.path.isfile(logo_path) else ""
    )

    # 注册 AI 工具配置后端
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from backend.codex_config import CodexConfig
    from backend.claude_desktop_config import ClaudeDesktopConfig

    codex = CodexConfig()
    claude_desktop = ClaudeDesktopConfig()
    engine.rootContext().setContextProperty("CodexConfig", codex)
    engine.rootContext().setContextProperty("ClaudeDesktopConfig", claude_desktop)

    qml_main = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "main.qml")
    engine.load(QUrl.fromLocalFile(qml_main))

    if not engine.rootObjects():
        print("[ERROR] 加载 main.qml 失败,检查组件路径或语法")
        return -1

    # QML 窗口已在 Component.onCompleted 中创建并显示；此时再设置原生
    # QWindow 图标，确保 Windows 任务栏收到当前窗口的图标刷新事件。
    window_instance = engine.rootObjects()[0].property("windowInstance")
    if window_instance is None:
        print("[WARN] 未找到主窗口实例，无法刷新原生窗口图标", file=sys.stderr)
    elif not taskbar_icon.isNull():
        window_instance.setIcon(taskbar_icon)

    # headless 自检:设了 SELFTEST 则加载成功后定时退出
    if os.environ.get("SELFTEST"):
        from PySide6.QtCore import QTimer
        print("[SELFTEST] QML 加载成功, rootObjects =", len(engine.rootObjects()))
        QTimer.singleShot(3000, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
