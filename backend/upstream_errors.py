# coding: utf-8
"""把上游 HTTP 错误码翻译成用户能照着做的中文提示。

上游（OpenAI 兼容中转站）返回的错误体格式各家不同，但状态码语义基本一致：

* new-api / one-api：``{"error": {"message": "...", "type": "new_api_error"}}``
* 官方 OpenAI：``{"error": {"message": "...", "type": "invalid_request_error"}}``
* 部分网关：``{"message": "..."}`` / ``{"error": "..."}``
* 反代或纯静态站：一页 HTML（说明地址根本不是 API 端点）

本模块只负责"读懂 + 说人话"，不参与任何重试或来源切换决策，
避免把提示逻辑散落在各个调用点里各说各话。
"""

from __future__ import annotations

import json
from typing import Any

# 单个上游 message 最多展示这么多字符：错误体偶尔会带上整段堆栈或 HTML。
_MAX_SERVER_MESSAGE = 240


class UpstreamRequestError(RuntimeError):
    """上游请求失败，消息已可读（含状态码与处置建议）。"""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


# 状态码 -> 用户下一步该做什么。措辞刻意写成"动作"而不是"原因"。
STATUS_HINTS: dict[int, str] = {
    400: "上游拒绝了请求参数：模型名可能不存在，或请求格式不被支持",
    401: "API Key 无效、已过期或未填写，请检查「API 密钥」后重试",
    402: "账户额度不足或未付费，请到中转站充值后重试",
    403: "上游拒绝访问：Key 可能没有该模型的权限，或被站点防护拦截",
    404: "接口路径不存在，请检查 API 地址是否正确（通常应以 /v1 结尾）",
    405: "接口方法不被支持，请确 API 地址指向的是兼容 OpenAI 的中转站",
    408: "上游请求超时，请稍后重试",
    409: "上游状态冲突，请稍后重试",
    413: "请求内容过大，请减少内容后重试",
    415: "上游不支持该内容类型，请检查 API 地址",
    422: "上游无法处理该请求参数，请检查模型名与参数",
    429: "请求过于频繁或已触发限流，请稍后再试",
    451: "上游因合规原因拒绝提供该内容",
    500: "上游服务器内部错误（与本地配置无关），请稍后重试",
    502: "上游网关错误，中转站可能正在重启或临时不可用",
    503: "上游服务暂不可用，请稍后重试",
    504: "上游网关超时，请稍后重试",
}


def _clean(text: Any, limit: int = _MAX_SERVER_MESSAGE) -> str:
    """压掉换行与连续空白，避免把整段 HTML 塞进通知条。"""
    value = " ".join(str(text or "").split())
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value


def redact(text: str, secret: str) -> str:
    """把可能被上游回显的密钥从提示里抹掉。"""
    value = str(text or "")
    token = str(secret or "").strip()
    if len(token) >= 8 and token in value:
        return value.replace(token, "***")
    return value


def _looks_like_html(body: str) -> bool:
    head = body.lstrip()[:200].lower()
    return head.startswith("<!doctype html") or head.startswith("<html") or "<body" in head


def _text_body(body: bytes | str | None) -> str:
    if body is None:
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", "replace")
    return str(body)


def server_message(body: bytes | str | None) -> str:
    """从错误响应体里取出上游自己给的那句话。

    JSON 解析失败时按文本处理：HTML 页面会被识别成"地址不是 API 端点"，
    因为这是把 API 地址填成站点首页时最常见的症状。
    """
    stripped = _text_body(body).strip()
    if not stripped:
        return ""
    try:
        payload = json.loads(stripped)
    except (ValueError, UnicodeDecodeError):
        if _looks_like_html(stripped):
            return "返回的是网页而不是 JSON，API 地址可能填成了站点主页"
        return _clean(stripped)
    message = _payload_message(payload)
    return _clean(message) if message else ""


def _payload_message(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        for key in ("message", "msg", "detail", "code"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("message", "msg", "detail", "error_description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    code = payload.get("code")
    return code.strip() if isinstance(code, str) else ""


def status_hint(status: int | None) -> str:
    if status is None:
        return "没有收到上游的 HTTP 响应，请检查网络、代理或地址是否可达"
    if 200 <= status < 300:
        return "上游返回的内容无法解析，请确认 API 地址指向兼容 OpenAI 的接口"
    return STATUS_HINTS.get(status, "上游返回了未预期的错误码，请检查中转站状态")


def explain_failure(
    status: int | None,
    body: bytes | str | None = None,
    *,
    secret: str = "",
) -> str:
    """拼出一条可直接展示的失败说明：状态码 + 处置建议 + 上游原话。"""
    detail = redact(server_message(body), secret)
    hint = status_hint(status)
    if status is None:
        head = "请求失败"
    elif 200 <= status < 300:
        # 2xx 却走到失败分支 = 响应体不是预期的 JSON，问题在内容而非状态码
        head = f"HTTP {status}（响应不是有效的 JSON）"
    else:
        head = f"HTTP {status}"
    first = f"{head}：{hint}"
    if not detail:
        return first
    # 上游原话常与建议重复（如 "Invalid token"），仍保留：用户反馈问题时要靠它。
    return f"{first}\n上游返回：{detail}"
