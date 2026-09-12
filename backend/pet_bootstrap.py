# coding: utf-8
"""桌宠装配唯一入口:主程序(main.py)与独立入口(pet_main.py)共用。

负责四件事:
1. 解析凭证来源(Codex/Claude)并创建 NewApiPet 控制器;
2. 把控制器/管理器注册进 QML 上下文(PetStandalone/NewApiPet/PetManager);
3. 提供保活 component 的 QML 窗口工厂(QQmlComponent 被回收会连带销毁窗口);
4. 按模式创建 PetManager(独立模式无主窗口约束,集成模式寿命跟随主窗口)。
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine

from backend.newapi_pet import NewApiPet
from backend.pet_config import (
    load_pet_config_safe,
    resolve_effective_config,
    resolve_pet_config_path,
)
from backend.pet_manager import PetManager
from backend.pet_sources import PetSourceResolver

LOGGER = logging.getLogger(__name__)


def _default_codex_store():
    from backend.codex_config_store import CodexConfigStore

    return CodexConfigStore(os.path.join(os.path.expanduser("~"), ".codex"))


def install_pet(
    engine: QQmlEngine,
    *,
    app_dir: str,
    standalone: bool,
    codex_store=None,
    claude_reader: Optional[Callable] = None,
    main_window: Optional[QObject] = None,
    show_at_startup: bool = True,
) -> tuple[PetManager, NewApiPet]:
    """装配桌宠并注册 QML 上下文,返回 (manager, controller) 供调用方自检/联动。"""
    if codex_store is None:
        codex_store = _default_codex_store()
    resolver = PetSourceResolver(codex_store, claude_reader)

    pet_config_path = resolve_pet_config_path()
    pet_loaded, pet_error = load_pet_config_safe(pet_config_path)
    if pet_error:
        LOGGER.warning("桌宠配置损坏,已回退默认值: %s", pet_error)
    controller = NewApiPet(
        str(pet_config_path),
        resolve_effective_config(pet_loaded),
        source_resolver=resolver,
    )

    engine.rootContext().setContextProperty("PetStandalone", standalone)
    engine.rootContext().setContextProperty("NewApiPet", controller)

    pet_dir = os.path.join(app_dir, "qml", "pet")

    def _make_qml_window(qml_name: str) -> Optional[QObject]:
        component = QQmlComponent(engine)
        component.loadUrl(QUrl.fromLocalFile(os.path.join(pet_dir, qml_name)))
        if component.isError():
            for err in component.errors():
                LOGGER.warning("%s: %s", qml_name, err.toString())
            return None
        window = component.create()
        if window is None:
            LOGGER.warning("%s 创建失败", qml_name)
            return None
        # 保活 component:否则其被回收时会连带销毁 create() 出的窗口。
        window._pet_component = component
        return window

    manager = PetManager(
        controller,
        lambda: _make_qml_window("PetWindow.qml"),
        lambda: _make_qml_window("PetSettingsDialog.qml"),
        standalone=standalone,
        # 桌宠寿命跟随主窗口:主窗口隐藏(关闭到托盘)时一并隐藏。
        main_window=main_window,
    )
    engine.rootContext().setContextProperty("PetManager", manager)
    # 保活:三个 QObject 都没有 Qt 父对象,QML 上下文属性不持有所有权。
    # 调用方若不接收返回值,它们会在引用计数归零后被 GC 随时回收
    # (信号互连成环更要等循环 GC),退出时拆除活对象会直接 access violation。
    # 挂到 engine 上与引擎同生命周期,调用方捕获返回值与否都安全。
    engine._pet_keepalive = (controller, resolver, manager)
    if show_at_startup:
        manager.show_at_startup()
    return manager, controller
