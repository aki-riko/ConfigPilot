# coding: utf-8
"""Claude Desktop 配置文件的解析与原子写入工具。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse
import uuid

LOGGER = logging.getLogger(__name__)


def read_json_object(path: Path, *, default: dict | None = None) -> dict:
    if not path.is_file():
        return dict(default or {})
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 顶层必须是 JSON 对象")
    return value


def _backup_file(path: Path) -> None:
    if path.is_file():
        shutil.copy2(path, path.with_name(path.name + ".bak"))


def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup_file(path)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            LOGGER.debug("无法调整 Claude 配置文件权限: %s", path, exc_info=True)
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.warning("清理 Claude 临时配置失败: %s", temporary_path, exc_info=True)
        raise


def valid_profile_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def parse_models(text: str) -> list[str]:
    models: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        model = line.strip()
        if model and model not in seen:
            seen.add(model)
            models.append(model)
    return models


def models_to_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    names: list[str] = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        else:
            continue
        if name:
            names.append(name)
    return "\n".join(names)


def models_to_json(value: object) -> str:
    """Serialize Claude's structured model list without dropping entry metadata."""
    if not isinstance(value, list):
        value = []
    return json.dumps(value, ensure_ascii=False, indent=2)


def _normalize_model_entry(index: int, item: object) -> object:
    if isinstance(item, str):
        name = item.strip()
        if not name:
            raise ValueError(f"第 {index} 个模型 ID 不能为空")
        return name
    if not isinstance(item, dict):
        raise ValueError(f"第 {index} 个模型必须是字符串或 JSON 对象")

    name = str(item.get("name", "")).strip()
    if not name:
        raise ValueError(f"第 {index} 个模型缺少 name")
    normalized = dict(item)
    normalized["name"] = name
    for key in ("supports1m", "prefer1m", "isFamilyDefault"):
        if key in normalized and not isinstance(normalized[key], bool):
            raise ValueError(f"第 {index} 个模型的 {key} 必须是布尔值")
    if normalized.get("prefer1m") and not normalized.get("supports1m"):
        raise ValueError(f"第 {index} 个模型启用 prefer1m 前必须启用 supports1m")

    allowed_tiers = {"haiku", "sonnet", "opus", "fable", "mythos"}
    if "anthropicFamilyTier" in normalized:
        tier = str(normalized["anthropicFamilyTier"]).strip().lower()
        if tier and tier not in allowed_tiers:
            raise ValueError(f"第 {index} 个模型的 Tier alias 无效")
        if tier:
            normalized["anthropicFamilyTier"] = tier
        else:
            normalized.pop("anthropicFamilyTier", None)
    if normalized.get("isFamilyDefault") and "anthropicFamilyTier" not in normalized:
        raise ValueError(f"第 {index} 个模型设置 Default for tier 时必须有 Tier alias")
    if "labelOverride" in normalized:
        if not isinstance(normalized["labelOverride"], str):
            raise ValueError(f"第 {index} 个模型的 labelOverride 必须是字符串")
        label = normalized["labelOverride"].strip()
        if label:
            normalized["labelOverride"] = label
        else:
            normalized.pop("labelOverride", None)
    return normalized


def parse_models_json(text: str) -> list[object]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型列表不是有效 JSON：{exc.msg}") from exc
    if not isinstance(value, list):
        raise ValueError("模型列表必须是 JSON 数组")
    return [_normalize_model_entry(index, item) for index, item in enumerate(value, 1)]


def parse_headers(text: str) -> dict[str, str]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"额外 Header 不是有效 JSON：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("额外 Header 必须是 JSON 对象")
    headers: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("Header 名称不能为空")
        if not isinstance(raw_value, str):
            raise ValueError(f"Header {key} 的值必须是字符串")
        headers[key] = raw_value
    return headers


def validate_endpoint(value: str) -> str:
    """校验并原样返回 Claude Gateway 根地址。

    Claude Desktop 会自行追加 ``/v1/messages``，这里不能复用 Codex 的
    ``/v1`` 归一化逻辑，否则会产生重复的版本路径。
    """
    endpoint = value.strip()
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Gateway endpoint 必须是完整的 http(s) URL")
    return endpoint
