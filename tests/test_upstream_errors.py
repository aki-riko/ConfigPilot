# coding: utf-8
"""上游错误码 -> 中文可操作提示 的回归测试。

样本取自真实中转站响应（2026-11 实测）：
* api.relyx.cc 无效 Key 的 /v1/models -> 401 + new-api 的 error.message
* api.relyx.cc 不存在的路径        -> 404 + OpenAI 格式 error.message
* 把 API 地址填成站点主页          -> 200 + HTML
"""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.codex_models_api import fetch_models_result
from backend.upstream_errors import (
    STATUS_HINTS,
    UpstreamRequestError,
    explain_failure,
    redact,
    server_message,
    status_hint,
)
from tests.qt_test_utils import wait_for_idle


NEW_API_401 = (
    b'{"error":{"code":"","message":"Invalid token (request id: '
    b'202611011909233336882928268d9d6IXN6iv67)","type":"new_api_error"}}'
)
OPENAI_404 = (
    b'{"error":{"message":"Invalid URL (GET /v1/no-such-endpoint)",'
    b'"type":"invalid_request_error","param":"","code":""}}'
)
SITE_HOMEPAGE = (
    b"<!doctype html>\n<html lang=\"en\">\n  <head>\n    <title>New API</title>\n"
    b"  </head>\n  <body><div id=\"app\"></div></body>\n</html>"
)


def http_error(status, body, url="https://relay.example/v1/models"):
    return urllib.error.HTTPError(
        url, status, "reason-text", {}, io.BytesIO(body)
    )


class ServerMessageParsingTests(unittest.TestCase):
    """各家错误体格式都要能取出那句"上游原话"。"""

    def test_new_api_shape(self):
        self.assertIn("Invalid token", server_message(NEW_API_401))

    def test_openai_shape_with_param_and_code(self):
        self.assertIn("Invalid URL", server_message(OPENAI_404))

    def test_flat_message_and_error_string_shapes(self):
        self.assertEqual(server_message(b'{"message":"quota exceeded"}'), "quota exceeded")
        self.assertEqual(server_message(b'{"error":"bad key"}'), "bad key")

    def test_html_is_recognised_as_wrong_endpoint(self):
        self.assertIn("网页", server_message(SITE_HOMEPAGE))
    def test_empty_and_non_text_bodies_do_not_raise(self):
        for body in (None, b"", "   ", b"\xff\xfe\x00"):
            with self.subTest(body=body):
                self.assertIsInstance(server_message(body), str)

    def test_long_message_is_clipped(self):
        message = server_message(json.dumps({"message": "x" * 5000}).encode())
        self.assertLessEqual(len(message), 240)
        self.assertTrue(message.endswith("…"))


class ExplainFailureTests(unittest.TestCase):
    """用户看到的提示必须能指导下一步动作。"""

    def test_401_tells_user_to_check_api_key(self):
        text = explain_failure(401, NEW_API_401)
        self.assertIn("HTTP 401", text)
        self.assertIn("API Key", text)
        self.assertIn("Invalid token", text)

    def test_every_documented_status_has_a_hint(self):
        for status in (400, 401, 402, 403, 404, 405, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                self.assertNotIn("未预期", status_hint(status))

    def test_unknown_status_falls_back_to_generic_hint(self):
        self.assertIn("未预期", status_hint(418))

    def test_missing_status_explains_network_layer(self):
        text = explain_failure(None, "Connection refused")
        self.assertIn("请求失败", text)
        self.assertIn("没有收到上游的 HTTP 响应", text)
        self.assertIn("Connection refused", text)

    def test_bodyless_failure_still_carries_the_hint(self):
        text = explain_failure(502, b"")
        self.assertIn("HTTP 502", text)
        self.assertNotIn("上游返回：", text)

    def test_secret_echoed_by_upstream_is_redacted(self):
        secret = "sk-live-abcdef123456"
        body = json.dumps({"error": {"message": f"invalid key {secret}"}}).encode()
        text = explain_failure(401, body, secret=secret)
        self.assertNotIn(secret, text)
        self.assertIn("***", text)

    def test_short_tokens_are_not_treated_as_secrets(self):
        # 太短的值做替换会把正常文字也毁掉，宁可不动
        self.assertEqual(redact("token abc is bad", "abc"), "token abc is bad")


class FetchModelsFailureTests(unittest.TestCase):
    """获取模型这条真实路径要产出可读提示，而不是 "HTTP 401: Unauthorized"。"""

    def test_401_raises_readable_error(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=http_error(401, NEW_API_401),
        ):
            with self.assertRaises(UpstreamRequestError) as caught:
                fetch_models_result("https://relay.example/v1", "sk-bad", lambda: [])
        message = str(caught.exception)
        self.assertEqual(caught.exception.status, 401)
        self.assertIn("API Key", message)
        self.assertIn("Invalid token", message)

    def test_404_mentions_api_address(self):
        with patch("urllib.request.urlopen", side_effect=http_error(404, OPENAI_404)):
            with self.assertRaises(UpstreamRequestError) as caught:
                fetch_models_result("https://relay.example/v1", "sk-bad", lambda: [])
        self.assertIn("/v1", str(caught.exception))

    def test_404_html_page_does_not_dump_raw_html(self):
        """真实样本：api.9li.life 的 404 是 openresty 的 HTML 页，不能整页塞进通知。"""
        html_404 = (
            b"<html>\n<head><title>404 Not Found</title></head>\n<body>\n"
            b"<center><h1>404 Not Found</h1></center>\n<hr>"
            b"<center>openresty</center>\n</body>\n</html>"
        )
        with patch("urllib.request.urlopen", side_effect=http_error(404, html_404)):
            with self.assertRaises(UpstreamRequestError) as caught:
                fetch_models_result("https://relay.example/v1", "sk-bad", lambda: [])
        message = str(caught.exception)
        self.assertIn("HTTP 404", message)
        self.assertIn("网页", message)
        self.assertNotIn("<html>", message)
        self.assertNotIn("openresty", message)

    def test_connection_error_is_reported_as_network_problem(self):
        reason = urllib.error.URLError("getaddrinfo failed")
        with patch("urllib.request.urlopen", side_effect=reason):
            with self.assertRaises(UpstreamRequestError) as caught:
                fetch_models_result("https://nope.example/v1", "sk-bad", lambda: [])
        self.assertIsNone(caught.exception.status)
        self.assertIn("网络", str(caught.exception))

    def test_html_200_body_reports_wrong_endpoint(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return SITE_HOMEPAGE

        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaises(UpstreamRequestError) as caught:
                fetch_models_result("https://relay.example/v1", "sk-key", lambda: [])
        message = str(caught.exception)
        self.assertIn("网页", message)
        # 2xx 不是"错误码"，提示要说明是响应内容解析不了
        self.assertIn("不是有效的 JSON", message)
        self.assertNotIn("未预期的错误码", message)

    def test_success_path_still_returns_models(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"data":[{"id":"gpt-5.6-sol"}]}'

        with patch("urllib.request.urlopen", return_value=Response()):
            result = fetch_models_result("https://relay.example/v1", "sk-key", lambda: [])
        self.assertEqual(result["ids"], ["gpt-5.6-sol"])


class ModelsFetchNotificationTests(unittest.TestCase):
    """端到端：界面通知里必须是翻译后的提示。"""

    def _config(self):
        import importlib

        sys.modules.pop("backend.codex_config", None)
        codex_config = importlib.import_module("backend.codex_config")
        return codex_config

    def test_notify_carries_status_hint_for_401(self):
        codex_config = self._config()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            with patch(
                "urllib.request.urlopen",
                side_effect=http_error(401, NEW_API_401),
            ):
                config.fetchModels("https://relay.example/v1", "sk-bad")
                wait_for_idle(config, "modelsLoading")

        failures = [item for item in notices if item[1] == "获取失败"]
        self.assertTrue(failures, "预期弹出「获取失败」")
        level, _, message = failures[-1]
        self.assertEqual(level, 3)
        self.assertIn("API Key", message)
        self.assertIn("Invalid token", message)
        self.assertNotIn("HTTP 401: Unauthorized", message)

    def test_non_http_failure_keeps_its_own_text(self):
        """非网络异常（例如 IndexError）不能被包成误导性提示。"""
        codex_config = self._config()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            with patch(
                "urllib.request.urlopen",
                side_effect=IndexError("内部解析失败"),
            ):
                config.fetchModels("https://relay.example/v1", "sk-key")
                wait_for_idle(config, "modelsLoading")

        self.assertTrue(any(m == "内部解析失败" for _, _, m in notices))


class PetFriendlyFailureTests(unittest.TestCase):
    """桌宠余额监控也复用同一套状态码口径。"""

    def test_401_and_402_are_explained(self):
        from backend.newapi_pet import NewApiPet

        self.assertIn("API Key", NewApiPet._friendly_failure(401, "HTTP 401"))
        self.assertIn("额度不足", NewApiPet._friendly_failure(402, "HTTP 402"))

    def test_existing_messages_are_unchanged(self):
        from backend.newapi_pet import NewApiPet

        self.assertIn("不是 new-api 站点", NewApiPet._friendly_failure(404, "HTTP 404"))
        self.assertIn("前置防护", NewApiPet._friendly_failure(403, "HTTP 403"))
        self.assertEqual(NewApiPet._friendly_failure(429, "HTTP 429"), "HTTP 429")


if __name__ == "__main__":
    unittest.main()
