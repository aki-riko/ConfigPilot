# coding: utf-8
"""将阻塞任务串行放到后台线程，并在 QObject 所在线程交付结果。"""

from __future__ import annotations

from collections.abc import Callable
import itertools
import logging
import queue
import threading
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot


LOGGER = logging.getLogger(__name__)
_STOP = object()


class SerialTaskRunner(QObject):
    """后台串行执行任务，避免阻塞 GUI，同时保留任务提交顺序。"""

    busyChanged = Signal()
    _completed = Signal(int, object, object)

    def __init__(self, parent: QObject | None = None, *, thread_name: str):
        super().__init__(parent)
        self._tasks: queue.Queue = queue.Queue()
        self._callbacks: dict[
            int,
            tuple[Callable[[Any], None], Callable[[Exception], None]],
        ] = {}
        self._ids = itertools.count(1)
        self._pending = 0
        self._completed.connect(self._deliver)
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=thread_name,
        )
        self._thread.start()

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._pending > 0

    def submit(
        self,
        operation: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> int:
        task_id = next(self._ids)
        was_busy = self.busy
        self._callbacks[task_id] = (on_success, on_error)
        self._pending += 1
        if not was_busy:
            self.busyChanged.emit()
        self._tasks.put((task_id, operation))
        return task_id

    def _run(self) -> None:
        while True:
            item = self._tasks.get()
            if item is _STOP:
                return
            task_id, operation = item
            try:
                result = operation()
                error = None
            except Exception as exc:  # 后台异常统一交回主线程处理
                result = None
                error = exc
            self._completed.emit(task_id, result, error)

    @Slot(int, object, object)
    def _deliver(self, task_id: int, result: object, error: object) -> None:
        callbacks = self._callbacks.pop(task_id, None)
        if callbacks is None:
            return
        on_success, on_error = callbacks
        try:
            if isinstance(error, Exception):
                on_error(error)
            else:
                on_success(result)
        except Exception:
            LOGGER.exception("后台任务结果交付失败")
        finally:
            self._pending -= 1
            if self._pending == 0:
                self.busyChanged.emit()
