import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from backend.pet_config import (
    PetConfig,
    build_config_from_user_input,
    load_pet_config,
    parse_pet_config,
    resolve_effective_config,
    resolve_pet_config_path,
    save_pet_config,
)
from backend.quota_math import (
    build_log_rows,
    format_compact_count,
    format_quota,
    format_quota_precise,
    local_midnight_timestamp,
    summarize_today,
)


def _ts(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute).timestamp()


class QuotaMathTests(unittest.TestCase):
    def test_quota_to_display_formats(self):
        # QuotaPerUnit=500000 -> $1
        self.assertEqual(format_quota(500_000, "USD", 500_000.0, 7.3), "$1.00")
        self.assertEqual(format_quota(500_000, "CNY", 500_000.0, 7.3), "¥7.30")
        self.assertEqual(format_quota(1_234_567, "TOKENS", 500_000.0, 7.3), "1,234,567")
        self.assertEqual(format_quota(0, "CNY", 500_000.0, 7.3), "¥0.00")

    def test_precise_format_trims_zeros(self):
        # 2500/500000 = $0.005 -> CNY 0.0365
        self.assertEqual(format_quota_precise(2_500, "CNY", 500_000.0, 7.3), "¥0.0365")
        self.assertEqual(format_quota_precise(1_000_000, "CNY", 500_000.0, 7.3), "¥14.6")
        self.assertEqual(format_quota_precise(0, "CNY", 500_000.0, 7.3), "¥0")
        self.assertEqual(format_quota_precise(500_000, "USD", 500_000.0, 7.3), "$1")

    def test_compact_count_abbreviates_millions_and_billions(self):
        # K=千 / M=百万 / B=十亿,小数位随量级收敛并去掉多余的 0
        cases = {
            0: "0",
            999: "999",
            1_000: "1K",
            54_818: "54.8K",
            282_050: "282K",
            1_159_134: "1.16M",
            119_134_252: "119.13M",
            1_159_134_252: "1.16B",
            2_500_000_000: "2.5B",
            1_234_567_890_123: "1.23T",
            -54_818: "-54.8K",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_compact_count(value), expected)

    def test_compact_count_handles_bad_input(self):
        self.assertEqual(format_compact_count(None), "0")
        self.assertEqual(format_compact_count(True), "0")  # bool 不是数量
        self.assertEqual(format_compact_count("12"), "12")
        self.assertEqual(format_compact_count("not-a-number"), "0")
        self.assertEqual(format_compact_count(float("inf")), "0")

    def test_summarize_today_only_counts_today_consumes(self):
        now = datetime(2026, 2, 7, 15, 0)
        logs = [
            {"created_at": _ts(2026, 2, 7, 14), "type": 2, "quota": 100,
             "prompt_tokens": 10, "completion_tokens": 20},
            {"created_at": _ts(2026, 2, 7, 9), "type": 2, "quota": 50,
             "prompt_tokens": 5, "completion_tokens": 5},
            {"created_at": _ts(2026, 2, 6, 23), "type": 2, "quota": 999,
             "prompt_tokens": 100, "completion_tokens": 100},  # 昨天,不计
            {"created_at": _ts(2026, 2, 7, 12), "type": 1, "quota": 700,
             "prompt_tokens": 1, "completion_tokens": 1},  # 充值,不计
            {"created_at": "bad", "type": 2, "quota": 5},  # 脏数据,跳过
            "not-a-dict",  # 非法条目,跳过
        ]
        stats = summarize_today(logs, now=now)
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["quota"], 150)
        self.assertEqual(stats["prompt_tokens"], 15)
        self.assertEqual(stats["completion_tokens"], 25)

    def test_summarize_today_empty_and_midnight_boundary(self):
        now = datetime(2026, 2, 7, 0, 30)
        midnight = local_midnight_timestamp(now)
        logs = [
            {"created_at": midnight, "type": 2, "quota": 7,
             "prompt_tokens": 1, "completion_tokens": 2},  # 零点整,计入
            {"created_at": midnight - 1, "type": 2, "quota": 8,
             "prompt_tokens": 1, "completion_tokens": 2},  # 零点前1秒,不计
        ]
        stats = summarize_today(logs, now=now)
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["quota"], 7)
        self.assertEqual(summarize_today(None, now=now)["count"], 0)

    def test_build_log_rows_shape_and_limit(self):
        logs = [
            {"created_at": _ts(2026, 2, 7, 14, 5), "type": 2, "quota": 2_500,
             "prompt_tokens": 120, "completion_tokens": 30, "model_name": "gpt-5.5"},
            {"created_at": _ts(2026, 2, 7, 13, 0), "type": 5, "quota": 0,
             "model_name": "error"},  # 错误日志不进消费列表
        ]
        rows = build_log_rows(logs, "CNY", 500_000.0, 7.3, limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "gpt-5.5")
        self.assertEqual(rows[0]["quotaText"], "¥0.0365")
        self.assertEqual(rows[0]["tokens"], "+120 / +30")
        self.assertEqual(len(build_log_rows(logs, "CNY", 500_000.0, 7.3, limit=0)), 0)

    def test_build_log_rows_abbreviates_tokens(self):
        logs = [
            {"created_at": _ts(2026, 2, 7, 14, 5), "type": 2, "quota": 2_500,
             "prompt_tokens": 54_818, "completion_tokens": 1_159_134_252,
             "model_name": "gpt-5.6-sol"},
        ]
        rows = build_log_rows(logs, "CNY", 500_000.0, 7.3, limit=10)
        self.assertEqual(rows[0]["tokens"], "+54.8K / +1.16B")


class PetConfigTests(unittest.TestCase):
    def test_parse_defaults_from_empty_dict(self):
        config = parse_pet_config({})
        self.assertEqual(config.poll_interval_seconds, 120)
        self.assertEqual(config.currency, "CNY")
        self.assertEqual(config.quota_per_unit, 500_000.0)
        self.assertEqual(config.cny_rate, 7.3)
        self.assertTrue(config.auto_show)
        self.assertEqual(config.base_url, "")
        self.assertEqual(config.api_key, "")

    def test_parse_rejects_invalid_values(self):
        cases = [
            {"currency": "JPY"},
            {"base_url": "ftp://example.com"},
            {"poll_interval_seconds": 1},
            {"poll_interval_seconds": "60"},
            {"quota_per_unit": -1},
            {"cny_rate": 0},
            {"auto_show": "yes"},
            {"window_x": -2},
            "not-a-dict",
        ]
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    parse_pet_config(data)

    def test_base_url_trailing_slash_is_trimmed(self):
        config = parse_pet_config({"base_url": "https://api.example.com/"})
        self.assertEqual(config.base_url, "https://api.example.com")

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "pet_config.json"
            config = PetConfig(
                base_url="https://api.example.com",
                api_key="sk-demo",
                poll_interval_seconds=30,
                currency="USD",
                quota_per_unit=500_000.0,
                cny_rate=7.3,
                window_x=100,
                window_bottom_y=200,
            )
            save_pet_config(path, config)
            loaded = load_pet_config(path)
            self.assertEqual(loaded, config)

    def test_load_missing_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_pet_config(Path(tmp) / "absent.json")
            self.assertEqual(config, PetConfig())

    def test_build_config_from_user_input(self):
        config, error = build_config_from_user_input(
            "https://api.example.com/", "sk-demo", "30", "CNY", "500000", "7.3", ""
        )
        self.assertEqual(error, "")
        self.assertEqual(config.base_url, "https://api.example.com")
        self.assertEqual(config.poll_interval_seconds, 30)

        bad_cases = [
            ("https://api.example.com", "sk-1", "abc", "CNY", "500000", "7.3", ""),
            ("https://api.example.com", "sk-1", "30", "CNY", "x", "7.3", ""),
            ("https://api.example.com", "sk-1", "30", "CNY", "500000", "x", ""),
            ("https://api.example.com", "sk-1", "0", "CNY", "500000", "7.3", ""),
            ("", "sk-1", "30", "CNY", "500000", "7.3", ""),  # 有 Key 必须有地址
            ("", "", "30", "CNY", "500000", "7.3", ""),  # 全空也允许(清空配置)
        ]
        for case in bad_cases:
            with self.subTest(case=case):
                parsed, error = build_config_from_user_input(*case)
                if case == ("", "", "30", "CNY", "500000", "7.3", ""):
                    self.assertEqual(error, "")
                else:
                    self.assertNotEqual(error, "")
                    self.assertEqual(parsed, PetConfig())

    def test_env_overrides(self):
        base = PetConfig(base_url="https://from-file.example.com", api_key="sk-file")
        effective = resolve_effective_config(
            base,
            environment={
                "CONFIGPILOT_NEWAPI_BASE": "https://from-env.example.com/",
                "CONFIGPILOT_NEWAPI_KEY": "sk-env",
            },
        )
        self.assertEqual(effective.base_url, "https://from-env.example.com")
        self.assertEqual(effective.api_key, "sk-env")
        untouched = resolve_effective_config(base, environment={})
        self.assertEqual(untouched.base_url, "https://from-file.example.com")

    def test_config_path_layout(self):
        path = resolve_pet_config_path(
            platform_name="nt",
            environment={"LOCALAPPDATA": "C:\\Users\\demo\\AppData\\Local"},
        )
        self.assertEqual(
            path,
            Path("C:\\Users\\demo\\AppData\\Local") / "ConfigPilot" / "pet_config.json",
        )
        path = resolve_pet_config_path(
            platform_name="posix",
            environment={},
            home="/home/demo",
        )
        self.assertEqual(path, Path("/home/demo/.config/ConfigPilot/pet_config.json"))


if __name__ == "__main__":
    unittest.main()
