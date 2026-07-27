# coding: utf-8
"""用 Codex 官方 OAuth 刷新协议把 refresh token 换成可持久化凭据。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Callable
import urllib.error
import urllib.request
from urllib.parse import urlparse


MAX_RESPONSE_BYTES = 64 * 1024
MAX_IMPORT_BYTES = 256 * 1024
REFRESH_URL_OVERRIDE_ENV = "CODEX_REFRESH_TOKEN_URL_OVERRIDE"
CLIENT_ID_OVERRIDE_ENV = "CODEX_APP_SERVER_LOGIN_CLIENT_ID"


class CodexOAuthError(RuntimeError):
    """不包含任何 token 原文的 OAuth 登录错误。"""


@dataclass(frozen=True)
class CodexOAuthSettings:
    token_url: str
    client_id: str
    timeout_seconds: float


def _required_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"配置项 codex_oauth.{key} 必须是非空字符串")
    return value.strip()


def load_codex_oauth_settings(path: str | Path) -> CodexOAuthSettings:
    """从应用配置加载公开 OAuth 客户端参数，并兼容 Codex 官方环境覆盖项。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    oauth = data.get("codex_oauth") if isinstance(data, dict) else None
    if not isinstance(oauth, dict):
        raise ValueError("配置项 codex_oauth 必须是对象")

    token_url = os.getenv(REFRESH_URL_OVERRIDE_ENV, "").strip()
    if not token_url:
        token_url = _required_string(oauth, "token_url")
    parsed_url = urlparse(token_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("配置项 codex_oauth.token_url 必须是有效 HTTPS 地址")

    client_id = os.getenv(CLIENT_ID_OVERRIDE_ENV, "").strip()
    if not client_id:
        client_id = _required_string(oauth, "client_id")

    timeout = oauth.get("timeout_seconds")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise ValueError("配置项 codex_oauth.timeout_seconds 必须是数字")
    if not 1 <= float(timeout) <= 120:
        raise ValueError("配置项 codex_oauth.timeout_seconds 必须位于 1 到 120 之间")
    return CodexOAuthSettings(token_url, client_id, float(timeout))


def _read_limited(response) -> bytes:
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise CodexOAuthError("OAuth 服务返回内容过大")
    return body


def _json_object(body: bytes) -> dict:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CodexOAuthError("OAuth 服务返回了无效 JSON") from exc
    if not isinstance(value, dict):
        raise CodexOAuthError("OAuth 服务返回格式无效")
    return value


def _oauth_error_message(status: int, body: bytes) -> str:
    code = ""
    try:
        payload = _json_object(body)
        error = payload.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or error.get("type") or "").strip()
        elif isinstance(error, str):
            code = error.strip()
        if not code:
            code = str(payload.get("code") or "").strip()
    except CodexOAuthError:
        pass
    known = {
        "refresh_token_expired": "refresh token 已过期，请重新获取",
        "refresh_token_reused": "refresh token 已被使用，请使用最新 token",
        "refresh_token_invalidated": "refresh token 已撤销，请重新登录",
        "invalid_grant": "refresh token 无效或已失效",
    }
    if code in known:
        return known[code]
    if status in {400, 401, 403}:
        return "refresh token 无效、已失效或不属于 Codex OAuth 客户端"
    return f"OAuth 服务请求失败（HTTP {status}）"


def _jwt_payload(token: str, token_name: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise CodexOAuthError(f"OAuth 服务返回的 {token_name} 不是有效 JWT")
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CodexOAuthError(f"OAuth 服务返回的 {token_name} 无法解析") from exc
    if not isinstance(payload, dict):
        raise CodexOAuthError(f"OAuth 服务返回的 {token_name} 载荷无效")
    return payload


def _account_id_from_payload(payload: dict) -> str:
    auth = payload.get("https://api.openai.com/auth")
    if isinstance(auth, dict):
        account_id = auth.get("chatgpt_account_id")
        if isinstance(account_id, str) and account_id.strip():
            return account_id.strip()
    account_id = payload.get("chatgpt_account_id")
    return account_id.strip() if isinstance(account_id, str) else ""


def _first_string(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _credential_candidates(value) -> list[dict]:
    if isinstance(value, list):
        candidates = []
        for item in value:
            candidates.extend(_credential_candidates(item))
        return candidates
    if not isinstance(value, dict):
        return []

    accounts = value.get("accounts")
    if isinstance(accounts, list):
        candidates = []
        for account in accounts:
            if not isinstance(account, dict):
                continue
            credentials = account.get("credentials")
            if isinstance(credentials, dict):
                candidates.append(credentials)
        return candidates

    tokens = value.get("tokens")
    if isinstance(tokens, dict):
        return [tokens]
    return [value]


def _load_import_payload(raw_json: str):
    text = str(raw_json or "").lstrip("\ufeff").strip()
    if not text:
        raise ValueError("认证 JSON 不能为空")
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ValueError("认证 JSON 不能超过 256 KiB")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("认证 JSON 格式无效，请检查是否复制完整") from exc


def _select_credential_source(payload) -> dict:
    candidates = []
    for candidate in _credential_candidates(payload):
        if any(
            _first_string(candidate, *aliases)
            for aliases in (
                ("refresh_token", "refreshToken"),
                ("access_token", "accessToken"),
                ("id_token", "idToken"),
            )
        ):
            candidates.append(candidate)
    if not candidates:
        raise ValueError("认证 JSON 中未找到 token 凭据")
    if len(candidates) != 1:
        raise ValueError("认证 JSON 包含多个账号，ConfigPilot 每次只能导入一个")
    return candidates[0]


def _normalized_import_tokens(source: dict) -> dict:
    return {
        "refresh_token": _first_string(source, "refresh_token", "refreshToken"),
        "access_token": _first_string(source, "access_token", "accessToken"),
        "id_token": _first_string(source, "id_token", "idToken"),
        "account_id": _first_string(
            source,
            "account_id",
            "accountId",
            "chatgpt_account_id",
            "chatgptAccountId",
        ),
    }


def _populate_import_account_id(tokens: dict, source: dict):
    if not tokens["account_id"]:
        account = source.get("account")
        if isinstance(account, dict):
            tokens["account_id"] = _first_string(account, "id")
    if not tokens["account_id"]:
        for token_name in ("id_token", "access_token"):
            token = tokens[token_name]
            if not token:
                continue
            tokens["account_id"] = _account_id_from_payload(
                _jwt_payload(token, token_name)
            )
            if tokens["account_id"]:
                break


def parse_chatgpt_auth_json(raw_json: str) -> dict:
    """解析 Codex auth.json 或 codex2api 兼容的单账号 JSON。"""
    payload = _load_import_payload(raw_json)
    source = _select_credential_source(payload)
    tokens = _normalized_import_tokens(source)
    if not tokens["refresh_token"]:
        raise ValueError("认证 JSON 中缺少 refresh_token")
    _populate_import_account_id(tokens, source)
    return {key: value for key, value in tokens.items() if value}


def exchange_refresh_token(
    refresh_token: str,
    settings: CodexOAuthSettings,
    *,
    urlopen: Callable = urllib.request.urlopen,
) -> dict:
    """交换一次 refresh token；成功结果可直接交给 CodexConfigStore。"""
    token = str(refresh_token or "").strip()
    if not token:
        raise ValueError("refresh token 不能为空")

    body = json.dumps(
        {
            "client_id": settings.client_id,
            "grant_type": "refresh_token",
            "refresh_token": token,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        settings.token_url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.timeout_seconds) as response:
            payload = _json_object(_read_limited(response))
    except urllib.error.HTTPError as exc:
        error_body = exc.read(MAX_RESPONSE_BYTES)
        raise CodexOAuthError(_oauth_error_message(exc.code, error_body)) from exc
    except urllib.error.URLError as exc:
        raise CodexOAuthError("无法连接 Codex OAuth 服务，请检查网络") from exc
    except TimeoutError as exc:
        raise CodexOAuthError("连接 Codex OAuth 服务超时") from exc

    access_token = payload.get("access_token")
    id_token = payload.get("id_token")
    rotated_refresh_token = payload.get("refresh_token") or token
    if not isinstance(access_token, str) or not access_token.strip():
        raise CodexOAuthError("OAuth 服务未返回 access_token")
    if not isinstance(id_token, str) or not id_token.strip():
        raise CodexOAuthError("OAuth 服务未返回 id_token，不能建立 Codex 登录")
    if not isinstance(rotated_refresh_token, str) or not rotated_refresh_token.strip():
        raise CodexOAuthError("OAuth 服务未返回可用的 refresh_token")

    id_token = id_token.strip()
    account_id = _account_id_from_payload(_jwt_payload(id_token, "id_token"))
    if not account_id:
        account_id = _account_id_from_payload(
            _jwt_payload(access_token.strip(), "access_token")
        )
    if not account_id:
        raise CodexOAuthError("token 中缺少 chatgpt_account_id，不能建立 Codex 登录")
    return {
        "id_token": id_token,
        "access_token": access_token.strip(),
        "refresh_token": rotated_refresh_token.strip(),
        "account_id": account_id,
    }
