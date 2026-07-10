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
import re
import shutil

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from PySide6.QtCore import QObject, Signal, Slot, Property

from backend.model_profiles import ModelProfiles

LOGGER = logging.getLogger(__name__)

DEFAULT_WIRE_API = "responses"
DEFAULT_MODEL = "gpt-5.5"
LEGACY_MANAGED_CONTEXT_CATALOG = "gpt-5.5-1m.json"
_KEEP = object()


def _codex_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".codex")


def _app_dir() -> str:
    """程序所在目录(打包后 = exe 同级, 开发时 = 本文件上级)。providers.json 放这里。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CodexConfig(QObject):
    changed = Signal()                      # 配置读取/写入后刷新 UI
    providersChanged = Signal()             # 预置中转列表变化
    modelsChanged = Signal()                # 获取到的模型列表变化
    notify = Signal(int, str, str)          # (level 0~3, 标题, 内容) -> QML 弹 InfoBar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._home = _codex_home()
        self._config_path = os.path.join(self._home, "config.toml")
        self._auth_path = os.path.join(self._home, "auth.json")
        self._providers_path = os.path.join(_app_dir(), "providers.json")
        self._model_profiles_path = os.path.join(_app_dir(), "model_profiles.json")
        self._model_profiles = ModelProfiles.from_file(self._model_profiles_path)
        self._provider = ""
        self._base_url = ""
        self._wire_api = ""
        self._model = ""
        self._has_key = False
        self._requires_auth = False
        self._reasoning_effort = ""
        self._disable_storage = False
        self._model_context_window = ""
        self._model_auto_compact_token_limit = ""
        self._tool_output_token_limit = ""
        self._model_catalog_json = ""
        self._available_models = []
        self._presets = []
        self._load_presets()
        self.reload()

    #__PRESETS__
    # ---------- 预置中转列表 ----------
    def _load_presets(self):
        """读 providers.json。结构: [{"name","baseUrl","provider","wireApi","model"}]"""
        self._presets = []
        if os.path.isfile(self._providers_path):
            try:
                with open(self._providers_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("presets", data) if isinstance(data, dict) else data
                for it in items:
                    if not isinstance(it, dict) or not it.get("baseUrl"):
                        continue
                    self._presets.append({
                        "name": str(it.get("name", it.get("baseUrl", ""))),
                        "baseUrl": str(it.get("baseUrl", "")),
                        "provider": str(it.get("provider", "relay")),
                        "wireApi": str(it.get("wireApi", DEFAULT_WIRE_API)),
                        "model": str(it.get("model", DEFAULT_MODEL)),
                    })
            except Exception as e:
                self.notify.emit(2, "预置列表读取失败", f"providers.json: {e}")

    @Property("QVariantList", notify=providersChanged)
    def presets(self):
        return self._presets

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

    @Property(bool, notify=changed)
    def configExists(self):
        return os.path.isfile(self._config_path)

    #__SLOTS__
    # ---------- 读 ----------
    @Slot()
    def reload(self):
        """用 tomllib 解析 config.toml 拿当前生效值;auth.json 判断是否有 key。"""
        self._provider = self._base_url = self._wire_api = self._model = ""
        self._has_key = False
        self._requires_auth = False
        self._reasoning_effort = ""
        self._disable_storage = False
        self._model_context_window = ""
        self._model_auto_compact_token_limit = ""
        self._tool_output_token_limit = ""
        self._model_catalog_json = ""
        if tomllib and os.path.isfile(self._config_path):
            try:
                with open(self._config_path, "rb") as f:
                    data = tomllib.load(f)
                self._provider = str(data.get("model_provider", ""))
                self._model = str(data.get("model", ""))
                self._reasoning_effort = str(data.get("model_reasoning_effort", ""))
                self._disable_storage = bool(data.get("disable_response_storage", False))
                self._model_context_window = self._number_to_text(data.get("model_context_window"))
                self._model_auto_compact_token_limit = self._number_to_text(data.get("model_auto_compact_token_limit"))
                self._tool_output_token_limit = self._number_to_text(data.get("tool_output_token_limit"))
                self._model_catalog_json = str(data.get("model_catalog_json", ""))
                prov = data.get("model_providers", {}).get(self._provider, {})
                self._base_url = str(prov.get("base_url", ""))
                self._wire_api = str(prov.get("wire_api", ""))
                self._requires_auth = bool(prov.get("requires_openai_auth", False))
            except Exception as e:
                self.notify.emit(3, "读取失败", f"config.toml 解析出错: {e}")
        if os.path.isfile(self._auth_path):
            try:
                with open(self._auth_path, "r", encoding="utf-8") as f:
                    auth = json.load(f)
                self._has_key = bool(auth.get("OPENAI_API_KEY"))
            except Exception as exc:
                self._has_key = False
                self.notify.emit(2, "认证读取失败", f"auth.json: {exc}")
        self.changed.emit()

    @Slot()
    def reloadPresets(self):
        self._load_presets()
        self.providersChanged.emit()

    # ---------- 写 config.toml(正则定点, 保留其它内容) ----------
    @staticmethod
    def _set_top_scalar(text, key, value, is_str=True):
        """设置/删除顶层标量字段。value 为 None 时删除该字段。"""
        if value is None:
            return re.sub(rf'(?m)^\s*{re.escape(key)}\s*=.*\n?', '', text, count=1)
        rhs = f'"{value}"' if is_str else ("true" if value else "false")
        if re.search(rf'(?m)^\s*{re.escape(key)}\s*=', text):
            return re.sub(rf'(?m)^(\s*{re.escape(key)}\s*=\s*).*$',
                          rf'\g<1>{rhs}', text, count=1)
        return f'{key} = {rhs}\n' + text

    @staticmethod
    def _set_top_integer(text, key, value):
        if value is None:
            return re.sub(rf'(?m)^\s*{re.escape(key)}\s*=.*\n?', '', text, count=1)
        rhs = str(int(value))
        if re.search(rf'(?m)^\s*{re.escape(key)}\s*=', text):
            return re.sub(rf'(?m)^(\s*{re.escape(key)}\s*=\s*).*$',
                          rf'\g<1>{rhs}', text, count=1)
        return f'{key} = {rhs}\n' + text

    @staticmethod
    def _set_top_toml_string(text, key, value):
        if value is None:
            return re.sub(rf'(?m)^\s*{re.escape(key)}\s*=.*\n?', '', text, count=1)
        rhs = json.dumps(str(value), ensure_ascii=False)
        if re.search(rf'(?m)^\s*{re.escape(key)}\s*=', text):
            return re.sub(rf'(?m)^(\s*{re.escape(key)}\s*=\s*).*$',
                          lambda m: m.group(1) + rhs, text, count=1)
        return f'{key} = {rhs}\n' + text

    @staticmethod
    def _get_top_toml_string(text, key):
        m = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*(.+?)\s*(?:#.*)?$', text)
        if not m:
            return ""
        raw = m.group(1).strip()
        if tomllib:
            try:
                return str(tomllib.loads(f"value = {raw}\n").get("value", ""))
            except Exception as exc:
                LOGGER.debug("无法按 TOML 解析 %s，回退为裸字符串: %s", key, exc)
        return raw.strip("\"'")

    def _managed_model_catalog_path(self):
        return os.path.join(self._home, "model-catalogs", LEGACY_MANAGED_CONTEXT_CATALOG)

    def _set_managed_model_catalog_json(self, text, value):
        if value:
            return self._set_top_toml_string(text, "model_catalog_json", value)

        existing = self._get_top_toml_string(text, "model_catalog_json")
        if not existing:
            return text
        try:
            same = os.path.normcase(os.path.abspath(existing)) == os.path.normcase(
                os.path.abspath(self._managed_model_catalog_path())
            )
        except Exception as exc:
            LOGGER.warning("比较旧模型目录路径失败: %s", exc)
            same = False
        return self._set_top_toml_string(text, "model_catalog_json", None) if same else text

    @staticmethod
    def _number_to_text(value):
        if value is None:
            return ""
        try:
            return str(int(value))
        except Exception as exc:
            LOGGER.debug("数值转文本失败，保留原值 %r: %s", value, exc)
            return str(value)

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

    @Slot(result="QVariantList")
    def contextPresetOptions(self):
        return self._model_profiles.context_preset_options()

    @Slot(str, str, result="QVariantMap")
    def contextPresetSelection(self, profile_id, current_model):
        return self._model_profiles.context_preset_selection(profile_id, current_model)

    @staticmethod
    def _set_block_scalar(block, key, value, is_str=True):
        """设置/删除 provider 块内标量字段。value 为 None 时删除。"""
        if value is None:
            return re.sub(rf'(?m)^\s*{re.escape(key)}\s*=.*\n?', '', block, count=1)
        rhs = f'"{value}"' if is_str else ("true" if value else "false")
        if re.search(rf'(?m)^\s*{re.escape(key)}\s*=', block):
            return re.sub(rf'(?m)^(\s*{re.escape(key)}\s*=\s*).*$',
                          rf'\g<1>{rhs}', block, count=1)
        return block.rstrip() + f'\n{key} = {rhs}\n'

    def _write_provider_block(self, text, provider, base_url, wire_api, model,
                              requires_auth=None, reasoning_effort=None,
                              disable_storage=None, context_window=_KEEP,
                              auto_compact_limit=_KEEP, tool_output_limit=_KEEP,
                              model_catalog_json=_KEEP):
        provider = provider or "relay"
        # 1. 顶层 model_provider
        if re.search(r'(?m)^\s*model_provider\s*=', text):
            text = re.sub(r'(?m)^(\s*model_provider\s*=\s*")[^"]*(")',
                          rf'\g<1>{provider}\g<2>', text, count=1)
        else:
            text = f'model_provider = "{provider}"\n' + text
        # 2. 顶层 model
        if model:
            text = self._set_top_scalar(text, "model", model)
        # 2b. 顶层高级标量(None 表示不动)
        if reasoning_effort is not None:
            text = self._set_top_scalar(text, "model_reasoning_effort",
                                        reasoning_effort or None)
        if disable_storage is not None:
            text = self._set_top_scalar(text, "disable_response_storage",
                                        disable_storage, is_str=False)
        if context_window is not _KEEP:
            text = self._set_top_integer(text, "model_context_window", context_window)
        if auto_compact_limit is not _KEEP:
            text = self._set_top_integer(text, "model_auto_compact_token_limit", auto_compact_limit)
        if tool_output_limit is not _KEEP:
            text = self._set_top_integer(text, "tool_output_token_limit", tool_output_limit)
        if model_catalog_json is not _KEEP:
            text = self._set_managed_model_catalog_json(text, model_catalog_json)
        # 3. [model_providers.<provider>] 块
        esc = re.escape(provider)
        block_re = re.compile(rf'(?ms)^\s*\[model_providers\.{esc}\]\s*.*?(?=^\s*\[|\Z)')
        m = block_re.search(text)
        if m:
            block = m.group(0)
            block = self._set_block_scalar(block, "base_url", base_url)
            if wire_api:
                block = self._set_block_scalar(block, "wire_api", wire_api)
            if requires_auth is not None:
                block = self._set_block_scalar(block, "requires_openai_auth",
                                               requires_auth, is_str=False)
            text = text[:m.start()] + block + text[m.end():]
        else:
            block = (f'\n\n[model_providers.{provider}]\n'
                     f'name = "{provider}"\n'
                     f'base_url = "{base_url}"\n')
            if wire_api:
                block += f'wire_api = "{wire_api}"\n'
            if requires_auth is not None:
                block += f'requires_openai_auth = {"true" if requires_auth else "false"}\n'
            text = text.rstrip() + block
        return text

    @Slot("QVariantMap")
    def applyConfig(self, cfg):
        """把指定的连接配置写入 config.toml(通用, 不写死任何中转)。
        cfg 字段: baseUrl(必填), provider, wireApi, model,
                 requiresAuth(bool), reasoningEffort(str), disableStorage(bool)
        """
        base_url = str(cfg.get("baseUrl", "")).strip()
        if not base_url:
            self.notify.emit(2, "未应用", "base_url 不能为空")
            return
        provider = (str(cfg.get("provider", "")) or "relay").strip()
        wire_api = str(cfg.get("wireApi", "")).strip()
        model = str(cfg.get("model", "")).strip()
        # 高级项: 缺省键 -> None(不写); 显式给值才写
        req = cfg.get("requiresAuth", None)
        eff = cfg.get("reasoningEffort", None)
        dis = cfg.get("disableStorage", None)
        req = None if req is None else bool(req)
        eff = None if eff is None else str(eff).strip()
        dis = None if dis is None else bool(dis)
        if eff and not self._model_profiles.supports_reasoning_effort(model, eff):
            self.notify.emit(2, "参数无效", f"{model} 不支持思考等级 {eff}")
            return
        try:
            context_window = (_KEEP if "modelContextWindow" not in cfg
                              else self._optional_positive_int(
                                  cfg.get("modelContextWindow"), "model_context_window"))
            auto_compact_limit = (_KEEP if "modelAutoCompactTokenLimit" not in cfg
                                  else self._optional_positive_int(
                                      cfg.get("modelAutoCompactTokenLimit"),
                                      "model_auto_compact_token_limit"))
            tool_output_limit = (_KEEP if "toolOutputTokenLimit" not in cfg
                                 else self._optional_positive_int(
                                     cfg.get("toolOutputTokenLimit"),
                                     "tool_output_token_limit"))
        except ValueError as e:
            self.notify.emit(2, "参数无效", str(e))
            return
        try:
            model_catalog_json = _KEEP
            if context_window is not _KEEP:
                context_preset = self._model_profiles.context_preset(model)
                if context_preset:
                    context_window = self._model_profiles.clamp_context_window(
                        model, context_window
                    )
                    if auto_compact_limit is not _KEEP:
                        auto_compact_limit = (
                            self._model_profiles.clamp_auto_compact_limit(
                                model, auto_compact_limit
                            )
                        )
                    model_catalog_json = None
                elif context_window is None:
                    model_catalog_json = None

            text = ""
            if os.path.isfile(self._config_path):
                shutil.copy2(self._config_path, self._config_path + ".bak")
                with open(self._config_path, "r", encoding="utf-8") as f:
                    text = f.read()
            else:
                os.makedirs(self._home, exist_ok=True)
            new_text = self._write_provider_block(
                text, provider, base_url, wire_api, model,
                requires_auth=req, reasoning_effort=eff, disable_storage=dis,
                context_window=context_window,
                auto_compact_limit=auto_compact_limit,
                tool_output_limit=tool_output_limit,
                model_catalog_json=model_catalog_json)
            with open(self._config_path, "w", encoding="utf-8", newline="") as f:
                f.write(new_text)
            self.reload()
            self.notify.emit(1, "已应用", f"已切到 {base_url},重启 Codex 生效")
        except Exception as e:
            self.notify.emit(3, "应用失败", str(e))

    @Slot()
    def resetDefault(self):
        """重置为默认: 用 providers.json 第一个预置覆盖当前配置。"""
        if not self._presets:
            self.notify.emit(2, "无默认", "providers.json 没有预置项可作默认")
            return
        p = self._presets[0]
        model = p.get("model", DEFAULT_MODEL)
        self.applyConfig({
            "baseUrl": p.get("baseUrl", ""),
            "provider": p.get("provider", "relay"),
            "wireApi": p.get("wireApi", DEFAULT_WIRE_API),
            "model": model,
            "reasoningEffort": self._model_profiles.highest_reasoning_effort(model),
        })

    # ---------- 写 auth.json 的 key ----------
    @Slot(str)
    def setKey(self, key: str):
        key = (key or "").strip()
        if not key:
            self.notify.emit(2, "未写入", "key 为空,已跳过")
            return
        try:
            auth = {
                "OPENAI_API_KEY": key,
                "auth_mode": "apikey",
            }
            os.makedirs(self._home, exist_ok=True)
            if os.path.isfile(self._auth_path):
                os.replace(self._auth_path, self._auth_path + ".bak")
            with open(self._auth_path, "w", encoding="utf-8") as f:
                json.dump(auth, f, ensure_ascii=False, indent=2)
            self.reload()
            self.notify.emit(1, "已写入", "API key 已保存到 auth.json")
        except Exception as e:
            self.notify.emit(3, "写入失败", str(e))

    # ---------- 获取模型列表(后台线程,不阻塞 UI) ----------
    @Slot(str, str)
    def fetchModels(self, base_url, key_override):
        """请求 {base_url}/models 拉取模型列表。网络在后台线程跑,完成后信号回主线程。
        key 优先用传入的 key_override(输入框现填的), 否则读 auth.json。
        """
        base_url = (base_url or "").strip().rstrip("/")
        if not base_url:
            self.notify.emit(2, "无法获取", "请先填写 base_url")
            return
        key = (key_override or "").strip()
        if not key and os.path.isfile(self._auth_path):
            try:
                with open(self._auth_path, "r", encoding="utf-8") as f:
                    key = json.load(f).get("OPENAI_API_KEY", "")
            except Exception as exc:
                key = ""
                self.notify.emit(2, "认证读取失败", f"auth.json: {exc}")
        import threading
        threading.Thread(target=self._fetch_models_worker,
                         args=(base_url, key), daemon=True).start()

    def _fetch_models_worker(self, base_url, key):
        """后台线程: 同步请求 /models。结果只经信号(自动排队回主线程)回传。"""
        import urllib.request
        import urllib.error
        url = base_url + "/models"
        try:
            headers = {"Accept": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data", payload) if isinstance(payload, dict) else payload
            ids = []
            for it in (data or []):
                mid = it.get("id") if isinstance(it, dict) else str(it)
                if mid:
                    ids.append(str(mid))
            if not ids:
                self.notify.emit(2, "无模型", "接口返回空列表")
                return
            self._available_models = ids
            self.modelsChanged.emit()
            preview = ", ".join(ids[:8]) + (f" 等 {len(ids)} 个" if len(ids) > 8 else "")
            self.notify.emit(1, f"获取到 {len(ids)} 个模型", preview)
        except urllib.error.HTTPError as e:
            self.notify.emit(3, "获取失败", f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            self.notify.emit(3, "获取失败", str(e))
