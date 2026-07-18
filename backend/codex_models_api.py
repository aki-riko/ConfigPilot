# coding: utf-8
"""Codex 模型接口的后台请求与响应解析。"""

from __future__ import annotations

import json
import logging
import urllib.request

from backend.endpoint_urls import append_api_path


LOGGER = logging.getLogger(__name__)


def fetch_models_result(base_url: str, key: str, catalog_fetcher) -> dict:
    url = append_api_path(base_url, "models")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
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
