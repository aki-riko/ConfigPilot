# coding: utf-8
"""桌宠形象令牌 ↔ 立绘文件的解析。

内置立绘随程序目录走(``resources/pet/``),不依赖用户配置目录,所以打包后
换机器、换用户名都不会失效;用户配置里只保存一个短令牌。

``pet_image`` 配置值的四种形态:

===========================  ==================================================
值                           含义
===========================  ==================================================
``""``                       未配置 —— 用 ``DEFAULT_PRESET_ID`` 的内置立绘
``"preset:<id>"``            指定 ``resources/pet/`` 里的某个内置立绘
``"vector"``                 老的自绘矢量小飞宠(``PetSprite.qml`` 内置形体)
``"D:\\pics\\pet.png"``      用户自备图片的绝对路径(原行为,保持兼容)
===========================  ==================================================

立绘清单来自 ``resources/pet/presets.json``;缺这个文件时退化为扫描目录里的
``*.png``,id 取文件名,保证手工放图也能用。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import re

LOGGER = logging.getLogger(__name__)

PET_IMAGE_VECTOR = "vector"
PRESET_PREFIX = "preset:"
DEFAULT_PRESET_ID = "navigator"
PRESET_SUBDIR = "pet"
PRESET_MANIFEST = "presets.json"

# 令牌里的 id 只允许安全字符,防止 "preset:../../windows/x" 这类路径穿越。
_PRESET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class PetPreset:
    """一个内置立绘选项。"""

    id: str
    label: str
    path: str
    exists: bool

    @property
    def token(self) -> str:
        return PRESET_PREFIX + self.id

    def to_map(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "token": self.token,
            "path": self.path,
            "exists": self.exists,
        }


def pet_image_kind(token: str) -> str:
    """返回 default / vector / preset / custom,供界面判断当前选中的是哪一类。"""
    text = (token or "").strip()
    if not text:
        return "default"
    if text.lower() == PET_IMAGE_VECTOR:
        return "vector"
    if text.startswith(PRESET_PREFIX):
        return "preset"
    return "custom"


def preset_id_of(token: str) -> str:
    """从 ``preset:<id>`` 取出 id;非法返回空串。"""
    text = (token or "").strip()
    if not text.startswith(PRESET_PREFIX):
        return ""
    candidate = text[len(PRESET_PREFIX):].strip()
    return candidate if _PRESET_ID_PATTERN.match(candidate) else ""


def preset_dir_of(resources_dir: str) -> str:
    return os.path.join(resources_dir, PRESET_SUBDIR)


def list_pet_presets(resources_dir: str) -> list[PetPreset]:
    """列出可用的内置立绘(清单缺失时退化为扫描目录)。"""
    directory = preset_dir_of(resources_dir)
    _, entries = _read_manifest(resources_dir)
    if not entries:
        try:
            names = sorted(
                name for name in os.listdir(directory)
                if name.lower().endswith(".png")
            )
        except OSError:
            names = []
        entries = [(os.path.splitext(name)[0], os.path.splitext(name)[0], name)
                   for name in names]
    return [
        PetPreset(id=pid, label=label, path=os.path.join(directory, filename),
                  exists=os.path.isfile(os.path.join(directory, filename)))
        for pid, label, filename in entries
    ]


def _read_manifest(resources_dir: str) -> tuple[str, list[tuple[str, str, str]]]:
    """读 presets.json,返回 (默认 id, [(id, label, 文件名)])。"""
    manifest = os.path.join(preset_dir_of(resources_dir), PRESET_MANIFEST)
    default_id = ""
    entries: list[tuple[str, str, str]] = []
    if not os.path.isfile(manifest):
        return default_id, entries
    try:
        with open(manifest, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        LOGGER.warning("桌宠立绘清单读取失败,改为扫描目录: %s", exc)
        return default_id, entries
    if not isinstance(payload, dict):
        LOGGER.warning("桌宠立绘清单根节点不是对象,已忽略")
        return default_id, entries
    raw_default = str(payload.get("default", "")).strip()
    if _PRESET_ID_PATTERN.match(raw_default):
        default_id = raw_default
    for item in payload.get("presets", []):
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id", "")).strip()
        if not _PRESET_ID_PATTERN.match(pid):
            continue
        entries.append((pid, str(item.get("label") or pid),
                        os.path.basename(str(item.get("file") or f"{pid}.png"))))
    return default_id, entries


def default_preset_token(resources_dir: str) -> str:
    """清单里 default 指向的立绘令牌(清单缺失时退回 ``DEFAULT_PRESET_ID``)。"""
    default_id, _ = _read_manifest(resources_dir)
    return PRESET_PREFIX + (default_id or DEFAULT_PRESET_ID)


def resolve_pet_image(token: str, resources_dir: str) -> str:
    """把配置值翻译成 ``PetSprite.imagePath`` 能直接用的绝对路径。

    返回空串表示"用自绘矢量形体"。内置立绘文件缺失时同样退回矢量,
    不会出现桌宠隐身。
    """
    kind = pet_image_kind(token)
    if kind == "vector":
        return ""
    if kind == "custom":
        return (token or "").strip()
    default_id, _ = _read_manifest(resources_dir)
    wanted = (default_id or DEFAULT_PRESET_ID) if kind == "default" else preset_id_of(token)
    if not wanted:
        return ""
    for preset in list_pet_presets(resources_dir):
        if preset.id.lower() == wanted.lower():
            return preset.path if preset.exists else ""
    return ""
