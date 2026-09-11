# coding: utf-8
"""NewAPI 余额桌宠控制器。

只依赖 new-api 的两条只读接口(仅凭 API Key 即可访问,令牌耗尽/过期也可查):
  GET {base}/api/usage/token/   -> {"code": true, "data": {total_granted/total_used/total_available/...}}
  GET {base}/api/log/token      -> {"success": true, "data": [消费日志...]}

网络全部走 QNetworkAccessManager 异步回调,GUI 线程不做任何阻塞等待。
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import time
from typing import Any, Optional

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from backend import quota_math
from backend.pet_config import (
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

    def __init__(self, config_path: str, config: PetConfig | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._config_path = str(config_path)
        if config is None:
            loaded, error = load_pet_config_safe(self._config_path)
            if error:
                LOGGER.warning("桌宠配置加载失败,使用默认配置: %s", error)
            config = loaded
        self._config = resolve_effective_config(config)

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
        QTimer.singleShot(0, self.refresh)

    # ------------------------------------------------------------------ 配置

    def _effective_config(self) -> PetConfig:
        return resolve_effective_config(self._config)

    @Property(str, notify=configSaved)
    def configBaseUrl(self) -> str:
        return self._effective_config().base_url

    @Property(str, notify=configSaved)
    def configApiKey(self) -> str:
        return self._effective_config().api_key

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

    @Slot(str, str, str, str, str, str, str, result=bool)
    def saveSettings(
        self,
        base_url: str,
        api_key: str,
        interval_text: str,
        currency: str,
        per_unit_text: str,
        rate_text: str,
        pet_image: str,
    ) -> bool:
        """保存设置窗口提交的内容;校验失败返回 False 并写入 saveErrorText。"""
        parsed, error = build_config_from_user_input(
            base_url, api_key, interval_text, currency, per_unit_text, rate_text, pet_image
        )
        if error:
            self._save_error = error
            self.saveErrorChanged.emit()
            LOGGER.info("桌宠设置保存被拒绝: %s", error)
            return False
        merged = PetConfig(
            base_url=parsed.base_url,
            api_key=parsed.api_key,
            poll_interval_seconds=parsed.poll_interval_seconds,
            currency=parsed.currency,
            quota_per_unit=parsed.quota_per_unit,
            cny_rate=parsed.cny_rate,
            auto_show=self._config.auto_show,
            bubble_timeout_seconds=self._config.bubble_timeout_seconds,
            window_x=self._config.window_x,
            window_bottom_y=self._config.window_bottom_y,
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
        self.saveErrorChanged.emit()
        self.configSaved.emit()
        self.statusChanged.emit()
        self.refresh()
        return True

    @Slot()
    def refresh(self) -> None:
        """立即轮询一次余额与日志。"""
        config = self._effective_config()
        if not config.api_key or not config.base_url:
            return
        self._generation += 1
        generation = self._generation
        self._pending = {"usage": True, "logs": True}
        self._staged = {}
        self._get(config, "/api/usage/token/", generation, "usage", self._handle_usage)
        self._get(config, "/api/log/token", generation, "logs", self._handle_logs)

    @Slot(int, int)
    def savePosition(self, x: int, bottom_y: int) -> None:
        """QML 拖动结束后保存窗口位置。"""
        if self._config.window_x == x and self._config.window_bottom_y == bottom_y:
            return
        self._config = PetConfig(
            base_url=self._config.base_url,
            api_key=self._config.api_key,
            poll_interval_seconds=self._config.poll_interval_seconds,
            currency=self._config.currency,
            quota_per_unit=self._config.quota_per_unit,
            cny_rate=self._config.cny_rate,
            auto_show=self._config.auto_show,
            bubble_timeout_seconds=self._config.bubble_timeout_seconds,
            window_x=x,
            window_bottom_y=bottom_y,
            pet_image=self._config.pet_image,
        )
        try:
            save_pet_config(self._config_path, self._config)
        except OSError as exc:
            LOGGER.warning("桌宠位置写入失败: %s", exc)
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
        config = self._effective_config()
        if not config.api_key or not config.base_url:
            return "未配置：右键桌宠 → 设置"
        if self._last_error:
            return f"请求失败：{self._last_error}"
        if self._last_updated <= 0:
            return "正在获取…"
        stamp = datetime.fromtimestamp(self._last_updated).strftime("%H:%M:%S")
        return f"每 {config.poll_interval_seconds}s 刷新 · {stamp}"

    @Property(bool, notify=statusChanged)
    def hasError(self) -> bool:
        config = self._effective_config()
        return bool(config.api_key and config.base_url and self._last_error)

    # ------------------------------------------------------------------ 网络

    def _get(self, config: PetConfig, path: str, generation: int, key: str, handler) -> None:
        url = QUrl(config.base_url + path)
        request = QNetworkRequest(url)
        request.setRawHeader(b"Authorization", f"Bearer {config.api_key}".encode("utf-8"))
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
        self.usageChanged.emit()
        self.logsChanged.emit()
        self.statusChanged.emit()
