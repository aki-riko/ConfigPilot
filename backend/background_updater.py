# coding: utf-8
"""PrismQML 更新器的后台文件写入实现。"""

from __future__ import annotations

import os
import logging
import queue
import tempfile
import threading

from PySide6.QtCore import QStandardPaths, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from prismqml import Updater


_USER_AGENT = b"PrismQML-Updater"
_READ_BUFFER_BYTES = 1024 * 1024
_WRITE_CHUNK_BYTES = 256 * 1024
_QUEUED_CHUNKS = 8
LOGGER = logging.getLogger(__name__)


class _DownloadWriter:
    def __init__(
        self,
        generation: int,
        path: str,
        *,
        prepared,
        capacity_available,
        completed,
    ):
        self.generation = generation
        self.path = path
        self._prepared = prepared
        self._capacity_available = capacity_available
        self._completed = completed
        self._chunks: queue.Queue[bytes] = queue.Queue(maxsize=_QUEUED_CHUNKS)
        self._finish_lock = threading.Lock()
        self._finish_requested = False
        self._finish_error = ""
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="ConfigPilotUpdateWriter",
        )

    def start(self) -> None:
        self._thread.start()

    def try_enqueue(self, chunk: bytes) -> bool:
        try:
            self._chunks.put_nowait(chunk)
            return True
        except queue.Full:
            return False

    def has_capacity(self) -> bool:
        return not self._chunks.full()

    def request_finish(self, error: str = "") -> None:
        with self._finish_lock:
            self._finish_requested = True
            self._finish_error = error
        if error:
            while True:
                try:
                    self._chunks.get_nowait()
                except queue.Empty:
                    break

    def _finish_state(self) -> tuple[bool, str]:
        with self._finish_lock:
            return self._finish_requested, self._finish_error

    def _remove_partial(self) -> str:
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
            return ""
        except OSError as exc:
            return f"清理更新残留失败: {exc}"

    def _run(self) -> None:
        handle = None
        received = 0
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
            handle = open(self.path, "wb")
            self._prepared.emit(self.generation, "")
            while True:
                try:
                    was_full = self._chunks.full()
                    chunk = self._chunks.get(timeout=0.05)
                    if was_full:
                        self._capacity_available.emit(self.generation)
                    handle.write(chunk)
                    received += len(chunk)
                except queue.Empty:
                    pass

                finish_requested, finish_error = self._finish_state()
                if not finish_requested or not self._chunks.empty():
                    continue
                handle.close()
                handle = None
                if finish_error:
                    cleanup_error = self._remove_partial()
                    message = (
                        f"{finish_error}；{cleanup_error}"
                        if cleanup_error
                        else finish_error
                    )
                    self._completed.emit(self.generation, "", message)
                elif received <= 0:
                    cleanup_error = self._remove_partial()
                    message = cleanup_error or "下载文件无效"
                    self._completed.emit(self.generation, "", message)
                else:
                    self._completed.emit(self.generation, self.path, "")
                return
        except Exception as exc:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    LOGGER.warning("关闭更新临时文件失败", exc_info=True)
            cleanup_error = self._remove_partial()
            message = f"写入更新文件失败: {exc}"
            if cleanup_error:
                message += f"；{cleanup_error}"
            self._completed.emit(self.generation, "", message)


class BackgroundDownloadUpdater(Updater):
    """保留 PrismQML 更新检查能力，将安装包磁盘写入移出 GUI 线程。"""

    _writerPrepared = Signal(int, str)
    _writerCapacityAvailable = Signal(int)
    _writerCompleted = Signal(int, str, str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._download_generation = 0
        self._writer: _DownloadWriter | None = None
        self._pending_download_url = ""
        self._network_finished = False
        self._network_error = ""
        self._writerPrepared.connect(self._on_writer_prepared)
        self._writerCapacityAvailable.connect(self._on_writer_capacity_available)
        self._writerCompleted.connect(self._on_writer_completed)

    @Slot(str)
    def downloadUpdate(self, url: str):
        if not url:
            self.downloadFailed.emit("下载地址为空")
            return
        if self._download_reply is not None or self._writer is not None:
            return

        name = QUrl(url).fileName() or "update_installer.exe"
        temp_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.TempLocation
        ) or tempfile.gettempdir()
        self._download_path = os.path.join(temp_dir, name)
        self._download_generation += 1
        self._pending_download_url = url
        self._network_finished = False
        self._network_error = ""
        self._writer = _DownloadWriter(
            self._download_generation,
            self._download_path,
            prepared=self._writerPrepared,
            capacity_available=self._writerCapacityAvailable,
            completed=self._writerCompleted,
        )
        self._writer.start()

    @Slot(int, str)
    def _on_writer_prepared(self, generation: int, error: str) -> None:
        if generation != self._download_generation or self._writer is None:
            return
        if error:
            self._writer = None
            self.downloadFailed.emit(error)
            return

        request = QNetworkRequest(QUrl(self._pending_download_url))
        request.setRawHeader(b"User-Agent", _USER_AGENT)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        self._download_reply = self._nam.get(request)
        self._download_reply.setReadBufferSize(_READ_BUFFER_BYTES)
        self._download_reply.downloadProgress.connect(self._on_download_progress)
        self._download_reply.readyRead.connect(self._on_download_ready_read)
        self._download_reply.finished.connect(self._on_download_finished)

    def _enqueue_available_data(self) -> None:
        reply = self._download_reply
        writer = self._writer
        if reply is None or writer is None:
            return
        while reply.bytesAvailable() > 0 and writer.has_capacity():
            size = min(int(reply.bytesAvailable()), _WRITE_CHUNK_BYTES)
            chunk = bytes(reply.read(size))
            if chunk and not writer.try_enqueue(chunk):
                raise RuntimeError("更新写入队列状态竞争")

    def _on_download_ready_read(self):
        try:
            self._enqueue_available_data()
        except Exception as exc:
            self._fail_active_download(str(exc))

    def _on_download_finished(self):
        reply = self._download_reply
        if reply is None:
            return
        self._network_finished = True
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._network_error = reply.errorString()
        try:
            self._enqueue_available_data()
            self._finish_network_if_drained()
        except Exception as exc:
            self._fail_active_download(str(exc))

    @Slot(int)
    def _on_writer_capacity_available(self, generation: int) -> None:
        if generation != self._download_generation:
            return
        try:
            self._enqueue_available_data()
            self._finish_network_if_drained()
        except Exception as exc:
            self._fail_active_download(str(exc))

    def _finish_network_if_drained(self) -> None:
        reply = self._download_reply
        writer = self._writer
        if not self._network_finished or reply is None or writer is None:
            return
        if not self._network_error and reply.bytesAvailable() > 0:
            return
        self._download_reply = None
        reply.deleteLater()
        writer.request_finish(self._network_error)

    def _fail_active_download(self, message: str) -> None:
        reply = self._download_reply
        self._download_reply = None
        if reply is not None:
            reply.abort()
            reply.deleteLater()
        if self._writer is not None:
            self._writer.request_finish(message)
        else:
            self.downloadFailed.emit(message)

    @Slot(int, str, str)
    def _on_writer_completed(self, generation: int, path: str, error: str) -> None:
        if generation != self._download_generation:
            return
        self._writer = None
        self._pending_download_url = ""
        if error:
            reply = self._download_reply
            self._download_reply = None
            if reply is not None:
                reply.abort()
                reply.deleteLater()
            self.downloadFailed.emit(error)
            return
        self.downloadFinished.emit(path)
