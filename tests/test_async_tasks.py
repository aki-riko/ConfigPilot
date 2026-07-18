import threading
import time
import unittest

from PySide6.QtCore import QObject, QTimer
import shiboken6

from backend.async_tasks import SerialTaskRunner
from tests.qt_test_utils import APP, wait_for_idle, wait_until


class AsyncTaskTests(unittest.TestCase):
    def test_slow_task_does_not_block_qt_event_loop(self):
        _ = APP
        runner = SerialTaskRunner(thread_name="ConfigPilotResponsivenessTest")
        self.addCleanup(runner.close)
        timer_fired = []
        completed = []
        errors = []
        started = time.perf_counter()

        QTimer.singleShot(
            10,
            lambda: timer_fired.append(time.perf_counter() - started),
        )
        runner.submit(
            lambda: time.sleep(0.2),
            lambda result: completed.append(True),
            errors.append,
        )

        wait_until(lambda: bool(timer_fired), timeout=0.15)
        self.assertTrue(runner.busy)
        self.assertLess(timer_fired[0], 0.15)
        wait_for_idle(runner, "busy")
        self.assertEqual(completed, [True])
        self.assertEqual(errors, [])

    def test_result_callback_returns_to_gui_thread(self):
        _ = APP
        runner = SerialTaskRunner(thread_name="ConfigPilotThreadAffinityTest")
        self.addCleanup(runner.close)
        main_thread = threading.get_ident()
        delivered = []
        errors = []

        runner.submit(
            threading.get_ident,
            lambda worker_thread: delivered.append(
                (worker_thread, threading.get_ident())
            ),
            errors.append,
        )
        wait_for_idle(runner, "busy")

        self.assertEqual(len(delivered), 1)
        worker_thread, callback_thread = delivered[0]
        self.assertNotEqual(worker_thread, main_thread)
        self.assertEqual(callback_thread, main_thread)
        self.assertEqual(errors, [])

    def test_drain_close_executes_all_queued_operations_and_rejects_submit(self):
        runner = SerialTaskRunner(
            thread_name="ConfigPilotDrainTest",
            drain_on_close=True,
        )
        executed = []
        for value in (1, 2, 3):
            runner.submit(
                lambda item=value: executed.append(item),
                lambda result: None,
                lambda error: None,
            )

        runner.close()

        self.assertEqual(executed, [1, 2, 3])
        self.assertFalse(runner._thread.is_alive())
        self.assertFalse(runner.busy)
        with self.assertRaisesRegex(RuntimeError, "已关闭"):
            runner.submit(lambda: None, lambda result: None, lambda error: None)

    def test_parent_destruction_does_not_raise_in_worker_thread(self):
        _ = APP
        parent = QObject()
        runner = SerialTaskRunner(parent, thread_name="ConfigPilotDestroyTest")
        started = threading.Event()
        release = threading.Event()
        worker_errors = []
        original_hook = threading.excepthook

        def operation():
            started.set()
            release.wait(1)

        threading.excepthook = lambda args: worker_errors.append(args.exc_value)
        try:
            runner.submit(operation, lambda result: None, lambda error: None)
            self.assertTrue(started.wait(1))
            worker_thread = runner._thread
            shiboken6.delete(parent)
            release.set()
            worker_thread.join(timeout=1)
            APP.processEvents()
        finally:
            threading.excepthook = original_hook
            release.set()

        self.assertFalse(worker_thread.is_alive())
        self.assertEqual(worker_errors, [])


if __name__ == "__main__":
    unittest.main()
