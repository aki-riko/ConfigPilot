# coding: utf-8
"""桌宠凭证来源解析:复用 Codex / Claude Desktop 已配好的接口地址与 API Key。

new-api 的余额接口挂在站点根(`/api/...`),而 Codex/Claude 里存的是推理端点
(通常带 `/v1`)。这里把端点归一化回站点根,并在后台线程读取各自的 key,
GUI 线程只拿缓存结果,绝不在主线程做磁盘读取。
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import QObject, Signal

from backend.async_tasks import SerialTaskRunner


LOGGER = logging.getLogger(__name__)

SOURCE_AUTO = "auto"
SOURCE_CODEX = "codex"
SOURCE_CLAUDE = "claude"
SOURCE_MANUAL = "manual"
VALID_SOURCES = (SOURCE_AUTO, SOURCE_CODEX, SOURCE_CLAUDE, SOURCE_MANUAL)


def site_root_from_base(value: str) -> str:
    """把推理端点(可能带 /v1)归一化为 new-api 站点根。"""
    candidate = str(value or "").strip().rstrip("/")
    if not candidate:
        return ""
    parsed = urlsplit(candidate)
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    if path.lower().endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class PetSourceResolver(QObject):
    """缓存各来源的站点根 + key;来源变化或 Codex/Claude 配置变化时后台刷新。"""

    sourcesChanged = Signal()   # 可用来源列表变化(供设置窗口下拉)
    credsChanged = Signal()     # 当前来源凭证变化(供控制器刷新)

    def __init__(self, codex_store, claude_reader=None, parent: QObject | None = None):
        super().__init__(parent)
        self._codex_store = codex_store
        # claude_reader: 零参可调用,返回 (endpoint, api_key);独立入口与主程序共用同一函数。
        self._claude_reader = claude_reader
        self._tasks = SerialTaskRunner(
            self, thread_name="ConfigPilotPetSources", drain_on_close=True
        )
        # source_id -> {"site","key","label","has_key"}
        self._cache: dict[str, dict] = {}
        self._resolving = False

    # ------------------------------------------------------------------ 查询

    def sources_for_ui(self) -> list[dict]:
        order = [SOURCE_CODEX, SOURCE_CLAUDE]
        default_labels = {SOURCE_CODEX: "Codex 当前配置", SOURCE_CLAUDE: "Claude Gateway"}
        result = []
        for source_id in order:
            entry = self._cache.get(source_id) or {}
            result.append(
                {
                    "id": source_id,
                    "label": entry.get("label") or default_labels.get(source_id, source_id),
                    "site": entry.get("site", ""),
                    "hasKey": bool(entry.get("has_key")),
                }
            )
        return result

    def resolve(self, source: str) -> tuple[str, str, str]:
        """返回 (site_root, api_key, source_used)。manual 交回空由控制器处理。

        source=auto 时优先 codex(有 key),其次 claude(有 key),都没有则返回空。
        """
        if source == SOURCE_MANUAL:
            return "", "", SOURCE_MANUAL
        if source == SOURCE_AUTO:
            for candidate in (SOURCE_CODEX, SOURCE_CLAUDE):
                entry = self._cache.get(candidate)
                if entry and entry.get("has_key") and entry.get("site"):
                    return entry["site"], entry["key"], candidate
            return "", "", SOURCE_AUTO
        entry = self._cache.get(source)
        if entry and entry.get("site"):
            return entry.get("site", ""), entry.get("key", ""), source
        return "", "", source

    def has_any_credential(self) -> bool:
        for entry in self._cache.values():
            if entry.get("has_key") and entry.get("site"):
                return True
        return False

    def candidate_sources(self) -> list[str]:
        """auto 模式按此顺序尝试:codex、claude 中真正有站点+key 的来源。"""
        result = []
        for source_id in (SOURCE_CODEX, SOURCE_CLAUDE):
            entry = self._cache.get(source_id)
            if entry and entry.get("has_key") and entry.get("site"):
                result.append(source_id)
        return result

    # ------------------------------------------------------------------ 刷新

    def refresh(self) -> None:
        """后台重新读取 Codex/Claude 凭证;同一时刻只跑一轮。"""
        if self._resolving:
            return
        self._resolving = True
        try:
            self._tasks.submit(self._read_all_sync, self._apply, self._fail)
        except RuntimeError as exc:  # 队列已关闭
            self._resolving = False
            LOGGER.debug("桌宠来源刷新被跳过: %s", exc)

    def _read_all_sync(self) -> dict:
        """在工作线程执行:读 config.toml/auth.json 与 Claude profile。"""
        cache: dict[str, dict] = {}
        # Codex
        if self._codex_store is not None:
            try:
                snapshot = self._codex_store.read_snapshot()
                auth = self._codex_store.read_provider_auth()
                site = site_root_from_base(str(snapshot.get("baseUrl", "")))
                key = str(auth.get("key", "") or "")
                cache[SOURCE_CODEX] = {
                    "site": site,
                    "key": key,
                    "label": "Codex 当前配置",
                    "has_key": bool(key) and bool(site),
                }
            except Exception as exc:
                LOGGER.info("读取 Codex 凭证失败: %s", exc)
                cache[SOURCE_CODEX] = {"site": "", "key": "", "label": "Codex 当前配置", "has_key": False}
        # Claude
        if self._claude_reader is not None:
            try:
                endpoint, key = self._claude_reader()
                site = site_root_from_base(endpoint)
                cache[SOURCE_CLAUDE] = {
                    "site": site,
                    "key": key,
                    "label": "Claude Gateway",
                    "has_key": bool(key) and bool(site),
                }
            except Exception as exc:
                LOGGER.info("读取 Claude 凭证失败: %s", exc)
                cache[SOURCE_CLAUDE] = {"site": "", "key": "", "label": "Claude Gateway", "has_key": False}
        return cache

    def _apply(self, cache: dict) -> None:
        self._resolving = False
        changed = cache != self._cache
        self._cache = cache
        if changed:
            self.sourcesChanged.emit()
            self.credsChanged.emit()

    def _fail(self, exc: Exception) -> None:
        self._resolving = False
        LOGGER.info("桌宠来源刷新失败: %s", exc)
