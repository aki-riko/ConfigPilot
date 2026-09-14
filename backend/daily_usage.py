# coding: utf-8
"""「今日已用」的远程累计口径(纯逻辑,不依赖 Qt,可独立测试)。

站点侧没有任何一条"只用 API Key 就能直接返回当天用量"的接口
(2026-09-14 在 api.relyx.cc 逐条实测):

* ``/api/log/token`` 固定只回**最近 1000 条**,且 ``p`` / ``page_size`` / ``limit`` /
  ``type`` / ``start_timestamp`` 参数**全部被忽略**(带参数与不带参数返回同一窗口);
* ``/api/usage/token/`` 与 ``/v1/dashboard/billing/usage`` 只有**终身累计值**,
  带 ``start_date`` / ``end_date`` 返回一模一样的数;
* 真正按天聚合的 ``/api/data/self``、``/api/log/self`` 要站点登录态(session),
  拿 API Key 访问是 401。

所以"当天"只能自己算。本模块改用**终身累计计数器做零点基线差值**:

    今日用量 = 当前累计值 − 今日零点的累计值

它不依赖日志窗口有没有把今天装下(超 1000 条/天不再掉数),也不依赖桌宠当天
是不是一直在线(累计值在服务端自己涨,重启后第一次采样就能接着算)。两个口径:

* ``token``   —— ``/api/usage/token/`` 的 ``total_used``,只算当前这把令牌;
* ``account`` —— ``/v1/dashboard/billing/usage`` 还原出的终身已用,算账户下所有令牌。

零点基线的来源按可信度排序,决定读数的置信度:

1. **日志窗口反推**(精确):窗口能证明覆盖到今日零点时,
   ``baseline = 累计值 − 窗口今日合计``,两个口径同源,误差为零;
2. **跨零点采样**(偏高):拿昨日最后一次采样当基线,把零点前那截也算进今天 → "≈";
3. **当天首次采样**(偏低):只能把当下当基线,零点到现在那段看不见 → "≥"。

累计值本身回退(站点重置额度、退款)时基线作废,等窗口反推重新锚定。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from backend.quota_math import local_midnight_timestamp


LOGGER = logging.getLogger(__name__)

# 两个远程累计计数器
COUNTER_TOKEN = "token"
COUNTER_ACCOUNT = "account"
COUNTERS = (COUNTER_TOKEN, COUNTER_ACCOUNT)

# 置信度:精确 / 含零点前尾段(偏高) / 有观测不到的洞(偏低)
CONFIDENCE_EXACT = "exact"
CONFIDENCE_ABOVE = "above"
CONFIDENCE_BELOW = "below"

CONFIDENCE_PREFIX = {
    CONFIDENCE_EXACT: "",
    CONFIDENCE_ABOVE: "≈",
    CONFIDENCE_BELOW: "≥",
}

PAYLOAD_VERSION = 1


def _as_int(value: Any) -> int | None:
    """把接口给的可能是 float/str 的累计值收成整数额度;收不下返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")) or number < 0:
        return None
    return int(round(number))


@dataclass(frozen=True)
class TodayReading:
    """一次"今日已用"读数。quota 是原始额度,confidence 决定 UI 前缀。"""

    quota: int
    confidence: str
    basis: str  # "counter" / "window" / "none"

    @property
    def prefix(self) -> str:
        return CONFIDENCE_PREFIX.get(self.confidence, "")

    @property
    def usable(self) -> bool:
        return self.basis != "none"


NO_READING = TodayReading(0, CONFIDENCE_EXACT, "none")


class DailyUsageTracker:
    """按本地时区"今天"维护两条终身累计计数器的零点基线。"""

    def __init__(self) -> None:
        self._day = ""
        self._identity = ""
        self._counters: dict[str, dict[str, Any]] = {}
        # 日志窗口给今天的合计(quota)与"窗口是否覆盖到零点",用来反推精确基线
        self._window_sum: int | None = None
        self._window_covered = False
        self._dirty = False
        self._revision = 0

    # ------------------------------------------------------------- 只读视图

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def day(self) -> str:
        return self._day

    def mark_saved(self, revision: int) -> None:
        if revision >= self._revision:
            self._dirty = False

    def _touch(self) -> None:
        self._dirty = True
        self._revision += 1

    def _counter(self, name: str) -> dict[str, Any]:
        return self._counters.setdefault(
            name,
            {
                "baseline": None,        # 今日零点累计值
                "confidence": CONFIDENCE_EXACT,
                "last": None,            # 最近一次采样到的累计值
                "last_ts": 0.0,
                "carried": None,         # 跨天前最后一次采样(用来当新一天基线)
                "carried_ts": 0.0,
            },
        )

    def reset(self) -> None:
        """换令牌/换站点:累计计数器身份变了,全部从空开始。"""
        self._day = ""
        self._identity = ""
        self._counters = {}
        self._window_sum = None
        self._window_covered = False
        self._dirty = False
        self._revision += 1

    # ------------------------------------------------------------- 跨天

    def roll(self, now: datetime | None = None) -> bool:
        """换到新的一天:把昨日最后一次采样当 provisional 基线,窗口合计清零。"""
        current = now or datetime.now()
        day = current.strftime("%Y-%m-%d")
        if day == self._day:
            return False
        midnight = local_midnight_timestamp(current)
        for entry in self._counters.values():
            if entry["last"] is not None:
                entry["carried"] = entry["last"]
                entry["carried_ts"] = entry["last_ts"]
            carried = entry["carried"]
            if carried is not None and entry["carried_ts"] < midnight:
                # 昨日尾段没采到样本 → 那截用量会被算进今天,偏高
                entry["baseline"] = carried
                entry["confidence"] = CONFIDENCE_ABOVE
            else:
                entry["baseline"] = None
                entry["confidence"] = CONFIDENCE_EXACT
        self._day = day
        self._window_sum = None
        self._window_covered = False
        self._touch()
        return True

    # ------------------------------------------------------------- 采样

    def observe(self, name: str, value: Any, now: datetime | None = None) -> None:
        """喂一次终身累计值(令牌 total_used 或账户 billing 还原后的额度)。"""
        if name not in COUNTERS:
            raise ValueError(f"未知的累计计数器: {name!r}")
        current = now or datetime.now()
        self.roll(current)
        sample = _as_int(value)
        if sample is None:
            return
        entry = self._counter(name)
        previous = entry["last"]
        if previous is not None and sample < previous:
            # 累计值回退 = 站点重置/退款:旧基线与旧窗口合计都不再可比,一起作废,
            # 等本轮日志窗口重新锚定(不能让陈旧窗口去锚新计数器的基线)。
            LOGGER.info("桌宠累计计数器 %s 回退(%d → %d),作废零点基线", name, previous, sample)
            entry["baseline"] = None
            entry["confidence"] = CONFIDENCE_EXACT
            if name == COUNTER_TOKEN:
                self._window_sum = None
                self._window_covered = False
            self._touch()
        if entry["baseline"] is None:
            derived = self._derive_baseline(name, sample, current)
            if derived is not None:
                entry["baseline"], entry["confidence"] = derived
                self._touch()
        entry["last"] = sample
        entry["last_ts"] = current.timestamp()
        entry["carried"] = sample
        entry["carried_ts"] = current.timestamp()

    def _derive_baseline(self, name: str, sample: int, current: datetime) -> tuple[int, str] | None:
        """在缺基线时尽量推出一个,返回 (基线, 置信度)。"""
        if name == COUNTER_TOKEN:
            if self._window_sum is None:
                return None
            # 窗口合计是"今天至少用了这么多",反推出来的基线就是零点累计值的上界:
            # 覆盖到今日零点时它是精确值,没覆盖时读数只能标 "≥" —— 但基线照样成立,
            # 之后累计值继续涨,金额跟着涨,不会钉死在窗口合计上。
            return max(0, sample - self._window_sum), (
                CONFIDENCE_EXACT if self._window_covered else CONFIDENCE_BELOW
            )
        # 账户口径:没有按天的远程接口,只能借本令牌的今日读数先锚一下。
        # 其它令牌在今天(此刻之前)的用量看不见,所以这样得到的读数只会偏低。
        token = self.reading(COUNTER_TOKEN, current)
        if token.usable:
            return max(0, sample - token.quota), CONFIDENCE_BELOW
        return None

    # ------------------------------------------------------------- 日志窗口

    def observe_window(self, today_sum: Any, covered: bool,
                       now: datetime | None = None) -> None:
        """喂一次**刚拿到的**日志窗口今日合计;``covered`` = 窗口能证明覆盖到今日零点。

        只在真的收到新窗口时调用:窗口没覆盖零点时合计只是下限,拿它反复重锚会把
        金额钉死在那一刻的合计上(又变成"数字不动")。覆盖零点时合计就是今天的精确
        用量,"累计值 − 合计"就是零点的精确累计值,直接重锚,顺带修掉跨天沿用基线
        带来的偏高。
        """
        current = now or datetime.now()
        self.roll(current)
        total = _as_int(today_sum)
        if total is None:
            return
        self._window_sum = total
        self._window_covered = bool(covered)
        entry = self._counter(COUNTER_TOKEN)
        if entry["last"] is None:
            self._touch()
            return
        if entry["baseline"] is None:
            # 还没有任何基线:窗口合计即使没覆盖零点,也够锚出一个"下限基线"让金额继续涨
            derived = self._derive_baseline(COUNTER_TOKEN, int(entry["last"]), current)
            if derived is not None:
                entry["baseline"], entry["confidence"] = derived
        elif self._window_covered:
            derived = max(0, int(entry["last"]) - total)
            entry["baseline"] = derived
            entry["confidence"] = CONFIDENCE_EXACT
        self._touch()

    # ------------------------------------------------------------- 读数

    def reading(self, name: str, now: datetime | None = None) -> TodayReading:
        """当前读数:累计差值与日志窗口合计都是"至少这么多"的下限,取大的那个。

        两者相等时优先报更可信的那个;窗口没覆盖到今日零点时,窗口合计只能标 "≥"。
        """
        if name not in COUNTERS:
            raise ValueError(f"未知的累计计数器: {name!r}")
        if self._day:
            self.roll(now or datetime.now())
        candidates: list[tuple[int, str, str]] = []
        entry = self._counters.get(name)
        if entry and entry["baseline"] is not None and entry["last"] is not None:
            candidates.append(
                (max(0, int(entry["last"]) - int(entry["baseline"])), entry["confidence"], "counter")
            )
        if name == COUNTER_TOKEN and self._window_sum is not None:
            candidates.append(
                (
                    int(self._window_sum),
                    CONFIDENCE_EXACT if self._window_covered else CONFIDENCE_BELOW,
                    "window",
                )
            )
        if not candidates:
            return NO_READING
        rank = {CONFIDENCE_EXACT: 1, CONFIDENCE_ABOVE: 0, CONFIDENCE_BELOW: -1}
        quota, confidence, basis = max(candidates, key=lambda item: (item[0], rank[item[1]]))
        return TodayReading(int(quota), confidence, basis)

    # ------------------------------------------------------------- 持久化

    def to_payload(self, identity: str = "") -> dict[str, Any]:
        counters = {}
        for name, entry in self._counters.items():
            counters[name] = {
                "baseline": entry["baseline"],
                "confidence": entry["confidence"],
                "last": entry["last"],
                "last_ts": entry["last_ts"],
                "carried": entry["carried"],
                "carried_ts": entry["carried_ts"],
            }
        return {
            "version": PAYLOAD_VERSION,
            "day": self._day,
            "identity": identity or self._identity,
            "counters": counters,
            "window_sum": self._window_sum,
            "window_covered": self._window_covered,
        }

    def load_payload(self, payload: Any, identity: str = "",
                     now: datetime | None = None) -> bool:
        """装载磁盘状态;跨天 / 换令牌 / 结构异常一律拒绝(从空状态开始)。"""
        current = now or datetime.now()
        day = current.strftime("%Y-%m-%d")
        if not isinstance(payload, dict) or payload.get("version") != PAYLOAD_VERSION:
            return False
        if str(payload.get("day") or "") != day:
            return False
        if identity and str(payload.get("identity") or "") != identity:
            return False
        counters = payload.get("counters")
        if not isinstance(counters, dict):
            return False
        loaded: dict[str, dict[str, Any]] = {}
        for name, raw in counters.items():
            if name not in COUNTERS or not isinstance(raw, dict):
                continue
            confidence = str(raw.get("confidence") or CONFIDENCE_EXACT)
            try:
                last_ts = float(raw.get("last_ts") or 0.0)
                carried_ts = float(raw.get("carried_ts") or 0.0)
            except (TypeError, ValueError):
                last_ts = carried_ts = 0.0
            loaded[name] = {
                "baseline": _as_int(raw.get("baseline")),
                "confidence": confidence if confidence in CONFIDENCE_PREFIX else CONFIDENCE_EXACT,
                "last": _as_int(raw.get("last")),
                "last_ts": last_ts,
                "carried": _as_int(raw.get("carried")),
                "carried_ts": carried_ts,
            }
        self._counters = loaded
        self._day = day
        self._identity = identity or str(payload.get("identity") or "")
        self._window_sum = _as_int(payload.get("window_sum"))
        self._window_covered = bool(payload.get("window_covered"))
        self._dirty = False
        self._revision += 1
        return True
