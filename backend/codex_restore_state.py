# coding: utf-8
"""记录 ConfigPilot 实际改过的 Codex 字段，供安全恢复使用。"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


LOGGER = logging.getLogger(__name__)
STATE_FILE_NAME = ".configpilot-managed-state.json"
STATE_VERSION = 1
TOP_FIELD_TYPES = {
    "model_provider": "string",
    "model": "string",
    "model_reasoning_effort": "string",
    "disable_response_storage": "bool",
    "model_context_window": "integer",
    "model_auto_compact_token_limit": "integer",
    "tool_output_token_limit": "integer",
    "model_catalog_json": "string",
}
PROVIDER_FIELD_TYPES = {
    "name": "string",
    "base_url": "string",
    "wire_api": "string",
    "env_key": "string",
    "requires_openai_auth": "bool",
}
_PROVIDER_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_config_text(text: str) -> dict:
    if not text.strip():
        return {}
    if not tomllib:
        raise RuntimeError("当前 Python 缺少 tomllib，无法安全处理 Codex 配置")
    return tomllib.loads(text)


def managed_field_names(current_data: dict, values: dict, keep_marker) -> list[str]:
    """列出本次 apply_config 会触及的字段。"""
    provider = values["provider"] or "relay"
    fields = ["top.model_provider"]
    if values["model"]:
        fields.append("top.model")
    if values["reasoningEffort"] is not None:
        fields.append("top.model_reasoning_effort")
    if values["disableStorage"] is not None:
        fields.append("top.disable_response_storage")
    for value_key, config_key in (
        ("contextWindow", "model_context_window"),
        ("autoCompactLimit", "model_auto_compact_token_limit"),
        ("toolOutputLimit", "tool_output_token_limit"),
    ):
        if values[value_key] is not keep_marker:
            fields.append(f"top.{config_key}")
    if values["modelCatalogJson"] is not keep_marker:
        fields.append("top.model_catalog_json")

    providers = current_data.get("model_providers", {})
    if not isinstance(providers, dict) or provider not in providers:
        fields.append(f"provider.{provider}.name")
    fields.append(f"provider.{provider}.base_url")
    if values["wireApi"]:
        fields.append(f"provider.{provider}.wire_api")
    if values.get("envKey", keep_marker) is not keep_marker:
        fields.append(f"provider.{provider}.env_key")
    if values["requiresAuth"] is not None:
        fields.append(f"provider.{provider}.requires_openai_auth")
    return fields


def _value_state(container: object, key: str) -> dict:
    if not isinstance(container, dict) or key not in container:
        return {"present": False}
    return {"present": True, "value": container[key]}


def capture_fields(data: dict, field_names) -> dict:
    """从已解析 TOML 中捕获管理字段，未知字段直接拒绝。"""
    captured = {}
    providers = data.get("model_providers", {})
    for field_name in field_names:
        parts = field_name.split(".")
        if len(parts) == 2 and parts[0] == "top":
            if parts[1] not in TOP_FIELD_TYPES:
                raise ValueError(f"恢复记录包含未知配置字段 {field_name}")
            captured[field_name] = _value_state(data, parts[1])
            continue
        if len(parts) == 3 and parts[0] == "provider":
            provider, key = parts[1], parts[2]
            if not _PROVIDER_PATTERN.fullmatch(provider):
                raise ValueError(f"恢复记录包含无效 provider {provider}")
            if key not in PROVIDER_FIELD_TYPES:
                raise ValueError(f"恢复记录包含未知配置字段 {field_name}")
            block = providers.get(provider, {}) if isinstance(providers, dict) else {}
            captured[field_name] = _value_state(block, key)
            continue
        raise ValueError(f"恢复记录包含无效配置字段 {field_name}")
    return captured


def file_state(path: str) -> dict:
    """返回可比较、可恢复的文件状态；内容可能包含认证信息，不应写入日志。"""
    if not os.path.isfile(path):
        return {"present": False, "content": ""}
    with open(path, "r", encoding="utf-8") as handle:
        return {"present": True, "content": handle.read()}


class ManagedChangeJournal:
    """保存字段的原值和 ConfigPilot 最后写入值。

    恢复时只有当前值仍等于 ``lastApplied`` 才能回写 ``original``，因此用户
    在 ConfigPilot 外部做过的新修改不会被覆盖。
    """

    def __init__(self, home: str):
        self.path = os.path.join(home, STATE_FILE_NAME)

    @staticmethod
    def _empty_state() -> dict:
        return {"version": STATE_VERSION, "config": {}, "auth": None}

    @staticmethod
    def _validate_value_state(value: object, label: str) -> None:
        if not isinstance(value, dict) or not isinstance(value.get("present"), bool):
            raise ValueError(f"恢复记录 {label} 缺少有效的 present")
        if value["present"] and "value" not in value:
            raise ValueError(f"恢复记录 {label} 缺少原始值")

    @staticmethod
    def _validate_file_state(value: object, label: str) -> None:
        if not isinstance(value, dict) or not isinstance(value.get("present"), bool):
            raise ValueError(f"恢复记录 {label} 缺少有效的 present")
        if not isinstance(value.get("content"), str):
            raise ValueError(f"恢复记录 {label} 缺少有效的文件内容")

    def _read(self) -> dict:
        if not os.path.isfile(self.path):
            return self._empty_state()
        with open(self.path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
            raise ValueError("ConfigPilot 恢复记录版本无效")
        entries = state.get("config")
        if not isinstance(entries, dict):
            raise ValueError("ConfigPilot 恢复记录中的 config 无效")
        for field_name, entry in entries.items():
            if not isinstance(field_name, str) or not isinstance(entry, dict):
                raise ValueError("ConfigPilot 恢复记录包含无效字段")
            self._validate_value_state(entry.get("original"), f"{field_name}.original")
            self._validate_value_state(
                entry.get("lastApplied"), f"{field_name}.lastApplied"
            )
        auth = state.get("auth")
        if auth is not None:
            if not isinstance(auth, dict):
                raise ValueError("ConfigPilot 恢复记录中的 auth 无效")
            self._validate_file_state(auth.get("original"), "auth.original")
            self._validate_file_state(auth.get("lastApplied"), "auth.lastApplied")
        return {"version": STATE_VERSION, "config": entries, "auth": auth}

    def _delete_empty_record(self) -> None:
        try:
            os.remove(self.path)
        except FileNotFoundError:
            return
        except OSError:
            LOGGER.exception("删除已清空的 ConfigPilot 恢复记录失败")
            raise

    @staticmethod
    def _cleanup_temporary_path(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            return
        except OSError:
            LOGGER.warning("清理 ConfigPilot 恢复记录临时文件失败", exc_info=True)

    def _write_payload(self, state: dict) -> None:
        parent = os.path.dirname(self.path) or os.curdir
        os.makedirs(parent, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix=f".{os.path.basename(self.path)}.", suffix=".tmp", dir=parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                LOGGER.debug("无法调整 ConfigPilot 恢复记录权限", exc_info=True)
        except Exception:
            self._cleanup_temporary_path(temporary_path)
            raise

    def _write(self, state: dict) -> None:
        if not state["config"] and state["auth"] is None:
            self._delete_empty_record()
            return
        self._write_payload(state)

    def has_changes(self) -> bool:
        state = self._read()
        return bool(state["config"] or state["auth"] is not None)

    def read_changes(self) -> dict:
        return self._read()

    def record_config(self, current: dict, applied: dict) -> None:
        if current.keys() != applied.keys():
            raise ValueError("配置恢复记录的字段集合不一致")
        if not current:
            return
        state = self._read()
        entries = state["config"]
        for field_name, current_value in current.items():
            previous = entries.get(field_name)
            if previous and previous["lastApplied"] == current_value:
                original = previous["original"]
            else:
                original = current_value
            entries[field_name] = {
                "original": original,
                "lastApplied": applied[field_name],
            }
        self._write(state)

    def record_auth(self, current: dict, applied: dict) -> None:
        state = self._read()
        previous = state["auth"]
        original = (
            previous["original"]
            if previous and previous["lastApplied"] == current
            else current
        )
        state["auth"] = {"original": original, "lastApplied": applied}
        self._write(state)

    def clear(self) -> None:
        self._write(self._empty_state())
