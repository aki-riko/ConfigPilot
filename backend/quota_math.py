# coding: utf-8
"""额度换算与"今日用量"统计的纯逻辑部分(不依赖 Qt,可独立测试)。

new-api 的额度(quota)是整数计分,默认 QuotaPerUnit = 500000 对应 $1
(见 new-api common/constants.go)。金额换算与展示类型由站点设置决定,
这里按桌宠配置在本地换算。
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any


LOG_TYPE_CONSUME = 2

_CURRENCY_SYMBOLS = {"USD": "$", "CNY": "¥"}

# 大数简写:千(K) / 百万(M) / 十亿(B)。中文语境里 M=百万、B=十亿。
_COMPACT_STEPS = (
    (1_000_000_000_000, "T"),
    (1_000_000_000, "B"),
    (1_000_000, "M"),
    (1_000, "K"),
)


def quota_to_amount(
    quota: float,
    currency: str,
    quota_per_unit: float,
    cny_rate: float,
) -> float:
    """把原始额度换算成展示金额(TOKENS 类型返回原始额度)。"""
    if currency == "TOKENS":
        return float(quota)
    usd = float(quota) / float(quota_per_unit)
    if currency == "CNY":
        return usd * float(cny_rate)
    return usd


def format_amount(amount: float, currency: str) -> str:
    """金额格式化;TOKENS 显示整数额度,其余带货币符号保留两位。

    负数必须是 "-¥48.00" 而不是 "¥-48.00" —— 符号在货币符号前面才读得通。
    """
    if currency == "TOKENS":
        return f"{amount:,.0f}"
    symbol = _CURRENCY_SYMBOLS.get(currency, "$")
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


# 货币口径:"auto" 表示跟随站点的额度展示类型(/api/status 的 quota_display_type),
# 这样桌宠数字和站点面板一致(站点显示 $ 就出 $,显示 ¥ 就出 ¥)。
CURRENCY_AUTO = "auto"
VALID_CURRENCIES = (CURRENCY_AUTO, "USD", "CNY", "TOKENS")
_SITE_TO_CURRENCY = {
    "USD": "USD",
    "CNY": "CNY",
    "TOKENS": "TOKENS",
    "CUSTOM": "CNY",  # 自定义币种按本地货币处理,符号由站点侧决定,这里退化为 CNY
}


def resolve_display_currency(config_currency: str, site_display_type: str) -> str:
    """把配置里的口径解析成具体币种。

    auto 跟随站点;站点口径缺失时退回 USD(OpenAI 兼容接口的默认口径)。
    """
    wanted = str(config_currency or CURRENCY_AUTO).strip()
    if wanted.lower() == CURRENCY_AUTO:
        site = str(site_display_type or "").strip().upper()
        return _SITE_TO_CURRENCY.get(site, "USD")
    upper = wanted.upper()
    return upper if upper in ("USD", "CNY", "TOKENS") else "USD"


def format_compact_count(value: float | int | None) -> str:
    """大数简写:1159.13 万 → 1.16M,11.59 亿 → 1.16B,小于 1000 原样显示。

    小数位随量级收敛(十亿以上 2 位、百万 2 位、千 1 位),并去掉多余的 0,
    这样日志行、卡片和气泡里都不会再出现 1,159,134,252 这种长串。
    """
    if value is None:
        return "0"
    if isinstance(value, bool):  # bool 是 int 子类,单独挡掉,避免 True 变成 1
        return "0"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "0"
    if not math.isfinite(amount):
        return "0"
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    for threshold, suffix in _COMPACT_STEPS:
        if amount >= threshold:
            scaled = amount / threshold
            digits = 1 if suffix == "K" else 2
            text = f"{scaled:.{digits}f}".rstrip("0").rstrip(".")
            fraction = text.split(".")[1] if "." in text else ""
            # 282050 这类"差一点就到整数"的数,尾数是 0/1 时丢掉小数更干净
            if fraction in ("", "0", "1"):
                text = f"{round(scaled):,}"
            return f"{sign}{text}{suffix}"
    return f"{sign}{amount:,.0f}"


def format_quota(
    quota: float,
    currency: str,
    quota_per_unit: float,
    cny_rate: float,
) -> str:
    """余额/总额度等大数展示,两位小数。"""
    return format_amount(
        quota_to_amount(quota, currency, quota_per_unit, cny_rate),
        currency,
    )


def format_quota_compact(
    quota: float,
    currency: str,
    quota_per_unit: float,
    cny_rate: float,
) -> str:
    """卡片/气泡里的大数字专用:超过一千就用 K/M/B 简写。

    账户余额可能是几千万这种量级,写全 "-¥48,132,920.48" 会被卡片宽度省略成
    "-¥48,13..." 反而读不出数量级;简写成 "-¥48.13M" 一眼能看懂。
    """
    amount = quota_to_amount(quota, currency, quota_per_unit, cny_rate)
    if currency == "TOKENS":
        return format_compact_count(amount)
    symbol = _CURRENCY_SYMBOLS.get(currency, "$")
    sign = "-" if amount < 0 else ""
    magnitude = abs(amount)
    if magnitude >= 1000:
        return f"{sign}{symbol}{format_compact_count(magnitude)}"
    return f"{sign}{symbol}{magnitude:,.2f}"


def format_quota_precise(
    quota: float,
    currency: str,
    quota_per_unit: float,
    cny_rate: float,
) -> str:
    """单次调用的小额展示:四位小数并去掉末尾多余的 0。"""
    if currency == "TOKENS":
        return f"{quota:,.0f}"
    symbol = _CURRENCY_SYMBOLS.get(currency, "$")
    amount = quota_to_amount(quota, currency, quota_per_unit, cny_rate)
    sign = "-" if amount < 0 else ""
    text = f"{symbol}{abs(amount):.4f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
        # 货币符号后至少保留一位小数,避免 "$." 这类空小数。
        if text.endswith(symbol):
            text += "0"
    return sign + text


# ---------------------------------------------------------------- 账户余额(billing 接口)
# new-api 的 /v1/dashboard/billing/* 返回的是"站点展示口径"的金额,不是原始额度:
# controller/billing.go 按 GetQuotaDisplayType() 分支 —— USD 除 QuotaPerUnit、
# CNY 再乘汇率、TOKENS 保持原值。所以必须先按站点口径还原成 quota,
# 再按桌宠自己的口径格式化,否则数字会差 500000 倍。
SITE_DISPLAY_TOKENS = "TOKENS"
SITE_DISPLAY_CNY = "CNY"
SITE_DISPLAY_CUSTOM = "CUSTOM"

# 余额口径:token=令牌自身额度(现状默认),account=账户钱包余额,auto=令牌无限额度时改用账户
BALANCE_SOURCE_TOKEN = "token"
BALANCE_SOURCE_ACCOUNT = "account"
BALANCE_SOURCE_AUTO = "auto"
VALID_BALANCE_SOURCES = (BALANCE_SOURCE_AUTO, BALANCE_SOURCE_TOKEN, BALANCE_SOURCE_ACCOUNT)


def billing_amount_to_quota(
    amount: object,
    display_type: str,
    quota_per_unit: float,
    usd_to_cny: float,
    custom_rate: float = 1.0,
) -> float:
    """把 billing 接口返回的展示金额还原成原始额度(quota)。"""
    if isinstance(amount, bool):  # bool 是 int 子类,True 不该被当成 1
        return 0.0
    try:
        value = float(amount)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    per_unit = float(quota_per_unit) or 1.0
    kind = str(display_type or "").strip().upper()
    if kind == SITE_DISPLAY_TOKENS:
        return value
    if kind == SITE_DISPLAY_CNY:
        return value / (float(usd_to_cny) or 1.0) * per_unit
    if kind == SITE_DISPLAY_CUSTOM:
        return value / (float(custom_rate) or 1.0) * per_unit
    return value * per_unit  # USD:字段名带 _usd,语义就是美元


# OpenAI 兼容惯例:new-api 的 total_usage 是"美分",而 subscription 的 *_usd 是"美元"
# (见 controller/billing.go:104 `TotalUsage: amount * 100`)。两个口径必须换算一致
# 才能相减,否则余额会被算成巨额负数。
BILLING_USAGE_CENTS_PER_DOLLAR = 100.0


def billing_usage_amount_to_quota(
    amount: object,
    display_type: str,
    quota_per_unit: float,
    usd_to_cny: float,
    custom_rate: float = 1.0,
) -> float:
    """还原 /v1/dashboard/billing/usage 的 total_usage(美分)为原始额度。"""
    if isinstance(amount, bool):  # bool 是 int 子类,不该被当成 1
        return 0.0
    try:
        value = float(amount)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return billing_amount_to_quota(
        value / BILLING_USAGE_CENTS_PER_DOLLAR,
        display_type, quota_per_unit, usd_to_cny, custom_rate,
    )


def resolve_balance_source(
    source: str,
    account_ready: bool,
    token_unlimited: bool,
) -> str:
    """决定大数字到底显示"令牌额度"还是"账户余额"。"""
    wanted = str(source or BALANCE_SOURCE_AUTO).strip().lower()
    if wanted == BALANCE_SOURCE_ACCOUNT:
        return "account" if account_ready else "token"
    if wanted == BALANCE_SOURCE_TOKEN:
        return "token"
    # auto:令牌开了无限额度时它的剩余额度恒为 ∞,没有信息量 → 改用账户余额
    return "account" if (account_ready and token_unlimited) else "token"


def local_midnight_timestamp(now: datetime | None = None) -> float:
    """本地时区"今天零点"的 unix 时间戳(秒)。"""
    current = now or datetime.now()
    return current.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def summarize_today(logs: list[dict[str, Any]] | None, now: datetime | None = None) -> dict[str, int]:
    """统计本地时区今天的消费日志。

    日志条目为 new-api /api/log/token 返回的 dict,至少包含
    created_at(unix 秒) / type / quota / prompt_tokens / completion_tokens。
    非消费(type != 2)与零点之前的条目不计入。
    """
    threshold = local_midnight_timestamp(now)
    count = 0
    quota = 0
    prompt_tokens = 0
    completion_tokens = 0
    for entry in logs or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != LOG_TYPE_CONSUME:
            continue
        created_at = entry.get("created_at")
        if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
            continue
        if created_at < threshold:
            continue
        count += 1
        quota += int(entry.get("quota") or 0)
        prompt_tokens += int(entry.get("prompt_tokens") or 0)
        completion_tokens += int(entry.get("completion_tokens") or 0)
    return {
        "count": count,
        "quota": quota,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def build_log_rows(
    logs: list[dict[str, Any]] | None,
    currency: str,
    quota_per_unit: float,
    cny_rate: float,
    limit: int = 50,
) -> list[dict[str, str]]:
    """把消费日志整理成 QML 列表行(字符串全部就地格式化)。"""
    if limit <= 0:
        return []
    rows: list[dict[str, str]] = []
    for entry in logs or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != LOG_TYPE_CONSUME:
            continue
        created_at = entry.get("created_at")
        if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
            continue
        stamp = datetime.fromtimestamp(created_at)
        prompt = int(entry.get("prompt_tokens") or 0)
        completion = int(entry.get("completion_tokens") or 0)
        rows.append(
            {
                "time": stamp.strftime("%m-%d %H:%M"),
                "model": str(entry.get("model_name") or "unknown"),
                "tokens": f"+{format_compact_count(prompt)} / +{format_compact_count(completion)}",
                "quotaText": format_quota_precise(
                    int(entry.get("quota") or 0), currency, quota_per_unit, cny_rate
                ),
            }
        )
        if len(rows) >= limit:
            break
    return rows
