# coding: utf-8
"""加载模型专属的思考等级和上下文预设。"""

from __future__ import annotations

import json
import re
from pathlib import Path


# Max 和 Ultra 只对 Codex 目录明确支持的模型开放。
SPECIAL_REASONING_EFFORTS = frozenset({"max", "ultra"})


class ModelProfiles:
    def __init__(self, default_options, profiles, stable_context_preset, labels):
        self._default_options = default_options
        self._profiles = profiles
        self._stable_context_preset = stable_context_preset
        self._labels = labels
        self._reasoning_overrides = {}

    @classmethod
    def empty(cls):
        """返回异步加载完成前可安全查询的空模型配置。"""
        return cls([], [], {}, {})

    @classmethod
    def from_file(cls, path):
        source = Path(path)
        with source.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        default_options = cls._normalize_options(
            data.get("defaultReasoningOptions"), "defaultReasoningOptions"
        )
        profiles = [
            cls._normalize_profile(item, index)
            for index, item in enumerate(data.get("profiles", []))
        ]
        stable_context_preset = cls._normalize_context(
            data.get("stableContextPreset", {}), "stableContextPreset"
        )
        labels = {
            str(value).strip(): str(text).strip()
            for value, text in data.get("reasoningLabels", {}).items()
            if str(value).strip() and str(text).strip()
        }
        return cls(default_options, profiles, stable_context_preset, labels)

    @staticmethod
    def _normalize_options(raw_options, field_name):
        if not isinstance(raw_options, list) or not raw_options:
            raise ValueError(f"{field_name} 必须是非空数组")
        options = []
        for item in raw_options:
            if not isinstance(item, dict):
                raise ValueError(f"{field_name} 的每一项必须是对象")
            value = str(item.get("value", "")).strip()
            text = str(item.get("text", value)).strip()
            options.append({"value": value, "text": text})
        return options

    @classmethod
    def _normalize_profile(cls, raw_profile, index):
        if not isinstance(raw_profile, dict):
            raise ValueError(f"profiles[{index}] 必须是对象")
        profile_id = str(raw_profile.get("id", "")).strip()
        pattern_text = str(raw_profile.get("modelPattern", "")).strip()
        if not profile_id or not pattern_text:
            raise ValueError(f"profiles[{index}] 缺少 id 或 modelPattern")
        try:
            pattern = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"{profile_id} 的 modelPattern 无效: {exc}") from exc
        reasoning_options = cls._normalize_options(
            raw_profile.get("reasoningOptions"),
            f"{profile_id}.reasoningOptions",
        )
        catalog_efforts = cls._normalize_catalog_special_efforts(
            profile_id,
            raw_profile.get("catalogSpecialReasoningEfforts"),
            reasoning_options,
        )
        return {
            "id": profile_id,
            "pattern": pattern,
            "reasoningOptions": reasoning_options,
            "catalogSpecialReasoningEfforts": catalog_efforts,
        }

    @staticmethod
    def _normalize_catalog_special_efforts(profile_id, raw_efforts, options):
        """解析远端目录可启用的特殊档位；默认沿用静态档位。"""
        if raw_efforts is None:
            return frozenset(
                option["value"].strip().lower()
                for option in options
                if option["value"].strip().lower() in SPECIAL_REASONING_EFFORTS
            )
        if not isinstance(raw_efforts, list):
            raise ValueError(
                f"{profile_id}.catalogSpecialReasoningEfforts 必须是数组"
            )
        catalog_efforts = {str(effort).strip().lower() for effort in raw_efforts}
        invalid_efforts = catalog_efforts - SPECIAL_REASONING_EFFORTS
        if invalid_efforts:
            raise ValueError(
                f"{profile_id}.catalogSpecialReasoningEfforts 包含无效值: "
                + ", ".join(sorted(invalid_efforts))
            )
        return frozenset(catalog_efforts)

    @staticmethod
    def _normalize_context(raw_context, field_name):
        if not isinstance(raw_context, dict):
            raise ValueError(f"{field_name} 必须是对象")
        result = {"menuText": str(raw_context.get("menuText", "")).strip()}
        if not result["menuText"]:
            raise ValueError(f"{field_name} 缺少 menuText")
        numeric_fields = (
            "contextWindow",
            "autoCompactLimit",
            "toolOutputLimit",
            "maxContextWindow",
            "maxAutoCompactLimit",
        )
        for field in numeric_fields:
            if field not in raw_context:
                continue
            value = int(raw_context[field])
            if value <= 0:
                raise ValueError(f"{field_name}.{field} 必须大于 0")
            result[field] = value
        return result

    def profile_for(self, model):
        model_name = str(model or "").strip()
        return next(
            (profile for profile in self._profiles if profile["pattern"].search(model_name)),
            None,
        )

    def reasoning_options(self, model):
        override = self._reasoning_overrides.get(str(model or "").strip().lower())
        if override:
            return [dict(option) for option in override]
        profile = self.profile_for(model)
        source = profile["reasoningOptions"] if profile else self._default_options
        return [dict(option) for option in source]

    def update_reasoning_from_models(self, models):
        updated = 0
        for item in models or []:
            if not isinstance(item, dict):
                continue
            model = str(item.get("slug") or item.get("id") or "").strip().lower()
            levels = item.get("supported_reasoning_levels")
            if not model or not isinstance(levels, list):
                continue
            options = []
            seen = set()
            for level in levels:
                effort = str(
                    level.get("effort", "") if isinstance(level, dict) else level
                ).strip().lower()
                if (
                    not effort
                    or (
                        effort in SPECIAL_REASONING_EFFORTS
                        and not self._catalog_allows_special_effort(model, effort)
                    )
                    or effort in seen
                ):
                    continue
                seen.add(effort)
                options.append({"value": effort, "text": self._labels.get(effort, effort)})
            if options:
                self._reasoning_overrides[model] = options
                updated += 1
        return updated

    def _catalog_allows_special_effort(self, model, effort):
        """仅接纳模型静态档位声明过的特殊思考等级。"""
        if effort not in SPECIAL_REASONING_EFFORTS:
            return False
        profile = self.profile_for(model)
        return bool(
            profile
            and effort in profile["catalogSpecialReasoningEfforts"]
        )

    def highest_reasoning_effort(self, model):
        """返回当前模型可用的最高非空思考档位。"""
        options = self.reasoning_options(model)
        return next(
            (option["value"] for option in reversed(options) if option["value"]),
            "",
        )

    def supports_reasoning_effort(self, model, effort):
        override = self._reasoning_overrides.get(str(model or "").strip().lower())
        if override:
            return any(option["value"] == effort for option in override)
        profile = self.profile_for(model)
        if not profile or not effort:
            return True
        return any(
            option["value"] == effort for option in profile["reasoningOptions"]
        )

    def context_preset(self, model):
        return dict(self._stable_context_preset) if self.profile_for(model) else {}

    def stable_context_preset(self):
        return dict(self._stable_context_preset)

    def clamp_context_window(self, model, value):
        return self._clamp_context_value(model, value, "maxContextWindow")

    def clamp_auto_compact_limit(self, model, value):
        return self._clamp_context_value(model, value, "maxAutoCompactLimit")

    def _clamp_context_value(self, model, value, maximum_field):
        if value is None:
            return None
        preset = self.context_preset(model)
        maximum = preset.get(maximum_field)
        return min(value, maximum) if maximum else value
