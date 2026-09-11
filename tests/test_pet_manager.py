from pathlib import Path
import unittest

from PySide6.QtCore import QObject, Signal

from tests.qt_test_utils import APP  # noqa: F401  确保存在 QCoreApplication 实例

from backend.pet_config import PetConfig
from backend.pet_manager import PetManager


class FakeController(QObject):
    """替身控制器:记录 setAutoShow/refresh 调用,提供 config 与信号。"""

    configSaved = Signal()
    statusChanged = Signal()

    def __init__(self, config: PetConfig, source_ready: bool = False):
        super().__init__()
        self._config = config
        self._source_ready = source_ready
        self.auto_show_calls = []
        self.refresh_calls = 0

    @property
    def config(self):
        return self._config

    @property
    def sourceReady(self):
        return self._source_ready

    def setAutoShow(self, enabled):
        self.auto_show_calls.append(bool(enabled))
        self._config = PetConfig(**{**self._config.__dict__, "auto_show": bool(enabled)})
        self.configSaved.emit()

    def refresh(self):
        self.refresh_calls += 1


class FakeWindow(QObject):
    def __init__(self):
        super().__init__()
        self.visible = False

    def setVisible(self, value):
        self.visible = bool(value)

    def isVisible(self):
        return self.visible


class FakeMainWindow(QObject):
    """替身主窗口:只提供桌宠跟随所需的可见性信号与查询。"""

    visibilityChanged = Signal()

    def __init__(self, visible=True):
        super().__init__()
        self._visible = bool(visible)

    def isVisible(self):
        return self._visible

    def set_visible(self, value):
        self._visible = bool(value)
        self.visibilityChanged.emit()


class PetManagerTests(unittest.TestCase):
    def _make(self, *, standalone=False, auto_show=False, api_key="", base_url="", source_ready=False,
              main_window=None):
        controller = FakeController(PetConfig(
            api_key=api_key, base_url=base_url, auto_show=auto_show), source_ready=source_ready)
        windows = []
        settings_windows = []

        def window_factory():
            win = FakeWindow()
            windows.append(win)
            return win

        def settings_factory():
            win = FakeWindow()
            settings_windows.append(win)
            return win

        manager = PetManager(controller, window_factory, settings_factory, standalone=standalone,
                             main_window=main_window)
        return manager, controller, windows, settings_windows

    def test_standalone_starts_enabled_and_shows(self):
        manager, controller, windows, _ = self._make(standalone=True)
        self.assertTrue(manager.petEnabled)
        manager.show_at_startup()
        self.assertEqual(len(windows), 1)
        self.assertTrue(windows[0].visible)

    def test_disabled_by_default_when_no_auto_show(self):
        manager, _, windows, _ = self._make(standalone=False, auto_show=False)
        self.assertFalse(manager.petEnabled)
        manager.show_at_startup()
        self.assertEqual(windows, [])  # 未开启不创建窗口

    def test_enable_creates_window_once_and_reuses(self):
        manager, controller, windows, _ = self._make(standalone=False, auto_show=False)
        manager.setEnabled(True)
        self.assertTrue(manager.petEnabled)
        self.assertEqual(len(windows), 1)
        self.assertTrue(windows[0].visible)
        self.assertEqual(controller.auto_show_calls, [True])
        # 关闭再开启:复用同一窗口对象,不重复创建
        manager.setEnabled(False)
        self.assertFalse(windows[0].visible)
        manager.setEnabled(True)
        self.assertEqual(len(windows), 1)
        self.assertTrue(windows[0].visible)
        self.assertEqual(controller.auto_show_calls, [True, False, True])

    def test_set_enabled_noop_when_unchanged(self):
        manager, controller, _, _ = self._make(standalone=False, auto_show=False)
        manager.setEnabled(False)
        self.assertEqual(controller.auto_show_calls, [])

    def test_window_close_syncs_switch_off(self):
        manager, controller, windows, _ = self._make(standalone=False, auto_show=True)
        manager.show_at_startup()
        self.assertTrue(windows[0].visible)
        manager.petWindowClosed()
        self.assertFalse(manager.petEnabled)
        self.assertEqual(controller.auto_show_calls, [False])

    def test_standalone_window_close_does_not_toggle(self):
        manager, controller, _, _ = self._make(standalone=True)
        manager.petWindowClosed()
        self.assertTrue(manager.petEnabled)
        self.assertEqual(controller.auto_show_calls, [])

    def test_open_settings_emits_and_creates_once(self):
        manager, _, _, settings_windows = self._make(standalone=False)
        received = []
        manager.openSettingsRequested.connect(lambda: received.append(1))
        manager.openSettings()
        manager.openSettings()
        self.assertEqual(len(settings_windows), 1)
        self.assertEqual(received, [1, 1])

    def test_has_api_key_property(self):
        manager, _, _, _ = self._make(source_ready=True)
        self.assertTrue(manager.petHasApiKey)
        manager2, _, _, _ = self._make(source_ready=False)
        self.assertFalse(manager2.petHasApiKey)

    def test_config_saved_shows_window_when_enabled(self):
        manager, controller, windows, _ = self._make(standalone=False, auto_show=True)
        # 开关为开但窗口尚未创建:保存配置后应自动显示
        controller.configSaved.emit()
        self.assertEqual(len(windows), 1)
        self.assertTrue(windows[0].visible)

    # ---------------------------------------------------------- 跟随主窗口生命周期

    def test_pet_hidden_while_main_window_hidden(self):
        main_window = FakeMainWindow(visible=False)
        manager, _, windows, _ = self._make(auto_show=True, main_window=main_window)
        manager.show_at_startup()
        # 主窗口还没显示:连桌宠窗口都不创建,避免先闪一下再被隐藏
        self.assertEqual(windows, [])

        main_window.set_visible(True)
        self.assertEqual(len(windows), 1)
        self.assertTrue(windows[0].visible)

    def test_pet_follows_main_window_visibility(self):
        main_window = FakeMainWindow(visible=True)
        manager, _, windows, _ = self._make(auto_show=True, main_window=main_window)
        manager.show_at_startup()
        self.assertTrue(windows[0].visible)

        # 主窗口隐藏(关闭到托盘):桌宠跟随隐藏,但开关状态不变
        main_window.set_visible(False)
        self.assertFalse(windows[0].visible)
        self.assertTrue(manager.petEnabled)

        # 主窗口再次出现:桌宠跟着回来
        main_window.set_visible(True)
        self.assertTrue(windows[0].visible)

    def test_pet_stays_hidden_after_switch_off(self):
        main_window = FakeMainWindow(visible=True)
        manager, _, windows, _ = self._make(auto_show=True, main_window=main_window)
        manager.show_at_startup()
        manager.setEnabled(False)
        # 关掉开关后主窗口再怎么显隐都不该把桌宠放出来
        main_window.set_visible(False)
        main_window.set_visible(True)
        self.assertFalse(windows[0].visible)

    def test_pet_visible_property_tracks_window(self):
        main_window = FakeMainWindow(visible=True)
        manager, _, _, _ = self._make(standalone=False, auto_show=False, main_window=main_window)
        self.assertFalse(manager.petVisible)  # 窗口还没创建
        manager.setEnabled(True)
        self.assertTrue(manager.petVisible)
        manager.setEnabled(False)
        self.assertFalse(manager.petVisible)

    def test_standalone_ignores_main_window(self):
        manager, _, windows, _ = self._make(standalone=True)
        manager.show_at_startup()
        self.assertTrue(windows[0].visible)


if __name__ == "__main__":
    unittest.main()
