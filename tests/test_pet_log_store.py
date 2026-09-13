# coding: utf-8
"""今日日志本地累计缓存(backend/log_store.py)的纯逻辑测试。

真实站点验证结论(2026-09-13):/api/log/token 恰好返回 1000 条,id 是每次请求
重排的相对序号(1..1000),request_id 才是稳定唯一键。测试围绕这两点设计:
滑动窗口去重累计、缺口(下限)判定、跨天/换令牌重置、落盘回读。
"""

import json
from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from backend import log_store
from backend.log_store import DailyLogStore, read_store, write_store
from backend.quota_math import local_midnight_timestamp

NOW = datetime(2026, 9, 13, 22, 0, 0)
MIDNIGHT = int(local_midnight_timestamp(NOW))
LATEST = int(NOW.timestamp())


def row(index, ts=None, quota=100, rtype=2):
    """一条消费日志;id 故意等于 index(接口窗口里的相对序号,不可作键)。"""
    return {
        "id": index % 1000 + 1,
        "request_id": f"req-{index}",
        "created_at": LATEST - index if ts is None else ts,
        "type": rtype,
        "quota": quota,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "model_name": "gpt-test",
    }


def window(start, count, step=60):
    """模拟一次接口返回:count 条、时间戳从 LATEST-start 起每条早 step 秒。

    quota 用全局 index 派生,保证同一 request_id 在任何一轮窗口里字段一致。
    """
    return [row(start + i, ts=LATEST - (start + i) * step, quota=100 + start + i)
            for i in range(count)]


class MergeTests(unittest.TestCase):
    def test_same_window_twice_adds_nothing(self):
        store = DailyLogStore()
        rows = window(0, 50)
        self.assertEqual(store.merge(rows, "site|tok", now=NOW), 50)
        self.assertEqual(store.merge(rows, "site|tok", now=NOW), 0)
        self.assertEqual(len(store), 50)
        self.assertTrue(store.complete)

    def test_id_is_not_used_as_key(self):
        """同一 request_id 在两次返回里 id 不同(相对序号重排),也只计一条。"""
        store = DailyLogStore()
        a = row(7, ts=LATEST - 100)
        b = dict(a, id=999)
        store.merge([a], "s|t", now=NOW)
        store.merge([b], "s|t", now=NOW)
        self.assertEqual(len(store), 1)

    def test_sliding_window_accumulates_beyond_page_limit(self):
        """连续轮询:窗口滑动掉的老条目已在本地,总量突破 1000 条窗口上限。"""
        store = DailyLogStore()
        morning = window(0, 300, step=60)   # 窗口不满 → 无缺口嫌疑
        store.merge(morning, "s|t", now=NOW)
        self.assertTrue(store.complete)
        # 第二轮窗口满 1000 条:与本地重叠(窗口最老一条早于本地最新一条)→ 仍完整
        later = window(50, 1000, step=60)
        store.merge(later, "s|t", now=NOW)
        self.assertTrue(store.complete)
        self.assertEqual(len(store), 1050)  # req-0..req-1049 的并集
        total = sum(int(e["quota"]) for e in store.entries)
        self.assertEqual(total, sum(100 + i for i in range(1050)))

    def test_fresh_start_with_saturated_window_is_lower_bound(self):
        """应用启动时窗口已被今天的日志占满:更早的今天记录没拿到 → 下限。"""
        store = DailyLogStore()
        store.merge(window(0, 1000, step=30), "s|t", now=NOW)
        self.assertEqual(len(store), 1000)
        self.assertFalse(store.complete)

    def test_unsaturated_window_from_empty_store_is_complete(self):
        store = DailyLogStore()
        store.merge(window(0, 999, step=30), "s|t", now=NOW)
        self.assertTrue(store.complete)

    def test_restart_gap_detected(self):
        """离线期间新增超过窗口:回来后窗口最老一条比本地最新一条还新 → 有洞。"""
        stale = DailyLogStore()
        stale.merge([row(5000, ts=MIDNIGHT + 60)], "s|t", now=NOW)  # 只有 00:01 一条
        gap_rows = window(0, 1000, step=30)  # 窗口最老一条 ≈ 13:41,晚于本地最新 00:01
        stale.merge(gap_rows, "s|t", now=NOW)
        self.assertFalse(stale.complete)
        self.assertEqual(len(stale), 1001)

    def test_non_consume_and_dirty_rows_skipped(self):
        store = DailyLogStore()
        rows = [
            row(1),
            row(2, rtype=1),            # 非消费
            {"created_at": "bad", "type": 2},
            {"type": 2},                 # 无 created_at
            row(3, ts=MIDNIGHT - 1),     # 昨天
            "not-a-dict",
            row(4),
        ]
        store.merge(rows, "s|t", now=NOW)
        self.assertEqual(len(store), 2)

    def test_day_rollover_resets(self):
        store = DailyLogStore()
        store.merge(window(0, 100), "s|t", now=NOW)
        tomorrow = datetime(2026, 9, 14, 0, 30, 0)
        tomorrow_ts = int(tomorrow.timestamp())
        rows = [row(1000 + i, ts=tomorrow_ts - i) for i in range(5)]
        added = store.merge(rows, "s|t", now=tomorrow)
        self.assertEqual(added, 5)
        self.assertEqual(len(store), 5)
        self.assertTrue(store.complete)

    def test_identity_change_resets(self):
        store = DailyLogStore()
        store.merge(window(0, 10), "siteA|tokA", now=NOW)
        store.merge(window(0, 3), "siteB|tokB", now=NOW)
        self.assertEqual(len(store), 3)


class PersistenceTests(unittest.TestCase):
    def test_roundtrip_restores_same_day_cache(self):
        store = DailyLogStore()
        store.merge(window(0, 1000, step=30), "s|t", now=NOW)  # 饱和 → complete False
        payload = store.to_payload("s|t")
        clone = DailyLogStore()
        self.assertTrue(clone.load_payload(json.loads(json.dumps(payload)), "s|t", now=NOW))
        self.assertEqual(len(clone), 1000)
        self.assertFalse(clone.complete)

    def test_stale_day_or_identity_rejected(self):
        store = DailyLogStore()
        store.merge(window(0, 5), "s|t", now=NOW)
        payload = store.to_payload("s|t")
        other_day = DailyLogStore()
        self.assertFalse(other_day.load_payload(payload, "s|t", now=datetime(2026, 9, 14)))
        other_id = DailyLogStore()
        self.assertFalse(other_id.load_payload(payload, "s|other", now=NOW))

    def test_write_and_read_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pet_logs.json"
            payload = {"version": 1, "day": "2026-09-13", "entries": []}
            write_store(path, payload)
            self.assertEqual(read_store(path), payload)
            self.assertIsNone(read_store(Path(tmp) / "missing.json"))
            path.write_text("{broken", encoding="utf-8")
            self.assertIsNone(read_store(path))

    def test_dirty_and_revision(self):
        store = DailyLogStore()
        self.assertFalse(store.dirty)
        store.merge(window(0, 5), "s|t", now=NOW)
        self.assertTrue(store.dirty)
        rev = store.revision
        store.mark_saved(rev)
        self.assertFalse(store.dirty)
        # 落盘期间又来新数据:旧修订号不得清 dirty
        store.merge(window(5, 3), "s|t", now=NOW)
        self.assertTrue(store.dirty)
        store.mark_saved(rev)
        self.assertTrue(store.dirty)
        store.mark_saved(store.revision)
        self.assertFalse(store.dirty)


class CapTests(unittest.TestCase):
    def test_max_entries_prunes_oldest_and_marks_lower_bound(self):
        original = log_store.MAX_ENTRIES
        log_store.MAX_ENTRIES = 10
        try:
            store = DailyLogStore()
            store.merge(window(0, 25, step=10), "s|t", now=NOW)
            self.assertEqual(len(store), 10)
            self.assertFalse(store.complete)
            newest = store.entries[0]["created_at"]
            self.assertEqual(newest, LATEST)
        finally:
            log_store.MAX_ENTRIES = original


if __name__ == "__main__":
    unittest.main()
