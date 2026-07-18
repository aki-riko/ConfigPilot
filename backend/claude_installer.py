# coding: utf-8
"""Claude 官方安装包的异步下载、校验与启动。"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Property, QProcess, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from backend.claude_install_sources import (
    InstallSpec,
    official_install_spec,
    resolve_linux_package,
)
from backend.claude_install_validation import (
    POWERSHELL_SCRIPT_MARKER,
    SHELL_SCRIPT_MARKER,
    verify_download,
)


LOGGER = logging.getLogger(__name__)
TEMP_DIR_PREFIX = "configpilot-claude-install-"


class InstallCancelled(Exception):
    """用户取消安装下载。"""


def _remove_download_tree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return
    except OSError:
        LOGGER.warning("清理 Claude 下载目录失败: %s", path, exc_info=True)


def _format_bytes(value: int) -> str:
    amount = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024 or unit == "GB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{int(value)} B"


def _validate_response_url(url: str, spec: InstallSpec) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in spec.allowed_hosts:
        raise RuntimeError(f"下载被重定向到未授权地址: {hostname or url}")


def _content_length(headers, maximum: int) -> int:
    raw = headers.get("Content-Length", "")
    if not raw:
        return 0
    try:
        length = int(raw)
    except ValueError as exc:
        raise RuntimeError("服务器返回了无效的文件大小") from exc
    if length <= 0 or length > maximum:
        raise RuntimeError("服务器返回的文件大小超出安全限制")
    return length


def _request(spec: InstallSpec, url: str, accept: str):
    headers = {"User-Agent": spec.user_agent, "Accept": accept}
    return urllib_request.Request(url, headers=headers)


def _fetch_metadata(spec: InstallSpec, cancel_event: threading.Event) -> bytes:
    req = _request(spec, spec.packages_url, "text/plain")
    try:
        with urllib_request.urlopen(req, timeout=spec.timeout_seconds) as response:
            _validate_response_url(response.geturl(), spec)
            _content_length(response.headers, spec.metadata_max_bytes)
            chunks: list[bytes] = []
            total = 0
            while True:
                if cancel_event.is_set():
                    raise InstallCancelled()
                chunk = response.read(spec.chunk_bytes)
                if not chunk:
                    break
                total += len(chunk)
                if total > spec.metadata_max_bytes:
                    raise RuntimeError("Anthropic 软件包索引超出安全限制")
                chunks.append(chunk)
            return b"".join(chunks)
    except urllib_error.HTTPError as exc:
        raise RuntimeError(f"获取 Anthropic 软件包索引失败: HTTP {exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"获取 Anthropic 软件包索引失败: {exc.reason}") from exc


def _open_download(spec: InstallSpec):
    req = _request(spec, spec.url, "application/octet-stream,*/*")
    try:
        response = urllib_request.urlopen(req, timeout=spec.timeout_seconds)
    except urllib_error.HTTPError as exc:
        raise RuntimeError(f"下载安装包失败: HTTP {exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"下载安装包失败: {exc.reason}") from exc
    _validate_response_url(response.geturl(), spec)
    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" in content_type:
        response.close()
        raise RuntimeError("官方地址返回了网页而不是安装文件")
    return response


def _stream_download(
    spec: InstallSpec,
    response,
    partial_path: Path,
    cancel_event: threading.Event,
    progress,
) -> tuple[int, str]:
    total = _content_length(response.headers, spec.max_bytes)
    received = 0
    digest = hashlib.sha256()
    with partial_path.open("wb") as handle:
        while True:
            if cancel_event.is_set():
                raise InstallCancelled()
            chunk = response.read(spec.chunk_bytes)
            if not chunk:
                break
            received += len(chunk)
            if received > spec.max_bytes:
                raise RuntimeError("下载内容超出安全大小限制")
            handle.write(chunk)
            digest.update(chunk)
            percent = int(received * 100 / total) if total else -1
            progress(percent, f"已下载 {_format_bytes(received)}")
        handle.flush()
        os.fsync(handle.fileno())
    return received, digest.hexdigest()


def _download_to_temp(
    spec: InstallSpec,
    cancel_event: threading.Event,
    progress,
) -> Path:
    download_dir = Path(tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX))
    partial_path = download_dir / f"{spec.file_name}.part"
    final_path = download_dir / spec.file_name
    try:
        with _open_download(spec) as response:
            received, sha256 = _stream_download(
                spec, response, partial_path, cancel_event, progress
            )
        _validate_download(spec, received, sha256)
        os.replace(partial_path, final_path)
        return final_path
    except Exception:
        _remove_download_tree(download_dir)
        raise


def _resolve_redirect_with_curl(spec: InstallSpec) -> InstallSpec:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("系统缺少 curl，无法解析 Anthropic Desktop 下载地址")
    command = [
        curl, "-sS", "-L", "-A", spec.user_agent,
        "--proto", "=https", "--proto-redir", "=https",
        "--max-filesize", "1", "-o", os.devnull,
        "-w", "%{url_effective}",
        "--connect-timeout", str(spec.timeout_seconds),
        "--max-time", str(spec.timeout_seconds), spec.url,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    resolved_url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    _validate_response_url(resolved_url, spec)
    if resolved_url == spec.url:
        raise RuntimeError("Anthropic Desktop 下载地址未返回独立安装包")
    return replace(spec, url=resolved_url, resolve_redirect_with_curl=False)


def _validate_download(spec: InstallSpec, received: int, sha256: str) -> None:
    if received <= 0:
        raise RuntimeError("下载文件为空")
    if spec.expected_bytes and received != spec.expected_bytes:
        raise RuntimeError("下载文件大小与 Anthropic 仓库索引不一致")
    if spec.sha256 and sha256.lower() != spec.sha256.lower():
        raise RuntimeError("下载文件 SHA-256 与 Anthropic 仓库索引不一致")


class ClaudeInstaller(QObject):
    """向 QML 暴露 Claude 安装任务状态。"""

    changed = Signal()
    notify = Signal(int, str, str)
    _workerProgress = Signal(int, str)
    _workerReady = Signal(object, str)
    _workerFailed = Signal(str)
    _workerCancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._cancelable = False
        self._progress = -1
        self._status = ""
        self._cancel_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._process: QProcess | None = None
        self._download_path = ""
        self._workerProgress.connect(self._on_worker_progress)
        self._workerReady.connect(self._on_worker_ready)
        self._workerFailed.connect(self._on_worker_failed)
        self._workerCancelled.connect(self._on_worker_cancelled)

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def cancelable(self):
        return self._cancelable

    @Property(int, notify=changed)
    def progress(self):
        return self._progress

    @Property(str, notify=changed)
    def status(self):
        return self._status

    def _set_state(self, *, busy: bool, cancelable: bool, progress: int, status: str):
        self._busy = busy
        self._cancelable = cancelable
        self._progress = progress
        self._status = status
        self.changed.emit()

    @Slot(str)
    def install(self, product: str):
        if self._busy:
            self.notify.emit(2, "安装任务进行中", "请等待当前 Claude 安装任务完成。")
            return
        try:
            spec = official_install_spec(product)
        except ValueError as exc:
            self.notify.emit(2, "无法开始安装", str(exc))
            return
        self._cancel_event = threading.Event()
        self._set_state(
            busy=True,
            cancelable=True,
            progress=-1,
            status=f"正在准备 {spec.display_name}",
        )
        self._thread = threading.Thread(
            target=self._download_worker,
            args=(spec, self._cancel_event),
            daemon=True,
            name="ConfigPilotClaudeInstaller",
        )
        self._thread.start()

    @Slot()
    def cancel(self):
        if not self._busy or not self._cancelable or self._cancel_event is None:
            self.notify.emit(2, "无法取消", "安装程序启动后需在系统安装界面中取消。")
            return
        self._cancel_event.set()
        self._status = "正在取消下载"
        self.changed.emit()

    def _download_worker(self, spec: InstallSpec, cancel_event: threading.Event):
        path: Path | None = None
        try:
            resolved = self._resolve_spec(spec, cancel_event)
            path = _download_to_temp(
                resolved,
                cancel_event,
                lambda percent, status: self._workerProgress.emit(percent, status),
            )
            self._workerProgress.emit(100, "正在校验官方安装文件")
            verify_download(resolved, path)
            self._workerReady.emit(resolved, str(path))
        except InstallCancelled:
            if path is not None:
                _remove_download_tree(path.parent)
            self._workerCancelled.emit()
        except Exception as exc:
            if path is not None:
                _remove_download_tree(path.parent)
            LOGGER.exception("Claude 安装文件处理失败")
            self._workerFailed.emit(str(exc))

    def _resolve_spec(self, spec: InstallSpec, cancel_event: threading.Event) -> InstallSpec:
        if spec.resolve_redirect_with_curl:
            self._workerProgress.emit(-1, "正在解析 Anthropic Desktop 官方下载地址")
            spec = _resolve_redirect_with_curl(spec)
        if spec.kind != "linux-deb":
            return spec
        self._workerProgress.emit(-1, "正在读取 Anthropic Linux 软件包索引")
        raw = _fetch_metadata(spec, cancel_event)
        try:
            index_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError("Anthropic Linux 软件包索引编码无效") from exc
        return resolve_linux_package(spec, index_text)

    @Slot(int, str)
    def _on_worker_progress(self, progress: int, status: str):
        self._progress = progress
        self._status = status
        self.changed.emit()

    @Slot(object, str)
    def _on_worker_ready(self, spec: InstallSpec, path: str):
        self._thread = None
        self._cancel_event = None
        self._download_path = path
        self._set_state(
            busy=True,
            cancelable=False,
            progress=100,
            status=f"正在启动 {spec.display_name} 安装程序",
        )
        try:
            self._launch(spec, Path(path))
        except Exception as exc:
            LOGGER.exception("启动 Claude 安装程序失败")
            self._cleanup_download()
            self._fail(str(exc))

    def _launch(self, spec: InstallSpec, path: Path):
        if spec.kind in {"powershell-script", "shell-script"}:
            self._start_script(spec, path)
            return
        if spec.kind == "windows-exe":
            self._open_windows_installer(path)
            self._finish("安装程序已打开", "请按 Anthropic 安装向导完成 Claude Desktop 安装。")
            return
        if spec.kind in {"macos-dmg", "linux-deb"}:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise RuntimeError("系统未能打开已验证的 Claude Desktop 安装包")
            self._finish("安装包已打开", "请在系统安装界面中完成 Claude Desktop 安装。")
            return
        raise RuntimeError(f"不支持的 Claude 安装类型: {spec.kind}")

    @staticmethod
    def _open_windows_installer(path: Path):
        import ctypes

        result = ctypes.windll.shell32.ShellExecuteW(
            None, "open", str(path), None, str(path.parent), 1
        )
        if int(result) <= 32:
            raise RuntimeError(f"Windows 无法启动 Claude Desktop 安装程序: {result}")

    def _start_script(self, spec: InstallSpec, path: Path):
        if spec.kind == "powershell-script":
            program = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
            arguments = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path), "latest"]
        else:
            program = shutil.which("bash")
            arguments = [str(path), "latest"]
        if not program:
            raise RuntimeError("系统缺少执行 Claude Code 官方安装脚本所需的命令")
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._drain_process_output)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)
        self._process.setWorkingDirectory(str(path.parent))
        self._process.start(program, arguments)
        self._status = "正在安装 Claude Code CLI"
        self.changed.emit()

    @Slot()
    def _drain_process_output(self):
        if self._process is None:
            return
        output = bytes(self._process.readAllStandardOutput()).decode("utf-8", "replace").strip()
        if output:
            LOGGER.info("Claude Code 安装器: %s", output)

    @Slot(QProcess.ProcessError)
    def _on_process_error(self, process_error):
        if self._process is None or process_error != QProcess.ProcessError.FailedToStart:
            return
        self._process.deleteLater()
        self._process = None
        self._cleanup_download()
        self._fail("Claude Code 官方安装脚本无法启动")

    @Slot(int, QProcess.ExitStatus)
    def _on_process_finished(self, exit_code: int, exit_status):
        process = self._process
        if process is None:
            return
        self._drain_process_output()
        process.deleteLater()
        self._process = None
        self._cleanup_download()
        normal = exit_status == QProcess.ExitStatus.NormalExit
        if normal and exit_code == 0:
            self._finish("Claude Code 已安装", "重新打开终端后即可运行 claude。")
        else:
            self._fail(f"Claude Code 安装脚本退出，代码 {exit_code}")

    @Slot(str)
    def _on_worker_failed(self, message: str):
        self._thread = None
        self._cancel_event = None
        self._fail(message)

    @Slot()
    def _on_worker_cancelled(self):
        self._thread = None
        self._cancel_event = None
        self._set_state(busy=False, cancelable=False, progress=-1, status="下载已取消")
        self.notify.emit(0, "已取消安装", "未启动任何 Claude 安装程序。")

    def _cleanup_download(self):
        if not self._download_path:
            return
        download_dir = Path(self._download_path).parent
        self._download_path = ""
        threading.Thread(
            target=_remove_download_tree,
            args=(download_dir,),
            daemon=True,
            name="ConfigPilotClaudeCleanup",
        ).start()

    def _finish(self, title: str, message: str):
        self._set_state(busy=False, cancelable=False, progress=100, status=title)
        self.notify.emit(1, title, message)

    def _fail(self, message: str):
        self._set_state(busy=False, cancelable=False, progress=-1, status="安装失败")
        self.notify.emit(3, "Claude 安装失败", message)
