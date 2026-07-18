# coding: utf-8
"""ConfigPilot 对 PrismQML Updater 的应用层协调。"""

from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot

from .app_settings import AppSettings
from .background_updater import BackgroundDownloadUpdater


class AppUpdater(QObject):
    """保留引擎更新能力，并补充自动/手动检查状态与应用配置。"""

    updateAvailable = Signal(str, str, str, str)
    upToDate = Signal(str, bool)
    checkFailed = Signal(str, bool)
    checkingChanged = Signal()
    downloadProgress = Signal(int, int)
    downloadReady = Signal()
    downloadFailed = Signal(str)
    installLaunchFailed = Signal(str)

    def __init__(
        self,
        settings: AppSettings,
        prismqml_version: str,
        parent: Optional[QObject] = None,
        updater_factory: Callable = BackgroundDownloadUpdater,
    ):
        super().__init__(parent)
        self._settings = settings
        self._prismqml_version = prismqml_version
        self._checking = False
        self._manual_check = False
        updates = settings.updates
        self._updater = updater_factory(
            updates.repository,
            f"v{settings.version}",
            updates.asset_keyword,
            parent=self,
        )
        self._connect_engine_signals()

    def _connect_engine_signals(self) -> None:
        self._updater.updateAvailable.connect(self._on_update_available)
        self._updater.upToDate.connect(self._on_up_to_date)
        self._updater.checkFailed.connect(self._on_check_failed)
        self._updater.downloadProgress.connect(self.downloadProgress.emit)
        self._updater.downloadFinished.connect(self._on_download_finished)
        self._updater.downloadFailed.connect(self.downloadFailed.emit)

    @Property(str, constant=True)
    def version(self) -> str:
        return self._settings.version

    @Property(str, constant=True)
    def currentVersion(self) -> str:  # noqa: N802 - QML 公开属性
        return f"v{self._settings.version}"

    @Property(str, constant=True)
    def prismqmlVersion(self) -> str:  # noqa: N802 - QML 公开属性
        return self._prismqml_version

    @Property(bool, constant=True)
    def autoCheckEnabled(self) -> bool:  # noqa: N802 - QML 公开属性
        return self._settings.updates.auto_check

    @Property(int, constant=True)
    def startupDelayMs(self) -> int:  # noqa: N802 - QML 公开属性
        return self._settings.updates.startup_delay_ms

    @Property(bool, constant=True)
    def isWindows(self) -> bool:  # noqa: N802 - QML 公开属性
        return sys.platform == "win32"

    @Property(bool, notify=checkingChanged)
    def checking(self) -> bool:
        return self._checking

    def _set_checking(self, value: bool) -> None:
        if self._checking == value:
            return
        self._checking = value
        self.checkingChanged.emit()

    def _start_check(self, manual: bool) -> None:
        if self._checking:
            self._manual_check = self._manual_check or manual
            return
        self._manual_check = manual
        self._set_checking(True)
        self._updater.checkForUpdate()

    def _finish_check(self) -> bool:
        manual = self._manual_check
        self._manual_check = False
        self._set_checking(False)
        return manual

    @Slot()
    def checkAutomatically(self) -> None:  # noqa: N802 - QML 公开槽
        if self._settings.updates.auto_check:
            self._start_check(False)

    @Slot()
    def checkManually(self) -> None:  # noqa: N802 - QML 公开槽
        self._start_check(True)

    @Slot(str)
    def downloadUpdate(self, url: str) -> None:  # noqa: N802 - QML 公开槽
        self._updater.downloadUpdate(url)

    @Slot(str, result=bool)
    def openReleasePage(self, url: str) -> bool:  # noqa: N802 - QML 公开槽
        return self._updater.openInBrowser(url)

    def _on_update_available(
        self, version: str, notes: str, download_url: str, html_url: str
    ) -> None:
        self._finish_check()
        self.updateAvailable.emit(version, notes, download_url, html_url)

    def _on_up_to_date(self, version: str) -> None:
        self.upToDate.emit(version, self._finish_check())

    def _on_check_failed(self, message: str) -> None:
        self.checkFailed.emit(message, self._finish_check())

    def _on_download_finished(self, installer_path: str) -> None:
        self.downloadReady.emit()
        launched = self._updater.runInstallerAndQuit(
            installer_path,
            self._settings.updates.windows_installer_args,
        )
        if not launched:
            self.installLaunchFailed.emit("无法启动更新安装程序，请稍后重试")
