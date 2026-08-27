# coding: utf-8
"""Codex 配置文件的读取、定点更新与认证密钥写入。"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from backend.codex_restore_state import (
    ManagedChangeJournal,
    PROVIDER_FIELD_TYPES,
    TOP_FIELD_TYPES,
    capture_fields,
    file_state,
    managed_field_names,
    parse_config_text,
)


LOGGER = logging.getLogger(__name__)
LEGACY_MANAGED_CONTEXT_CATALOG = "gpt-5.5-1m.json"
KEEP = object()
_PROVIDER_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_CODEX_API_KEY_ENV = "OPENAI_API_KEY"


def persist_user_environment(name: str, value: str) -> None:
    """更新当前进程和 Windows 用户环境，供之后启动的 Codex 继承。"""
    if not _ENV_KEY_PATTERN.fullmatch(name or ""):
        raise ValueError("环境变量名无效")
    if not isinstance(value, str) or not value:
        raise ValueError("环境变量值不能为空")
    os.environ[name] = value
    if os.name != "nt":
        return
    import winreg

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF,
            0x001A,
            0,
            "Environment",
            0x0002,
            1000,
            None,
        )
    except Exception as exc:
        LOGGER.debug("广播用户环境变量更新失败: %s", exc)


class CodexConfigStore:
    def __init__(self, home: str):
        self.home = home
        self.config_path = os.path.join(home, "config.toml")
        self.auth_path = os.path.join(home, "auth.json")
        self._journal = ManagedChangeJournal(home)

    @staticmethod
    def _number_to_text(value) -> str:
        if value is None:
            return ""
        try:
            return str(int(value))
        except Exception as exc:
            LOGGER.debug("数值转文本失败，保留原值 %r: %s", value, exc)
            return str(value)

    def read_snapshot(self) -> dict:
        snapshot = {
            "configExists": False,
            "authError": "",
            "provider": "",
            "baseUrl": "",
            "wireApi": "",
            "model": "",
            "hasKey": False,
            "authMode": "",
            "hasChatgptAuth": False,
            "requiresAuth": False,
            "envKey": "",
            "envKeyPresent": False,
            "authSource": "none",
            "authReady": True,
            "reasoningEffort": "",
            "disableStorage": False,
            "modelContextWindow": "",
            "modelAutoCompactTokenLimit": "",
            "toolOutputTokenLimit": "",
            "modelCatalogJson": "",
            "hasRestorableChanges": False,
            "restoreError": "",
        }
        config_exists = os.path.isfile(self.config_path)
        snapshot["configExists"] = config_exists
        if tomllib and config_exists:
            with open(self.config_path, "rb") as handle:
                data = tomllib.load(handle)
            provider = str(data.get("model_provider", ""))
            provider_data = data.get("model_providers", {}).get(provider, {})
            env_key = str(provider_data.get("env_key", "")).strip()
            requires_auth = bool(provider_data.get("requires_openai_auth", False))
            snapshot.update(
                {
                    "provider": provider,
                    "baseUrl": str(provider_data.get("base_url", "")),
                    "wireApi": str(provider_data.get("wire_api", "")),
                    "model": str(data.get("model", "")),
                    "requiresAuth": requires_auth,
                    "envKey": env_key,
                    "envKeyPresent": bool(env_key and os.environ.get(env_key)),
                    "authSource": (
                        "auth_json" if requires_auth
                        else "environment" if env_key
                        else "none"
                    ),
                    "reasoningEffort": str(
                        data.get("model_reasoning_effort", "")
                    ),
                    "disableStorage": bool(
                        data.get("disable_response_storage", False)
                    ),
                    "modelContextWindow": self._number_to_text(
                        data.get("model_context_window")
                    ),
                    "modelAutoCompactTokenLimit": self._number_to_text(
                        data.get("model_auto_compact_token_limit")
                    ),
                    "toolOutputTokenLimit": self._number_to_text(
                        data.get("tool_output_token_limit")
                    ),
                    "modelCatalogJson": str(data.get("model_catalog_json", "")),
                }
            )
        try:
            auth_status = self.read_auth_status()
            snapshot.update(auth_status)
            if snapshot["authSource"] == "auth_json":
                snapshot["authReady"] = bool(
                    snapshot["hasKey"] or snapshot["hasChatgptAuth"]
                )
            elif snapshot["authSource"] == "environment":
                snapshot["authReady"] = bool(snapshot["envKeyPresent"])
        except Exception as exc:
            LOGGER.warning("读取 Codex 认证文件失败: %s", self.auth_path, exc_info=True)
            snapshot["authError"] = f"auth.json: {exc}"
            if snapshot["authSource"] == "auth_json":
                snapshot["authReady"] = False
        try:
            snapshot["hasRestorableChanges"] = self._journal.has_changes()
        except Exception as exc:
            LOGGER.warning("读取 ConfigPilot 恢复记录失败", exc_info=True)
            snapshot["restoreError"] = str(exc)
        return snapshot

    def read_api_key(self) -> str:
        if not os.path.isfile(self.auth_path):
            return ""
        with open(self.auth_path, "r", encoding="utf-8-sig") as handle:
            auth = json.load(handle)
        return str(auth.get("OPENAI_API_KEY", "")) if isinstance(auth, dict) else ""

    def read_provider_api_key(self) -> str:
        """读取当前 provider 实际使用的 key，供模型探测复用。"""
        return self.read_provider_auth()["key"]

    def read_provider_auth(self) -> dict:
        """解析当前 provider 的认证来源，避免 UI 探测和 Codex 配置分叉。"""
        source = (
            "auth_json"
            if not os.path.isfile(self.config_path) and os.path.isfile(self.auth_path)
            else "none"
        )
        env_key = ""
        if os.path.isfile(self.config_path) and tomllib:
            with open(self.config_path, "rb") as handle:
                data = tomllib.load(handle)
            provider = str(data.get("model_provider", ""))
            provider_data = data.get("model_providers", {}).get(provider, {})
            if bool(provider_data.get("requires_openai_auth", False)):
                source = "auth_json"
            else:
                env_key = str(provider_data.get("env_key", "")).strip()
                if env_key:
                    source = "environment"
        key = self.read_api_key() if source == "auth_json" else (
            os.environ.get(env_key, "") if source == "environment" else ""
        )
        return {
            "source": source,
            "envKey": env_key,
            "key": str(key or ""),
            "ready": bool(key) if source != "none" else True,
        }

    def read_auth_status(self) -> dict:
        status = {"hasKey": False, "authMode": "", "hasChatgptAuth": False}
        if not os.path.isfile(self.auth_path):
            return status
        with open(self.auth_path, "r", encoding="utf-8-sig") as handle:
            auth = json.load(handle)
        if not isinstance(auth, dict):
            raise ValueError("auth.json 根节点必须是对象")
        auth_mode = str(auth.get("auth_mode") or "")
        tokens = auth.get("tokens")
        required_tokens = ("id_token", "access_token", "refresh_token", "account_id")
        has_chatgpt_auth = (
            auth_mode == "chatgpt"
            and isinstance(tokens, dict)
            and all(isinstance(tokens.get(name), str) and tokens[name].strip()
                    for name in required_tokens)
        )
        return {
            "hasKey": bool(str(auth.get("OPENAI_API_KEY") or "").strip()),
            "authMode": auth_mode,
            "hasChatgptAuth": has_chatgpt_auth,
        }

    def read_chatgpt_refresh_token(self) -> str:
        """读取当前 ChatGPT 会话的 refresh token，不返回其它敏感凭据。"""
        if not os.path.isfile(self.auth_path):
            raise ValueError("auth.json 不存在")
        with open(self.auth_path, "r", encoding="utf-8-sig") as handle:
            auth = json.load(handle)
        if (
            not isinstance(auth, dict)
            or str(auth.get("auth_mode") or "") != "chatgpt"
        ):
            raise ValueError("当前 auth.json 不是 ChatGPT OAuth 会话")
        tokens = auth.get("tokens")
        refresh_token = tokens.get("refresh_token") if isinstance(tokens, dict) else None
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            raise ValueError("auth.json 中缺少 refresh_token")
        return refresh_token.strip()

    @staticmethod
    def _set_top_scalar(text, key, value, is_str=True):
        if value is None:
            return re.sub(
                rf"(?m)^\s*{re.escape(key)}\s*=.*\n?",
                "",
                text,
                count=1,
            )
        rhs = (
            json.dumps(str(value), ensure_ascii=False)
            if is_str
            else ("true" if value else "false")
        )
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*=", text):
            return re.sub(
                rf"(?m)^(\s*{re.escape(key)}\s*=\s*).*$",
                rf"\g<1>{rhs}",
                text,
                count=1,
            )
        return f"{key} = {rhs}\n" + text

    @staticmethod
    def _set_top_integer(text, key, value):
        if value is None:
            return re.sub(
                rf"(?m)^\s*{re.escape(key)}\s*=.*\n?",
                "",
                text,
                count=1,
            )
        rhs = str(int(value))
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*=", text):
            return re.sub(
                rf"(?m)^(\s*{re.escape(key)}\s*=\s*).*$",
                rf"\g<1>{rhs}",
                text,
                count=1,
            )
        return f"{key} = {rhs}\n" + text

    @staticmethod
    def _set_top_toml_string(text, key, value):
        if value is None:
            return re.sub(
                rf"(?m)^\s*{re.escape(key)}\s*=.*\n?",
                "",
                text,
                count=1,
            )
        rhs = json.dumps(str(value), ensure_ascii=False)
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*=", text):
            return re.sub(
                rf"(?m)^(\s*{re.escape(key)}\s*=\s*).*$",
                lambda match: match.group(1) + rhs,
                text,
                count=1,
            )
        return f"{key} = {rhs}\n" + text

    @staticmethod
    def _get_top_toml_string(text, key):
        match = re.search(
            rf"(?m)^\s*{re.escape(key)}\s*=\s*(.+?)\s*(?:#.*)?$",
            text,
        )
        if not match:
            return ""
        raw = match.group(1).strip()
        if tomllib:
            try:
                return str(tomllib.loads(f"value = {raw}\n").get("value", ""))
            except Exception as exc:
                LOGGER.debug("无法按 TOML 解析 %s，回退为裸字符串: %s", key, exc)
        return raw.strip("\"'")

    def _managed_model_catalog_path(self):
        return os.path.join(
            self.home,
            "model-catalogs",
            LEGACY_MANAGED_CONTEXT_CATALOG,
        )

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
        return (
            self._set_top_toml_string(text, "model_catalog_json", None)
            if same
            else text
        )

    @staticmethod
    def _set_block_scalar(block, key, value, is_str=True):
        if value is None:
            return re.sub(
                rf"(?m)^\s*{re.escape(key)}\s*=.*\n?",
                "",
                block,
                count=1,
            )
        rhs = (
            json.dumps(str(value), ensure_ascii=False)
            if is_str
            else ("true" if value else "false")
        )
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*=", block):
            return re.sub(
                rf"(?m)^(\s*{re.escape(key)}\s*=\s*).*$",
                rf"\g<1>{rhs}",
                block,
                count=1,
            )
        return block.rstrip() + f"\n{key} = {rhs}\n"

    @staticmethod
    def _provider_block_pattern(provider: str):
        return re.compile(
            rf"(?ms)^\s*\[model_providers\.{re.escape(provider)}\]\s*.*?"
            r"(?=^\s*\[|\Z)"
        )

    def _set_provider_field_state(
        self, text: str, provider: str, key: str, state: dict
    ) -> str:
        pattern = self._provider_block_pattern(provider)
        match = pattern.search(text)
        if not match and not state["present"]:
            return text
        if not match:
            text = text.rstrip() + f"\n\n[model_providers.{provider}]\n"
            match = pattern.search(text)
        block = match.group(0)
        value = state.get("value") if state["present"] else None
        field_type = PROVIDER_FIELD_TYPES[key]
        block = self._set_block_scalar(
            block, key, value, is_str=field_type == "string"
        )
        return text[: match.start()] + block + text[match.end() :]

    def _restore_field_state(self, text: str, field_name: str, state: dict) -> str:
        parts = field_name.split(".")
        if len(parts) == 2:
            key = parts[1]
            field_type = TOP_FIELD_TYPES[key]
            value = state.get("value") if state["present"] else None
            if field_type == "integer":
                return self._set_top_integer(text, key, value)
            return self._set_top_scalar(
                text, key, value, is_str=field_type == "string"
            )
        return self._set_provider_field_state(
            text, parts[1], parts[2], state
        )

    def _remove_empty_provider_blocks(self, text: str, providers: set[str]) -> str:
        for provider in providers:
            pattern = self._provider_block_pattern(provider)
            match = pattern.search(text)
            if not match:
                continue
            header = re.match(
                rf"(?s)^\s*\[model_providers\.{re.escape(provider)}\]\s*",
                match.group(0),
            )
            if header and not match.group(0)[header.end() :].strip():
                text = text[: match.start()] + text[match.end() :]
        return text

    def _write_provider_block(self, text, values):
        provider = values["provider"] or "relay"
        if not _PROVIDER_PATTERN.fullmatch(provider):
            raise ValueError("provider 只能包含字母、数字、下划线和连字符")
        if re.search(r"(?m)^\s*model_provider\s*=", text):
            text = re.sub(
                r'(?m)^(\s*model_provider\s*=\s*")[^"]*(")',
                rf"\g<1>{provider}\g<2>",
                text,
                count=1,
            )
        else:
            text = f'model_provider = "{provider}"\n' + text
        if values["model"]:
            text = self._set_top_scalar(text, "model", values["model"])
        optional_scalars = (
            ("reasoningEffort", "model_reasoning_effort", True),
            ("disableStorage", "disable_response_storage", False),
        )
        for value_key, config_key, is_str in optional_scalars:
            value = values[value_key]
            if value is not None:
                text = self._set_top_scalar(
                    text,
                    config_key,
                    value or None if is_str else value,
                    is_str=is_str,
                )
        for value_key, config_key in (
            ("contextWindow", "model_context_window"),
            ("autoCompactLimit", "model_auto_compact_token_limit"),
            ("toolOutputLimit", "tool_output_token_limit"),
        ):
            value = values[value_key]
            if value is not KEEP:
                text = self._set_top_integer(text, config_key, value)
        if values["modelCatalogJson"] is not KEEP:
            text = self._set_managed_model_catalog_json(
                text,
                values["modelCatalogJson"],
            )

        block_re = self._provider_block_pattern(provider)
        match = block_re.search(text)
        if match:
            block = match.group(0)
            block = self._set_block_scalar(block, "base_url", values["baseUrl"])
            if values["wireApi"]:
                block = self._set_block_scalar(block, "wire_api", values["wireApi"])
            if values.get("envKey", KEEP) is not KEEP:
                block = self._set_block_scalar(
                    block, "env_key", values.get("envKey")
                )
            if values["requiresAuth"] is not None:
                block = self._set_block_scalar(
                    block,
                    "requires_openai_auth",
                    values["requiresAuth"],
                    is_str=False,
                )
            return text[: match.start()] + block + text[match.end() :]

        block = (
            f"\n\n[model_providers.{provider}]\n"
            f'name = "{provider}"\n'
            f'base_url = "{values["baseUrl"]}"\n'
        )
        if values["wireApi"]:
            block += f'wire_api = "{values["wireApi"]}"\n'
        if values.get("envKey", KEEP) is not KEEP and values.get("envKey"):
            block += f'env_key = "{values["envKey"]}"\n'
        if values["requiresAuth"] is not None:
            enabled = "true" if values["requiresAuth"] else "false"
            block += f"requires_openai_auth = {enabled}\n"
        return text.rstrip() + block

    @staticmethod
    def _atomic_write_text(path: str, text: str) -> None:
        parent = os.path.dirname(path) or os.curdir
        os.makedirs(parent, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix=f".{os.path.basename(path)}.",
            suffix=".tmp",
            dir=parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            if os.path.isfile(path):
                shutil.copy2(path, path + ".bak")
            os.replace(temporary_path, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                LOGGER.debug("无法调整 Codex 配置文件权限: %s", path, exc_info=True)
        except Exception:
            try:
                os.remove(temporary_path)
            except FileNotFoundError:
                pass
            except OSError:
                LOGGER.warning("清理 Codex 临时配置失败: %s", temporary_path, exc_info=True)
            raise

    def apply_config(self, values: dict) -> dict:
        text = ""
        if os.path.isfile(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as handle:
                text = handle.read()
        current_data = parse_config_text(text)
        new_text = self._write_provider_block(text, values)
        new_data = parse_config_text(new_text)
        managed_fields = managed_field_names(current_data, values, KEEP)
        current_fields = capture_fields(current_data, managed_fields)
        applied_fields = capture_fields(new_data, managed_fields)
        changed_fields = [
            name for name in managed_fields
            if current_fields[name] != applied_fields[name]
        ]
        self._journal.record_config(
            {name: current_fields[name] for name in changed_fields},
            {name: applied_fields[name] for name in changed_fields},
        )
        self._atomic_write_text(self.config_path, new_text)
        return self.read_snapshot()

    def _replace_auth(self, auth: dict) -> dict:
        text = json.dumps(auth, ensure_ascii=False, indent=2) + "\n"
        current_state = file_state(self.auth_path)
        applied_state = {"present": True, "content": text}
        if current_state != applied_state:
            self._journal.record_auth(current_state, applied_state)
        self._atomic_write_text(self.auth_path, text)
        return self.read_snapshot()

    def set_key(self, key: str) -> dict:
        snapshot = self._replace_auth({"OPENAI_API_KEY": key, "auth_mode": "apikey"})
        return self._set_provider_auth_source("auth_json", snapshot)

    def repair_relay_auth(self, key: str) -> dict:
        """修复中转 provider 的认证来源，同时保留现有 OAuth 凭据。"""
        key = str(key or "").strip()
        provider_auth = self.read_provider_auth()
        if not key:
            key = provider_auth["key"] or self.read_api_key()
        if not key:
            raise ValueError("没有可用的 API key")
        text = ""
        if os.path.isfile(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as handle:
                text = handle.read()
        current_data = parse_config_text(text)
        provider = str(current_data.get("model_provider", ""))
        providers = current_data.get("model_providers", {})
        provider_data = (
            providers.get(provider) if isinstance(providers, dict) else None
        )
        if not provider or not isinstance(provider_data, dict):
            raise ValueError("请先应用中转站连接配置")
        env_key = str(provider_data.get("env_key") or DEFAULT_CODEX_API_KEY_ENV).strip()
        if not _ENV_KEY_PATTERN.fullmatch(env_key):
            raise ValueError("provider.env_key 无效")

        persist_user_environment(env_key, key)
        return self._set_provider_auth_source(
            "environment",
            env_key_override=env_key,
        )

    def set_chatgpt_auth(self, tokens: dict) -> dict:
        required = ("id_token", "access_token", "refresh_token", "account_id")
        if not isinstance(tokens, dict) or any(
            not isinstance(tokens.get(name), str) or not tokens[name].strip()
            for name in required
        ):
            raise ValueError("ChatGPT OAuth 凭据不完整")
        auth = {
            "auth_mode": "chatgpt",
            "OPENAI_API_KEY": None,
            "tokens": {name: tokens[name].strip() for name in required},
            "last_refresh": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        snapshot = self._replace_auth(auth)
        return self._set_provider_auth_source("auth_json", snapshot)

    def _set_provider_auth_source(
        self, source: str, snapshot=None, env_key_override=KEEP
    ) -> dict:
        if source not in ("auth_json", "environment", "none"):
            raise ValueError("未知认证来源")
        text = ""
        if os.path.isfile(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as handle:
                text = handle.read()
        current_data = parse_config_text(text)
        provider = str(current_data.get("model_provider", ""))
        providers = current_data.get("model_providers", {})
        if not provider or not isinstance(providers, dict) or provider not in providers:
            return snapshot or self.read_snapshot()
        env_key = (
            str(env_key_override).strip()
            if env_key_override is not KEEP
            else self._provider_env_key_for_source(source, providers[provider])
        )
        if source == "environment" and not env_key:
            raise ValueError("环境变量认证缺少 env_key")
        fields = [
            f"provider.{provider}.env_key",
            f"provider.{provider}.requires_openai_auth",
        ]
        new_text = self._set_provider_field_state(
            text,
            provider,
            "env_key",
            {"present": source == "environment", "value": env_key},
        )
        new_text = self._set_provider_field_state(
            new_text,
            provider,
            "requires_openai_auth",
            {"present": True, "value": source == "auth_json"},
        )
        new_data = parse_config_text(new_text)
        current_fields = capture_fields(current_data, fields)
        applied_fields = capture_fields(new_data, fields)
        changed_fields = [
            name for name in fields
            if current_fields[name] != applied_fields[name]
        ]
        if changed_fields:
            self._journal.record_config(
                {name: current_fields[name] for name in changed_fields},
                {name: applied_fields[name] for name in changed_fields},
            )
            self._atomic_write_text(self.config_path, new_text)
        return self.read_snapshot()

    @staticmethod
    def _provider_env_key_for_source(source: str, provider_data: dict) -> str:
        if source != "environment":
            return ""
        return str(provider_data.get("env_key", "")).strip()

    def _build_restored_config(self, text, entries, field_names):
        new_text = text
        restored_providers = set()
        for field_name in field_names:
            new_text = self._restore_field_state(
                new_text, field_name, entries[field_name]["original"]
            )
            parts = field_name.split(".")
            if parts[0] == "provider":
                restored_providers.add(parts[1])
        return self._remove_empty_provider_blocks(new_text, restored_providers)

    def _restore_config_entries(self, entries):
        if not entries:
            return 0, 0
        if not os.path.isfile(self.config_path):
            return 0, len(entries)
        with open(self.config_path, "r", encoding="utf-8") as handle:
            text = handle.read()
        current_fields = capture_fields(parse_config_text(text), entries.keys())
        restorable = [
            name for name, entry in entries.items()
            if current_fields[name] == entry["lastApplied"]
        ]
        new_text = self._build_restored_config(text, entries, restorable)
        parse_config_text(new_text)
        if new_text != text:
            self._atomic_write_text(self.config_path, new_text)
        return len(restorable), len(entries) - len(restorable)

    def _restore_auth_entry(self, entry):
        if entry is None:
            return 0, 0
        if file_state(self.auth_path) != entry["lastApplied"]:
            return 0, 1
        original = entry["original"]
        if original["present"]:
            self._atomic_write_text(self.auth_path, original["content"])
        elif os.path.isfile(self.auth_path):
            shutil.copy2(self.auth_path, self.auth_path + ".bak")
            os.remove(self.auth_path)
        return 1, 0

    def restore_managed_changes(self) -> dict:
        """恢复仍由 ConfigPilot 拥有的字段，保留工作区和外部新修改。"""
        changes = self._journal.read_changes()
        config_counts = self._restore_config_entries(changes["config"])
        auth_counts = self._restore_auth_entry(changes["auth"])
        restored = config_counts[0] + auth_counts[0]
        skipped = config_counts[1] + auth_counts[1]
        self._journal.clear()
        return {
            "snapshot": self.read_snapshot(),
            "restored": restored,
            "skipped": skipped,
        }
