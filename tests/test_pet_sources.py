import unittest

from backend.pet_sources import (
    SOURCE_AUTO,
    SOURCE_CLAUDE,
    SOURCE_CODEX,
    SOURCE_MANUAL,
    PetSourceResolver,
    site_root_from_base,
)


class SiteRootTests(unittest.TestCase):
    def test_strips_v1_and_trailing_slash(self):
        cases = {
            "https://api.9li.life/v1": "https://api.9li.life",
            "https://api.9li.life/v1/": "https://api.9li.life",
            "https://api.9li.life": "https://api.9li.life",
            "https://x.example/openai/v1": "https://x.example/openai",
            "http://localhost:3000/v1": "http://localhost:3000",
            "": "",
            "not a url": "",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(site_root_from_base(source), expected)


class FakeCodexStore:
    def __init__(self, base_url, key):
        self._base_url = base_url
        self._key = key

    def read_snapshot(self):
        return {"baseUrl": self._base_url}

    def read_provider_auth(self):
        return {"key": self._key}


class ResolverTests(unittest.TestCase):
    def _resolver(self, codex=("https://c.example/v1", "sk-c"), claude=("https://d.example/v1", "sk-d")):
        store = FakeCodexStore(*codex) if codex else None
        claude_reader = (lambda: claude) if claude else None
        resolver = PetSourceResolver(store, claude_reader)
        resolver._cache = resolver._read_all_sync()  # 直接跑同步 worker,绕开线程
        return resolver

    def test_read_all_sync_populates_both(self):
        resolver = self._resolver()
        self.assertEqual(resolver._cache[SOURCE_CODEX]["site"], "https://c.example")
        self.assertEqual(resolver._cache[SOURCE_CODEX]["key"], "sk-c")
        self.assertTrue(resolver._cache[SOURCE_CODEX]["has_key"])
        self.assertEqual(resolver._cache[SOURCE_CLAUDE]["site"], "https://d.example")
        self.assertTrue(resolver._cache[SOURCE_CLAUDE]["has_key"])

    def test_resolve_explicit_source(self):
        resolver = self._resolver()
        self.assertEqual(resolver.resolve(SOURCE_CODEX), ("https://c.example", "sk-c", SOURCE_CODEX))
        self.assertEqual(resolver.resolve(SOURCE_CLAUDE), ("https://d.example", "sk-d", SOURCE_CLAUDE))

    def test_resolve_auto_prefers_codex(self):
        resolver = self._resolver()
        site, key, used = resolver.resolve(SOURCE_AUTO)
        self.assertEqual(used, SOURCE_CODEX)
        self.assertEqual(site, "https://c.example")

    def test_resolve_auto_falls_back_to_claude_when_codex_empty(self):
        resolver = self._resolver(codex=None, claude=("https://d.example/v1", "sk-d"))
        site, key, used = resolver.resolve(SOURCE_AUTO)
        self.assertEqual(used, SOURCE_CLAUDE)
        self.assertEqual(site, "https://d.example")

    def test_resolve_auto_empty_when_nothing_configured(self):
        resolver = self._resolver(codex=None, claude=None)
        site, key, used = resolver.resolve(SOURCE_AUTO)
        self.assertEqual((site, key, used), ("", "", SOURCE_AUTO))
        self.assertFalse(resolver.has_any_credential())

    def test_resolve_manual_returns_empty_for_controller_fallback(self):
        resolver = self._resolver()
        self.assertEqual(resolver.resolve(SOURCE_MANUAL), ("", "", SOURCE_MANUAL))

    def test_missing_key_marks_not_ready(self):
        resolver = self._resolver(codex=("https://c.example/v1", ""), claude=None)
        self.assertFalse(resolver._cache[SOURCE_CODEX]["has_key"])
        # auto 时 codex 无 key 且无 claude → 空
        self.assertEqual(resolver.resolve(SOURCE_AUTO)[2], SOURCE_AUTO)

    def test_sources_for_ui_shape(self):
        resolver = self._resolver()
        ui = resolver.sources_for_ui()
        ids = [entry["id"] for entry in ui]
        self.assertEqual(ids, [SOURCE_CODEX, SOURCE_CLAUDE])
        self.assertTrue(all(entry["hasKey"] for entry in ui))

    def test_candidate_sources_order_and_filter(self):
        # 两个都有 key → [codex, claude]
        self.assertEqual(self._resolver().candidate_sources(), [SOURCE_CODEX, SOURCE_CLAUDE])
        # 只有 claude 有 key → [claude]
        self.assertEqual(
            self._resolver(codex=("https://c.example/v1", ""), claude=("https://d.example/v1", "sk-d")).candidate_sources(),
            [SOURCE_CLAUDE],
        )
        # 都没有 → []
        self.assertEqual(self._resolver(codex=None, claude=None).candidate_sources(), [])


if __name__ == "__main__":
    unittest.main()
