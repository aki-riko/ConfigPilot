import time

from PySide6.QtCore import QCoreApplication


APP = QCoreApplication.instance() or QCoreApplication([])


def wait_until(predicate, *, timeout=3.0, message="Qt 异步任务未完成"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        APP.processEvents()
        if predicate():
            APP.processEvents()
            return
        time.sleep(0.001)
    raise AssertionError(message)


def wait_for_idle(target, property_name="operationBusy", *, timeout=3.0):
    wait_until(
        lambda: not bool(getattr(target, property_name)),
        timeout=timeout,
        message=f"{type(target).__name__} 后台任务超时",
    )
