# coding: utf-8
"""NewAPI 余额桌宠控制器。

只读接口(仅凭 API Key 即可访问,令牌耗尽/过期也可查):
  GET {base}/api/usage/token/   -> {"code": true, "data": {total_granted/total_used/total_available/...}}
  GET {base}/api/log/token      -> {"success": true, "data": [最近 1000 条消费日志,无任何分页/时间参数]}
  GET {base}/v1/dashboard/billing/{subscription,usage} + /api/status -> 账户钱包余额与站点展示口径

「今日已用」走远程累计差值(见 backend/daily_usage.py):站点没有按天接口,所以拿
total_used / billing 已用的**零点基线差值**算,日志窗口只作下限校准与次数/Token 明细
来源。这样限流冻结、进程重启、超 1000 条/天都不会让数字变小或长时间卡住。

网络全部走 QNetworkAccessManager 异步回调,GUI 线程不做任何阻塞等待。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import logging
import math
import os
import re
import time
from typing import Any, Optional

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from backend import quota_math
from backend.async_tasks import SerialTaskRunner
from backend.daily_usage import (
    CONFIDENCE_BELOW,
    CONFIDENCE_EXACT,
    CONFIDENCE_PREFIX,
    COUNTER_ACCOUNT,
    COUNTER_TOKEN,
    DailyUsageTracker,
)
from backend.log_store import DailyLogStore, read_store, write_store
from backend.pet_art import (
    default_preset_token,
    list_pet_presets,
    resolve_pet_frames,
    resolve_pet_image,
)
from backend.pet_config import (
    SOURCE_AUTO,
    SOURCE_MANUAL,
    VALID_SOURCES,
    PetConfig,
    build_config_from_user_input,
    load_pet_config_safe,
    resolve_effective_config,
    save_pet_config,
)


LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT_MS = 15000
_MAX_LOG_ROWS = 50

# 必须自带可识别的 User-Agent:Cloudflare 的 Error 1010 会按浏览器特征直接拒绝
# 空 UA 与 "Python-urllib" 这类客户端 UA(HTTP 403),桌宠就会"看起来余额 0"。
# 实测该 UA 能通过 CF 到达源站,且不需要冒充浏览器。
USER_AGENT = "ConfigPilot (Qt QNetworkAccessManager)"


def _default_resources_dir() -> str:
    """包位置推导 resources 目录(源码运行与 Nuitka 单目录打包都成立)。"""
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(package_root, "resources")


class NewApiPet(QObject):
    """轮询余额/日志并向 QML 暴露只读状态与设置入口。"""

    usageChanged = Signal()
    logsChanged = Signal()
    statusChanged = Signal()
    configSaved = Signal()
    saveErrorChanged = Signal()
    usageBumped = Signal()
    sourcesChanged = Signal()
    accountChanged = Signal()

    def __init__(
        self,
        config_path: str,
        config: PetConfig | None = None,
        source_resolver=None,
        resources_dir: str = "",
        log_store_path: str = "",
        daily_state_path: str = "",
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._config_path = str(config_path)
        # 内置立绘目录:优先用装配层传入的程序目录;缺省时按包位置推导,
        # 源码运行与 Nuitka 单目录打包(<dist>/resources)都能命中。
        self._resources_dir = str(resources_dir or _default_resources_dir())
        if config is None:
            loaded, error = load_pet_config_safe(self._config_path)
            if error:
                LOGGER.warning("桌宠配置加载失败,使用默认配置: %s", error)
            config = loaded
        self._config = resolve_effective_config(config)
        self._resolver = source_resolver

        # 当前解析出的凭证(站点根 + key + 实际来源),轮询与状态展示都读它。
        self._resolved_base = ""
        self._resolved_key = ""
        self._resolved_source = self._config.source
        # auto 模式:逐个候选试到能用为止;成功后锁定,避免每轮抖动。
        self._auto_pos = 0
        self._auto_locked = ""
        self._auto_attempt = 0

        self._nam = QNetworkAccessManager(self)
        try:
            self._nam.setTransferTimeout(_REQUEST_TIMEOUT_MS)
        except AttributeError:  # 极旧 Qt 绑定没有传输超时,忽略即可
            LOGGER.debug("QNetworkAccessManager 不支持 setTransferTimeout,跳过")

        self._token_name = ""
        self._total_granted = 0
        self._total_used = 0
        self._total_available = 0
        self._unlimited = False
        self._expires_at = 0
        self._today: dict[str, int] = {
            "count": 0,
            "quota": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
        self._log_rows: list[dict[str, str]] = []
        self._raw_logs: list[Any] = []
        # 今日日志本地累计缓存:接口窗口只有最近 1000 条,靠 request_id 增量合并
        # 才能覆盖全天;log_store_path 为空(测试/独立入口)时退化为纯内存。
        self._log_store_path = str(log_store_path or "")
        self._log_store = DailyLogStore()
        if self._log_store_path:
            loaded = read_store(self._log_store_path)
            if loaded is not None and self._log_store.load_payload(loaded):
                LOGGER.info("桌宠今日日志缓存已从磁盘恢复(%d 条)。", len(self._log_store))
        self._log_store_tasks: Optional[SerialTaskRunner] = None
        self._log_store_saving = False
        self._today_complete = True
        # 「今日已用」的远程累计口径:两条终身累计计数器的零点基线
        # (见 backend/daily_usage.py)。状态落盘,重启后当天继续累计;身份变了就作废。
        self._daily_state_path = str(daily_state_path or "")
        self._daily = DailyUsageTracker()
        self._daily_identity = ""
        self._daily_loaded = False
        self._daily_saving = False
        self._daily_reading = None
        self._daily_account_reading = None
        self._last_error = ""
        self._save_error = ""
        self._last_updated = 0.0
        self._known_used: Optional[int] = None
        self._generation = 0
        self._pending: dict[str, bool] = {}
        self._staged: dict[str, Any] = {}
        # 限流退避与单飞:new-api 的 CriticalRateLimit 是每 IP 每路由 20 次/20 分钟,
        # 收到 429/503 必须按 Retry-After 退避,且一轮请求未回来前不再叠加。
        # 退避按路由分开:日志路由被限流只该停日志,不能把令牌累计(金额数字)一起冻住。
        self._inflight = False
        self._queued_refresh = False
        self._blocked_until = 0.0
        self._retry_after = 0
        self._logs_blocked_until = 0.0
        self._next_log_fetch = 0.0
        self._cycle_failed = False

        # 账户钱包余额:走 /v1/dashboard/billing/*,与令牌额度是两套数据。
        # 站点把金额按自己的"额度展示类型"换算过(billing.go),所以要先还原成
        # quota 再按桌宠口径格式化;展示类型从公开的 /api/status 读一次即可。
        self._account_quota: Optional[int] = None
        self._account_used: Optional[int] = None
        self._account_error = ""
        self._account_updated = 0.0
        self._account_generation = 0
        self._account_pending: dict[str, bool] = {}
        self._account_staged: dict[str, Any] = {}
        self._account_inflight = False
        self._account_retry_scheduled = False
        self._site_display_type = "USD"
        self._site_quota_per_unit = 500_000.0
        self._site_usd_rate = 7.3
        self._site_custom_rate = 1.0
        self._site_display_known = False
        self._site_display_base = ""

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._config.poll_interval_seconds * 1000)
        self._poll_timer.timeout.connect(self.refresh)
        self._poll_timer.start()

        self._account_timer = QTimer(self)
        self._account_timer.setInterval(self._config.account_poll_interval_seconds * 1000)
        self._account_timer.timeout.connect(self._refresh_account)
        self._account_timer.start()

        if self._resolver is not None:
            self._resolver.credsChanged.connect(self._on_creds_changed)
            self._resolver.sourcesChanged.connect(self.sourcesChanged.emit)
            self._resolver.refresh()
        self._update_credentials()
        QTimer.singleShot(0, self.refresh)

    # ------------------------------------------------------------------ 凭证解析

    def _update_credentials(self) -> None:
        base, key, used = self._resolve_credentials()
        self._resolved_base = base
        self._resolved_key = key
        self._resolved_source = used

    def _resolve_credentials(self) -> tuple[str, str, str]:
        source = self._config.source
        if source == SOURCE_MANUAL or self._resolver is None:
            env = resolve_effective_config(self._config)
            return env.base_url, env.api_key, SOURCE_MANUAL
        if source == SOURCE_AUTO:
            candidates = self._resolver.candidate_sources()
            if not candidates:
                return "", "", SOURCE_AUTO
            if self._auto_locked in candidates:
                chosen = self._auto_locked
            else:
                chosen = candidates[min(self._auto_pos, len(candidates) - 1)]
            site, key, _ = self._resolver.resolve(chosen)
            return site, key, chosen
        site, key, used = self._resolver.resolve(source)
        return site, key, used

    def _reset_auto_selection(self) -> None:
        self._auto_pos = 0
        self._auto_locked = ""
        self._auto_attempt = 0

    def _on_creds_changed(self) -> None:
        self._reset_auto_selection()
        self._update_credentials()
        self._reset_account()
        self.statusChanged.emit()
        self.sourcesChanged.emit()
        # 凭证到位后立即补一次轮询。
        if self._resolved_base and self._resolved_key:
            self.refresh()

    # ------------------------------------------------------------------ 配置

    @property
    def config(self) -> PetConfig:
        """当前生效配置(供 PetManager 等 Python 侧读取)。"""
        return self._config

    def _effective_config(self) -> PetConfig:
        return resolve_effective_config(self._config)

    @Property(str, notify=configSaved)
    def configBaseUrl(self) -> str:
        return self._config.base_url

    @Property(str, notify=configSaved)
    def configApiKey(self) -> str:
        return self._config.api_key

    @Property(str, notify=configSaved)
    def currentSource(self) -> str:
        return self._config.source

    @Property(str, notify=statusChanged)
    def effectiveSite(self) -> str:
        return self._resolved_base

    @Property(str, notify=statusChanged)
    def sourceLabel(self) -> str:
        labels = {
            SOURCE_MANUAL: "手动配置",
            "codex": "Codex 当前配置",
            "claude": "Claude Gateway",
        }
        return labels.get(self._resolved_source, self._resolved_source)

    @Property("QVariantList", notify=sourcesChanged)
    def petSources(self) -> list:
        if self._resolver is None:
            return [
                {"id": "codex", "label": "Codex 当前配置", "site": "", "hasKey": False},
                {"id": "claude", "label": "Claude Gateway", "site": "", "hasKey": False},
            ]
        sources = list(self._resolver.sources_for_ui())
        sources.append({"id": SOURCE_MANUAL, "label": "手动填写", "site": self._config.base_url, "hasKey": bool(self._config.api_key)})
        return sources

    @Property(str, notify=configSaved)
    def configIntervalText(self) -> str:
        return str(self._effective_config().poll_interval_seconds)

    @Property(str, notify=configSaved)
    def configCurrency(self) -> str:
        return self._effective_config().currency

    @Property(str, notify=statusChanged)
    def resolvedCurrency(self) -> str:
        """auto 解析后的实际币种,供设置窗口显示"当前跟随"。"""
        return self._display_params()[0]

    @Property(str, notify=configSaved)
    def configQuotaPerUnitText(self) -> str:
        value = self._effective_config().quota_per_unit
        return str(int(value)) if float(value).is_integer() else str(value)

    @Property(str, notify=configSaved)
    def configCnyRateText(self) -> str:
        value = self._effective_config().cny_rate
        return str(int(value)) if float(value).is_integer() else str(value)

    @Property(str, notify=configSaved)
    def configPetImage(self) -> str:
        return self._effective_config().pet_image

    @Property(str, notify=configSaved)
    def petImageSource(self) -> str:
        """立绘令牌解析后的绝对路径;空串 = 用 PetSprite 自绘的矢量形体。"""
        return resolve_pet_image(self._effective_config().pet_image, self._resources_dir)

    @Property("QVariantMap", notify=configSaved)
    def petImageFrames(self) -> dict:
        """当前预设的姿势帧表(角色 → 绝对路径);空表 = 只有单图或自绘形体。"""
        return resolve_pet_frames(self._effective_config().pet_image, self._resources_dir)

    @Property("QVariantList", notify=configSaved)
    def petImagePresets(self) -> list:
        """resources/pet 里可用的内置立绘,供设置窗做形象选择。"""
        return [preset.to_map() for preset in list_pet_presets(self._resources_dir)]

    @Property(str, notify=configSaved)
    def defaultPetImageToken(self) -> str:
        """pet_image 留空时实际生效的立绘令牌(设置窗据此高亮当前选项)。"""
        return default_preset_token(self._resources_dir)

    @Slot(str, result=str)
    def resolvePetImage(self, token: str) -> str:
        """按界面上正在编辑的值实时解析路径(设置窗预览用,不落盘)。"""
        return resolve_pet_image(token, self._resources_dir)

    @Property(str, notify=configSaved)
    def configAccountIntervalText(self) -> str:
        return str(self._effective_config().account_poll_interval_seconds)

    @Property(str, notify=configSaved)
    def configLogIntervalText(self) -> str:
        """日志窗口(/api/log/token)的轮询间隔:单独限频,避免顶在站点路由限流上。"""
        return str(self._effective_config().log_poll_interval_seconds)

    @Property(int, notify=configSaved)
    def bubbleTimeoutSeconds(self) -> int:
        return self._effective_config().bubble_timeout_seconds

    @Property(int, notify=configSaved)
    def windowX(self) -> int:
        return self._config.window_x

    @Property(int, notify=configSaved)
    def windowBottomY(self) -> int:
        return self._config.window_bottom_y

    @Property(str, notify=saveErrorChanged)
    def saveErrorText(self) -> str:
        return self._save_error

    @Slot(str, str, str, str, str, str, str, str, str, str, str, result=bool)
    def saveSettings(
        self,
        base_url: str,
        api_key: str,
        interval_text: str,
        currency: str,
        per_unit_text: str,
        rate_text: str,
        pet_image: str,
        source: str,
        balance_source: str = "auto",
        account_interval_text: str = "300",
        log_interval_text: str = "180",
    ) -> bool:
        """保存设置窗口提交的内容;校验失败返回 False 并写入 saveErrorText。"""
        parsed, error = build_config_from_user_input(
            base_url, api_key, interval_text, currency, per_unit_text, rate_text,
            pet_image, source, balance_source, account_interval_text, log_interval_text,
        )
        if error:
            self._save_error = error
            self.saveErrorChanged.emit()
            LOGGER.info("桌宠设置保存被拒绝: %s", error)
            return False
        merged = replace(
            self._config,
            base_url=parsed.base_url,
            api_key=parsed.api_key,
            source=parsed.source,
            poll_interval_seconds=parsed.poll_interval_seconds,
            currency=parsed.currency,
            quota_per_unit=parsed.quota_per_unit,
            cny_rate=parsed.cny_rate,
            pet_image=parsed.pet_image,
            balance_source=parsed.balance_source,
            account_poll_interval_seconds=parsed.account_poll_interval_seconds,
            log_poll_interval_seconds=parsed.log_poll_interval_seconds,
        )
        try:
            save_pet_config(self._config_path, merged)
        except OSError as exc:
            self._save_error = f"写入配置文件失败: {exc}"
            self.saveErrorChanged.emit()
            LOGGER.warning("桌宠配置写入失败: %s", exc)
            return False
        self._config = merged
        self._save_error = ""
        self._poll_timer.setInterval(self._config.poll_interval_seconds * 1000)
        self._account_timer.setInterval(self._config.account_poll_interval_seconds * 1000)
        self._reset_auto_selection()
        if self._resolver is not None:
            self._resolver.refresh()
        self._update_credentials()
        self._reset_account()
        self.saveErrorChanged.emit()
        self.configSaved.emit()
        self.statusChanged.emit()
        self.refresh()
        return True

    def _reset_account(self) -> None:
        """换来源/换站点后丢掉旧的账户数据,并强制重新识别站点展示口径。"""
        self._account_quota = None
        self._account_used = None
        self._account_error = ""
        self._account_updated = 0.0
        self._account_pending.clear()
        self._account_staged = {}
        self._site_display_known = False
        self._site_display_base = ""
        self._daily_account_reading = None
        self._account_generation += 1  # 丢弃在途的账户响应
        self.accountChanged.emit()

    @Slot(str, result=bool)
    def setSource(self, source: str) -> bool:
        """切换凭证来源(codex/claude/manual/auto)并持久化。"""
        source = str(source).strip()
        if source not in VALID_SOURCES:
            return False
        if self._config.source == source:
            return True
        self._config = replace(self._config, source=source)
        try:
            save_pet_config(self._config_path, self._config)
        except OSError as exc:
            LOGGER.warning("桌宠来源写入失败: %s", exc)
            return False
        self._reset_auto_selection()
        if self._resolver is not None:
            self._resolver.refresh()
        self._update_credentials()
        self.configSaved.emit()
        self.statusChanged.emit()
        self.refresh()
        return True

    @Slot()
    def refresh(self) -> None:
        """立即轮询一次余额与日志(auto 模式重置候选游标)。"""
        self._auto_attempt = 0
        # 手动刷新是用户明确要"现在就看到",这一次日志窗口不受低频间隔约束。
        self._next_log_fetch = 0.0
        self._do_refresh()
        # 手动刷新时顺带把账户余额也拉一次,两个口径的"上次更新"才对得上。
        QTimer.singleShot(0, self._refresh_account)

    def _do_refresh(self) -> None:
        # 单飞:一轮请求未回来时不叠加,只记一次待补,避免自己把自己打到限流。
        if self._inflight:
            self._queued_refresh = True
            return
        now = time.time()
        if now < self._blocked_until:
            self.statusChanged.emit()  # 展示"限流退避中"
            return
        self._update_credentials()
        base = self._resolved_base
        key = self._resolved_key
        if not base or not key:
            # 来源凭证尚未就绪:触发一次后台解析,等 credsChanged 再补轮询。
            if self._config.source != SOURCE_MANUAL and self._resolver is not None:
                self._resolver.refresh()
            self.statusChanged.emit()
            return
        self._generation += 1
        generation = self._generation
        self._pending = {"usage": True}
        self._staged = {}
        self._cycle_failed = False
        self._inflight = True
        self._get(base, key, "/api/usage/token/", generation, "usage", self._handle_usage)
        # 日志窗口单独限频:它只贡献"次数 / Token 明细 / 最近调用",每 60s 打一次
        # 正好顶在站点每路由 20 次/20 分钟的上限上,一次手动刷新就能把该路由打进 429。
        now = time.time()
        if now >= self._next_log_fetch and now >= self._logs_blocked_until:
            self._pending["logs"] = True
            self._next_log_fetch = now + max(30, self._effective_config().log_poll_interval_seconds)
            self._get(base, key, "/api/log/token", generation, "logs", self._handle_logs)

    def _finish_cycle(self) -> None:
        """一轮(成功或失败)结束后清标志,并补发被合并的刷新请求。"""
        self._inflight = False
        if self._queued_refresh:
            self._queued_refresh = False
            # 冷却未到就等定时器,不立刻再打。
            if time.time() >= self._blocked_until:
                QTimer.singleShot(0, self._do_refresh)

    @Slot(int, int)
    def savePosition(self, x: int, bottom_y: int) -> None:
        """QML 拖动结束后保存窗口位置。"""
        if self._config.window_x == x and self._config.window_bottom_y == bottom_y:
            return
        self._config = replace(self._config, window_x=x, window_bottom_y=bottom_y)
        try:
            save_pet_config(self._config_path, self._config)
        except OSError as exc:
            LOGGER.warning("桌宠位置写入失败: %s", exc)
            return
        self.configSaved.emit()

    @Slot(bool)
    def setAutoShow(self, enabled: bool) -> None:
        """主界面开关持久化 auto_show(不触发窗口显隐,由 PetManager 负责)。"""
        enabled = bool(enabled)
        if self._config.auto_show == enabled:
            return
        self._config = replace(self._config, auto_show=enabled)
        try:
            save_pet_config(self._config_path, self._config)
        except OSError as exc:
            LOGGER.warning("桌宠开关写入失败: %s", exc)
            return
        self.configSaved.emit()

    # ------------------------------------------------------------------ 状态

    def _display_params(self) -> tuple[str, float, float]:
        """返回 (币种, quota_per_unit, 汇率)。

        配置为 auto 时跟随站点 `/api/status` 的 quota_display_type,汇率也改用站点自己的
        usd_exchange_rate —— 这样桌宠数字和站点面板同口径(站点显示 $ 就出 $)。
        """
        config = self._effective_config()
        currency = quota_math.resolve_display_currency(config.currency, self._site_display_type)
        if str(config.currency).strip().lower() == quota_math.CURRENCY_AUTO:
            return currency, self._site_quota_per_unit, self._site_usd_rate
        return currency, config.quota_per_unit, config.cny_rate

    def _fmt(self, quota: float) -> str:
        currency, per_unit, rate = self._display_params()
        return quota_math.format_quota(quota, currency, per_unit, rate)

    def _fmt_compact(self, quota: float) -> str:
        """卡片/气泡里的大数字:超过一千用 K/M/B 简写,免得被宽度省略掉数量级。"""
        currency, per_unit, rate = self._display_params()
        return quota_math.format_quota_compact(quota, currency, per_unit, rate)

    def _schedule_log_store_save(self, identity: str) -> None:
        """把今日日志缓存落盘;序列化与写文件都在后台线程,主线程零阻塞。"""
        if not self._log_store_path or not self._log_store.dirty or self._log_store_saving:
            return
        if self._log_store_tasks is None:
            self._log_store_tasks = SerialTaskRunner(
                self, thread_name="ConfigPilotPetLogStore", drain_on_close=True
            )
        payload = self._log_store.to_payload(identity)
        revision = self._log_store.revision
        path = self._log_store_path
        self._log_store_saving = True
        try:
            self._log_store_tasks.submit(
                lambda: write_store(path, payload),
                lambda _result: self._log_store_saved(revision),
                self._log_store_save_failed,
            )
        except RuntimeError as exc:  # 队列已关闭(退出中)
            self._log_store_saving = False
            LOGGER.info("桌宠日志落盘被跳过: %s", exc)

    def _log_store_saved(self, revision: int) -> None:
        self._log_store_saving = False
        self._log_store.mark_saved(revision)

    def _log_store_save_failed(self, exc: Exception) -> None:
        self._log_store_saving = False
        LOGGER.info("桌宠日志落盘失败(下轮重试): %s", exc)

    def _reformat_rows(self) -> None:
        """按当前生效口径重建"最近调用"行。

        站点展示类型(/api/status)可能晚于第一轮令牌轮询到达,所以行内容要能在
        口径确定后重算一次,否则日志金额会停留在错误的币种。
        """
        currency, per_unit, rate = self._display_params()
        self._log_rows = quota_math.build_log_rows(
            self._raw_logs, currency, per_unit, rate, _MAX_LOG_ROWS
        )

    @Property(str, notify=usageChanged)
    def tokenName(self) -> str:
        return self._token_name

    @Property(str, notify=usageChanged)
    def balanceText(self) -> str:
        if self._unlimited:
            return "∞"
        return self._fmt_compact(self._total_available)

    @Property(str, notify=usageChanged)
    def grantedText(self) -> str:
        if self._unlimited:
            return "∞"
        return self._fmt(self._total_granted)

    @Property(str, notify=usageChanged)
    def usedText(self) -> str:
        return self._fmt(self._total_used)

    @Property(bool, notify=usageChanged)
    def unlimitedQuota(self) -> bool:
        return self._unlimited

    @Property(bool, notify=usageChanged)
    def lowBalance(self) -> bool:
        return not self._unlimited and self._total_available <= 0

    @Property(bool, notify=usageChanged)
    def todayLowerBound(self) -> bool:
        """True = 今日**次数/Token** 只是下限(日志窗口有本地补不回的洞)。

        金额自 2026-09-14 起另有远程累计口径,不受日志窗口影响,它的前缀单独由
        ``_today_quota()`` 的置信度决定;这里只管次数与 Token 明细。
        """
        return not self._today_complete

    @Property(str, notify=usageChanged)
    def todayText(self) -> str:
        currency, per_unit, rate = self._display_params()
        quota, confidence = self._today_quota()
        amount = quota_math.format_quota(quota, currency, per_unit, rate)
        count_prefix = "" if self._today_complete else "≥"
        return (
            f"今日已用 {CONFIDENCE_PREFIX[confidence]}{amount}"
            f" · {count_prefix}{self._today['count']} 次"
        )

    @Property(str, notify=usageChanged)
    def todayAmountText(self) -> str:
        """今日已用金额(本令牌,已带下限前缀),供卡片大数字展示。"""
        quota, confidence = self._today_quota()
        return CONFIDENCE_PREFIX[confidence] + self._fmt_compact(quota)

    @Property(bool, notify=accountChanged)
    def todayAccountReady(self) -> bool:
        """账户口径(该账户下**所有**令牌合计)的今日读数是否可用。"""
        reading = self._daily_account_reading
        return bool(reading is not None and reading.usable)

    @Property(str, notify=accountChanged)
    def todayAccountAmountText(self) -> str:
        """今日已用金额(全账户,含其它令牌);拿不到基线时给占位符不猜数。"""
        reading = self._daily_account_reading
        if reading is None or not reading.usable:
            return "—"
        return CONFIDENCE_PREFIX[reading.confidence] + self._fmt_compact(reading.quota)

    @Property(str, notify=accountChanged)
    def todayAccountStateText(self) -> str:
        """账户今日还不可用时的一行原因(设置窗用),不用估算值糊弄。"""
        if self.todayAccountReady:
            return ""
        if self._account_error:
            return f"账户累计未就绪：{self.accountErrorBrief}"
        return "账户累计未就绪：等一次账户轮询"

    @Property(int, notify=usageChanged)
    def todayCount(self) -> int:
        return int(self._today["count"])

    @Property(int, notify=usageChanged)
    def todayPromptTokens(self) -> int:
        return int(self._today["prompt_tokens"])

    @Property(int, notify=usageChanged)
    def todayCompletionTokens(self) -> int:
        return int(self._today["completion_tokens"])

    @Property(str, notify=usageChanged)
    def todayPromptTokensText(self) -> str:
        """输入 Token 简写(如 1.16B)。"""
        return quota_math.format_compact_count(self._today["prompt_tokens"])

    @Property(str, notify=usageChanged)
    def todayCompletionTokensText(self) -> str:
        """输出 Token 简写(如 282K)。"""
        return quota_math.format_compact_count(self._today["completion_tokens"])

    @Property(str, notify=usageChanged)
    def todayTokensText(self) -> str:
        return (
            f"↑{quota_math.format_compact_count(self._today['prompt_tokens'])}"
            f" ↓{quota_math.format_compact_count(self._today['completion_tokens'])}"
        )

    # ------------------------------------------------------ 账户钱包余额(billing)
    # 账户字段变化时同时发 usageChanged,大数字相关属性统一挂一个通知信号即可。

    @Property(bool, notify=accountChanged)
    def accountReady(self) -> bool:
        return self._account_quota is not None and not self._account_error

    @Property(str, notify=accountChanged)
    def accountErrorText(self) -> str:
        return self._account_error

    @Property(str, notify=accountChanged)
    def accountErrorBrief(self) -> str:
        """给一行小字用的简短失败原因:只取 HTTP 状态码,没有就截首段,避免挤爆卡片。"""
        message = self._account_error
        if not message:
            return ""
        found = re.search(r"HTTP\s+(\d{3})", message)
        if found:
            return f"HTTP {found.group(1)}"
        return message.split("（")[0].split(":")[0][:24]

    @Property(str, notify=accountChanged)
    def accountBalanceText(self) -> str:
        if self._account_quota is None:
            return "—"
        return self._fmt_compact(self._account_quota)

    @Property(str, notify=accountChanged)
    def accountUsedText(self) -> str:
        if self._account_used is None:
            return "—"
        return self._fmt(self._account_used)

    @Property(str, notify=accountChanged)
    def accountUpdatedText(self) -> str:
        if self._account_updated <= 0:
            return ""
        return datetime.fromtimestamp(self._account_updated).strftime("%H:%M:%S")

    @Property(str, notify=configSaved)
    def balanceSource(self) -> str:
        """配置的余额口径:auto / token / account。"""
        return self._effective_config().balance_source

    @Property(str, notify=accountChanged)
    def activeBalanceSource(self) -> str:
        """实际生效的口径(account=账户钱包,token=令牌额度)。"""
        return quota_math.resolve_balance_source(
            self._effective_config().balance_source,
            self.accountReady,
            self._unlimited,
        )

    @Property(str, notify=usageChanged)
    def primaryBalanceText(self) -> str:
        """气泡/明细里那个大数字:按生效口径取账户余额或令牌剩余额度。"""
        if self.activeBalanceSource == quota_math.BALANCE_SOURCE_ACCOUNT:
            return self.accountBalanceText
        return self.balanceText

    @Property(str, notify=usageChanged)
    def primaryBalanceCaption(self) -> str:
        if self.activeBalanceSource == quota_math.BALANCE_SOURCE_ACCOUNT:
            return "账户余额"
        return "剩余额度"

    @Property(bool, notify=usageChanged)
    def primaryBalanceNegative(self) -> bool:
        return (self.activeBalanceSource == quota_math.BALANCE_SOURCE_ACCOUNT
                and self._account_quota is not None and self._account_quota < 0)

    @Property(str, notify=usageChanged)
    def expiresText(self) -> str:
        if self._expires_at <= 0:
            return "永久有效"
        stamp = datetime.fromtimestamp(self._expires_at)
        if self._expires_at <= time.time():
            return f"已过期（{stamp.strftime('%Y-%m-%d %H:%M')}）"
        return f"{stamp.strftime('%Y-%m-%d %H:%M')} 到期"

    @Property("QVariantList", notify=logsChanged)
    def recentLogs(self) -> list:
        return self._log_rows

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        if not self._resolved_base or not self._resolved_key:
            if self._config.source != SOURCE_MANUAL and self._resolver is not None:
                return "正在读取已配置的接口凭证…"
            return "未配置：右键桌宠 → 设置"
        now = time.time()
        if now < self._blocked_until:
            return f"已限流，{int(self._blocked_until - now) + 1}s 后自动重试"
        if self._last_error:
            return f"请求失败：{self._last_error}"
        if self._last_updated <= 0:
            return "正在获取…"
        stamp = datetime.fromtimestamp(self._last_updated).strftime("%H:%M:%S")
        return f"{self.sourceLabel} · 每 {self._config.poll_interval_seconds}s 刷新 · {stamp}"

    @Property(bool, notify=statusChanged)
    def hasError(self) -> bool:
        # 限流退避期间不算硬错误(气泡不闪红),只是暂停。
        if self._resolved_base and self._resolved_key and time.time() < self._blocked_until:
            return False
        return bool(self._resolved_base and self._resolved_key and self._last_error)

    @Property(bool, notify=statusChanged)
    def sourceReady(self) -> bool:
        """当前来源是否已解析出可用的站点 + key(含复用 Codex/Claude)。"""
        return bool(self._resolved_base and self._resolved_key)

    # ------------------------------------------------------------------ 网络

    def _build_request(self, base_url: str, path: str, api_key: str, auth: bool) -> QNetworkRequest:
        """构造请求:统一带上 User-Agent(否则 Cloudflare 会以 1010/403 直接拒掉)。"""
        request = QNetworkRequest(QUrl(base_url + path))
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, USER_AGENT)
        request.setRawHeader(b"Accept", b"application/json")
        if auth:
            request.setRawHeader(b"Authorization", f"Bearer {api_key}".encode("utf-8"))
        return request

    def _get(
        self,
        base_url: str,
        api_key: str,
        path: str,
        generation: int,
        key: str,
        handler,
        auth: bool = True,
        counter: str = "main",
    ) -> None:
        request = self._build_request(base_url, path, api_key, auth)
        reply = self._nam.get(request)
        reply.finished.connect(
            lambda rep=reply, gen=generation, req_key=key, cb=handler, cnt=counter:
            self._on_finished(rep, gen, req_key, cb, cnt)
        )

    def _live_generation(self, counter: str) -> int:
        return self._account_generation if counter == "account" else self._generation

    def _on_finished(
        self,
        reply: QNetworkReply,
        generation: int,
        key: str,
        handler,
        counter: str = "main",
    ) -> None:
        try:
            reply.deleteLater()
            if generation != self._live_generation(counter):
                return  # 过期响应(用户改配置/手动刷新后),直接丢弃
            body = bytes(reply.readAll())
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            status_int = int(status) if status is not None else None
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._route_failure(counter, status_int, self._retry_after_seconds(reply),
                                    self._describe_failure(reply, body), key)
                return
            if status_int is None or status_int != 200:
                self._route_failure(counter, status_int, self._retry_after_seconds(reply),
                                    self._describe_failure(reply, body), key)
                return
            try:
                data = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                self._route_failure(counter, status_int, 0, f"响应解析失败: {exc}", key)
                return
            handler(data)
        except RuntimeError as exc:  # reply 已被销毁等运行期异常
            LOGGER.debug("桌宠响应处理异常: %s", exc)

    @staticmethod
    def _retry_after_seconds(reply: QNetworkReply) -> int:
        raw = bytes(reply.rawHeader("Retry-After")).decode("utf-8", "ignore").strip()
        try:
            return max(0, int(raw))
        except ValueError:
            return 0

    @staticmethod
    def _describe_failure(reply: QNetworkReply, body: bytes) -> str:
        """组合网络层错误与服务端返回的 message。"""
        server_message = ""
        try:
            data = json.loads(body.decode("utf-8"))
            if isinstance(data, dict) and data.get("message"):
                server_message = str(data["message"])
        except (UnicodeDecodeError, ValueError):
            pass
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        status_text = f"HTTP {status}" if status is not None else reply.errorString()
        return f"{status_text}：{server_message}" if server_message else status_text

    # 明确"来源不对"的状态码:换下一个候选才有意义。
    _WRONG_SOURCE_STATUS = {400, 401, 403, 404, 405}

    @staticmethod
    def _friendly_failure(status, message: str) -> str:
        """把裸状态码翻译成用户看得懂的原因,避免只显示"HTTP 404"让人以为没消费。"""
        if status == 404:
            return f"{message}（站点未提供 new-api 查询接口，可能不是 new-api 站点）"
        if status == 403:
            return f"{message}（被拒绝：可能是密钥无效，或被站点前置防护拦截）"
        if status is None:
            return f"{message}（请求未发出或未收到 HTTP 响应）"
        return message

    def _handle_failure(self, status, retry_after: int, message: str, key: str) -> None:
        """单条请求失败只作废这一条,同轮另一条的结果照样入账。

        旧实现一次失败就 ``_pending.clear()`` 中止整轮:日志路由(new-api 每 IP 每路由
        20 次/20 分钟)被 429 时,连已经成功返回的令牌累计一起被丢掉,整张卡冻结到
        退避结束 —— 这正是"数字半天不动"的来源。
        """
        self._cycle_failed = True
        self._last_error = self._friendly_failure(status, message)
        LOGGER.info("桌宠请求失败(%s): %s", key, message)
        if status in (429, 503):
            # 限流:按 Retry-After 退避,绝不回退/重试(那只会更快再次 429)。
            wait = retry_after if retry_after > 0 else max(self._config.poll_interval_seconds, 60)
            if key == "logs":
                # 日志路由单独退避:金额已改走累计计数器口径,不该被日志限流拖住
                self._logs_blocked_until = time.time() + wait
                self._next_log_fetch = self._logs_blocked_until
            else:
                self._retry_after = wait
                self._blocked_until = time.time() + wait
            self.statusChanged.emit()
        else:
            self.statusChanged.emit()
        self._pending.pop(key, None)
        if self._pending:
            return  # 同轮还有请求在途,等它回来再收尾
        # 404/405/401 等 = 该来源不是可用 new-api;auto 才换下一个候选。
        if (status in self._WRONG_SOURCE_STATUS or status is None) and self._maybe_advance_auto():
            return
        self._maybe_finish()

    def _route_failure(self, counter: str, status, retry_after: int, message: str, key: str) -> None:
        if counter == "account":
            self._handle_account_failure(status, retry_after, message, key)
            return
        self._handle_failure(status, retry_after, message, key)

    def _handle_account_failure(self, status, retry_after: int, message: str, key: str) -> None:
        """账户余额请求失败:只影响余额口径,不污染令牌状态、不参与 auto 来源回退。"""
        self._account_pending.clear()
        self._account_error = message
        self._account_inflight = False
        LOGGER.info("桌宠账户余额请求失败(%s): %s", key, message)
        if status in (429, 503):
            wait = retry_after if retry_after > 0 else max(self._config.poll_interval_seconds, 60)
            self._blocked_until = time.time() + wait
        self.accountChanged.emit()
        self.statusChanged.emit()
        if key == "site" and status in (404, 403, None):
            # 站点没有公开的 /api/status(例如非 new-api 或前置防护):
            # 按 OpenAI 默认口径(USD / QuotaPerUnit=500000)继续试 billing,
            # 否则账户余额会被这个可选接口永久卡住。
            self._site_display_known = True
            self._site_display_base = self._resolved_base
            self._schedule_account_retry(500)
            return
        if status is None or status >= 500:
            # 网络抖动/服务端错误值得快速再试一次;401/403/404 交给慢周期,不刷配额。
            self._schedule_account_retry(5000)

    def _schedule_account_retry(self, delay_ms: int) -> None:
        if self._account_retry_scheduled:
            return
        self._account_retry_scheduled = True
        QTimer.singleShot(delay_ms, self._account_retry_now)

    def _account_retry_now(self) -> None:
        self._account_retry_scheduled = False
        self._refresh_account()

    def _refresh_account(self) -> None:
        """低频拉取账户钱包余额;站点展示口径未知时先读公开的 /api/status。"""
        if self._account_inflight:
            return
        if time.time() < self._blocked_until:
            return
        self._update_credentials()
        base, key = self._resolved_base, self._resolved_key
        if not base or not key:
            return
        self._account_inflight = True
        self._account_generation += 1
        generation = self._account_generation
        if not self._site_display_known or self._site_display_base != base:
            # 公开接口,不带 key
            self._get(base, "", "/api/status", generation, "site",
                      self._handle_site_status, auth=False, counter="account")
            return
        self._account_pending = {"subscription": True, "usage": True}
        self._account_staged = {}
        self._get(base, key, "/v1/dashboard/billing/subscription", generation,
                  "subscription", self._handle_subscription, counter="account")
        self._get(base, key, "/v1/dashboard/billing/usage", generation,
                  "usage", self._handle_usage_amount, counter="account")

    def _handle_site_status(self, data: Any) -> None:
        """记住站点的额度展示口径,才能把 billing 金额还原成原始额度。"""
        self._account_inflight = False
        payload = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) \
            else (data if isinstance(data, dict) else {})
        display = str(payload.get("quota_display_type") or "").strip().upper()
        changed = self._site_display_type != (display or "USD")
        self._site_display_type = display or "USD"
        self._site_quota_per_unit = self._positive_float(payload.get("quota_per_unit"), 500_000.0)
        self._site_usd_rate = self._positive_float(payload.get("usd_exchange_rate"), 7.3)
        self._site_custom_rate = self._positive_float(
            payload.get("custom_currency_exchange_rate"), 1.0)
        self._site_display_known = True
        self._site_display_base = self._resolved_base
        if changed and self._raw_logs:
            # 口径变了(例如第一轮先按 USD 兜底、随后站点其实是 CNY),重算已格式化的行
            self._reformat_rows()
            self.logsChanged.emit()
            self.usageChanged.emit()
        self._refresh_account()

    @staticmethod
    def _positive_float(value: Any, fallback: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed > 0 and math.isfinite(parsed) else fallback

    def _handle_subscription(self, data: Any) -> None:
        self._account_staged["subscription"] = self._extract_amount(data, "hard_limit_usd")
        self._account_pending.pop("subscription", None)
        self._maybe_finish_account()

    def _handle_usage_amount(self, data: Any) -> None:
        self._account_staged["usage"] = self._extract_amount(data, "total_usage")
        self._account_pending.pop("usage", None)
        self._maybe_finish_account()

    @staticmethod
    def _extract_amount(data: Any, field: str) -> Optional[float]:
        if not isinstance(data, dict):
            return None
        value = data.get(field)
        if value is None and isinstance(data.get("data"), dict):
            value = data["data"].get(field)
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    def _maybe_finish_account(self) -> None:
        if self._account_pending:
            return
        self._account_inflight = False
        subscription = self._account_staged.get("subscription")
        usage = self._account_staged.get("usage")
        self._account_staged = {}
        if subscription is None or usage is None:
            self._account_error = "billing 响应缺少金额字段"
            self.accountChanged.emit()
            self.statusChanged.emit()
            return
        total = quota_math.billing_amount_to_quota(
            subscription, self._site_display_type, self._site_quota_per_unit,
            self._site_usd_rate, self._site_custom_rate,
        )
        # usage 是美分、subscription 是美元,必须各自还原后再相减
        used = quota_math.billing_usage_amount_to_quota(
            usage, self._site_display_type, self._site_quota_per_unit,
            self._site_usd_rate, self._site_custom_rate,
        )
        self._account_quota = int(round(total - used))
        self._account_used = int(round(used))
        self._account_error = ""
        self._account_updated = time.time()
        # 账户终身累计是"今日已用(全账户)"的数据源:喂给零点基线推算
        self._refresh_daily_readings()
        self.accountChanged.emit()
        # 大数字可能切到账户口径,面板绑的是 usageChanged,这里补发一次。
        self.usageChanged.emit()
        self.statusChanged.emit()

    def _maybe_advance_auto(self) -> bool:
        """auto 模式:当前来源请求失败就换下一个候选重试,直到用尽。返回是否已发起。"""
        if self._config.source != SOURCE_AUTO or self._resolver is None:
            return False
        candidates = self._resolver.candidate_sources()
        if len(candidates) <= 1:
            return False
        try:
            current = candidates.index(self._resolved_source)
        except ValueError:
            current = -1
        nxt = current + 1
        if nxt >= len(candidates) or self._auto_attempt >= len(candidates):
            self._auto_locked = ""  # 全部失败,清除锁定,下轮从头再试
            return False
        self._auto_attempt += 1
        self._auto_pos = nxt
        self._do_refresh()
        return True

    def _handle_usage(self, data: Any) -> None:
        if not isinstance(data, dict) or not (data.get("code") is True or data.get("success") is True):
            message = data.get("message", "接口返回异常") if isinstance(data, dict) else "接口返回异常"
            self._handle_failure(None, 0, str(message), "usage")
            return
        payload = data.get("data")
        if not isinstance(payload, dict):
            self._handle_failure(None, 0, "usage 数据缺少 data 字段", "usage")
            return
        self._staged["usage"] = payload
        self._pending.pop("usage", None)
        self._maybe_finish()

    def _handle_logs(self, data: Any) -> None:
        if not isinstance(data, dict) or data.get("success") is not True:
            message = data.get("message", "接口返回异常") if isinstance(data, dict) else "接口返回异常"
            self._handle_failure(None, 0, str(message), "logs")
            return
        rows = data.get("data")
        if not isinstance(rows, list):
            self._handle_failure(None, 0, "log 数据缺少 data 字段", "logs")
            return
        self._staged["logs"] = rows
        self._pending.pop("logs", None)
        self._maybe_finish()

    def _maybe_finish(self) -> None:
        if self._pending:
            return
        usage = self._staged.get("usage")
        logs = self._staged.get("logs")
        self._staged = {}
        if not self._cycle_failed:
            self._last_error = ""
        if isinstance(usage, dict):
            previous_used = self._known_used
            self._token_name = str(usage.get("name") or "")
            self._total_granted = int(usage.get("total_granted") or 0)
            self._total_used = int(usage.get("total_used") or 0)
            self._total_available = int(usage.get("total_available") or 0)
            self._unlimited = bool(usage.get("unlimited_quota"))
            expires_at = int(usage.get("expires_at") or 0)
            self._expires_at = 0 if expires_at < 0 else expires_at
            self._known_used = self._total_used
            if previous_used is not None and self._total_used > previous_used:
                self.usageBumped.emit()
        if isinstance(logs, list):
            identity = self._daily_identity_key()
            self._log_store.merge(logs, identity=identity)
            merged = self._log_store.entries
            self._raw_logs = merged
            self._today = quota_math.summarize_today(merged)
            self._today_complete = self._log_store.complete
            self._schedule_log_store_save(identity)
            self._reformat_rows()
        self._refresh_daily_readings(window_fresh=isinstance(logs, list))
        self._last_updated = time.time()
        if self._config.source == SOURCE_AUTO and not self._last_error:
            self._auto_locked = self._resolved_source  # 锁定可用来源,避免每轮抖动
        if not self._cycle_failed:
            self._blocked_until = 0.0
            self._retry_after = 0
        self.usageChanged.emit()
        self.logsChanged.emit()
        self.statusChanged.emit()
        # 账户口径的今日读数依赖令牌累计值,令牌轮询也可能让它从"未就绪"变可用
        self.accountChanged.emit()
        self._finish_cycle()

    # ------------------------------------------------------ 今日已用(远程累计)

    def _daily_identity_key(self) -> str:
        return f"{self._resolved_base}|{self._token_name}"

    def _refresh_daily_readings(self, window_fresh: bool = False) -> None:
        """把两条终身累计值与日志窗口喂进零点基线推算,再取一次读数。

        顺序有讲究:先 observe(令牌累计),再 observe_window(本轮**新到**的窗口合计),
        这样窗口才能拿"累计值 − 窗口合计"反推出精确的零点基线。窗口不是本轮新到的
        时候绝不能重锚 —— 那会把金额钉死在上一次窗口的合计上,又变成"数字不动"。
        """
        identity = self._daily_identity_key()
        if not identity.startswith("http") or not self._token_name:
            self._daily_reading = None
            self._daily_account_reading = None
            return
        if identity != self._daily_identity:
            # 换站点或换令牌:累计口径不能跨身份延续
            self._daily_identity = identity
            self._daily = DailyUsageTracker()
            self._daily_loaded = False
        if not self._daily_loaded:
            self._daily_loaded = True
            if self._daily_state_path:
                stored = read_store(self._daily_state_path)
                if stored is not None and self._daily.load_payload(stored, identity=identity):
                    LOGGER.info("桌宠今日累计基线已从磁盘恢复(%s)。", self._daily.day)
        self._daily.observe(COUNTER_TOKEN, self._total_used)
        if window_fresh and self._raw_logs:
            self._daily.observe_window(self._today["quota"], self._log_store.day_covered)
        if self._account_used is not None:
            self._daily.observe(COUNTER_ACCOUNT, self._account_used)
        self._daily_reading = self._daily.reading(COUNTER_TOKEN)
        self._daily_account_reading = self._daily.reading(COUNTER_ACCOUNT)
        self._schedule_daily_save(identity)

    def _schedule_daily_save(self, identity: str) -> None:
        """零点基线落盘(与日志缓存共用同一条后台队列),主线程零阻塞。"""
        if not self._daily_state_path or not self._daily.dirty or self._daily_saving:
            return
        if self._log_store_tasks is None:
            self._log_store_tasks = SerialTaskRunner(
                self, thread_name="ConfigPilotPetLogStore", drain_on_close=True
            )
        payload = self._daily.to_payload(identity)
        revision = self._daily.revision
        path = self._daily_state_path
        self._daily_saving = True
        try:
            self._log_store_tasks.submit(
                lambda: write_store(path, payload),
                lambda _result: self._daily_saved(revision),
                self._daily_save_failed,
            )
        except RuntimeError as exc:  # 队列已关闭(退出中)
            self._daily_saving = False
            LOGGER.info("桌宠累计基线落盘被跳过: %s", exc)

    def _daily_saved(self, revision: int) -> None:
        self._daily_saving = False
        self._daily.mark_saved(revision)

    def _daily_save_failed(self, exc: Exception) -> None:
        self._daily_saving = False
        LOGGER.info("桌宠累计基线落盘失败(下轮重试): %s", exc)

    def _today_quota(self) -> tuple[int, str]:
        """今日已用(本令牌)的额度与置信度;累计口径不可用时退回日志窗口合计。"""
        reading = self._daily_reading
        if reading is not None and reading.usable:
            return reading.quota, reading.confidence
        return int(self._today["quota"]), (
            CONFIDENCE_EXACT if self._today_complete else CONFIDENCE_BELOW
        )
