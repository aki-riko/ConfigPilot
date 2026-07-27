import base64
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from backend.codex_oauth import (
    CodexOAuthError,
    CodexOAuthSettings,
    exchange_refresh_token,
    load_codex_oauth_settings,
    parse_chatgpt_auth_json,
)


ROOT = Path(__file__).resolve().parents[1]


def jwt(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        return self.body[:size] if size >= 0 else self.body


class CodexOAuthTests(unittest.TestCase):
    def setUp(self):
        self.settings = CodexOAuthSettings(
            "https://auth.example.com/oauth/token",
            "public-client-id",
            17,
        )
        self.id_token = jwt(
            {
                "email": "user@example.com",
                "https://api.openai.com/auth": {
                    "chatgpt_account_id": "account-123",
                },
            }
        )

    def test_real_app_config_has_valid_oauth_settings(self):
        settings = load_codex_oauth_settings(ROOT / "app_config.json")
        self.assertEqual(settings.token_url, "https://auth.openai.com/oauth/token")
        self.assertTrue(settings.client_id.startswith("app_"))
        self.assertEqual(settings.timeout_seconds, 30)

    def test_non_https_token_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "app_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "codex_oauth": {
                            "token_url": "http://auth.example.com/oauth/token",
                            "client_id": "public-client-id",
                            "timeout_seconds": 30,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                load_codex_oauth_settings(config_path)

    def test_parse_flat_codex2api_json_with_camel_case(self):
        result = parse_chatgpt_auth_json(
            json.dumps(
                {
                    "refresh_token": "refresh-token",
                    "accessToken": "access-token",
                    "idToken": self.id_token,
                    "chatgpt_account_id": "account-flat",
                }
            )
        )
        self.assertEqual(
            result,
            {
                "refresh_token": "refresh-token",
                "access_token": "access-token",
                "id_token": self.id_token,
                "account_id": "account-flat",
            },
        )

    def test_parse_official_codex_auth_json(self):
        result = parse_chatgpt_auth_json(
            json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "tokens": {
                        "refresh_token": "refresh-token",
                        "access_token": "access-token",
                        "id_token": self.id_token,
                        "account_id": "account-123",
                    },
                }
            )
        )
        self.assertEqual(result["account_id"], "account-123")
        self.assertEqual(result["refresh_token"], "refresh-token")

    def test_parse_sub2api_single_account_json(self):
        result = parse_chatgpt_auth_json(
            json.dumps(
                {
                    "accounts": [
                        {
                            "name": "test",
                            "credentials": {
                                "refresh_token": "refresh-token",
                                "access_token": "access-token",
                                "id_token": self.id_token,
                            },
                        }
                    ]
                }
            )
        )
        self.assertEqual(result["account_id"], "account-123")

    def test_parse_rejects_multiple_accounts(self):
        payload = {
            "accounts": [
                {"credentials": {"refresh_token": "secret-one"}},
                {"credentials": {"refresh_token": "secret-two"}},
            ]
        }
        with self.assertRaisesRegex(ValueError, "每次只能导入一个") as caught:
            parse_chatgpt_auth_json(json.dumps(payload))
        self.assertNotIn("secret-one", str(caught.exception))
        self.assertNotIn("secret-two", str(caught.exception))

    def test_parse_rejects_access_token_only_json(self):
        with self.assertRaisesRegex(ValueError, "缺少 refresh_token"):
            parse_chatgpt_auth_json('{"accessToken":"access-only-secret"}')

    def test_refresh_exchange_uses_official_json_contract(self):
        calls = []

        def opener(request, timeout):
            calls.append((request, timeout))
            return FakeResponse(
                {
                    "id_token": self.id_token,
                    "access_token": "new-access-token",
                    "refresh_token": "rotated-refresh-token",
                }
            )

        result = exchange_refresh_token(
            "original-refresh-token",
            self.settings,
            urlopen=opener,
        )

        self.assertEqual(result["account_id"], "account-123")
        self.assertEqual(result["refresh_token"], "rotated-refresh-token")
        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.full_url, self.settings.token_url)
        self.assertEqual(timeout, 17)
        self.assertEqual(
            json.loads(request.data),
            {
                "client_id": "public-client-id",
                "grant_type": "refresh_token",
                "refresh_token": "original-refresh-token",
            },
        )
        self.assertEqual(request.get_header("Content-type"), "application/json")

    def test_refresh_exchange_retains_token_when_server_does_not_rotate_it(self):
        result = exchange_refresh_token(
            "original-refresh-token",
            self.settings,
            urlopen=lambda request, timeout: FakeResponse(
                {"id_token": self.id_token, "access_token": "new-access-token"}
            ),
        )
        self.assertEqual(result["refresh_token"], "original-refresh-token")

    def test_missing_id_token_is_rejected(self):
        with self.assertRaisesRegex(CodexOAuthError, "未返回 id_token"):
            exchange_refresh_token(
                "refresh-token",
                self.settings,
                urlopen=lambda request, timeout: FakeResponse(
                    {"access_token": "new-access-token"}
                ),
            )

    def test_http_error_is_classified_without_exposing_token(self):
        secret = "refresh-token-must-not-leak"

        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(
                    json.dumps(
                        {"error": {"code": "refresh_token_reused"}}
                    ).encode("utf-8")
                ),
            )

        with self.assertRaises(CodexOAuthError) as caught:
            exchange_refresh_token(secret, self.settings, urlopen=opener)
        self.assertIn("已被使用", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))

    def test_invalid_jwt_is_rejected(self):
        with self.assertRaisesRegex(CodexOAuthError, "不是有效 JWT"):
            exchange_refresh_token(
                "refresh-token",
                self.settings,
                urlopen=lambda request, timeout: FakeResponse(
                    {
                        "id_token": "invalid",
                        "access_token": "new-access-token",
                    }
                ),
            )


if __name__ == "__main__":
    unittest.main()
