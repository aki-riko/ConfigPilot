from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

from PySide6.QtCore import QObject, QTimer
import shiboken6

from tests.qt_test_utils import wait_until


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, url: str, content_type="application/octet-stream"):
        super().__init__(payload)
        self._url = url
        self.headers = {
            "Content-Length": str(len(payload)),
            "Content-Type": content_type,
        }

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class ClaudeInstallerTests(unittest.TestCase):
    def load_modules(self):
        import importlib
        import sys

        sys.path.insert(0, str(ROOT))
        sys.modules.pop("backend.claude_installer", None)
        sys.modules.pop("backend.claude_install_validation", None)
        sys.modules.pop("backend.claude_install_sources", None)
        sources = importlib.import_module("backend.claude_install_sources")
        installer = importlib.import_module("backend.claude_installer")
        return sources, installer

    def test_install_source_read_does_not_block_gui_thread(self):
        _, installer = self.load_modules()
        backend = installer.ClaudeInstaller()
        main_thread = threading.get_ident()
        worker_threads = []
        timer_fired = []

        def slow_source(product):
            worker_threads.append(threading.get_ident())
            time.sleep(0.2)
            raise RuntimeError("停止后续下载")

        with mock.patch.object(
            installer,
            "official_install_spec",
            side_effect=slow_source,
        ):
            QTimer.singleShot(10, lambda: timer_fired.append(True))
            started = time.perf_counter()
            backend.install("claude-code")
            call_elapsed = time.perf_counter() - started
            wait_until(lambda: bool(timer_fired), timeout=0.15)
            self.assertTrue(backend.busy)
            self.assertLess(call_elapsed, 0.1)
            wait_until(lambda: not backend.busy)

        self.assertEqual(len(worker_threads), 1)
        self.assertNotEqual(worker_threads[0], main_thread)

    def test_cancel_during_validation_never_launches_installer(self):
        sources, installer = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "win32"):
            spec = sources.official_install_spec("claude-code")
        backend = installer.ClaudeInstaller()
        verify_started = threading.Event()
        release_verify = threading.Event()
        notices = []
        backend.notify.connect(
            lambda level, title, message: notices.append((level, title, message))
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / spec.file_name
            path.write_bytes(b"official-script")

            def slow_verify(resolved, downloaded_path):
                verify_started.set()
                release_verify.wait(1)

            with (
                mock.patch.object(installer, "official_install_spec", return_value=spec),
                mock.patch.object(installer, "_download_to_temp", return_value=path),
                mock.patch.object(installer, "verify_download", side_effect=slow_verify),
                mock.patch.object(backend, "_launch") as launch,
            ):
                backend.install("claude-code")
                self.assertTrue(verify_started.wait(1))
                backend.cancel()
                release_verify.set()
                wait_until(lambda: not backend.busy, timeout=2)

            launch.assert_not_called()
            self.assertTrue(any(title == "已取消安装" for _, title, _ in notices))

    def test_cancel_after_ready_signal_is_queued_never_launches_installer(self):
        sources, installer = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "win32"):
            spec = sources.official_install_spec("claude-code")
        backend = installer.ClaudeInstaller()
        backend._cancel_event = threading.Event()
        backend._set_state(
            busy=True,
            cancelable=True,
            progress=100,
            status="等待启动安装程序",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / spec.file_name
            path.write_bytes(b"official-script")
            emitter = threading.Thread(
                target=lambda: backend._workerReady.emit(spec, str(path))
            )
            with mock.patch.object(backend, "_launch") as launch:
                emitter.start()
                emitter.join(timeout=1)
                self.assertFalse(emitter.is_alive())
                backend.cancel()
                wait_until(lambda: not backend.busy, timeout=2)

            launch.assert_not_called()

    def test_parent_destruction_does_not_raise_in_installer_thread(self):
        sources, installer = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "win32"):
            spec = sources.official_install_spec("claude-code")
        parent = QObject()
        backend = installer.ClaudeInstaller(parent)
        source_started = threading.Event()
        release_source = threading.Event()
        worker_errors = []
        original_hook = threading.excepthook

        def slow_source(product):
            source_started.set()
            release_source.wait(1)
            return spec

        threading.excepthook = lambda args: worker_errors.append(args.exc_value)
        try:
            with mock.patch.object(
                installer,
                "official_install_spec",
                side_effect=slow_source,
            ):
                backend.install("claude-code")
                self.assertTrue(source_started.wait(1))
                worker_thread = backend._thread
                shiboken6.delete(parent)
                release_source.set()
                worker_thread.join(timeout=1)
        finally:
            threading.excepthook = original_hook
            release_source.set()

        self.assertFalse(worker_thread.is_alive())
        self.assertEqual(worker_errors, [])

    def test_linux_package_resolution_selects_latest_and_preserves_hash(self):
        sources, _ = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "linux"), mock.patch.object(
            sources.platform, "machine", return_value="x86_64"
        ):
            spec = sources.official_install_spec("claude-desktop")
        index = """
Package: claude-desktop
Version: 1.9.0
Architecture: amd64
Filename: pool/main/c/claude-desktop/claude-desktop_1.9.0_amd64.deb
Size: 3
SHA256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

Package: claude-desktop
Version: 1.10.0
Architecture: amd64
Filename: pool/main/c/claude-desktop/claude-desktop_1.10.0_amd64.deb
Size: 4
SHA256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
"""
        resolved = sources.resolve_linux_package(spec, index)
        self.assertTrue(resolved.url.endswith("claude-desktop_1.10.0_amd64.deb"))
        self.assertEqual(resolved.expected_bytes, 4)
        self.assertEqual(resolved.sha256, "b" * 64)

    def test_install_source_rejects_unapproved_hostname(self):
        sources, _ = self.load_modules()
        config = json.loads(
            (ROOT / "resources" / "claude_install_sources.json").read_text(
                encoding="utf-8"
            )
        )
        config["claudeDesktop"]["windows-x64"]["url"] = "https://example.com/setup.exe"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CONFIGPILOT_CLAUDE_INSTALL_SOURCES": str(path)}
            ), mock.patch.object(sources.sys, "platform", "win32"), mock.patch.object(
                sources.platform, "machine", return_value="AMD64"
            ):
                with self.assertRaisesRegex(ValueError, "允许列表"):
                    sources.official_install_spec("claude-desktop")

    def test_streamed_download_checks_size_and_sha256(self):
        sources, installer = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "linux"), mock.patch.object(
            sources.platform, "machine", return_value="x86_64"
        ):
            base_spec = sources.official_install_spec("claude-desktop")
        payload = b"real-deb-payload"
        spec = replace(
            base_spec,
            url="https://downloads.claude.ai/claude-desktop/test.deb",
            file_name="test.deb",
            expected_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        response = FakeResponse(payload, spec.url)
        progress = []
        with mock.patch.object(installer, "_open_download", return_value=response):
            path = installer._download_to_temp(
                spec, threading.Event(), lambda percent, status: progress.append(percent)
            )
        self.addCleanup(shutil.rmtree, path.parent, True)
        self.assertEqual(path.read_bytes(), payload)
        self.assertEqual(progress[-1], 100)

    def test_windows_signature_requires_anthropic_publisher(self):
        sources, installer = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "win32"), mock.patch.object(
            sources.platform, "machine", return_value="AMD64"
        ):
            spec = sources.official_install_spec("claude-desktop")
        signature = mock.Mock(
            returncode=0,
            stdout='Valid\nCN="Anthropic, PBC", O="Anthropic, PBC"\n',
        )
        with tempfile.TemporaryDirectory() as tmp:
            installer_path = Path(tmp) / "ClaudeSetup.exe"
            installer_path.write_bytes(b"signed")
            with mock.patch(
                "backend.claude_install_validation.shutil.which",
                return_value="powershell.exe",
            ), mock.patch(
                "backend.claude_install_validation.subprocess.run",
                return_value=signature,
            ):
                installer.verify_download(spec, installer_path)

            invalid = mock.Mock(returncode=0, stdout="Valid\nCN=Other Publisher\n")
            with mock.patch(
                "backend.claude_install_validation.shutil.which",
                return_value="powershell.exe",
            ), mock.patch(
                "backend.claude_install_validation.subprocess.run",
                return_value=invalid,
            ):
                with self.assertRaisesRegex(RuntimeError, "不是 Anthropic"):
                    installer.verify_download(spec, installer_path)

    def test_desktop_redirect_resolves_only_to_allowed_download_host(self):
        sources, installer = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "win32"), mock.patch.object(
            sources.platform, "machine", return_value="AMD64"
        ):
            spec = sources.official_install_spec("claude-desktop")
        resolved_url = "https://downloads.claude.ai/releases/win32/x64/ClaudeSetup.exe"
        result = mock.Mock(returncode=63, stdout=resolved_url, stderr="")
        with mock.patch.object(installer.shutil, "which", return_value="curl.exe"), mock.patch.object(
            installer.subprocess, "run", return_value=result
        ):
            resolved = installer._resolve_redirect_with_curl(spec)
        self.assertEqual(resolved.url, resolved_url)
        self.assertFalse(resolved.resolve_redirect_with_curl)

        rejected = mock.Mock(
            returncode=63,
            stdout="https://example.com/ClaudeSetup.exe",
            stderr="",
        )
        with mock.patch.object(installer.shutil, "which", return_value="curl.exe"), mock.patch.object(
            installer.subprocess, "run", return_value=rejected
        ):
            with self.assertRaisesRegex(RuntimeError, "未授权"):
                installer._resolve_redirect_with_curl(spec)

    def test_official_scripts_must_contain_anthropic_release_marker(self):
        sources, installer = self.load_modules()
        with mock.patch.object(sources.sys, "platform", "win32"):
            spec = sources.official_install_spec("claude-code")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "install.ps1"
            path.write_text(installer.POWERSHELL_SCRIPT_MARKER, encoding="utf-8")
            installer.verify_download(spec, path)
            path.write_text("Write-Output hacked", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "缺少预期"):
                installer.verify_download(spec, path)


if __name__ == "__main__":
    unittest.main()
