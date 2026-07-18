import json
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QObject, Signal

from backend.app_settings import load_app_settings
from backend.app_updater import AppUpdater


ROOT = Path(__file__).resolve().parents[1]


class FakeEngineUpdater(QObject):
    updateAvailable = Signal(str, str, str, str)
    upToDate = Signal(str)
    checkFailed = Signal(str)
    downloadProgress = Signal(int, int)
    downloadFinished = Signal(str)
    downloadFailed = Signal(str)

    def __init__(self, repo, current_version, asset_keyword, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_version = current_version
        self.asset_keyword = asset_keyword
        self.check_count = 0
        self.download_urls = []
        self.browser_urls = []
        self.install_calls = []
        self.install_result = True

    def checkForUpdate(self):
        self.check_count += 1

    def downloadUpdate(self, url):
        self.download_urls.append(url)

    def openInBrowser(self, url):
        self.browser_urls.append(url)
        return bool(url)

    def runInstallerAndQuit(self, path, args):
        self.install_calls.append((path, args))
        return self.install_result


class AppUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.settings = load_app_settings(ROOT / "app_config.json")
        self.controller = AppUpdater(
            self.settings,
            "0.2.24.13",
            updater_factory=FakeEngineUpdater,
        )
        self.engine = self.controller._updater

    def test_real_configuration_builds_verified_engine_contract(self):
        self.assertEqual(self.controller.version, "1.0.14")
        self.assertEqual(self.controller.currentVersion, "v1.0.14")
        self.assertEqual(self.controller.prismqmlVersion, "0.2.24.13")
        self.assertEqual(self.engine.repo, "aki-riko/ConfigPilot")
        self.assertEqual(self.engine.asset_keyword, "Setup")

    def test_manual_and_automatic_checks_keep_feedback_context(self):
        up_to_date = []
        failures = []
        self.controller.upToDate.connect(lambda version, manual: up_to_date.append((version, manual)))
        self.controller.checkFailed.connect(lambda message, manual: failures.append((message, manual)))

        self.controller.checkAutomatically()
        self.assertTrue(self.controller.checking)
        self.engine.upToDate.emit("v1.0.14")
        self.assertEqual(up_to_date, [("v1.0.14", False)])

        self.controller.checkManually()
        self.engine.checkFailed.emit("network down")
        self.assertEqual(failures, [("network down", True)])
        self.assertFalse(self.controller.checking)

    def test_duplicate_manual_check_reuses_active_request(self):
        results = []
        self.controller.upToDate.connect(lambda version, manual: results.append((version, manual)))

        self.controller.checkAutomatically()
        self.controller.checkManually()
        self.assertEqual(self.engine.check_count, 1)
        self.engine.upToDate.emit("v1.0.14")
        self.assertEqual(results, [("v1.0.14", True)])

    def test_download_completion_uses_configured_silent_installer_args(self):
        ready = []
        self.controller.downloadReady.connect(lambda: ready.append(True))

        self.controller.downloadUpdate("https://example.test/setup.exe")
        self.engine.downloadFinished.emit("C:/Temp/setup.exe")

        self.assertEqual(self.engine.download_urls, ["https://example.test/setup.exe"])
        self.assertEqual(ready, [True])
        self.assertEqual(
            self.engine.install_calls,
            [("C:/Temp/setup.exe", self.settings.updates.windows_installer_args)],
        )

    def test_installer_launch_failure_is_visible(self):
        failures = []
        self.engine.install_result = False
        self.controller.installLaunchFailed.connect(failures.append)

        self.engine.downloadFinished.emit("C:/Temp/setup.exe")

        self.assertEqual(failures, ["无法启动更新安装程序，请稍后重试"])

    def test_invalid_repository_is_rejected(self):
        payload = json.loads((ROOT / "app_config.json").read_text(encoding="utf-8"))
        payload["updates"]["repository"] = "https://example.test/repo"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app_config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "owner/repo"):
                load_app_settings(path)


if __name__ == "__main__":
    unittest.main()
