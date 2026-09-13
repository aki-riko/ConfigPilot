# coding: utf-8
"""今日消费日志的本地累计缓存(纯逻辑,不依赖 Qt,可独立测试)。

背景:new-api 的 /api/log/token 只回该令牌**最近 1000 条**日志且无分页;真实站点
验证(2026-09-13, api.relyx.cc)确认响应里的 id 是每次请求重排的相对序号(1..1000),
不能作去重键;request_id 才是跨请求稳定的唯一键(1000/1000 行都有且互不重复)。

桌宠每轮把窗口按 request_id 增量并入本地缓存并落盘(重启不丢),「今日已用」
因此能覆盖全天调用。若应用离线期间今天新增超过 1000 条,缺口无法找回,
complete 置 False,UI 给金额/次数加 "≥" 前缀,诚实标注这是下限。
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any

from backend.quota_math import LOG_TYPE_CONSUME, local_midnight_timestamp


LOGGER = logging.getLogger(__name__)

# 接口单页上限:返回条数达到它且最老一条仍属今天,说明更早的今天日志可能已被挤出。
WINDOW_LIMIT = 1000
# 本地缓存硬上限,防极端刷量撑爆内存/磁盘;触顶丢弃最老并置 complete=False。
MAX_ENTRIES = 50_000

# 明细列表与统计只需要这几个字段,落盘前裁剪,单条约 120B。
_KEPT_FIELDS = (
    "request_id",
    "created_at",
    "type",
    "quota",
    "prompt_tokens",
    "completion_tokens",
    "model_name",
)


def _valid_timestamp(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def entry_key(entry: dict[str, Any]) -> tuple:
    """去重键:request_id 优先;缺失时退化为字段指纹(同秒同价的两条会并成一条)。"""
    rid = entry.get("request_id")
    if isinstance(rid, str) and rid:
        return ("r", rid)
    return (
        "s",
        entry.get("created_at"),
        entry.get("quota"),
        entry.get("prompt_tokens"),
        entry.get("completion_tokens"),
        entry.get("model_name"),
    )


def slim_entry(entry: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in _KEPT_FIELDS:
        out[field] = entry.get(field)
    return out


class DailyLogStore:
    """按本地时区"今天"累积的消费日志集合;跨天或令牌身份变化即重置。"""

    def __init__(self) -> None:
        self._day = ""
        self._identity = ""
        self._by_key: dict[tuple, dict[str, Any]] = {}
        self._newest: int | None = None
        self._complete = True
        self._dirty = False
        self._revision = 0

    # ------------------------------------------------------------- 只读视图

    @property
    def entries(self) -> list[dict[str, Any]]:
        return sorted(self._by_key.values(), key=lambda e: e.get("created_at") or 0, reverse=True)

    @property
    def complete(self) -> bool:
        return self._complete

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def revision(self) -> int:
        """每次内容变化 +1;落盘成功只回清"快照之后没有新变化"的 dirty 标记。"""
        return self._revision

    def __len__(self) -> int:
        return len(self._by_key)

    def mark_saved(self, revision: int) -> None:
        if revision >= self._revision:
            self._dirty = False

    # ------------------------------------------------------------- 合并

    def merge(self, rows: list[Any] | None, identity: str = "",
              now: datetime | None = None) -> int:
        """并入一轮接口窗口,返回新增条数。rows 为 /api/log/token 的 data 列表。"""
        current = now or datetime.now()
        day = current.strftime("%Y-%m-%d")
        if day != self._day or (identity and identity != self._identity):
            self._day = day
            self._identity = identity or self._identity
            self._by_key.clear()
            self._newest = None
            self._complete = True
            self._dirty = True
            self._revision += 1
        midnight = local_midnight_timestamp(current)

        stamps = [
            ts for ts in (_valid_timestamp(r.get("created_at")) for r in rows or [] if isinstance(r, dict))
            if ts is not None
        ]
        window_oldest = min(stamps) if stamps else None
        prev_newest = self._newest
        was_complete = self._complete
        added = 0
        for row in rows or []:
            if not isinstance(row, dict) or row.get("type") != LOG_TYPE_CONSUME:
                continue
            ts = _valid_timestamp(row.get("created_at"))
            if ts is None or ts < midnight:
                continue
            slimmed = slim_entry(row)
            slimmed["created_at"] = ts
            key = entry_key(slimmed)
            if key in self._by_key:
                continue
            self._by_key[key] = slimmed
            if self._newest is None or ts > self._newest:
                self._newest = ts
            added += 1

        # 缺口判定:窗口被今天的日志占满时,只有"窗口最老一条"与本地已有记录连续
        # (不晚于本地最新一条)才能证明中间没漏;今天零点之后才开始有记录则视为有洞。
        if (
            window_oldest is not None
            and len(rows or []) >= WINDOW_LIMIT
            and window_oldest >= midnight
            and (prev_newest is None and window_oldest > midnight
                 or prev_newest is not None and window_oldest > prev_newest)
        ):
            self._complete = False

        if len(self._by_key) > MAX_ENTRIES:
            keep = sorted(self._by_key.items(),
                          key=lambda kv: kv[1].get("created_at") or 0, reverse=True)[:MAX_ENTRIES]
            self._by_key = dict(keep)
            self._newest = max(int(e.get("created_at") or 0) for e in self._by_key.values())
            self._complete = False

        if added or self._complete != was_complete or len(self._by_key) > MAX_ENTRIES:
            self._dirty = True
            self._revision += 1
        return added

    # ------------------------------------------------------------- 持久化

    def to_payload(self, identity: str = "") -> dict[str, Any]:
        return {
            "version": 1,
            "day": self._day,
            "identity": identity or self._identity,
            "complete": self._complete,
            "entries": self.entries,
        }

    def load_payload(self, payload: Any, identity: str = "",
                     now: datetime | None = None) -> bool:
        """装载磁盘缓存;跨天/换令牌/结构异常一律拒绝并返回 False(从空集开始)。"""
        current = now or datetime.now()
        day = current.strftime("%Y-%m-%d")
        if not isinstance(payload, dict) or payload.get("version") != 1:
            return False
        if str(payload.get("day") or "") != day:
            return False
        if identity and str(payload.get("identity") or "") != identity:
            return False
        rows = payload.get("entries")
        if not isinstance(rows, list):
            return False
        midnight = local_midnight_timestamp(current)
        by_key: dict[tuple, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("type") != LOG_TYPE_CONSUME:
                continue
            ts = _valid_timestamp(row.get("created_at"))
            if ts is None or ts < midnight:
                continue
            slimmed = slim_entry(row)
            slimmed["created_at"] = ts
            by_key[entry_key(slimmed)] = slimmed
        self._day = day
        self._identity = identity or str(payload.get("identity") or "")
        self._by_key = by_key
        self._newest = (max(int(e["created_at"]) for e in by_key.values()) if by_key else None)
        self._complete = bool(payload.get("complete", True))
        self._dirty = False
        self._revision += 1
        return True


def read_store(path: str | Path) -> Any:
    """读缓存文件;不存在/损坏返回 None,由调用方决定回退。"""
    file_path = Path(path)
    if not file_path.is_file():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        LOGGER.warning("桌宠日志缓存读取失败,按空缓存处理(%s): %s", file_path, exc)
        return None


def write_store(path: str | Path, payload: dict[str, Any]) -> None:
    """原子写(tmp + os.replace),供后台线程调用。"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    os.replace(tmp_path, file_path)
