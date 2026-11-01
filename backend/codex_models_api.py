# coding: utf-8
"""Codex 模型接口的后台请求与响应解析。"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from backend.endpoint_urls import append_api_path
from backend.upstream_errors import UpstreamRequestError, explain_failure


LOGGER = logging.getLogger(__name__)


def _read_body(exc: urllib.error.HTTPError) -> bytes:
    """尽量读出错误体：上游的 message 是提示里最有用的部分。"""
    try:
        return exc.read() or b""
    except Exception:  # 读取失败不能掩盖原始错误
        LOGGER.debug("读取上游错误响应体失败", exc_info=True)
        return b""


def _looks_like_html(body: bytes) -> bool:
    head = (body or b"").lstrip()[:200].lower()
    return (
        head.startswith(b"<!doctype html")
        or head.startswith(b"<html")
        or b"<body" in head
    )


def fetch_models_result(base_url: str, key: str, catalog_fetcher) -> dict:
    url = append_api_path(base_url, "models")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        # 401/403/404/429 等：按状态码给出可操作提示，并带上上游原话。
        body = _read_body(exc)
        if _looks_like_html(body):
            # 404 页是网页 = 服务器根本没人处理这个路径（地址填错/不是中转站），
            # 不能套用"接口路径不存在"后还附一句 HTML，用户看不懂。
            raise UpstreamRequestError(
                explain_failure(
                    exc.code,
                    "返回的是网页而不是 JSON，API 地址可能填错了",
                    secret=key,
                ),
                status=exc.code,
            ) from exc
        raise UpstreamRequestError(
            explain_failure(exc.code, body, secret=key),
            status=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        raise UpstreamRequestError(
            explain_failure(None, str(getattr(exc, "reason", exc)), secret=key),
            status=None,
        ) from exc
    except TimeoutError as exc:
        raise UpstreamRequestError(
            explain_failure(None, "连接超时"), status=None
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        # 填成站点主页时的典型症状：200 + HTML，解析失败只说"Expecting value"没法看。
        raise UpstreamRequestError(
            explain_failure(200, raw, secret=key), status=200
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        # 填成站点主页时的典型症状：200 + HTML，解析失败只说"Expecting value"没法看。
        raise UpstreamRequestError(
            explain_failure(200, raw, secret=key), status=200
        ) from exc
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    ids = []
    for item in data or []:
        model_id = item.get("id") if isinstance(item, dict) else str(item)
        if model_id:
            ids.append(str(model_id))
    catalog = []
    has_reasoning = any(
        isinstance(item, dict)
        and isinstance(item.get("supported_reasoning_levels"), list)
        for item in data or []
    )
    if ids and not has_reasoning:
        try:
            catalog = catalog_fetcher()
        except Exception as exc:
            LOGGER.info("Codex 远端模型目录回退失败: %s", exc)
    return {"ids": ids, "models": data or [], "catalog": catalog}
