import os
import sys
import tempfile
import unittest
from pathlib import Path

from backend.codex_config_store import CodexConfigStore, KEEP
from backend.fs_repair import ensure_directory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def managed_values(provider="relay"):
    return {
        "baseUrl": "https://gateway.example/v1",
        "provider": provider,
        "wireApi": "responses",
        "model": "gpt-5.6-sol",
        "requiresAuth": True,
        "reasoningEffort": "xhigh",
        "disableStorage": True,
        "contextWindow": 258400,
        "autoCompactLimit": 245000,
        "toolOutputLimit": 6000,
        "modelCatalogJson": KEEP,
    }


class EnsureDirectoryTests(unittest.TestCase):
    def test_creates_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, ".codex")
            self.assertIsNone(ensure_directory(target))
            self.assertTrue(os.path.isdir(target))

    def test_existing_directory_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, ".codex")
            os.mkdir(target)
            marker = os.path.join(target, "keep.txt")
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write("x")
            self.assertIsNone(ensure_directory(target))
            self.assertTrue(os.path.isfile(marker))

    def test_blocking_file_is_backed_up_then_replaced_by_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, ".codex")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write('base_url = "https://misplaced-script.example/v1"\n')
            backup = ensure_directory(target)
            self.assertIsNotNone(backup)
            self.assertTrue(os.path.isdir(target))
            self.assertTrue(os.path.isfile(backup))
            self.assertIn("misplaced-script", Path(backup).read_text(encoding="utf-8"))

    def test_repeated_blocking_files_get_distinct_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, ".codex")
            for content in ("first", "second"):
                if os.path.isdir(target):
                    os.rmdir(target)
                with open(target, "w", encoding="utf-8") as handle:
                    handle.write(content)
                ensure_directory(target)
            backups = [
                name
                for name in os.listdir(tmp)
                if name.startswith(".codex.file-")
            ]
            self.assertEqual(len(backups), 2)

    def test_dangling_symlink_is_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, ".codex")
            try:
                os.symlink(os.path.join(tmp, "nowhere-exists"), target)
            except OSError:  # Windows 无创建符号链接权限时跳过
                self.skipTest("os.symlink unavailable")
            backup = ensure_directory(target)
            self.assertTrue(os.path.isdir(target))
            self.assertIsNotNone(backup)


class CodexWriteSelfHealTests(unittest.TestCase):
    def test_apply_config_succeeds_when_codex_home_is_a_file(self):
        """客户场景复现：~/.codex 被一键脚本误建成文件后，写入应静默自愈成功。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = os.path.join(tmp, ".codex")
            with open(home, "w", encoding="utf-8") as handle:
                handle.write("model = \"gpt-5.5\"\n")
            store = CodexConfigStore(home)
            store.apply_config(managed_values())
            self.assertTrue(os.path.isdir(home))
            config_path = os.path.join(home, "config.toml")
            self.assertTrue(os.path.isfile(config_path))
            text = Path(config_path).read_text(encoding="utf-8")
            self.assertIn("https://gateway.example/v1", text)
            backups = [
                name
                for name in os.listdir(tmp)
                if name.startswith(".codex.file-")
            ]
            self.assertEqual(len(backups), 1)
            self.assertIn("gpt-5.5", Path(os.path.join(tmp, backups[0])).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
