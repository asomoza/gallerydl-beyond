from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from gallerydl_beyond.common.database_manager import DatabaseManager
from gallerydl_beyond.threads.download_worker import DownloadWorker


logger = logging.getLogger(__name__)


class DownloadManager(QObject):
    all_started = pyqtSignal()
    all_finished = pyqtSignal()

    worker_output = pyqtSignal(int, str)  # worker_id, line
    worker_started = pyqtSignal(int, str)  # worker_id, url
    worker_completed = pyqtSignal(int, int)  # worker_id, url_id
    worker_failed = pyqtSignal(int, int, str)  # worker_id, url_id, error

    queue_updated = pyqtSignal(int, int)  # pending_count, active_count

    def __init__(
        self,
        *,
        db_manager: DatabaseManager,
        gallerydl_cmd: list[str],
        config_path: str | Path,
        max_workers: int = 2,
        parent=None,
    ):
        super().__init__(parent)
        self._db = db_manager
        self._gallerydl_cmd = list(gallerydl_cmd)
        self._config_path = Path(config_path)

        self._max_workers = max(1, int(max_workers))
        self._running = False
        self._paused = False

        self._next_worker_id = 1
        self._workers: dict[int, DownloadWorker] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_max_workers(self, count: int) -> None:
        self._max_workers = max(1, int(count))
        if self._running and not self._paused:
            self._fill_workers()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        self.all_started.emit()
        self._fill_workers()

    def pause(self) -> None:
        if not self._running:
            return
        self._paused = True

    def resume(self) -> None:
        if not self._running:
            return
        self._paused = False
        self._fill_workers()

    def stop_all(self) -> None:
        self._running = False
        self._paused = False

        workers = list(self._workers.values())
        for worker in workers:
            worker.request_stop()

    def _emit_counts(self) -> None:
        try:
            pending, active = self._db.get_counts()
            self.queue_updated.emit(pending, active)
        except Exception:
            logger.exception("Failed to query counts")

    def _fill_workers(self) -> None:
        if not self._running or self._paused:
            self._emit_counts()
            return

        while self._running and (not self._paused) and len(self._workers) < self._max_workers:
            row = self._db.claim_next_pending()
            if row is None:
                break

            worker_id = self._next_worker_id
            self._next_worker_id += 1

            worker = DownloadWorker(
                worker_id=worker_id,
                db_manager=self._db,
                row=row,
                gallerydl_cmd=self._gallerydl_cmd,
                config_path=self._config_path,
            )

            worker.output.connect(self.worker_output)
            worker.url_started.connect(self._on_worker_started)
            worker.url_completed.connect(self._on_worker_completed)
            worker.url_failed.connect(self._on_worker_failed)
            worker.finished.connect(lambda wid=worker_id: self._on_worker_finished(wid))

            self._workers[worker_id] = worker
            worker.start()

        self._emit_counts()

        if self._running and not self._workers:
            # Nothing to do.
            self._running = False
            self.all_finished.emit()

    def _on_worker_started(self, worker_id: int, url_id: int, url: str) -> None:
        self.worker_started.emit(worker_id, url)
        self._emit_counts()

    def _on_worker_completed(self, worker_id: int, url_id: int) -> None:
        self.worker_completed.emit(worker_id, url_id)
        self._emit_counts()

    def _on_worker_failed(self, worker_id: int, url_id: int, error: str) -> None:
        self.worker_failed.emit(worker_id, url_id, error)
        self._emit_counts()

    def _on_worker_finished(self, worker_id: int) -> None:
        self._workers.pop(worker_id, None)

        if self._running and not self._paused:
            self._fill_workers()
            return

        self._emit_counts()

        if not self._running and not self._workers:
            self.all_finished.emit()
