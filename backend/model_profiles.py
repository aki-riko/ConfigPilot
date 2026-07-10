# coding: utf-8
"""加载模型专属的思考等级和上下文预设。"""

from __future__ import annotations

import json
import re
from pathlib import Path


class ModelProfiles:
    def __init__(self, default_options, profiles):
        self._default_options = default_options
        self._profiles = profiles

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
        return cls(default_options, profiles)

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
        return {
            "id": profile_id,
            "pattern": pattern,
            "reasoningOptions": cls._normalize_options(
                raw_profile.get("reasoningOptions"),
                f"{profile_id}.reasoningOptions",
            ),
            "contextPreset": cls._normalize_context(
                raw_profile.get("contextPreset", {}), profile_id
            ),
        }

    @staticmethod
    def _normalize_context(raw_context, profile_id):
        if not isinstance(raw_context, dict):
            raise ValueError(f"{profile_id}.contextPreset 必须是对象")
        result = {"buttonText": str(raw_context.get("buttonText", "")).strip()}
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
                raise ValueError(f"{profile_id}.{field} 必须大于 0")
            result[field] = value
        return result

    def profile_for(self, model):
        model_name = str(model or "").strip()
        return next(
            (profile for profile in self._profiles if profile["pattern"].search(model_name)),
            None,
        )

    def reasoning_options(self, model):
        profile = self.profile_for(model)
        source = profile["reasoningOptions"] if profile else self._default_options
        return [dict(option) for option in source]

    def supports_reasoning_effort(self, model, effort):
        profile = self.profile_for(model)
        if not profile or not effort:
            return True
        return any(
            option["value"] == effort for option in profile["reasoningOptions"]
        )

    def context_preset(self, model):
        profile = self.profile_for(model)
        return dict(profile["contextPreset"]) if profile else {}

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
