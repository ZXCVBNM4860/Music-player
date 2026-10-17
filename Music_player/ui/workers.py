# ui/workers.py

from PyQt6.QtCore import QThread, pyqtSignal


_PENDING = set()


class CallWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func, args=(), kwargs=None):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs or {}

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.succeeded.emit(result)

    def _release(self):
        _PENDING.discard(self)
        self.deleteLater()


def run_async(func, args=(), kwargs=None, on_success=None, on_error=None):
    worker = CallWorker(func, args=args, kwargs=kwargs)

    if on_success is not None:
        worker.succeeded.connect(on_success)

    if on_error is not None:
        worker.failed.connect(on_error)

    worker.finished.connect(worker._release)
    _PENDING.add(worker)
    worker.start()

    return worker


def wait_for_pending(timeout=5000):
    for worker in list(_PENDING):
        if worker.isRunning():
            worker.wait(timeout)

    _PENDING.clear()
