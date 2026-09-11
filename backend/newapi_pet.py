# coding: utf-8
"""NewAPI 余额桌宠控制器。

只依赖 new-api 的两条只读接口(仅凭 API Key 即可访问,令牌耗尽/过期也可查):
  GET {base}/api/usage/token/   -> {"code": true, "data": {total_granted/total_used/total_available/...}}
  GET {base}/api/log/token      -> {"success": true, "data": [消费日志...]}

网络全部走 QNetworkAccessManager 异步回调,GUI 线程不做任何阻塞等待。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import logging
import math
import time
from typing import Any, Optional

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from backend import quota_math
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
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._config_path = str(config_path)
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
        self._last_error = ""
        self._save_error = ""
        self._last_updated = 0.0
        self._known_used: Optional[int] = None
        self._generation = 0
        self._pending: dict[str, bool] = {}
        self._staged: dict[str, Any] = {}
        # 限流退避与单飞:new-api 的 CriticalRateLimit 是每 IP 每路由 20 次/20 分钟,
        # 收到 429/503 必须按 Retry-After 退避,且一轮请求未回来前不再叠加。
        self._inflight = False
        self._queued_refresh = False
        self._blocked_until = 0.0
        self._retry_after = 0

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
    def configAccountIntervalText(self) -> str:
        return str(self._effective_config().account_poll_interval_seconds)

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

    @Slot(str, str, str, str, str, str, str, str, str, str, result=bool)
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
    ) -> bool:
        """保存设置窗口提交的内容;校验失败返回 False 并写入 saveErrorText。"""
        parsed, error = build_config_from_user_input(
            base_url, api_key, interval_text, currency, per_unit_text, rate_text,
            pet_image, source, balance_source, account_interval_text,
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
        self._pending = {"usage": True, "logs": True}
        self._staged = {}
        self._inflight = True
        self._get(base, key, "/api/usage/token/", generation, "usage", self._handle_usage)
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

    def _fmt(self, quota: float) -> str:
        config = self._effective_config()
        return quota_math.format_quota(quota, config.currency, config.quota_per_unit, config.cny_rate)

    def _fmt_compact(self, quota: float) -> str:
        """卡片/气泡里的大数字:超过一千用 K/M/B 简写,免得被宽度省略掉数量级。"""
        config = self._effective_config()
        return quota_math.format_quota_compact(
            quota, config.currency, config.quota_per_unit, config.cny_rate
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

    @Property(str, notify=usageChanged)
    def todayText(self) -> str:
        config = self._effective_config()
        amount = quota_math.format_quota(
            self._today["quota"], config.currency, config.quota_per_unit, config.cny_rate
        )
        return f"今日已用 {amount} · {self._today['count']} 次"

    @Property(str, notify=usageChanged)
    def todayAmountText(self) -> str:
        """今日消费金额(不带前缀),供卡片拆行展示。"""
        return self._fmt_compact(self._today["quota"])

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
        url = QUrl(base_url + path)
        request = QNetworkRequest(url)
        if auth:
            request.setRawHeader(b"Authorization", f"Bearer {api_key}".encode("utf-8"))
        request.setRawHeader(b"Accept", b"application/json")
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

    def _handle_failure(self, status, retry_after: int, message: str, key: str) -> None:
        self._pending.clear()  # 一次失败即中止本轮合并
        self._last_error = message
        self._inflight = False
        LOGGER.info("桌宠请求失败(%s): %s", key, message)
        if status in (429, 503):
            # 限流:按 Retry-After 退避,绝不回退/重试(那只会更快再次 429)。
            wait = retry_after if retry_after > 0 else max(self._config.poll_interval_seconds, 60)
            self._retry_after = wait
            self._blocked_until = time.time() + wait
            self.statusChanged.emit()
            self._drain_queued()
            return
        self.statusChanged.emit()
        # 404/405/401 等 = 该来源不是可用 new-api;auto 才换下一个候选。
        if status in self._WRONG_SOURCE_STATUS or status is None:
            if self._maybe_advance_auto():
                return
        self._drain_queued()

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
        self._site_display_type = display or "USD"
        self._site_quota_per_unit = self._positive_float(payload.get("quota_per_unit"), 500_000.0)
        self._site_usd_rate = self._positive_float(payload.get("usd_exchange_rate"), 7.3)
        self._site_custom_rate = self._positive_float(
            payload.get("custom_currency_exchange_rate"), 1.0)
        self._site_display_known = True
        self._site_display_base = self._resolved_base
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
        used = quota_math.billing_amount_to_quota(
            usage, self._site_display_type, self._site_quota_per_unit,
            self._site_usd_rate, self._site_custom_rate,
        )
        self._account_quota = int(round(total - used))
        self._account_used = int(round(used))
        self._account_error = ""
        self._account_updated = time.time()
        self.accountChanged.emit()
        # 大数字可能切到账户口径,面板绑的是 usageChanged,这里补发一次。
        self.usageChanged.emit()
        self.statusChanged.emit()

    def _drain_queued(self) -> None:
        if self._queued_refresh:
            self._queued_refresh = False
            if time.time() >= self._blocked_until:
                QTimer.singleShot(0, self._do_refresh)

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
        config = self._effective_config()
        usage = self._staged.get("usage")
        logs = self._staged.get("logs")
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
            self._today = quota_math.summarize_today(logs)
            self._log_rows = quota_math.build_log_rows(
                logs, config.currency, config.quota_per_unit, config.cny_rate, _MAX_LOG_ROWS
            )
        self._last_updated = time.time()
        if self._config.source == SOURCE_AUTO and not self._last_error:
            self._auto_locked = self._resolved_source  # 锁定可用来源,避免每轮抖动
        self._inflight = False
        self._blocked_until = 0.0
        self._retry_after = 0
        self.usageChanged.emit()
        self.logsChanged.emit()
        self.statusChanged.emit()
        self._drain_queued()
