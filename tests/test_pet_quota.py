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
    BALANCE_SOURCE_ACCOUNT,
    BALANCE_SOURCE_TOKEN,
    billing_amount_to_quota,
    billing_usage_amount_to_quota,
    build_log_rows,
    format_compact_count,
    format_quota,
    format_quota_compact,
    format_quota_precise,
    local_midnight_timestamp,
    resolve_balance_source,
    resolve_display_currency,
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

    def test_compact_card_format_keeps_magnitude_readable(self):
        # 卡片宽度有限:超过一千必须简写,否则 "-¥48,132,920.48" 会被省略成读不出量级
        self.assertEqual(format_quota_compact(-3_296_775_375_482, "CNY", 500_000.0, 7.3),
                         "-¥48.13M")
        self.assertEqual(format_quota_compact(500_000, "CNY", 500_000.0, 7.3), "¥7.30")
        self.assertEqual(format_quota_compact(2_500_000_000, "USD", 500_000.0, 7.3), "$5K")
        self.assertEqual(format_quota_compact(0, "CNY", 500_000.0, 7.3), "¥0.00")
        self.assertEqual(format_quota_compact(-25_000, "USD", 500_000.0, 7.3), "-$0.05")
        # TOKENS 口径下就是纯数字简写,不带货币符号
        self.assertEqual(format_quota_compact(1_159_134_252, "TOKENS", 500_000.0, 7.3), "1.16B")

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

    def test_billing_amount_restores_site_display_unit(self):
        # billing 返回的是"站点展示口径"金额,必须先还原成 quota 再按桌宠口径格式化
        self.assertEqual(
            billing_amount_to_quota(990365.511636, "USD", 500_000.0, 7.3), 495_182_755_818.0
        )
        # CNY:站点用 7.3 汇率乘过,这里除回去
        self.assertEqual(
            billing_amount_to_quota(7300.0, "CNY", 500_000.0, 7.3), 500_000_000.0
        )
        # TOKENS:原值就是 quota
        self.assertEqual(billing_amount_to_quota(12345, "TOKENS", 500_000.0, 7.3), 12345.0)
        # 自定义币种:按站点自定义汇率还原
        self.assertEqual(
            billing_amount_to_quota(100.0, "CUSTOM", 500_000.0, 7.3, 2.0), 25_000_000.0
        )
        # 展示类型大小写/空值都按 USD 兜底(billing.go 的 default 分支就是 USD)
        self.assertEqual(billing_amount_to_quota(1.0, " usd ", 500_000.0, 7.3), 500_000.0)
        self.assertEqual(billing_amount_to_quota(1.0, "", 500_000.0, 7.3), 500_000.0)

    def test_billing_amount_handles_garbage(self):
        for bad in (None, "n/a", {}, float("nan"), float("inf"), True):
            with self.subTest(bad=bad):
                self.assertEqual(billing_amount_to_quota(bad, "USD", 500_000.0, 7.3), 0.0)
        # 汇率为 0 属于脏数据,按 1.0 兜底而不是抛错
        self.assertEqual(billing_amount_to_quota(73.0, "CNY", 500_000.0, 0.0), 36_500_000.0)

    def test_account_balance_is_subscription_minus_usage(self):
        # 站点关掉 DisplayTokenStatEnabled 后:subscription=余额+已用(美元),
        # usage=已用(美分),两者各自还原成 quota 后才能相减。
        total = billing_amount_to_quota(990365.511636, "USD", 500_000.0, 7.3)
        used = billing_usage_amount_to_quota(7583916.2626, "USD", 500_000.0, 7.3)
        balance = int(round(total - used))
        self.assertGreater(balance, 0)
        self.assertEqual(format_quota(balance, "USD", 500_000.0, 7.3), "$914,526.35")
        # 桌宠按 CNY 展示时用的是桌宠自己的换算,不掺站点口径
        self.assertEqual(format_quota(balance, "CNY", 500_000.0, 7.3), "¥6,676,042.35")
        self.assertEqual(format_quota(-2_500, "USD", 500_000.0, 7.3), "-$0.01")
        self.assertEqual(format_quota_precise(-2_500, "CNY", 500_000.0, 7.3), "-¥0.0365")

    def test_billing_usage_is_cents_not_dollars(self):
        """total_usage 是美分(billing.go:104 amount*100),必须除回去再和 subscription 相减。

        曾经按同一单位直接相减,把 $914,320 的余额算成了 -$6,593,550(-¥48M)。
        """
        # 站点实测值(USD 展示):subscription=余额+已用,usage=已用×100
        total = billing_amount_to_quota(990365.511636, "USD", 500_000.0, 7.3)
        used = billing_usage_amount_to_quota(7583916.2626, "USD", 500_000.0, 7.3)
        self.assertEqual(used, 37_919_581_313.0)
        balance = int(round(total - used))
        # 对上面板"当前余额 $914,320.57"(两次抓取有正常漂移)
        self.assertEqual(format_quota(balance, "USD", 500_000.0, 7.3), "$914,526.35")
        self.assertEqual(format_quota_compact(balance, "CNY", 500_000.0, 7.3), "¥6.68M")
        # 未除 100 的旧算法确实会算成巨额负数 —— 锁住这个回归
        wrong = int(round(total - billing_amount_to_quota(7583916.2626, "USD", 500_000.0, 7.3)))
        self.assertLess(wrong, -3_000_000_000_000)

    def test_billing_usage_amount_handles_garbage(self):
        self.assertEqual(billing_usage_amount_to_quota(None, "USD", 500_000.0, 7.3), 0.0)
        self.assertEqual(billing_usage_amount_to_quota("x", "USD", 500_000.0, 7.3), 0.0)
        self.assertEqual(billing_usage_amount_to_quota(True, "USD", 500_000.0, 7.3), 0.0)
        # CNY 展示口径下同样先除 100 再反推汇率
        self.assertEqual(
            billing_usage_amount_to_quota(730000.0, "CNY", 500_000.0, 7.3), 500_000_000.0
        )

    def test_resolve_balance_source_matrix(self):
        # auto:令牌无限额度才有必要改用账户余额
        self.assertEqual(resolve_balance_source("auto", True, True), BALANCE_SOURCE_ACCOUNT)
        self.assertEqual(resolve_balance_source("auto", True, False), BALANCE_SOURCE_TOKEN)
        self.assertEqual(resolve_balance_source("auto", False, True), BALANCE_SOURCE_TOKEN)
        # 显式要账户余额,但还没拿到 → 退回令牌,不显示空值
        self.assertEqual(resolve_balance_source("account", True, False), BALANCE_SOURCE_ACCOUNT)
        self.assertEqual(resolve_balance_source("account", False, False), BALANCE_SOURCE_TOKEN)
        # 显式要令牌口径:永远不切
        self.assertEqual(resolve_balance_source("token", True, True), BALANCE_SOURCE_TOKEN)
        # 未知值按 auto 处理
        self.assertEqual(resolve_balance_source("", True, True), BALANCE_SOURCE_ACCOUNT)

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
        # 默认跟随站点展示口径,避免站点显示 $ 而桌宠擅自换算成 ¥
        self.assertEqual(config.currency, "auto")
        self.assertEqual(config.quota_per_unit, 500_000.0)
        self.assertEqual(config.cny_rate, 7.3)
        self.assertTrue(config.auto_show)
        self.assertEqual(config.base_url, "")
        self.assertEqual(config.api_key, "")

    def test_display_currency_follows_site(self):
        # auto:跟随 /api/status 的 quota_display_type
        self.assertEqual(resolve_display_currency("auto", "USD"), "USD")
        self.assertEqual(resolve_display_currency("auto", "CNY"), "CNY")
        self.assertEqual(resolve_display_currency("auto", "TOKENS"), "TOKENS")
        self.assertEqual(resolve_display_currency("auto", "custom"), "CNY")
        # 站点口径缺失/未知 → 退回 OpenAI 默认的 USD
        self.assertEqual(resolve_display_currency("auto", ""), "USD")
        self.assertEqual(resolve_display_currency("auto", "WEIRD"), "USD")
        # 显式配置优先于站点
        self.assertEqual(resolve_display_currency("CNY", "USD"), "CNY")
        self.assertEqual(resolve_display_currency("USD", "CNY"), "USD")
        self.assertEqual(resolve_display_currency("TOKENS", "USD"), "TOKENS")
        # 大小写不敏感,垃圾值退回 USD
        self.assertEqual(resolve_display_currency("AUTO", "USD"), "USD")
        self.assertEqual(resolve_display_currency("yen", "USD"), "USD")

    def test_auto_currency_uses_site_rate_not_local_rate(self):
        # 站点 CNY 口径:反推额度用站点的 quota_per_unit/usd_exchange_rate,
        # 桌宠再按同一口径格式化,保证和面板数字一致而不是差 7.3 倍。
        self.assertEqual(parse_pet_config({"currency": "auto"}).currency, "auto")
        self.assertEqual(parse_pet_config({"currency": "USD"}).currency, "USD")
        with self.assertRaises(ValueError):
            parse_pet_config({"currency": "JPY"})

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

    def test_balance_source_defaults_and_validation(self):
        config = parse_pet_config({})
        self.assertEqual(config.balance_source, "auto")
        self.assertEqual(config.account_poll_interval_seconds, 300)

        config = parse_pet_config({
            "balance_source": "account",
            "account_poll_interval_seconds": 900,
        })
        self.assertEqual(config.balance_source, "account")
        self.assertEqual(config.account_poll_interval_seconds, 900)

        for bad in ({"balance_source": "wallet"}, {"balance_source": 1},
                    {"account_poll_interval_seconds": 10},      # < 30
                    {"account_poll_interval_seconds": 99999}):  # > 7200
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_pet_config(bad)

    def test_balance_source_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pet_config.json"
            save_pet_config(path, PetConfig(balance_source="account",
                                            account_poll_interval_seconds=600))
            loaded = load_pet_config(path)
            self.assertEqual(loaded.balance_source, "account")
            self.assertEqual(loaded.account_poll_interval_seconds, 600)

    def test_build_config_keeps_legacy_seven_arg_call(self):
        # 老调用(7 个位置参数)必须仍然可用,新字段走默认值
        config, error = build_config_from_user_input(
            "https://api.example.com", "sk-demo", "30", "CNY", "500000", "7.3", ""
        )
        self.assertEqual(error, "")
        self.assertEqual(config.balance_source, "auto")
        self.assertEqual(config.account_poll_interval_seconds, 300)

        config, error = build_config_from_user_input(
            "https://api.example.com", "sk-demo", "30", "CNY", "500000", "7.3", "",
            "manual", "account", "60",
        )
        self.assertEqual(error, "")
        self.assertEqual(config.balance_source, "account")
        self.assertEqual(config.account_poll_interval_seconds, 60)

        _, error = build_config_from_user_input(
            "https://api.example.com", "sk-demo", "30", "CNY", "500000", "7.3", "",
            "manual", "account", "abc",
        )
        self.assertEqual(error, "账户余额轮询间隔必须是整数秒")

    def test_log_poll_interval_round_trip(self):
        """日志窗口间隔必须能存能读能校验:它决定会不会把该路由打进 429。"""
        config, error = build_config_from_user_input(
            "https://api.example.com", "sk-demo", "30", "CNY", "500000", "7.3", "",
            "manual", "account", "60", "240",
        )
        self.assertEqual(error, "")
        self.assertEqual(config.log_poll_interval_seconds, 240)

        # 老调用不传第 11 个参数 → 用 180s 默认值(顶在 20 次/20 分钟死线上的是 60s)
        legacy, error = build_config_from_user_input(
            "https://api.example.com", "sk-demo", "30", "CNY", "500000", "7.3", "",
            "manual", "account", "60",
        )
        self.assertEqual(error, "")
        self.assertEqual(legacy.log_poll_interval_seconds, 180)

        _, error = build_config_from_user_input(
            "https://api.example.com", "sk-demo", "30", "CNY", "500000", "7.3", "",
            "manual", "account", "60", "5",
        )
        self.assertIn("log_poll_interval_seconds", error)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pet_log_interval.json"
            save_pet_config(path, PetConfig(log_poll_interval_seconds=420))
            self.assertEqual(load_pet_config(path).log_poll_interval_seconds, 420)

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
