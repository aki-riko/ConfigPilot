# coding: utf-8
"""
Codex 配置管理后端 —— 暴露给 QML 的 QObject。
读: tomllib 解析 config.toml 拿当前值
写: 正则定点替换(保留 notify 等其它内容,不引入写库依赖)
中转列表: 从 providers.json 读取(发货前预置, 客户可加), 不再写死任何地址。
key 写入 auth.json。
"""
import json
import logging
import os

from PySide6.QtCore import QObject, Signal, Slot, Property

from backend.async_tasks import SerialTaskRunner
from backend.codex_config_store import CodexConfigStore, KEEP
from backend.codex_model_catalog import fetch_codex_model_catalog
from backend.codex_models_api import fetch_models_result
from backend.codex_oauth import (
    CodexOAuthError,
    exchange_refresh_token,
    load_codex_oauth_settings,
    parse_chatgpt_auth_json,
)
from backend.endpoint_urls import normalize_v1_base_url
from backend.model_profiles import ModelProfiles

LOGGER = logging.getLogger(__name__)

DEFAULT_WIRE_API = "responses"
DEFAULT_MODEL = "gpt-5.5"
def _codex_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".codex")


def _app_dir() -> str:
    """程序所在目录(打包后 = exe 同级, 开发时 = 本文件上级)。providers.json 放这里。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CodexConfig(QObject):
    changed = Signal()                      # 配置读取/写入后刷新 UI
    providersChanged = Signal()             # 预置中转列表变化
    modelsChanged = Signal()                # 获取到的模型列表变化
    reasoningProfilesChanged = Signal()     # 远端模型目录中的思考等级变化
    operationBusyChanged = Signal()
    modelsLoadingChanged = Signal()
    notify = Signal(int, str, str)          # (level 0~3, 标题, 内容) -> QML 弹 InfoBar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._home = _codex_home()
        self._store = CodexConfigStore(self._home)
        self._config_path = self._store.config_path
        self._auth_path = self._store.auth_path
        self._providers_path = os.path.join(_app_dir(), "providers.json")
        self._model_profiles_path = os.path.join(_app_dir(), "model_profiles.json")
        self._model_profiles = ModelProfiles.empty()
        self._model_profiles_loaded = False
        self._profiles_revision = 0
        self._reasoning_refresh_requested = False
        self._config_exists = False
        self._provider = ""
        self._base_url = ""
        self._wire_api = ""
        self._model = ""
        self._has_key = False
        self._auth_mode = ""
        self._has_chatgpt_auth = False
        self._requires_auth = False
        self._env_key = ""
        self._env_key_present = False
        self._auth_source = "none"
        self._auth_ready = True
        self._reasoning_effort = ""
        self._disable_storage = False
        self._model_context_window = ""
        self._model_auto_compact_token_limit = ""
        self._tool_output_token_limit = ""
        self._model_catalog_json = ""
        self._has_restorable_changes = False
        self._available_models = []
        self._models_loading = False
        self._reasoning_refresh_pending = False
        self._config_tasks = SerialTaskRunner(
            self,
            thread_name="ConfigPilotCodexConfig",
            drain_on_close=True,
        )
        self._network_tasks = SerialTaskRunner(
            self,
            thread_name="ConfigPilotCodexNetwork",
        )
        self._catalog_tasks = SerialTaskRunner(
            self,
            thread_name="ConfigPilotCodexCatalog",
        )
        self._config_tasks.busyChanged.connect(self.operationBusyChanged.emit)
        self._presets = []
        self._config_tasks.submit(
            lambda: ModelProfiles.from_file(self._model_profiles_path),
            self._apply_model_profiles,
            self._model_profiles_failed,
        )
        self.reloadPresets()
        self.reload()

    #__PRESETS__
    # ---------- 预置中转列表 ----------
    def _read_presets(self):
        """读 providers.json。结构: [{"name","baseUrl","provider","wireApi","model"}]"""
        if not os.path.isfile(self._providers_path):
            return []
        with open(self._providers_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        items = data.get("presets", data) if isinstance(data, dict) else data
        presets = []
        for item in items:
            if not isinstance(item, dict) or not item.get("baseUrl"):
                continue
            presets.append(
                {
                    "name": str(item.get("name", item.get("baseUrl", ""))),
                    "baseUrl": str(item.get("baseUrl", "")),
                    "provider": str(item.get("provider", "relay")),
                    "wireApi": str(item.get("wireApi", DEFAULT_WIRE_API)),
                    "model": str(item.get("model", DEFAULT_MODEL)),
                }
            )
        return presets

    def _apply_presets(self, presets):
        self._presets = list(presets)
        self.providersChanged.emit()

    def _presets_failed(self, exc):
        self.notify.emit(2, "预置列表读取失败", f"providers.json: {exc}")

    def _apply_model_profiles(self, profiles):
        self._model_profiles = profiles
        self._finish_model_profiles_load()

    def _model_profiles_failed(self, exc):
        LOGGER.exception(
            "读取模型配置失败",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        self.notify.emit(3, "模型配置读取失败", str(exc))
        self._finish_model_profiles_load()

    def _finish_model_profiles_load(self):
        self._model_profiles_loaded = True
        self._profiles_revision += 1
        self.reasoningProfilesChanged.emit()
        if self._reasoning_refresh_requested:
            self._reasoning_refresh_requested = False
            self.refreshReasoningProfiles()

    @Property("QVariantList", notify=providersChanged)
    def presets(self):
        return self._presets

    @Property(int, notify=reasoningProfilesChanged)
    def profilesRevision(self):
        return self._profiles_revision

    @Property(str, notify=changed)
    def configPath(self):
        return self._config_path

    @Property(str, notify=changed)
    def provider(self):
        return self._provider

    @Property(str, notify=changed)
    def baseUrl(self):
        return self._base_url

    @Property(str, notify=changed)
    def wireApi(self):
        return self._wire_api

    @Property(str, notify=changed)
    def model(self):
        return self._model

    @Property(bool, notify=changed)
    def requiresAuth(self):
        return self._requires_auth

    @Property(str, notify=changed)
    def envKey(self):
        return self._env_key

    @Property(bool, notify=changed)
    def envKeyPresent(self):
        return self._env_key_present

    @Property(str, notify=changed)
    def authSource(self):
        return self._auth_source

    @Property(bool, notify=changed)
    def authReady(self):
        return self._auth_ready

    @Property(str, notify=changed)
    def reasoningEffort(self):
        return self._reasoning_effort

    @Property(bool, notify=changed)
    def disableStorage(self):
        return self._disable_storage

    @Property(str, notify=changed)
    def modelContextWindow(self):
        return self._model_context_window

    @Property(str, notify=changed)
    def modelAutoCompactTokenLimit(self):
        return self._model_auto_compact_token_limit

    @Property(str, notify=changed)
    def toolOutputTokenLimit(self):
        return self._tool_output_token_limit

    @Property(str, notify=changed)
    def modelCatalogJson(self):
        return self._model_catalog_json

    @Property("QVariantList", notify=modelsChanged)
    def availableModels(self):
        return self._available_models

    @Property(bool, notify=changed)
    def hasKey(self):
        return self._has_key

    @Property(str, notify=changed)
    def authMode(self):
        return self._auth_mode

    @Property(bool, notify=changed)
    def hasChatgptAuth(self):
        return self._has_chatgpt_auth

    @Property(bool, notify=changed)
    def configExists(self):
        return self._config_exists

    @Property(bool, notify=changed)
    def hasRestorableChanges(self):
        return self._has_restorable_changes

    @Property(bool, notify=operationBusyChanged)
    def operationBusy(self):
        return self._config_tasks.busy

    @Property(bool, notify=modelsLoadingChanged)
    def modelsLoading(self):
        return self._models_loading

    def _set_models_loading(self, value):
        value = bool(value)
        if self._models_loading == value:
            return
        self._models_loading = value
        self.modelsLoadingChanged.emit()

    #__SLOTS__
    # ---------- 读 ----------
    @Slot()
    def _apply_snapshot(self, snapshot):
        self._config_exists = bool(snapshot["configExists"])
        self._provider = str(snapshot["provider"])
        self._base_url = str(snapshot["baseUrl"])
        self._wire_api = str(snapshot["wireApi"])
        self._model = str(snapshot["model"])
        self._has_key = bool(snapshot["hasKey"])
        self._auth_mode = str(snapshot.get("authMode", ""))
        self._has_chatgpt_auth = bool(snapshot.get("hasChatgptAuth", False))
        self._requires_auth = bool(snapshot["requiresAuth"])
        self._env_key = str(snapshot.get("envKey", ""))
        self._env_key_present = bool(snapshot.get("envKeyPresent", False))
        self._auth_source = str(snapshot.get("authSource", "none"))
        self._auth_ready = bool(snapshot.get("authReady", True))
        self._reasoning_effort = str(snapshot["reasoningEffort"])
        self._disable_storage = bool(snapshot["disableStorage"])
        self._model_context_window = str(snapshot["modelContextWindow"])
        self._model_auto_compact_token_limit = str(
            snapshot["modelAutoCompactTokenLimit"]
        )
        self._tool_output_token_limit = str(snapshot["toolOutputTokenLimit"])
        self._model_catalog_json = str(snapshot["modelCatalogJson"])
        self._has_restorable_changes = bool(
            snapshot.get("hasRestorableChanges", False)
        )
        self.changed.emit()
        auth_error = str(snapshot.get("authError", ""))
        if auth_error:
            self.notify.emit(2, "认证读取失败", auth_error)
        restore_error = str(snapshot.get("restoreError", ""))
        if restore_error:
            self.notify.emit(3, "恢复记录读取失败", restore_error)

    def _config_read_failed(self, exc):
        LOGGER.exception(
            "读取 Codex 配置失败",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        self.notify.emit(3, "读取失败", str(exc))

    @Slot()
    def reload(self):
        self._config_tasks.submit(
            self._store.read_snapshot,
            self._apply_snapshot,
            self._config_read_failed,
        )

    @Slot()
    def reloadPresets(self):
        self._config_tasks.submit(
            self._read_presets,
            self._apply_presets,
            self._presets_failed,
        )

    @staticmethod
    def _optional_positive_int(value, field_name):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = int(text)
        except Exception as exc:
            raise ValueError(f"{field_name} 必须是整数") from exc
        if parsed <= 0:
            raise ValueError(f"{field_name} 必须大于 0")
        return parsed

    @Slot(str, result="QVariantList")
    def reasoningOptionsForModel(self, model):
        return self._model_profiles.reasoning_options(model)

    @Slot(str, result=str)
    def highestReasoningEffortForModel(self, model):
        return self._model_profiles.highest_reasoning_effort(model)

    @Slot(str, result="QVariantMap")
    def contextPresetForModel(self, model):
        return self._model_profiles.context_preset(model)

    @Slot(result="QVariantMap")
    def stableContextPreset(self):
        return self._model_profiles.stable_context_preset()

    @Slot()
    def refreshReasoningProfiles(self):
        if not self._model_profiles_loaded:
            self._reasoning_refresh_requested = True
            return
        if self._reasoning_refresh_pending:
            return
        self._reasoning_refresh_pending = True
        self._catalog_tasks.submit(
            fetch_codex_model_catalog,
            self._apply_reasoning_catalog,
            self._reasoning_catalog_failed,
        )

    def _apply_reasoning_catalog(self, models):
        self._reasoning_refresh_pending = False
        if self._model_profiles.update_reasoning_from_models(models):
            self.reasoningProfilesChanged.emit()

    def _reasoning_catalog_failed(self, exc):
        self._reasoning_refresh_pending = False
        LOGGER.info("无法从 Codex 远端模型目录更新思考等级: %s", exc)

    def _complete_config_change(self, snapshot, title, message):
        self._apply_snapshot(snapshot)
        self.notify.emit(1, title, message)

    def _config_write_failed(self, exc):
        LOGGER.exception(
            "写入 Codex 配置失败",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        if isinstance(exc, ValueError):
            self.notify.emit(2, "参数无效", str(exc))
        else:
            self.notify.emit(3, "写入失败", str(exc))

    @Slot("QVariantMap")
    def applyConfig(self, cfg):
        """把指定的连接配置写入 config.toml(通用, 不写死任何中转)。
        cfg 字段: baseUrl(必填), provider, wireApi, model,
                 requiresAuth(bool), reasoningEffort(str), disableStorage(bool)
        """
        raw_base_url = str(cfg.get("baseUrl", "")).strip()
        if not raw_base_url:
            self.notify.emit(2, "未应用", "base_url 不能为空")
            return
        base_url = normalize_v1_base_url(raw_base_url)
        provider = (str(cfg.get("provider", "")) or "relay").strip()
        wire_api = str(cfg.get("wireApi", "")).strip()
        model = str(cfg.get("model", "")).strip()
        # 高级项: 缺省键 -> None(不写); 显式给值才写
        auth_source = cfg.get("authSource", None)
        env_key = KEEP
        if auth_source == "auth_json":
            req = True
            env_key = None
        elif auth_source == "environment":
            req = False
            env_key = str(cfg.get("envKey", "")).strip()
            if not env_key:
                self.notify.emit(2, "参数无效", "环境变量认证必须填写 env_key")
                return
        elif auth_source == "none":
            req = False
            env_key = None
        else:
            req = cfg.get("requiresAuth", None)
            if req is True:
                env_key = None
        eff = cfg.get("reasoningEffort", None)
        dis = cfg.get("disableStorage", None)
        req = None if req is None else bool(req)
        eff = None if eff is None else str(eff).strip()
        dis = None if dis is None else bool(dis)
        if eff and not self._model_profiles.supports_reasoning_effort(model, eff):
            self.notify.emit(2, "参数无效", f"{model} 不支持思考等级 {eff}")
            return
        try:
            context_window = (KEEP if "modelContextWindow" not in cfg
                              else self._optional_positive_int(
                                  cfg.get("modelContextWindow"), "model_context_window"))
            auto_compact_limit = (KEEP if "modelAutoCompactTokenLimit" not in cfg
                                  else self._optional_positive_int(
                                      cfg.get("modelAutoCompactTokenLimit"),
                                      "model_auto_compact_token_limit"))
            tool_output_limit = (KEEP if "toolOutputTokenLimit" not in cfg
                                 else self._optional_positive_int(
                                     cfg.get("toolOutputTokenLimit"),
                                     "tool_output_token_limit"))
        except ValueError as e:
            self.notify.emit(2, "参数无效", str(e))
            return
        model_catalog_json = KEEP
        if context_window is not KEEP:
            context_preset = self._model_profiles.context_preset(model)
            if context_preset:
                model_catalog_json = None
            elif context_window is None:
                model_catalog_json = None

        values = {
            "baseUrl": base_url,
            "provider": provider,
            "wireApi": wire_api,
            "model": model,
            "requiresAuth": req,
            "envKey": env_key,
            "reasoningEffort": eff,
            "disableStorage": dis,
            "contextWindow": context_window,
            "autoCompactLimit": auto_compact_limit,
            "toolOutputLimit": tool_output_limit,
            "modelCatalogJson": model_catalog_json,
        }
        self._config_tasks.submit(
            lambda: self._store.apply_config(values),
            lambda snapshot: self._complete_config_change(
                snapshot,
                "已应用",
                f"已切到 {base_url},重启 Codex 生效",
            ),
            self._config_write_failed,
        )

    def _complete_restore(self, result):
        self._apply_snapshot(result["snapshot"])
        restored = int(result["restored"])
        skipped = int(result["skipped"])
        if restored:
            message = f"已恢复 {restored} 项 ConfigPilot 修改"
            if skipped:
                message += f"；{skipped} 项已有外部修改，未覆盖"
            message += "。请完全重启 Codex 生效"
            self.notify.emit(1, "已恢复初始设置", message)
        elif skipped:
            self.notify.emit(
                2,
                "未覆盖外部修改",
                f"{skipped} 项设置已在 ConfigPilot 外部改变，全部保留",
            )
        else:
            self.notify.emit(0, "无需恢复", "没有 ConfigPilot 修改记录")

    @Slot()
    def restoreInitialSettings(self):
        """只恢复 ConfigPilot 记录过且此后未被外部修改的设置。"""
        if not self._has_restorable_changes:
            self.notify.emit(0, "无需恢复", "没有 ConfigPilot 修改记录")
            return
        self._config_tasks.submit(
            self._store.restore_managed_changes,
            self._complete_restore,
            self._config_write_failed,
        )

    # ---------- 写 auth.json 的 key ----------
    @Slot(str)
    def setKey(self, key: str):
        key = (key or "").strip()
        if not key:
            self.notify.emit(2, "未写入", "key 为空,已跳过")
            return
        self._config_tasks.submit(
            lambda: self._store.set_key(key),
            lambda snapshot: self._complete_config_change(
                snapshot,
                "已写入",
                "API key 已保存到 auth.json",
            ),
            self._config_write_failed,
        )

    def _import_and_store_auth_json(self, raw_json: str):
        tokens = parse_chatgpt_auth_json(raw_json)
        required = ("id_token", "access_token", "refresh_token", "account_id")
        if not all(tokens.get(name) for name in required):
            settings = load_codex_oauth_settings(
                os.path.join(_app_dir(), "app_config.json")
            )
            tokens = exchange_refresh_token(tokens["refresh_token"], settings)
        return self._store.set_chatgpt_auth(tokens)

    def _auth_json_import_failed(self, exc):
        LOGGER.error(
            "Codex 认证 JSON 导入失败: %s",
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        if isinstance(exc, (CodexOAuthError, ValueError)):
            self.notify.emit(2, "导入失败", str(exc))
        else:
            self.notify.emit(3, "导入失败", "写入 Codex 认证失败，请检查日志")

    def _refresh_chatgpt_auth(self):
        refresh_token = self._store.read_chatgpt_refresh_token()
        settings = load_codex_oauth_settings(
            os.path.join(_app_dir(), "app_config.json")
        )
        tokens = exchange_refresh_token(refresh_token, settings)
        return self._store.set_chatgpt_auth(tokens)

    def _chatgpt_auth_refresh_failed(self, exc):
        LOGGER.error(
            "Codex ChatGPT 会话刷新失败: %s",
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        if isinstance(exc, (CodexOAuthError, ValueError)):
            self.notify.emit(2, "401 修复失败", str(exc))
        else:
            self.notify.emit(3, "401 修复失败", "刷新 Codex 认证失败，请检查日志")

    @Slot(str)
    def importAuthJson(self, raw_json: str):
        value = str(raw_json or "").strip()
        if not value:
            self.notify.emit(2, "未导入", "认证 JSON 不能为空")
            return
        self._config_tasks.submit(
            lambda: self._import_and_store_auth_json(value),
            lambda snapshot: self._complete_config_change(
                snapshot,
                "ChatGPT 认证导入成功",
                "OAuth 凭据已保存到 auth.json，请完全重启 Codex 生效",
            ),
            self._auth_json_import_failed,
        )

    @Slot()
    def refreshChatgptAuth(self):
        """使用现有 refresh token 获取新凭据，单独处理已过期 access token。"""
        self._config_tasks.submit(
            self._refresh_chatgpt_auth,
            lambda snapshot: self._complete_config_change(
                snapshot,
                "401 修复成功",
                "ChatGPT 会话已刷新，请完全重启 Codex 生效",
            ),
            self._chatgpt_auth_refresh_failed,
        )

    # ---------- 获取模型列表(后台线程,不阻塞 UI) ----------
    @Slot(str, str)
    def fetchModels(self, base_url, key_override):
        """请求 {base_url}/models 拉取模型列表。网络在后台线程跑,完成后信号回主线程。
        key 优先用传入的 key_override(输入框现填的), 否则读 auth.json。
        """
        base_url = normalize_v1_base_url(base_url)
        if not base_url:
            self.notify.emit(2, "无法获取", "请先填写 base_url")
            return
        if self._models_loading:
            return
        key = (key_override or "").strip()
        self._set_models_loading(True)
        if key:
            self._queue_models_fetch(base_url, key)
            return
        if not key:
            self._config_tasks.submit(
                self._store.read_provider_auth,
                lambda auth: self._queue_models_auth_fetch(base_url, auth),
                self._models_fetch_failed,
            )
            return

    def _queue_models_auth_fetch(self, base_url, auth):
        if not auth["ready"]:
            source = auth["envKey"] if auth["source"] == "environment" else "auth.json"
            self._set_models_loading(False)
            self.notify.emit(2, "无法获取", f"认证来源 {source} 未设置")
            return
        self._queue_models_fetch(base_url, auth["key"])

    def _queue_models_fetch(self, base_url, key):
        self._network_tasks.submit(
            lambda: fetch_models_result(base_url, key, fetch_codex_model_catalog),
            self._apply_models_result,
            self._models_fetch_failed,
        )

    def _apply_models_result(self, result):
        self._set_models_loading(False)
        ids = result["ids"]
        if not ids:
            self.notify.emit(2, "无模型", "接口返回空列表")
            return
        updated = self._model_profiles.update_reasoning_from_models(result["models"])
        if not updated:
            updated = self._model_profiles.update_reasoning_from_models(
                result["catalog"]
            )
        if updated:
            self.reasoningProfilesChanged.emit()
        self._available_models = list(ids)
        self.modelsChanged.emit()
        self.notify.emit(
            1,
            f"获取到 {len(ids)} 个模型",
            "思考等级已从远端同步"
            if updated
            else "接口未提供思考等级，已使用内置回退",
        )

    def _models_fetch_failed(self, exc):
        import urllib.error

        self._set_models_loading(False)
        if isinstance(exc, urllib.error.HTTPError):
            message = f"HTTP {exc.code}: {exc.reason}"
        else:
            message = str(exc)
        self.notify.emit(3, "获取失败", message)
