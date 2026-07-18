# coding: utf-8
"""Codex 配置文件的读取、定点更新与认证密钥写入。"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


LOGGER = logging.getLogger(__name__)
LEGACY_MANAGED_CONTEXT_CATALOG = "gpt-5.5-1m.json"
KEEP = object()
_PROVIDER_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class CodexConfigStore:
    def __init__(self, home: str):
        self.home = home
        self.config_path = os.path.join(home, "config.toml")
        self.auth_path = os.path.join(home, "auth.json")

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
            "requiresAuth": False,
            "reasoningEffort": "",
            "disableStorage": False,
            "modelContextWindow": "",
            "modelAutoCompactTokenLimit": "",
            "toolOutputTokenLimit": "",
            "modelCatalogJson": "",
        }
        config_exists = os.path.isfile(self.config_path)
        snapshot["configExists"] = config_exists
        if tomllib and config_exists:
            with open(self.config_path, "rb") as handle:
                data = tomllib.load(handle)
            provider = str(data.get("model_provider", ""))
            provider_data = data.get("model_providers", {}).get(provider, {})
            snapshot.update(
                {
                    "provider": provider,
                    "baseUrl": str(provider_data.get("base_url", "")),
                    "wireApi": str(provider_data.get("wire_api", "")),
                    "model": str(data.get("model", "")),
                    "requiresAuth": bool(
                        provider_data.get("requires_openai_auth", False)
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
            snapshot["hasKey"] = bool(self.read_api_key())
        except Exception as exc:
            LOGGER.warning("读取 Codex 认证文件失败: %s", self.auth_path, exc_info=True)
            snapshot["authError"] = f"auth.json: {exc}"
        return snapshot

    def read_api_key(self) -> str:
        if not os.path.isfile(self.auth_path):
            return ""
        with open(self.auth_path, "r", encoding="utf-8") as handle:
            auth = json.load(handle)
        return str(auth.get("OPENAI_API_KEY", "")) if isinstance(auth, dict) else ""

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

        block_re = re.compile(
            rf"(?ms)^\s*\[model_providers\.{re.escape(provider)}\]\s*.*?"
            r"(?=^\s*\[|\Z)"
        )
        match = block_re.search(text)
        if match:
            block = match.group(0)
            block = self._set_block_scalar(block, "base_url", values["baseUrl"])
            if values["wireApi"]:
                block = self._set_block_scalar(block, "wire_api", values["wireApi"])
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
        new_text = self._write_provider_block(text, values)
        if tomllib:
            tomllib.loads(new_text)
        self._atomic_write_text(self.config_path, new_text)
        return self.read_snapshot()

    def set_key(self, key: str) -> dict:
        auth = {"OPENAI_API_KEY": key, "auth_mode": "apikey"}
        text = json.dumps(auth, ensure_ascii=False, indent=2) + "\n"
        self._atomic_write_text(self.auth_path, text)
        return self.read_snapshot()
