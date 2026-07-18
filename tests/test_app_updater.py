from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from PySide6.QtCore import QObject, Signal

from backend.app_settings import load_app_settings
from backend.app_updater import AppUpdater
from backend.background_updater import BackgroundDownloadUpdater, _DownloadWriter
from tests.qt_test_utils import APP, wait_until


ROOT = Path(__file__).resolve().parents[1]


class CallbackSignal:
    def __init__(self, callback):
        self._callback = callback

    def emit(self, *args):
        self._callback(*args)


class BufferedReply:
    def __init__(self, payload):
        self.payload = bytearray(payload)
        self.read_calls = 0

    def bytesAvailable(self):
        return len(self.payload)

    def read(self, size):
        self.read_calls += 1
        chunk = self.payload[:size]
        del self.payload[:size]
        return bytes(chunk)


class ControlledWriter:
    def __init__(self, has_capacity):
        self.capacity = has_capacity
        self.chunks = []

    def has_capacity(self):
        return self.capacity

    def try_enqueue(self, chunk):
        self.chunks.append(chunk)
        return True


class PayloadHandler(BaseHTTPRequestHandler):
    payload = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        return


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

    def test_download_writer_preserves_bytes_off_main_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "update.exe"
            prepared = threading.Event()
            completed = threading.Event()
            result = {}
            worker_threads = []

            writer = _DownloadWriter(
                7,
                str(path),
                prepared=CallbackSignal(
                    lambda generation, error: (
                        worker_threads.append(threading.get_ident()),
                        prepared.set(),
                    )
                ),
                capacity_available=CallbackSignal(lambda generation: None),
                completed=CallbackSignal(
                    lambda generation, output_path, error: (
                        result.update(path=output_path, error=error),
                        completed.set(),
                    )
                ),
            )
            main_thread = threading.get_ident()
            writer.start()
            self.assertTrue(prepared.wait(1))
            self.assertTrue(writer.try_enqueue(b"first-"))
            self.assertTrue(writer.try_enqueue(b"second"))
            writer.request_finish()
            self.assertTrue(completed.wait(1))

            self.assertNotEqual(worker_threads, [main_thread])
            self.assertEqual(result, {"path": str(path), "error": ""})
            self.assertEqual(path.read_bytes(), b"first-second")

    def test_network_reply_is_not_read_until_writer_has_capacity(self):
        _ = APP
        updater = BackgroundDownloadUpdater("owner/repo", "v1.0.0", "Setup")
        reply = BufferedReply(b"payload")
        writer = ControlledWriter(False)
        updater._download_reply = reply
        updater._writer = writer

        updater._enqueue_available_data()
        self.assertEqual(reply.read_calls, 0)
        self.assertEqual(bytes(reply.payload), b"payload")

        writer.capacity = True
        updater._enqueue_available_data()
        self.assertEqual(reply.read_calls, 1)
        self.assertEqual(b"".join(writer.chunks), b"payload")

    def test_real_qt_download_matches_source_bytes(self):
        _ = APP
        payload = bytes(range(256)) * 12289
        PayloadHandler.payload = payload
        server = ThreadingHTTPServer(("127.0.0.1", 0), PayloadHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        downloaded = []
        failures = []
        updater = BackgroundDownloadUpdater("owner/repo", "v1.0.0", "Setup")
        updater.downloadFinished.connect(downloaded.append)
        updater.downloadFailed.connect(failures.append)
        file_name = f"configpilot-{uuid.uuid4().hex}.bin"
        host, port = server.server_address

        try:
            updater.downloadUpdate(f"http://{host}:{port}/{file_name}")
            wait_until(
                lambda: bool(downloaded or failures),
                timeout=5,
                message="真实 Qt 更新下载超时",
            )
            self.assertEqual(failures, [])
            self.assertEqual(len(downloaded), 1)
            output_path = Path(downloaded[0])
            self.assertEqual(output_path.read_bytes(), payload)
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=1)
            if downloaded:
                try:
                    os.remove(downloaded[0])
                except FileNotFoundError:
                    pass


if __name__ == "__main__":
    unittest.main()
