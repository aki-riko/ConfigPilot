# coding: utf-8
"""
ConfigPilot 应用入口。

运行: <venv>/python.exe main.py
"""
import os
import sys


APP_WINDOW_WIDTH = 980
APP_WINDOW_HEIGHT = 640

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
    app_dir = os.path.dirname(os.path.abspath(__file__))
    from backend.app_settings import load_app_settings, resolve_prismqml_config_path

    try:
        app_settings = load_app_settings(os.path.join(app_dir, "app_config.json"))
    except (OSError, ValueError) as exc:
        print(f"[ERROR] 加载应用配置失败: {exc}", file=sys.stderr)
        return -1

    taskbar_icon_path = os.path.join(
        app_dir,
        "resources",
        "app_icon.ico" if sys.platform == "win32" else "app_icon.png",
    )
    app = App(
        sys.argv,
        application_icon=taskbar_icon_path,
        splash_subtitle="正在加载...",
        splash_width=APP_WINDOW_WIDTH,
        splash_height=APP_WINDOW_HEIGHT,
        config_path=resolve_prismqml_config_path(),
        persist_appearance=True,
    )
    app.setApplicationName("ConfigPilot")
    app.setApplicationVersion(app_settings.version)
    engine = app.engine

    # 在创建 QML Window 前设置应用级图标，避免 Windows 任务栏先缓存通用图标。
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

    # 更新检查、下载、摘要校验和安装启动全部交给 PrismQML 引擎。
    # 应用侧只提供仓库、当前版本和安装包关键词。
    app_updater = app.enable_auto_update(
        app_settings.updates.repository,
        f"v{app_settings.version}",
        app_settings.updates.asset_keyword,
    )
    codex = CodexConfig()
    claude_desktop = ClaudeDesktopConfig()
    engine.rootContext().setContextProperty("AppUpdater", app_updater)
    engine.rootContext().setContextProperty("AppVersion", app_settings.version)
    engine.rootContext().setContextProperty("PrismQMLVersion", prismqml.__version__)
    engine.rootContext().setContextProperty(
        "PrismQMLHomepage", app_settings.prismqml_url
    )
    engine.rootContext().setContextProperty("AppHomepage", app_settings.project_url)
    engine.rootContext().setContextProperty("AppAuthor", app_settings.author)
    engine.rootContext().setContextProperty("AppYear", app_settings.year)
    engine.rootContext().setContextProperty(
        "AppAutoCheckEnabled", app_settings.updates.auto_check
    )
    engine.rootContext().setContextProperty(
        "AppUpdateStartupDelayMs", app_settings.updates.startup_delay_ms
    )
    engine.rootContext().setContextProperty(
        "AppInstallerSilentArgs", app_settings.updates.windows_installer_args
    )
    engine.rootContext().setContextProperty("CodexConfig", codex)
    engine.rootContext().setContextProperty("ClaudeDesktopConfig", claude_desktop)

    qml_main = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "main.qml")
    engine.load(QUrl.fromLocalFile(qml_main))

    if not engine.rootObjects():
        print("[ERROR] 加载 main.qml 失败,检查组件路径或语法")
        return -1

    # QML 窗口已创建但保持隐藏；先完成 FastSplash 尺寸/元数据交接，再显示主窗。
    window_instance = engine.rootObjects()[0].property("windowInstance")
    if window_instance is None:
        print("[WARN] 未找到主窗口实例，无法刷新原生窗口图标", file=sys.stderr)
    else:
        # QML 创建的 Window 不会经过 Python WindowCore.show()，需要显式
        # 交给 PrismQML 的 FastSplash 交接入口完成元数据同步和首帧交接。
        if not app.attach_startup_window(window_instance):
            print("[WARN] FastSplash 主窗口绑定失败", file=sys.stderr)
        if not taskbar_icon.isNull():
            window_instance.setIcon(taskbar_icon)
        if not window_instance.isVisible():
            window_instance.show()

    # 余额监控桌宠:始终注册控制器与开关管理器(主界面设置页需要),
    # 悬浮窗与设置窗口按需懒创建;未配置 Key 时开关默认关,不影响原有行为。
    try:
        from PySide6.QtQml import QQmlComponent

        from backend.newapi_pet import NewApiPet
        from backend.pet_config import (
            load_pet_config_safe,
            resolve_effective_config,
            resolve_pet_config_path,
        )
        from backend.pet_manager import PetManager
        from backend.pet_sources import PetSourceResolver

        pet_config_path = resolve_pet_config_path()
        pet_loaded, pet_error = load_pet_config_safe(pet_config_path)
        if pet_error:
            print(f"[WARN] 桌宠配置损坏,已回退默认值: {pet_error}", file=sys.stderr)
        pet_effective = resolve_effective_config(pet_loaded)
        pet_resolver = PetSourceResolver(codex.store, claude_desktop.read_gateway_credentials)
        pet_controller = NewApiPet(
            str(pet_config_path), pet_effective, source_resolver=pet_resolver
        )
        engine.rootContext().setContextProperty("PetStandalone", False)
        engine.rootContext().setContextProperty("NewApiPet", pet_controller)

        def _make_qml_window(qml_name):
            component = QQmlComponent(engine)
            component.loadUrl(QUrl.fromLocalFile(os.path.join(app_dir, "qml", "pet", qml_name)))
            if component.isError():
                for err in component.errors():
                    print(f"[WARN] {qml_name}: {err.toString()}", file=sys.stderr)
                return None
            window = component.create()
            if window is None:
                for err in component.errors():
                    print(f"[WARN] {qml_name} 创建失败: {err.toString()}", file=sys.stderr)
                return None
            # 保活 component:否则其被回收时会连带销毁 create() 出的窗口。
            window._pet_component = component
            return window

        pet_manager = PetManager(
            pet_controller,
            lambda: _make_qml_window("PetWindow.qml"),
            lambda: _make_qml_window("PetSettingsDialog.qml"),
            standalone=False,
            # 桌宠寿命跟随主窗口:主窗口隐藏(关闭到托盘)时一并隐藏。
            main_window=window_instance,
        )
        engine.rootContext().setContextProperty("PetManager", pet_manager)
        if not os.environ.get("SELFTEST"):
            pet_manager.show_at_startup()
        else:
            print(
                "[SELFTEST] 桌宠:开关 =", pet_manager.petEnabled,
                "/ 悬浮窗可见 =", pet_manager.petVisible,
                "/ 主窗口可见 =", bool(window_instance.isVisible()) if window_instance else None,
            )
    except Exception as exc:
        print(f"[WARN] 余额桌宠初始化失败: {exc}", file=sys.stderr)

    # headless 自检:设了 SELFTEST 则加载成功后定时退出
    if os.environ.get("SELFTEST"):
        from PySide6.QtCore import QTimer
        print("[SELFTEST] QML 加载成功, rootObjects =", len(engine.rootObjects()))
        QTimer.singleShot(3000, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
