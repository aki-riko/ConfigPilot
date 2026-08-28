# coding: utf-8
"""Claude Desktop 开发者模式与第三方推理配置后端。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import uuid

from PySide6.QtCore import QObject, Property, Signal, Slot

from backend.claude_install_sources import (
    claude_desktop_installed,
    claude_install_target,
)
from backend.claude_installer import ClaudeInstaller
from backend.async_tasks import SerialTaskRunner
from backend.system_launcher import open_external_target
from backend.claude_config_io import (
    atomic_write_json,
    models_to_text,
    parse_headers,
    parse_models,
    read_json_object,
    valid_profile_id,
    validate_endpoint,
)


LOGGER = logging.getLogger(__name__)

CLAUDE_APP_NAME = "Claude"
CLAUDE_THIRD_PARTY_DIR_NAME = "Claude-3p"
CONFIG_FILE_NAME = "claude_desktop_config.json"
DEVELOPER_SETTINGS_FILE_NAME = "developer_settings.json"
CONFIG_LIBRARY_DIR_NAME = "configLibrary"
CONFIG_LIBRARY_META_FILE_NAME = "_meta.json"
DEFAULT_PROFILE_NAME = "ConfigPilot"
CC_SWITCH_PROFILE_NAME = "CC Switch"
SUPPORTED_AUTH_SCHEMES = {"bearer", "x-api-key"}


def _primary_data_dir() -> Path:
    override = os.environ.get("CONFIGPILOT_CLAUDE_PRIMARY_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / CLAUDE_APP_NAME
    return Path.home() / "Library" / "Application Support" / CLAUDE_APP_NAME


def _third_party_data_dir() -> Path:
    override = os.environ.get("CONFIGPILOT_CLAUDE_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / CLAUDE_THIRD_PARTY_DIR_NAME
    return Path.home() / "Library" / "Application Support" / CLAUDE_THIRD_PARTY_DIR_NAME


class ClaudeDesktopConfig(QObject):
    """读取并安全写入 Claude Desktop 的第三方推理配置库。"""

    changed = Signal()
    operationBusyChanged = Signal()
    installChanged = Signal()
    notify = Signal(int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._primary_dir = _primary_data_dir()
        self._data_dir = _third_party_data_dir()
        self._install_target = claude_install_target()
        self._installer = ClaudeInstaller(self)
        self._installer.changed.connect(self.installChanged.emit)
        self._installer.notify.connect(self.notify.emit)
        self._tasks = SerialTaskRunner(
            self,
            thread_name="ConfigPilotClaudeConfig",
            drain_on_close=True,
        )
        self._tasks.busyChanged.connect(self.operationBusyChanged.emit)
        self._config_library_dir = self._data_dir / CONFIG_LIBRARY_DIR_NAME
        self._meta_path = self._config_library_dir / CONFIG_LIBRARY_META_FILE_NAME
        self._desktop_config_path = self._data_dir / CONFIG_FILE_NAME
        self._developer_settings_paths = tuple(
            dict.fromkeys(
                [
                    self._primary_dir / DEVELOPER_SETTINGS_FILE_NAME,
                    self._data_dir / DEVELOPER_SETTINGS_FILE_NAME,
                ]
            )
        )
        self._active_config_path = self._config_library_dir
        self._installed = False
        self._developer_mode_enabled = False
        self._third_party_enabled = False
        self._endpoint = ""
        self._auth_scheme = "bearer"
        self._models_text = ""
        self._has_api_key = False
        self._header_count = 0
        self._profile_name = ""
        self._configpilot_profile_exists = False
        self._active_profile_name = ""
        self._can_import_active_profile = False
        self.reload()

    @Property(str, notify=changed)
    def dataDir(self):
        return str(self._data_dir)

    @Property(str, notify=changed)
    def configPath(self):
        return str(self._active_config_path)

    @Property(bool, notify=changed)
    def installed(self):
        return self._installed

    @Property(bool, notify=changed)
    def developerModeEnabled(self):
        return self._developer_mode_enabled

    @Property(bool, notify=changed)
    def thirdPartyEnabled(self):
        return self._third_party_enabled

    @Property(str, notify=changed)
    def endpoint(self):
        return self._endpoint

    @Property(str, notify=changed)
    def authScheme(self):
        return self._auth_scheme

    @Property(str, notify=changed)
    def modelsText(self):
        return self._models_text

    @Property(bool, notify=changed)
    def hasApiKey(self):
        return self._has_api_key

    @Property(int, notify=changed)
    def headerCount(self):
        return self._header_count

    @Property(str, notify=changed)
    def profileName(self):
        return self._profile_name

    @Property(bool, notify=changed)
    def configPilotProfileExists(self):
        return self._configpilot_profile_exists

    @Property(str, notify=changed)
    def activeProfileName(self):
        return self._active_profile_name

    @Property(bool, notify=changed)
    def canImportActiveProfile(self):
        return self._can_import_active_profile

    @Property(bool, notify=operationBusyChanged)
    def operationBusy(self):
        return self._tasks.busy

    @Property(bool, notify=installChanged)
    def installBusy(self):
        return self._installer.busy

    @Property(bool, notify=installChanged)
    def installCancelable(self):
        return self._installer.cancelable

    @Property(int, notify=installChanged)
    def installProgress(self):
        return self._installer.progress

    @Property(str, notify=installChanged)
    def installStatus(self):
        return self._installer.status

    @staticmethod
    def _validated_entries(meta: dict) -> list[dict]:
        entries = meta.get("entries", [])
        if not isinstance(entries, list):
            raise ValueError("_meta.json 的 entries 必须是数组")
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or not valid_profile_id(entry.get("id"))
                or not isinstance(entry.get("name"), str)
            ):
                raise ValueError("_meta.json 包含无效配置条目，已拒绝覆盖")
        return entries

    def _active_profile(self, meta: dict) -> tuple[str, str]:
        """Return ConfigPilot's own profile, independent of Claude's active profile."""
        entries = self._validated_entries(meta)
        configpilot_entries = [
            entry
            for entry in entries
            if entry.get("name") == DEFAULT_PROFILE_NAME
        ]
        if len(configpilot_entries) > 1:
            raise ValueError("_meta.json 中存在多个 ConfigPilot 档案，已拒绝覆盖")
        if not configpilot_entries:
            return "", ""

        configpilot_id = str(configpilot_entries[0]["id"])
        if any(
            entry.get("name") == CC_SWITCH_PROFILE_NAME
            and entry.get("id") == configpilot_id
            for entry in entries
        ):
            raise ValueError("ConfigPilot 与 CC Switch 档案 ID 冲突，已拒绝覆盖")
        return configpilot_id, DEFAULT_PROFILE_NAME

    def _active_profile_entry(self, meta: dict) -> tuple[str, str]:
        applied_id = meta.get("appliedId", "")
        if not valid_profile_id(applied_id):
            return "", ""
        for entry in self._validated_entries(meta):
            if entry.get("id") == applied_id:
                return str(applied_id), str(entry["name"])
        return "", ""

    def _empty_snapshot(self) -> dict:
        return {
            "installed": False,
            "developerModeEnabled": False,
            "thirdPartyEnabled": False,
            "endpoint": "",
            "authScheme": "bearer",
            "modelsText": "",
            "hasApiKey": False,
            "headerCount": 0,
            "profileName": "",
            "configPilotProfileExists": False,
            "activeProfileName": "",
            "canImportActiveProfile": False,
            "activeConfigPath": self._config_library_dir,
        }

    def _read_snapshot(self) -> dict:
        snapshot = self._empty_snapshot()
        snapshot["installed"] = claude_desktop_installed(self._install_target)
        snapshot["developerModeEnabled"] = any(
            read_json_object(path).get("allowDevTools") is True
            for path in self._developer_settings_paths
        )
        desktop_config = read_json_object(self._desktop_config_path)
        meta = read_json_object(self._meta_path)
        configpilot_id, profile_name = self._active_profile(meta)
        active_id, active_name = self._active_profile_entry(meta)
        snapshot.update(
            {
                "configPilotProfileExists": bool(configpilot_id),
                "activeProfileName": active_name,
                "canImportActiveProfile": bool(
                    active_id
                    and active_id != configpilot_id
                    and active_name != DEFAULT_PROFILE_NAME
                    and not configpilot_id
                ),
            }
        )
        profile = {}
        profile_path = self._config_library_dir
        if configpilot_id:
            profile_path = self._config_library_dir / f"{configpilot_id}.json"
            profile = read_json_object(profile_path)
        elif active_id:
            source_path = self._config_library_dir / f"{active_id}.json"
            source_profile = read_json_object(source_path)
            if source_profile.get("inferenceProvider") == "gateway":
                profile = source_profile
                profile_path = source_path

        if not profile:
            return snapshot

        endpoint = str(profile.get("inferenceGatewayBaseUrl", ""))
        auth_scheme = str(
            profile.get("inferenceGatewayAuthScheme", "bearer")
        ).strip()
        headers = profile.get(
            "inferenceCustomHeaders",
            profile.get("inferenceGatewayHeaders", {}),
        )
        snapshot.update(
            {
                "activeConfigPath": profile_path,
                "profileName": profile_name if configpilot_id else "",
                "endpoint": endpoint,
                "authScheme": (
                    auth_scheme if auth_scheme in SUPPORTED_AUTH_SCHEMES else "bearer"
                ),
                "modelsText": models_to_text(profile.get("inferenceModels")),
                "hasApiKey": bool(profile.get("inferenceGatewayApiKey")),
                "headerCount": len(headers) if isinstance(headers, dict) else 0,
                "thirdPartyEnabled": (
                    desktop_config.get("deploymentMode") == "3p"
                    and bool(configpilot_id)
                    and meta.get("appliedId") == configpilot_id
                    and profile.get("inferenceProvider") == "gateway"
                    and bool(endpoint)
                ),
            }
        )
        return snapshot

    def _apply_snapshot(self, snapshot: dict) -> None:
        self._installed = bool(snapshot["installed"])
        self._developer_mode_enabled = bool(snapshot["developerModeEnabled"])
        self._third_party_enabled = bool(snapshot["thirdPartyEnabled"])
        self._endpoint = str(snapshot["endpoint"])
        self._auth_scheme = str(snapshot["authScheme"])
        self._models_text = str(snapshot["modelsText"])
        self._has_api_key = bool(snapshot["hasApiKey"])
        self._header_count = int(snapshot["headerCount"])
        self._profile_name = str(snapshot["profileName"])
        self._configpilot_profile_exists = bool(snapshot["configPilotProfileExists"])
        self._active_profile_name = str(snapshot["activeProfileName"])
        self._can_import_active_profile = bool(snapshot["canImportActiveProfile"])
        self._active_config_path = Path(snapshot["activeConfigPath"])
        self.changed.emit()

    def _on_reload_failed(self, exc: Exception) -> None:
        LOGGER.exception(
            "读取 Claude Desktop 配置失败",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        self._apply_snapshot(self._empty_snapshot())
        self.notify.emit(3, "Claude 配置读取失败", str(exc))

    @Slot()
    def reload(self):
        self._tasks.submit(
            self._read_snapshot,
            self._apply_snapshot,
            self._on_reload_failed,
        )

    def _prepare_profile(
        self,
        cfg: dict,
        current_models_text: str,
    ) -> tuple[dict, dict, Path]:
        meta = read_json_object(self._meta_path)
        entries = self._validated_entries(meta)

        active_id, active_name = self._active_profile_entry(meta)
        profile_id, _ = self._active_profile(meta)
        if not profile_id:
            profile_id = str(uuid.uuid4())
            if any(entry.get("id") == profile_id for entry in entries):
                raise ValueError("新建 ConfigPilot 档案 ID 与现有档案冲突，已拒绝覆盖")
            entries.append({"id": profile_id, "name": DEFAULT_PROFILE_NAME})
            meta["entries"] = entries

        # ConfigPilot must activate its own profile without replacing other tools'
        # profiles (for example CC Switch or Default).
        meta["appliedId"] = profile_id

        profile_path = self._config_library_dir / f"{profile_id}.json"
        profile = read_json_object(profile_path)
        if not profile:
            if active_id and active_name != DEFAULT_PROFILE_NAME:
                source_profile = read_json_object(
                    self._config_library_dir / f"{active_id}.json"
                )
                if source_profile.get("inferenceProvider") == "gateway":
                    profile = source_profile
        endpoint = validate_endpoint(str(cfg.get("endpoint", "")))
        auth_scheme = str(cfg.get("authScheme", "bearer")).strip()
        if auth_scheme not in SUPPORTED_AUTH_SCHEMES:
            raise ValueError("认证方式只能是 bearer 或 x-api-key")

        models_text = str(cfg.get("modelsText", ""))
        profile["inferenceProvider"] = "gateway"
        profile["inferenceGatewayBaseUrl"] = endpoint
        profile["inferenceCredentialKind"] = "static"
        profile["inferenceGatewayAuthScheme"] = auth_scheme

        if models_text != current_models_text:
            models = parse_models(models_text)
            if models:
                profile["inferenceModels"] = models
            else:
                profile.pop("inferenceModels", None)

        api_key = str(cfg.get("apiKey", "")).strip()
        if bool(cfg.get("clearApiKey", False)):
            profile.pop("inferenceGatewayApiKey", None)
        elif api_key:
            profile["inferenceGatewayApiKey"] = api_key

        headers_text = str(cfg.get("headersText", "")).strip()
        if bool(cfg.get("clearHeaders", False)):
            profile.pop("inferenceCustomHeaders", None)
            profile.pop("inferenceGatewayHeaders", None)
        elif headers_text:
            profile["inferenceCustomHeaders"] = parse_headers(headers_text)
            profile.pop("inferenceGatewayHeaders", None)

        return meta, profile, profile_path

    def _saved_gateway_profile(self) -> dict:
        meta = read_json_object(self._meta_path)
        profile_id, _ = self._active_profile(meta)
        if not profile_id:
            raise ValueError("尚未保存 Gateway 配置，请先填写并应用")
        profile_path = self._config_library_dir / f"{profile_id}.json"
        profile = read_json_object(profile_path)
        if profile.get("inferenceProvider") != "gateway":
            raise ValueError("当前配置档案不是 Gateway 类型")
        validate_endpoint(str(profile.get("inferenceGatewayBaseUrl", "")))
        return profile

    def _clone_active_profile_worker(self) -> dict:
        meta = read_json_object(self._meta_path)
        entries = self._validated_entries(meta)
        active_id, active_name = self._active_profile_entry(meta)
        if not active_id:
            raise ValueError("当前没有可复制的 Claude 档案")
        if active_name == DEFAULT_PROFILE_NAME:
            raise ValueError("当前已经是 ConfigPilot 档案")

        source_path = self._config_library_dir / f"{active_id}.json"
        source_profile = read_json_object(source_path)
        if source_profile.get("inferenceProvider") != "gateway":
            raise ValueError("当前激活档案不是 Gateway 配置，无法复制")
        validate_endpoint(str(source_profile.get("inferenceGatewayBaseUrl", "")))

        configpilot_id, _ = self._active_profile(meta)
        if configpilot_id:
            raise ValueError("ConfigPilot 档案已存在，请直接编辑，不会覆盖现有档案")
        configpilot_id = str(uuid.uuid4())
        if any(entry.get("id") == configpilot_id for entry in entries):
            raise ValueError("新建 ConfigPilot 档案 ID 与现有档案冲突，已拒绝覆盖")
        entries.append({"id": configpilot_id, "name": DEFAULT_PROFILE_NAME})
        meta["entries"] = entries

        target_path = self._config_library_dir / f"{configpilot_id}.json"
        atomic_write_json(target_path, source_profile)
        meta["appliedId"] = configpilot_id
        atomic_write_json(self._meta_path, meta)
        return self._read_snapshot()

    @Slot(str)
    def installProduct(self, product):
        self._installer.install(product)

    @Slot()
    def cancelInstall(self):
        self._installer.cancel()

    def _complete_change(self, snapshot: dict, title: str, message: str) -> None:
        self._apply_snapshot(snapshot)
        self.notify.emit(1, title, message)

    def _change_failed(
        self,
        exc: Exception,
        *,
        invalid_title: str,
        failure_title: str,
    ) -> None:
        if isinstance(exc, ValueError):
            self.notify.emit(2, invalid_title, str(exc))
        else:
            LOGGER.exception(
                failure_title,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            self.notify.emit(3, failure_title, str(exc))
            self.reload()

    def _set_developer_mode_worker(self, enabled: bool) -> dict:
        for path in self._developer_settings_paths:
            settings = read_json_object(path)
            settings["allowDevTools"] = enabled
            atomic_write_json(path, settings)
        return self._read_snapshot()

    @Slot(bool)
    def setDeveloperModeEnabled(self, enabled):
        enabled = bool(enabled)
        state = "启用" if enabled else "关闭"
        self._tasks.submit(
            lambda: self._set_developer_mode_worker(enabled),
            lambda snapshot: self._complete_change(
                snapshot,
                f"Developer Mode 已{state}",
                "请完全退出并重新打开 Claude Desktop。",
            ),
            lambda exc: self._change_failed(
                exc,
                invalid_title="无法切换 Developer Mode",
                failure_title="切换 Developer Mode 失败",
            ),
        )

    def _set_third_party_worker(self, enabled: bool) -> dict:
        if enabled:
            self._saved_gateway_profile()
            meta = read_json_object(self._meta_path)
            profile_id, _ = self._active_profile(meta)
            if not profile_id:
                raise ValueError("尚未保存 ConfigPilot Gateway 配置，请先填写并应用")
            meta["appliedId"] = profile_id
            atomic_write_json(self._meta_path, meta)
        desktop_config = read_json_object(self._desktop_config_path)
        desktop_config["deploymentMode"] = "3p" if enabled else "1p"
        atomic_write_json(self._desktop_config_path, desktop_config)
        return self._read_snapshot()

    @Slot(bool)
    def setThirdPartyEnabled(self, enabled):
        enabled = bool(enabled)
        state = "启用" if enabled else "关闭"
        self._tasks.submit(
            lambda: self._set_third_party_worker(enabled),
            lambda snapshot: self._complete_change(
                snapshot,
                f"Gateway 已{state}",
                "已保留配置档案；请完全退出并重新打开 Claude Desktop。",
            ),
            lambda exc: self._change_failed(
                exc,
                invalid_title="无法启用 Gateway",
                failure_title="切换 Gateway 失败",
            ),
        )

    @Slot()
    def cloneActiveProfileToConfigPilot(self):
        self._tasks.submit(
            self._clone_active_profile_worker,
            lambda snapshot: self._complete_change(
                snapshot,
                "已创建 ConfigPilot 档案",
                "当前档案已复制为 ConfigPilot；后续修改不会影响来源档案。",
            ),
            lambda exc: self._change_failed(
                exc,
                invalid_title="无法创建 ConfigPilot 档案",
                failure_title="创建 ConfigPilot 档案失败",
            ),
        )

    def _apply_config_worker(self, cfg: dict, current_models_text: str) -> dict:
        meta, profile, profile_path = self._prepare_profile(
            cfg,
            current_models_text,
        )
        desktop_config = read_json_object(self._desktop_config_path)
        desktop_config["deploymentMode"] = "3p"

        developer_settings: list[tuple[Path, dict]] = []
        for path in self._developer_settings_paths:
            settings = read_json_object(path)
            settings["allowDevTools"] = True
            developer_settings.append((path, settings))

        atomic_write_json(profile_path, profile)
        atomic_write_json(self._meta_path, meta)
        for path, settings in developer_settings:
            atomic_write_json(path, settings)
        # 最后切换 deploymentMode，避免配置库未写完时进入 3p 模式。
        atomic_write_json(self._desktop_config_path, desktop_config)
        return self._read_snapshot()

    @Slot("QVariantMap")
    def applyConfig(self, cfg):
        config = dict(cfg)
        current_models_text = self._models_text
        self._tasks.submit(
            lambda: self._apply_config_worker(config, current_models_text),
            lambda snapshot: self._complete_change(
                snapshot,
                "Claude Desktop 已配置",
                "开发者模式与第三方 Gateway 已写入；请完全退出并重新打开 Claude Desktop。",
            ),
            lambda exc: self._change_failed(
                exc,
                invalid_title="参数无效",
                failure_title="应用失败",
            ),
        )

    def _open_config_directory_worker(self) -> bool:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        return open_external_target(self._data_dir)

    def _open_config_directory_completed(self, opened: object) -> None:
        if not bool(opened):
            self.notify.emit(3, "打开失败", "系统未能打开配置目录")

    @Slot()
    def openConfigDirectory(self):
        self._tasks.submit(
            self._open_config_directory_worker,
            self._open_config_directory_completed,
            lambda exc: self._change_failed(
                exc,
                invalid_title="无法打开配置目录",
                failure_title="打开失败",
            ),
        )
