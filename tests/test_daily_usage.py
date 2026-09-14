# coding: utf-8
"""「今日已用」远程累计口径(daily_usage)的单元测试。

背景(2026-09-14 在 api.relyx.cc 实测):站点没有任何一条只用 API Key 就能返回
"当天"用量的接口 —— /api/log/token 固定只回最近 1000 条且忽略所有分页/时间参数,
/api/usage/token/ 与 /v1/dashboard/billing/usage 只有终身累计值。所以"当天"只能靠
零点基线差值算,这里锁死它的每一条推导规则与置信度标注。
"""

from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from backend.daily_usage import (
    CONFIDENCE_ABOVE,
    CONFIDENCE_BELOW,
    CONFIDENCE_EXACT,
    CONFIDENCE_PREFIX,
    COUNTER_ACCOUNT,
    COUNTER_TOKEN,
    DailyUsageTracker,
)


NOON = datetime(2026, 9, 14, 12, 0, 0)
NEXT_DAY = NOON + timedelta(days=1)


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return NOON.replace(hour=hour, minute=minute, second=second)


def tomorrow(hour: int, minute: int = 0) -> datetime:
    """跨到第二天:零点基线相关规则只在 day 字符串真的变了之后才生效。"""
    return NEXT_DAY.replace(hour=hour, minute=minute, second=0)


class BaselineDerivationTests(unittest.TestCase):
    def test_no_source_yet_reports_unusable(self):
        tracker = DailyUsageTracker()
        reading = tracker.reading(COUNTER_TOKEN, NOON)
        self.assertFalse(reading.usable)
        self.assertEqual(reading.prefix, "")

    def test_covered_window_anchors_exact_midnight_baseline(self):
        """窗口覆盖零点:基线 = 累计值 − 窗口合计,读数精确。"""
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, True, NOON)
        reading = tracker.reading(COUNTER_TOKEN, NOON)
        self.assertEqual((reading.quota, reading.confidence, reading.basis), (200, CONFIDENCE_EXACT, "counter"))
        # 累计值继续涨,窗口还没刷新:差值接着算,不掉回 200
        tracker.observe(COUNTER_TOKEN, 1100, at(12, 1))
        self.assertEqual(tracker.reading(COUNTER_TOKEN, at(12, 1)).quota, 300)
        self.assertEqual(tracker.reading(COUNTER_TOKEN, at(12, 1)).confidence, CONFIDENCE_EXACT)

    def test_truncated_window_only_gives_lower_bound(self):
        """满窗且最老一条仍在今日 → 更早的今天没拿到:金额标 ≥,但仍要能继续涨。"""
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, False, NOON)
        reading = tracker.reading(COUNTER_TOKEN, NOON)
        self.assertEqual((reading.quota, reading.confidence), (200, CONFIDENCE_BELOW))
        self.assertEqual(reading.prefix, "≥")
        entry = tracker._counters[COUNTER_TOKEN]  # noqa: SLF001
        self.assertEqual(entry["baseline"], 800, "窗口合计仍够锚一个下限基线")
        # 关键:基线锚住之后,后续累计照常反映出来(不能钉死在 200 上)
        tracker.observe(COUNTER_TOKEN, 1500, at(12, 5))
        later = tracker.reading(COUNTER_TOKEN, at(12, 5))
        self.assertEqual((later.quota, later.confidence), (700, CONFIDENCE_BELOW))

    def test_stale_window_does_not_freeze_the_amount(self):
        """回归:窗口不是本轮新到的时候绝不能重锚基线。

        用陈旧合计反复重锚会把金额钉死在上一次的窗口合计上 —— 那正是"数字半天不动"。
        """
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, True, NOON)
        for minute in range(1, 30):
            tracker.observe(COUNTER_TOKEN, 1000 + minute * 10, at(12, minute))
        reading = tracker.reading(COUNTER_TOKEN, at(12, 29))
        self.assertEqual(reading.quota, 490, "累计差值必须跟着累计值继续涨")
        self.assertEqual(reading.confidence, CONFIDENCE_EXACT)

    def test_counter_regression_voids_baseline(self):
        """站点重置/退款导致累计值回退:旧基线作废,不出现负数或跳变。"""
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, True, NOON)
        tracker.observe(COUNTER_TOKEN, 50, at(12, 5))
        entry = tracker._counters[COUNTER_TOKEN]  # noqa: SLF001
        self.assertIsNone(entry["baseline"])
        self.assertGreaterEqual(tracker.reading(COUNTER_TOKEN, at(12, 5)).quota, 0)

    def test_unknown_counter_rejected(self):
        tracker = DailyUsageTracker()
        with self.assertRaises(ValueError):
            tracker.observe("nonsense", 1, NOON)
        with self.assertRaises(ValueError):
            tracker.reading("nonsense", NOON)


class DayRolloverTests(unittest.TestCase):
    def test_carry_over_baseline_is_marked_as_over_estimate(self):
        """跨零点沿用昨日最后一次采样:零点前那截会被算进今天 → 标 ≈。"""
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, at(23, 59))
        tracker.observe_window(200, True, at(23, 59))
        self.assertEqual(tracker.reading(COUNTER_TOKEN, at(23, 59)).quota, 200)
        # 新的一天,还没拿到窗口
        tracker.observe(COUNTER_TOKEN, 1030, tomorrow(0, 1))
        reading = tracker.reading(COUNTER_TOKEN, tomorrow(0, 1))
        self.assertEqual((reading.quota, reading.confidence), (30, CONFIDENCE_ABOVE))
        self.assertEqual(reading.prefix, "≈")

    def test_window_after_midnight_corrects_the_carry_over(self):
        """零点后第一次拿到覆盖零点的窗口:重锚基线,偏高立刻被修正。"""
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, at(23, 59))
        tracker.observe_window(200, True, at(23, 59))
        tracker.observe(COUNTER_TOKEN, 1030, tomorrow(0, 1))       # ≈30(含昨天尾段 20)
        tracker.observe_window(5, True, tomorrow(0, 2))            # 今天其实只用了 5
        reading = tracker.reading(COUNTER_TOKEN, tomorrow(0, 2))
        self.assertEqual((reading.quota, reading.confidence), (5, CONFIDENCE_EXACT))

    def test_rollover_clears_yesterday_window(self):
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, at(23, 59))
        tracker.observe_window(200, True, at(23, 59))
        tracker.roll(tomorrow(0, 1))
        self.assertIsNone(tracker._window_sum)  # noqa: SLF001
        self.assertFalse(tracker._window_covered)  # noqa: SLF001


class AccountScopeTests(unittest.TestCase):
    """全账户口径:站点只有终身累计值,今天这段只能靠基线差值。"""

    def test_account_anchors_on_token_reading_as_lower_bound(self):
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, True, NOON)
        tracker.observe(COUNTER_ACCOUNT, 90_000, NOON)
        reading = tracker.reading(COUNTER_ACCOUNT, NOON)
        self.assertEqual(reading.quota, 200, "首次锚定只能给出与本令牌相同的下限")
        self.assertEqual(reading.confidence, CONFIDENCE_BELOW)
        # 之后账户涨得比本令牌快 → 说明别的令牌也在用,差值如实反映
        tracker.observe(COUNTER_TOKEN, 1010, at(12, 5))
        tracker.observe(COUNTER_ACCOUNT, 90_500, at(12, 5))
        reading = tracker.reading(COUNTER_ACCOUNT, at(12, 5))
        self.assertEqual(reading.quota, 700)
        self.assertEqual(reading.prefix, "≥")

    def test_account_unusable_before_any_sample(self):
        tracker = DailyUsageTracker()
        self.assertFalse(tracker.reading(COUNTER_ACCOUNT, NOON).usable)
        tracker.observe(COUNTER_ACCOUNT, 500, NOON)
        self.assertFalse(tracker.reading(COUNTER_ACCOUNT, NOON).usable,
                         "没有本令牌读数可锚时不许瞎猜账户今日")


class PersistenceTests(unittest.TestCase):
    def test_payload_round_trip_restores_baseline(self):
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, True, NOON)
        tracker.observe(COUNTER_ACCOUNT, 90_000, NOON)
        payload = tracker.to_payload("https://x|Codex")

        clone = DailyUsageTracker()
        self.assertTrue(clone.load_payload(payload, identity="https://x|Codex", now=NOON))
        reading = clone.reading(COUNTER_TOKEN, NOON)
        self.assertEqual((reading.quota, reading.confidence), (200, CONFIDENCE_EXACT))
        self.assertTrue(clone.reading(COUNTER_ACCOUNT, NOON).usable)
        # 恢复后继续累计,不从零开始
        clone.observe(COUNTER_TOKEN, 1050, at(12, 10))
        self.assertEqual(clone.reading(COUNTER_TOKEN, at(12, 10)).quota, 250)

    def test_payload_rejected_across_day_or_identity(self):
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, True, NOON)
        payload = tracker.to_payload("https://x|Codex")
        other_day = DailyUsageTracker()
        self.assertFalse(other_day.load_payload(payload, identity="https://x|Codex",
                                                now=NOON + timedelta(days=1)))
        other_id = DailyUsageTracker()
        self.assertFalse(other_id.load_payload(payload, identity="https://x|Claude", now=NOON))
        self.assertFalse(other_id.load_payload({"version": 99}, now=NOON))
        self.assertFalse(other_id.load_payload(None, now=NOON))

    def test_reset_drops_everything(self):
        tracker = DailyUsageTracker()
        tracker.observe(COUNTER_TOKEN, 1000, NOON)
        tracker.observe_window(200, True, NOON)
        tracker.reset()
        self.assertFalse(tracker.reading(COUNTER_TOKEN, NOON).usable)
        self.assertEqual(tracker.day, "")


class PrefixTests(unittest.TestCase):
    def test_prefixes_are_distinct_and_complete(self):
        self.assertEqual(CONFIDENCE_PREFIX[CONFIDENCE_EXACT], "")
        self.assertEqual(CONFIDENCE_PREFIX[CONFIDENCE_BELOW], "≥")
        self.assertEqual(CONFIDENCE_PREFIX[CONFIDENCE_ABOVE], "≈")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
