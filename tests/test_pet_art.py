# coding: utf-8
"""桌宠形象令牌解析(backend/pet_art.py)的单元测试。

覆盖三件事:随程序发布的内置立绘能被真实解析、令牌形态向后兼容
(老配置里的空串与绝对路径都要继续工作)、id 不能变成路径穿越。
"""

import json
from pathlib import Path
import tempfile
import unittest

import backend.pet_art as pet_art


def _make_resources(root: Path, presets: list[dict], default: str = "") -> Path:
    directory = root / "resources" / "pet"
    directory.mkdir(parents=True, exist_ok=True)
    for item in presets:
        target = directory / item["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\x89PNG\r\n\x1a\n")
        for relative in (item.get("frames") or {}).values():
            frame = directory / relative
            frame.parent.mkdir(parents=True, exist_ok=True)
            frame.write_bytes(b"\x89PNG\r\n\x1a\n")
    payload = {"presets": presets}
    if default:
        payload["default"] = default
    (directory / "presets.json").write_text(json.dumps(payload), encoding="utf-8")
    return root / "resources"


class ShippedPresetsTests(unittest.TestCase):
    """仓库里真实发布的立绘资源(打包时由 --include-data-dir=resources 带上)。"""

    RESOURCES = Path(__file__).resolve().parents[1] / "resources"

    def test_default_token_points_at_an_existing_art(self):
        token = pet_art.default_preset_token(str(self.RESOURCES))
        self.assertEqual(token, "preset:navigator")
        path = pet_art.resolve_pet_image("", str(self.RESOURCES))
        self.assertEqual(path, pet_art.resolve_pet_image(token, str(self.RESOURCES)))
        self.assertTrue(Path(path).is_file(), f"内置立绘缺失: {path}")

    def test_every_manifest_entry_exists(self):
        presets = pet_art.list_pet_presets(str(self.RESOURCES))
        self.assertTrue(presets)
        for preset in presets:
            self.assertTrue(preset.exists, f"清单里的立绘文件缺失: {preset.id}")
            self.assertNotEqual(preset.label, preset.id, "清单缺少中文 label")

    def test_vector_option_resolves_to_no_image(self):
        self.assertEqual(pet_art.resolve_pet_image("vector", str(self.RESOURCES)), "")
        self.assertEqual(pet_art.preset_id_of("vector"), "")


class TokenKindTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(pet_art.pet_image_kind(""), "default")
        self.assertEqual(pet_art.pet_image_kind("   "), "default")
        self.assertEqual(pet_art.pet_image_kind("VECTOR"), "vector")
        self.assertEqual(pet_art.pet_image_kind("preset:barista"), "preset")
        self.assertEqual(pet_art.pet_image_kind(r"D:\pics\pet.png"), "custom")

    def test_custom_path_is_passed_through(self):
        self.assertEqual(
            pet_art.resolve_pet_image(r"D:\pics\pet.png", "/nope"), r"D:\pics\pet.png"
        )


class ManifestFallbackTests(unittest.TestCase):
    def test_missing_manifest_scans_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            pet_dir = Path(tmp) / "resources" / "pet"
            pet_dir.mkdir(parents=True)
            (pet_dir / "solo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            presets = pet_art.list_pet_presets(str(Path(tmp) / "resources"))
            self.assertEqual([preset.id for preset in presets], ["solo"])
            self.assertTrue(presets[0].exists)
            # 没有清单时退回代码里的 DEFAULT_PRESET_ID,该 id 不存在 → 退回自绘形体
            self.assertEqual(pet_art.resolve_pet_image("", str(Path(tmp) / "resources")), "")

    def test_broken_manifest_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = _make_resources(Path(tmp), [{"id": "a", "label": "A", "file": "a.png"}])
            (resources / "pet" / "presets.json").write_text("{ not json", encoding="utf-8")
            presets = pet_art.list_pet_presets(str(resources))
            self.assertEqual([preset.id for preset in presets], ["a"])

    def test_unknown_preset_falls_back_to_vector_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = _make_resources(
                Path(tmp), [{"id": "a", "label": "A", "file": "a.png"}], default="a")
            self.assertEqual(pet_art.resolve_pet_image("preset:zzz", str(resources)), "")
            self.assertTrue(
                Path(pet_art.resolve_pet_image("", str(resources))).is_file()
            )

    def test_preset_id_cannot_escape_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = _make_resources(Path(tmp), [{"id": "a", "label": "A", "file": "a.png"}])
            for evil in ("preset:../a", "preset:..\\..\\x", "preset:a/b", "preset:", "preset:."):
                self.assertEqual(pet_art.preset_id_of(evil), "", evil)
                self.assertEqual(pet_art.resolve_pet_image(evil, str(resources)), "")

    def test_manifest_file_name_cannot_escape_directory(self):
        """清单里的 file/frames 只能是目录内的相对 .png,不能穿越出去。"""
        with tempfile.TemporaryDirectory() as tmp:
            resources = _make_resources(
                Path(tmp), [{"id": "a", "label": "A", "file": "a.png"}])
            manifest = resources / "pet" / "presets.json"
            manifest.write_text(json.dumps({"presets": [{
                "id": "a", "label": "A", "file": "../../outside.png",
                "frames": {"idle": "../../outside.png", "wave": "/etc/passwd.png",
                           "cheer": "C:/windows/x.png", "blink": "a/../../up.png"},
            }]}), encoding="utf-8")
            preset = pet_art.list_pet_presets(str(resources))[0]
            self.assertTrue(preset.exists, "file 非法时应退回 <id>.png")
            self.assertTrue(Path(preset.path).resolve().is_relative_to(resources.resolve()))
            self.assertEqual(sorted(preset.frames), ["idle"],
                             f"非法路径的姿势帧必须被丢弃: {preset.frames}")
            self.assertTrue(
                Path(preset.frames["idle"]).resolve().is_relative_to(resources.resolve()))

    def test_frames_may_live_in_a_subdirectory(self):
        """立绘与姿势帧按约定放 <id>/ 子目录,不能像以前那样被 basename 压平。"""
        with tempfile.TemporaryDirectory() as tmp:
            resources = _make_resources(Path(tmp), [{
                "id": "nav", "label": "导航", "file": "nav/idle.png",
                "frames": {"idle": "nav/idle.png", "wave": "nav/wave.png"},
            }], default="nav")
            preset = pet_art.list_pet_presets(str(resources))[0]
            self.assertTrue(preset.exists, f"子目录立绘没解析到: {preset.path}")
            self.assertEqual(preset.path, str(resources / "pet" / "nav" / "idle.png"))
            self.assertEqual(sorted(preset.frames), ["idle", "wave"])
            frames = pet_art.resolve_pet_frames("", str(resources))
            self.assertEqual(sorted(frames), ["idle", "wave"])
            self.assertTrue(Path(frames["wave"]).is_file())

    def test_frames_auto_discovered_without_manifest_entry(self):
        """清单不写 frames 也能动:约定 <id>/*.png,文件名即角色名。"""
        with tempfile.TemporaryDirectory() as tmp:
            resources = _make_resources(
                Path(tmp), [{"id": "nav", "label": "导航", "file": "nav.png"}])
            folder = resources / "pet" / "nav"
            folder.mkdir(parents=True, exist_ok=True)
            for role in ("idle", "blink", "wave"):
                (folder / f"{role}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (folder / "notes.txt").write_text("x", encoding="utf-8")
            preset = pet_art.list_pet_presets(str(resources))[0]
            self.assertEqual(sorted(preset.frames), ["blink", "idle", "wave"])

    def test_static_preset_has_only_idle_frame(self):
        """单图预设(无姿势帧)只给 idle,界面据此退回单图动画。"""
        with tempfile.TemporaryDirectory() as tmp:
            resources = _make_resources(
                Path(tmp), [{"id": "solo", "label": "单图", "file": "solo.png"}], default="solo")
            preset = pet_art.list_pet_presets(str(resources))[0]
            self.assertEqual(sorted(preset.frames), ["idle"])
            self.assertEqual(preset.frames["idle"], preset.path)
            self.assertEqual(pet_art.resolve_pet_frames("", str(resources)),
                             {"idle": str(resources / "pet" / "solo.png")})
            # 自绘形体与用户自备图没有姿势帧
            self.assertEqual(pet_art.resolve_pet_frames("vector", str(resources)), {})
            self.assertEqual(pet_art.resolve_pet_frames(r"D:\pics\a.png", str(resources)), {})


if __name__ == "__main__":
    unittest.main()
