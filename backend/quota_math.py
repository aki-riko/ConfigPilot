# coding: utf-8
"""额度换算与"今日用量"统计的纯逻辑部分(不依赖 Qt,可独立测试)。

new-api 的额度(quota)是整数计分,默认 QuotaPerUnit = 500000 对应 $1
(见 new-api common/constants.go)。金额换算与展示类型由站点设置决定,
这里按桌宠配置在本地换算。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


LOG_TYPE_CONSUME = 2

_CURRENCY_SYMBOLS = {"USD": "$", "CNY": "¥"}


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
    """金额格式化;TOKENS 显示整数额度,其余带货币符号保留两位。"""
    if currency == "TOKENS":
        return f"{amount:,.0f}"
    symbol = _CURRENCY_SYMBOLS.get(currency, "$")
    return f"{symbol}{amount:,.2f}"


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
    text = f"{symbol}{quota_to_amount(quota, currency, quota_per_unit, cny_rate):.4f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
        # 货币符号后至少保留一位小数,避免 "$." 这类空小数。
        if text.endswith(symbol):
            text += "0"
    return text


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
                "tokens": f"+{prompt:,} / +{completion:,}",
                "quotaText": format_quota_precise(
                    int(entry.get("quota") or 0), currency, quota_per_unit, cny_rate
                ),
            }
        )
        if len(rows) >= limit:
            break
    return rows
