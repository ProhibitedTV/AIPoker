import threading
import time

from PyQt5.QtCore import QCoreApplication, QThreadPool

from gui import StageWorker


def test_stage_worker_runs_action_off_the_qt_event_thread():
    app = QCoreApplication.instance() or QCoreApplication([])
    event_thread = threading.get_ident()
    worker_threads = []
    finished = []
    worker = StageWorker(lambda: worker_threads.append(threading.get_ident()))
    worker.signals.finished.connect(lambda: finished.append(True))
    pool = QThreadPool()

    pool.start(worker)
    deadline = time.monotonic() + 5
    while not finished and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    pool.waitForDone(1000)

    assert finished
    assert worker_threads[0] != event_thread
