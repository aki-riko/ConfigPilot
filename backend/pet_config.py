# coding: utf-8
"""余额监控桌宠的用户配置:路径解析、加载、保存与校验。

配置文件位于用户配置目录(ConfigPilot/pet_config.json),接口地址与
API Key 也可以通过环境变量 CONFIGPILOT_NEWAPI_BASE / CONFIGPILOT_NEWAPI_KEY
覆盖,代码中不出现任何具体站点或密钥。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse


_WINDOWS_CONFIG_ROOT_ENVIRONMENT = "LOCALAPPDATA"
_XDG_CONFIG_HOME_ENVIRONMENT = "XDG_CONFIG_HOME"
_APPLICATION_CONFIG_DIR_NAME = "ConfigPilot"
_PET_CONFIG_FILE_NAME = "pet_config.json"

_BASE_URL_ENVIRONMENT = "CONFIGPILOT_NEWAPI_BASE"
_API_KEY_ENVIRONMENT = "CONFIGPILOT_NEWAPI_KEY"

# auto = 跟随站点的额度展示类型(/api/status 的 quota_display_type),
# 保证桌宠数字与站点面板同口径(站点显示 $ 就出 $)。
_CURRENCIES = ("auto", "USD", "CNY", "TOKENS")
# 凭证来源:auto=自动复用 Codex/Claude;codex/claude=指定来源;manual=手动填写。
SOURCE_AUTO = "auto"
SOURCE_CODEX = "codex"
SOURCE_CLAUDE = "claude"
SOURCE_MANUAL = "manual"
VALID_SOURCES = (SOURCE_AUTO, SOURCE_CODEX, SOURCE_CLAUDE, SOURCE_MANUAL)
# 余额口径:与 quota_math.BALANCE_SOURCE_* 一致(配置层不 import 计算层,避免反向依赖)。
BALANCE_AUTO = "auto"
BALANCE_TOKEN = "token"
BALANCE_ACCOUNT = "account"
VALID_BALANCE_SOURCES = (BALANCE_AUTO, BALANCE_TOKEN, BALANCE_ACCOUNT)
_MIN_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_INTERVAL_SECONDS = 3600
_MIN_ACCOUNT_POLL_INTERVAL_SECONDS = 30
_MAX_ACCOUNT_POLL_INTERVAL_SECONDS = 7200
_MIN_BUBBLE_TIMEOUT_SECONDS = 2
_MAX_BUBBLE_TIMEOUT_SECONDS = 120
_DEFAULT_QUOTA_PER_UNIT = 500_000.0
_DEFAULT_CNY_RATE = 7.3


@dataclass(frozen=True)
class PetConfig:
    """桌宠运行配置;所有字段都有安全默认值。"""

    base_url: str = ""
    api_key: str = ""
    source: str = SOURCE_AUTO
    poll_interval_seconds: int = 120
    currency: str = "auto"
    quota_per_unit: float = _DEFAULT_QUOTA_PER_UNIT
    cny_rate: float = _DEFAULT_CNY_RATE
    auto_show: bool = True
    bubble_timeout_seconds: int = 8
    window_x: int = -1
    window_bottom_y: int = -1
    pet_image: str = ""
    # 大数字显示令牌额度还是账户钱包余额;auto = 令牌开了无限额度时改用账户余额。
    balance_source: str = BALANCE_AUTO
    # 账户余额变化慢,单独低频轮询,避免打爆 new-api 的按路由限流配额。
    account_poll_interval_seconds: int = 300


def resolve_pet_config_path(
    platform_name: str | None = None,
    environment: dict[str, str] | None = None,
    home: str | Path | None = None,
) -> Path:
    """返回桌宠配置文件路径,与 app_settings 的目录约定保持一致。"""
    current_platform = platform_name or os.name
    current_environment = environment if environment is not None else os.environ
    if current_platform == "nt":
        config_root = current_environment.get(_WINDOWS_CONFIG_ROOT_ENVIRONMENT)
        if not config_root:
            raise RuntimeError("LOCALAPPDATA 未设置，无法定位 ConfigPilot 配置目录")
        base_path = Path(config_root)
    else:
        xdg_config_home = current_environment.get(_XDG_CONFIG_HOME_ENVIRONMENT)
        base_path = (
            Path(xdg_config_home)
            if xdg_config_home
            else (Path(home) if home is not None else Path.home()) / ".config"
        )
    return base_path / _APPLICATION_CONFIG_DIR_NAME / _PET_CONFIG_FILE_NAME


def _optional_http_url(value: object, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"配置项 {field!r} 必须是字符串")
    normalized = value.strip().rstrip("/")
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"配置项 {field!r} 必须是 http(s):// 开头的接口地址")
    return normalized


def _positive_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"配置项 {field!r} 必须是数字")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"配置项 {field!r} 必须是正数")
    return result


def _bounded_int(
    value: object,
    field: str,
    minimum: int,
    maximum: int,
    default: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"配置项 {field!r} 必须是整数")
    if not minimum <= value <= maximum:
        raise ValueError(f"配置项 {field!r} 必须位于 {minimum} 到 {maximum} 之间")
    return value


def _optional_int(value: object, field: str) -> int:
    if value is None:
        return -1
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"配置项 {field!r} 必须是整数")
    if value < -1:
        raise ValueError(f"配置项 {field!r} 不能小于 -1(-1 表示默认位置)")
    return value


def _optional_file_path(value: object, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"配置项 {field!r} 必须是字符串")
    return value.strip()


def parse_pet_config(data: object) -> PetConfig:
    """从 dict 构造并校验配置,字段损坏时显式报错。"""
    if not isinstance(data, dict):
        raise ValueError("桌宠配置根节点必须是对象")
    currency = data.get("currency", "auto")
    if not isinstance(currency, str) or currency not in _CURRENCIES:
        raise ValueError(f"配置项 'currency' 必须是 {'/'.join(_CURRENCIES)} 之一")
    auto_show = data.get("auto_show", True)
    if not isinstance(auto_show, bool):
        raise ValueError("配置项 'auto_show' 必须是布尔值")
    source = data.get("source", SOURCE_AUTO)
    if not isinstance(source, str) or source not in VALID_SOURCES:
        raise ValueError(f"配置项 'source' 必须是 {'/'.join(VALID_SOURCES)} 之一")
    balance_source = data.get("balance_source", BALANCE_AUTO)
    if not isinstance(balance_source, str) or balance_source not in VALID_BALANCE_SOURCES:
        raise ValueError(
            f"配置项 'balance_source' 必须是 {'/'.join(VALID_BALANCE_SOURCES)} 之一"
        )
    return PetConfig(
        base_url=_optional_http_url(data.get("base_url"), "base_url"),
        api_key=data.get("api_key", "").strip()
        if isinstance(data.get("api_key", ""), str)
        else _raise_type("api_key"),
        source=source,
        poll_interval_seconds=_bounded_int(
            data.get("poll_interval_seconds"),
            "poll_interval_seconds",
            _MIN_POLL_INTERVAL_SECONDS,
            _MAX_POLL_INTERVAL_SECONDS,
            120,
        ),
        currency=currency,
        quota_per_unit=_positive_number(data.get("quota_per_unit", _DEFAULT_QUOTA_PER_UNIT), "quota_per_unit"),
        cny_rate=_positive_number(data.get("cny_rate", _DEFAULT_CNY_RATE), "cny_rate"),
        auto_show=auto_show,
        bubble_timeout_seconds=_bounded_int(
            data.get("bubble_timeout_seconds"),
            "bubble_timeout_seconds",
            _MIN_BUBBLE_TIMEOUT_SECONDS,
            _MAX_BUBBLE_TIMEOUT_SECONDS,
            8,
        ),
        window_x=_optional_int(data.get("window_x"), "window_x"),
        window_bottom_y=_optional_int(data.get("window_bottom_y"), "window_bottom_y"),
        pet_image=_optional_file_path(data.get("pet_image"), "pet_image"),
        balance_source=balance_source,
        account_poll_interval_seconds=_bounded_int(
            data.get("account_poll_interval_seconds"),
            "account_poll_interval_seconds",
            _MIN_ACCOUNT_POLL_INTERVAL_SECONDS,
            _MAX_ACCOUNT_POLL_INTERVAL_SECONDS,
            300,
        ),
    )


def _raise_type(field: str) -> str:
    raise ValueError(f"配置项 {field!r} 必须是字符串")


def load_pet_config(path: str | Path) -> PetConfig:
    """读取桌宠配置;文件不存在时返回默认配置。"""
    config_path = Path(path)
    if not config_path.is_file():
        return PetConfig()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return parse_pet_config(data)


def load_pet_config_safe(path: str | Path) -> tuple[PetConfig, str]:
    """load_pet_config 的容错版本,损坏时回退默认配置并返回错误信息。"""
    try:
        return load_pet_config(path), ""
    except (OSError, ValueError) as exc:
        return PetConfig(), str(exc)


def save_pet_config(path: str | Path, config: PetConfig) -> None:
    """原子写入配置文件(临时文件 + replace)。"""
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    payload = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "source": config.source,
        "poll_interval_seconds": config.poll_interval_seconds,
        "currency": config.currency,
        "quota_per_unit": config.quota_per_unit,
        "cny_rate": config.cny_rate,
        "auto_show": config.auto_show,
        "bubble_timeout_seconds": config.bubble_timeout_seconds,
        "window_x": config.window_x,
        "window_bottom_y": config.window_bottom_y,
        "pet_image": config.pet_image,
        "balance_source": config.balance_source,
        "account_poll_interval_seconds": config.account_poll_interval_seconds,
    }
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, config_path)


def build_config_from_user_input(
    base_url: str,
    api_key: str,
    interval_text: str,
    currency: str,
    per_unit_text: str,
    rate_text: str,
    pet_image: str,
    source: str = SOURCE_MANUAL,
    balance_source: str = BALANCE_AUTO,
    account_interval_text: str = "300",
) -> tuple[PetConfig, str]:
    """把设置窗口的字符串输入解析成配置;失败时返回错误信息。

    source != manual 时接口地址与 key 由来源解析,这里不保存它们。
    """
    try:
        interval = int(str(interval_text).strip())
    except ValueError:
        return PetConfig(), "轮询间隔必须是整数秒"
    try:
        account_interval = int(str(account_interval_text).strip() or "300")
    except ValueError:
        return PetConfig(), "账户余额轮询间隔必须是整数秒"
    try:
        per_unit = float(str(per_unit_text).strip())
    except ValueError:
        return PetConfig(), "$ 对应额度必须是数字"
    try:
        rate = float(str(rate_text).strip())
    except ValueError:
        return PetConfig(), "CNY 汇率必须是数字"
    source_text = str(source).strip() or SOURCE_MANUAL
    if source_text == SOURCE_MANUAL:
        base = _optional_http_url(str(base_url), "接口地址")
        key = str(api_key).strip()
        if key and base == "":
            return PetConfig(), "手动模式下填写了 API Key 时必须同时填写接口地址"
    else:
        base = ""
        key = ""
    try:
        config = parse_pet_config(
            {
                "base_url": base,
                "api_key": key,
                "source": source_text,
                "poll_interval_seconds": interval,
                "currency": str(currency),
                "quota_per_unit": per_unit,
                "cny_rate": rate,
                "pet_image": str(pet_image),
                "balance_source": str(balance_source).strip() or BALANCE_AUTO,
                "account_poll_interval_seconds": account_interval,
            }
        )
    except ValueError as exc:
        return PetConfig(), str(exc)
    return config, ""


def resolve_effective_config(config: PetConfig, environment: dict[str, str] | None = None) -> PetConfig:
    """应用环境变量覆盖:站点地址与 API Key 可不落盘。"""
    current_environment = environment if environment is not None else os.environ
    base_url = current_environment.get(_BASE_URL_ENVIRONMENT, "").strip().rstrip("/")
    api_key = current_environment.get(_API_KEY_ENVIRONMENT, "").strip()
    return replace(
        config,
        base_url=base_url or config.base_url,
        api_key=api_key or config.api_key,
    )
