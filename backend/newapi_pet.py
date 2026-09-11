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

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._config.poll_interval_seconds * 1000)
        self._poll_timer.timeout.connect(self.refresh)
        self._poll_timer.start()

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

    @Slot(str, str, str, str, str, str, str, str, result=bool)
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
    ) -> bool:
        """保存设置窗口提交的内容;校验失败返回 False 并写入 saveErrorText。"""
        parsed, error = build_config_from_user_input(
            base_url, api_key, interval_text, currency, per_unit_text, rate_text,
            pet_image, source,
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
        self._reset_auto_selection()
        if self._resolver is not None:
            self._resolver.refresh()
        self._update_credentials()
        self.saveErrorChanged.emit()
        self.configSaved.emit()
        self.statusChanged.emit()
        self.refresh()
        return True

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

    def _do_refresh(self) -> None:
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
        self._get(base, key, "/api/usage/token/", generation, "usage", self._handle_usage)
        self._get(base, key, "/api/log/token", generation, "logs", self._handle_logs)

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

    @Property(str, notify=usageChanged)
    def tokenName(self) -> str:
        return self._token_name

    @Property(str, notify=usageChanged)
    def balanceText(self) -> str:
        if self._unlimited:
            return "∞"
        return self._fmt(self._total_available)

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
    def todayTokensText(self) -> str:
        return (
            f"↑{self._today['prompt_tokens']:,} ↓{self._today['completion_tokens']:,} tokens"
        )

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
        if self._last_error:
            return f"请求失败：{self._last_error}"
        if self._last_updated <= 0:
            return "正在获取…"
        stamp = datetime.fromtimestamp(self._last_updated).strftime("%H:%M:%S")
        return f"{self.sourceLabel} · 每 {self._config.poll_interval_seconds}s 刷新 · {stamp}"

    @Property(bool, notify=statusChanged)
    def hasError(self) -> bool:
        return bool(self._resolved_base and self._resolved_key and self._last_error)

    @Property(bool, notify=statusChanged)
    def sourceReady(self) -> bool:
        """当前来源是否已解析出可用的站点 + key(含复用 Codex/Claude)。"""
        return bool(self._resolved_base and self._resolved_key)

    # ------------------------------------------------------------------ 网络

    def _get(self, base_url: str, api_key: str, path: str, generation: int, key: str, handler) -> None:
        url = QUrl(base_url + path)
        request = QNetworkRequest(url)
        request.setRawHeader(b"Authorization", f"Bearer {api_key}".encode("utf-8"))
        request.setRawHeader(b"Accept", b"application/json")
        reply = self._nam.get(request)
        reply.finished.connect(
            lambda rep=reply, gen=generation, req_key=key, cb=handler: self._on_finished(rep, gen, req_key, cb)
        )

    def _on_finished(self, reply: QNetworkReply, generation: int, key: str, handler) -> None:
        try:
            reply.deleteLater()
            if generation != self._generation:
                return  # 过期响应(用户改配置/手动刷新后),直接丢弃
            body = bytes(reply.readAll())
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._fail(self._describe_failure(reply, body), key)
                return
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            if status is None or int(status) != 200:
                self._fail(self._describe_failure(reply, body), key)
                return
            try:
                data = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                self._fail(f"响应解析失败: {exc}", key)
                return
            handler(data)
        except RuntimeError as exc:  # reply 已被销毁等运行期异常
            LOGGER.debug("桌宠响应处理异常: %s", exc)

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

    def _fail(self, message: str, key: str) -> None:
        self._pending.pop(key, None)
        self._last_error = message
        self._pending.clear()  # 一次失败即中止本轮合并
        LOGGER.info("桌宠请求失败(%s): %s", key, message)
        self.statusChanged.emit()
        self._maybe_advance_auto()

    def _maybe_advance_auto(self) -> None:
        """auto 模式:当前来源请求失败就换下一个候选重试,直到用尽。"""
        if self._config.source != SOURCE_AUTO or self._resolver is None:
            return
        candidates = self._resolver.candidate_sources()
        if len(candidates) <= 1:
            return
        try:
            current = candidates.index(self._resolved_source)
        except ValueError:
            current = -1
        nxt = current + 1
        if nxt >= len(candidates) or self._auto_attempt >= len(candidates):
            self._auto_locked = ""  # 全部失败,清除锁定,下轮从头再试
            return
        self._auto_attempt += 1
        self._auto_pos = nxt
        self._do_refresh()

    def _handle_usage(self, data: Any) -> None:
        if not isinstance(data, dict) or not (data.get("code") is True or data.get("success") is True):
            message = data.get("message", "接口返回异常") if isinstance(data, dict) else "接口返回异常"
            self._fail(str(message), "usage")
            return
        payload = data.get("data")
        if not isinstance(payload, dict):
            self._fail("usage 数据缺少 data 字段", "usage")
            return
        self._staged["usage"] = payload
        self._pending.pop("usage", None)
        self._maybe_finish()

    def _handle_logs(self, data: Any) -> None:
        if not isinstance(data, dict) or data.get("success") is not True:
            message = data.get("message", "接口返回异常") if isinstance(data, dict) else "接口返回异常"
            self._fail(str(message), "logs")
            return
        rows = data.get("data")
        if not isinstance(rows, list):
            self._fail("log 数据缺少 data 字段", "logs")
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
        self.usageChanged.emit()
        self.logsChanged.emit()
        self.statusChanged.emit()
