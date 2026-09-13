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
import math
import os
import re
from typing import Callable, Optional

from PySide6.QtCore import QObject, QRect, QTimer, QUrl
from PySide6.QtGui import QImage, QRegion
from PySide6.QtQml import QQmlComponent, QQmlEngine

from backend.async_tasks import SerialTaskRunner
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


# alpha ≥ 16/255 视为"有像素";低于它的都是肉眼不可见的噪声边缘。
_MASK_ALPHA_RUN = re.compile(rb"[\x10-\xff]+")
_MASK_DEBOUNCE_MS = 300   # 形态切换/淡入淡出跑完后再抓像素
_MASK_FOLLOWUP_MS = 600   # 事件驱动刷新后补一次,防抓到动画中途的帧


def _build_mask_region(bits: bytes, stride: int, width: int, height: int,
                       dpr: float) -> QRegion:
    """纯函数:把 grabWindow 的 BGRA 字节流转成逻辑坐标 QRegion。

    逐行用正则取 alpha 游程(字节级扫描,C 速度),映射到逻辑 x 后并入该
    逻辑行的游程列表,最后逐行 OR。输入是 bytes 拷贝、输出是值类型 QRegion,
    全程可安全在后台线程执行。
    """
    inv = 1.0 / dpr if dpr and dpr > 0 else 1.0
    rows: dict[int, list[list[int]]] = {}
    for y in range(height):
        base = y * stride + 3  # 小端 ARGB32_Premultiplied:A 在第 4 字节
        row = bits[base : base + 4 * (width - 1) + 1 : 4]
        if not row:
            continue
        spans = rows.setdefault(int(y * inv), [])
        for m in _MASK_ALPHA_RUN.finditer(row):
            x0 = int(m.start() * inv)
            x1 = max(x0 + 1, int(math.ceil(m.end() * inv)))
            if spans and x0 <= spans[-1][1]:
                if x1 > spans[-1][1]:
                    spans[-1][1] = x1
            else:
                spans.append([x0, x1])
    region = QRegion()
    for ly, spans in rows.items():
        for x0, x1 in spans:
            region |= QRegion(QRect(x0, ly, x1 - x0, 1))
    return region


def _attach_pet_window_mask(window: QObject) -> None:
    """把悬浮窗的可交互区限制在"真正画了像素"的地方(像素级遮罩)。

    窗口尺寸恒定取最大形态高度,形态切换只改内容与遮罩,窗口永不 resize
    (透明无边框窗口 resize 会重建渲染表面,表现为整个悬浮窗闪 1~2 帧)。
    遮罩走系统窗口区域(SetWindowRgn),遮罩之外对系统等于不存在:不参与
    合成、不接收鼠标。

    旧版遮罩是 visibleContentHeight 的整宽矩形:pet 形态桌宠只占右下角
    ~136×136,矩形却是 340×156,大片没画东西的区域照样挡住桌面点击。
    现在改为:抓窗口像素 → alpha 游程建区域,只有真正画了像素的地方可交互。
    形态变化先立即铺整宽矩形保底(新内容不被误裁),300ms 防抖后用像素
    区域收紧;立绘姿势帧(sleepy/wave/cheer)变化会改变剪影,钩住
    PetSprite.poseRoleChanged 补扫(眨眼不改剪影,跳过)。逐行字节扫描在
    后台线程,主线程只做抓帧与 setMask。抓帧失败/结果为空一律回退整宽
    矩形,桌宠绝不会"点不到"。
    """
    if not hasattr(window, "setMask") or not hasattr(window, "grabWindow"):
        return

    def apply_rect_mask() -> None:
        height = int(window.height())
        width = int(window.width())
        visible = window.property("visibleContentHeight")
        if not isinstance(visible, (int, float)) or visible <= 0:
            visible = height
        visible = max(1, min(int(visible), height))
        if width <= 0 or height <= 0:
            # 窗口还没拿到真实尺寸:先不设遮罩,等 width/height 变化信号再算。
            # 设成空区域等于把窗口永久变透明,桌宠会"进程活着但屏幕上什么都没有"。
            return
        window.setMask(QRegion(QRect(0, height - visible, width, visible)))
        LOGGER.debug(
            "桌宠保底遮罩已应用: 窗口=%dx%d 可见高=%d dpr=%.2f",
            width, height, visible, float(window.devicePixelRatio()),
        )

    state: dict = {"tasks": None, "busy": False, "followup": False}

    def on_region(region: QRegion) -> None:
        state["busy"] = False
        if region.isEmpty():
            # 全透明:还没渲染或抓帧时机不对 → 保底矩形,等补扫拿真区域
            apply_rect_mask()
        else:
            window.setMask(region)
            LOGGER.debug("桌宠像素遮罩已应用: %d 个矩形", region.rectCount())
        if state["followup"]:
            state["followup"] = False
            window._pet_mask_followup.start()

    def on_region_failed(exc: Exception) -> None:
        state["busy"] = False
        LOGGER.info("桌宠像素遮罩计算失败(保持保底矩形): %s", exc)

    def capture() -> None:
        if state["busy"]:
            return
        width = int(window.width())
        height = int(window.height())
        if width <= 0 or height <= 0 or not window.isVisible():
            return
        try:
            image = window.grabWindow()
        except Exception as exc:
            LOGGER.info("桌宠遮罩抓帧失败(保持保底矩形): %s", exc)
            return
        if image.isNull():
            return
        if not image.hasAlphaChannel():
            # 平台没给透明通道:按"全不透明"处理会把整窗并入区域,反而变差 → 保持现状
            return
        image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        bits = bytes(image.constBits())
        stride = image.bytesPerLine()
        img_w = image.width()
        img_h = image.height()
        dpr = float(window.devicePixelRatio()) or 1.0
        if state["tasks"] is None:
            state["tasks"] = SerialTaskRunner(
                window, thread_name="ConfigPilotPetMask", drain_on_close=True
            )

        def work() -> QRegion:
            return _build_mask_region(bits, stride, img_w, img_h, dpr)

        state["busy"] = True
        try:
            state["tasks"].submit(work, on_region, on_region_failed)
        except RuntimeError as exc:  # 队列已关闭(退出中)
            state["busy"] = False
            LOGGER.info("桌宠像素遮罩被跳过: %s", exc)

    def schedule(widen: bool = True) -> None:
        # 形态/尺寸变化:立刻铺保底矩形,像素收紧前新内容不会被旧遮罩误裁;
        # 姿势变化只动桌宠剪影,直接补扫即可,不重新铺宽。
        if widen:
            apply_rect_mask()
        state["followup"] = True
        # 本 PySide6 版本 QTimer 没有 restart();对运行中的单次定时器再 start() 即重置。
        window._pet_mask_debounce.start()

    def schedule_from_signal(*_args) -> None:
        schedule(True)

    window._pet_mask_debounce = QTimer(window)
    window._pet_mask_debounce.setSingleShot(True)
    window._pet_mask_debounce.setInterval(_MASK_DEBOUNCE_MS)
    window._pet_mask_debounce.timeout.connect(capture)
    window._pet_mask_followup = QTimer(window)
    window._pet_mask_followup.setSingleShot(True)
    window._pet_mask_followup.setInterval(_MASK_FOLLOWUP_MS)
    window._pet_mask_followup.timeout.connect(capture)

    signals = ("visibleContentHeightChanged", "widthChanged", "heightChanged", "screenChanged")
    for name in signals:
        signal = getattr(window, name, None)
        if signal is not None:
            signal.connect(schedule_from_signal)

    def _on_visibility_changed(visible: bool) -> None:
        if visible:
            schedule(False)

    visibility = getattr(window, "visibilityChanged", None)
    if visibility is not None:
        visibility.connect(_on_visibility_changed)

    # 姿势帧(sleepy/wave/cheer)会改变剪影:钩住 PetSprite.poseRoleChanged 补扫;
    # blink 只是闭眼、剪影不变,跳过,免得每 3~6 秒白扫一次。
    def _on_pose_changed() -> None:
        sprite = window._pet_mask_sprite
        if str(sprite.property("poseRole") or "") == "blink":
            return
        schedule(False)

    sprite = window.findChild(QObject, "petSprite")
    if sprite is None:
        LOGGER.info("桌宠遮罩:未找到 petSprite,姿势变化不会触发补扫")
    else:
        pose_changed = getattr(sprite, "poseRoleChanged", None)
        if pose_changed is not None:
            window._pet_mask_sprite = sprite  # 保活包装对象,回调里还要读属性
            pose_changed.connect(_on_pose_changed)
    schedule()


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
        # 内置桌宠立绘随程序目录发布(resources/pet),不写进用户配置目录。
        resources_dir=os.path.join(app_dir, "resources"),
        # 今日日志本地累计缓存:与配置文件同目录,重启后"今日已用"不清零。
        log_store_path=str(pet_config_path.parent / "pet_logs.json"),
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
        if qml_name == "PetWindow.qml":
            # 悬浮窗尺寸恒定,靠遮罩切换可见区;设置窗是普通窗口,不需要遮罩
            # (加遮罩反而会把它自己的投影裁掉)。
            _attach_pet_window_mask(window)
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
