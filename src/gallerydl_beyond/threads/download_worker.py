from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from gallerydl_beyond.common.database_manager import DatabaseManager, UrlRow


class DownloadWorker(QThread):
    output = pyqtSignal(int, str)  # worker_id, line
    url_started = pyqtSignal(int, int, str)  # worker_id, url_id, url
    url_completed = pyqtSignal(int, int)  # worker_id, url_id
    url_failed = pyqtSignal(int, int, str)  # worker_id, url_id, error

    def __init__(
        self,
        *,
        worker_id: int,
        db_manager: DatabaseManager,
        row: UrlRow,
        gallerydl_cmd: list[str],
        config_path: str | Path,
        parent=None,
    ):
        super().__init__(parent)
        self._worker_id = worker_id
        self._db = db_manager
        self._row = row
        self._gallerydl_cmd = list(gallerydl_cmd)
        self._config_path = Path(config_path)

        self._stop_requested = False
        self._process: subprocess.Popen[str] | None = None

    @property
    def worker_id(self) -> int:
        return self._worker_id

    @property
    def url_id(self) -> int:
        return self._row.id

    @property
    def url(self) -> str:
        return self._row.url

    def request_stop(self) -> None:
        self._stop_requested = True
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    def _popen_kwargs(self) -> dict:
        kwargs: dict = {}
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            # Helps ensure we can terminate the subprocess cleanly.
            kwargs["start_new_session"] = True
        return kwargs

    def run(self) -> None:
        self.url_started.emit(self._worker_id, self._row.id, self._row.url)

        cmd = list(self._gallerydl_cmd)
        cmd.extend(["-c", str(self._config_path)])
        if int(self._row.force_redownload) == 1:
            cmd.append("--no-skip")
        cmd.append(self._row.url)

        try:
            self.output.emit(self._worker_id, f"$ {' '.join(cmd)}")
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **self._popen_kwargs(),
            )

            assert self._process.stdout is not None
            for raw_line in self._process.stdout:
                if self._stop_requested:
                    break
                line = raw_line.rstrip("\n")
                if line:
                    self.output.emit(self._worker_id, line)

            if self._stop_requested:
                try:
                    self._process.terminate()
                except Exception:
                    pass

            try:
                returncode = self._process.wait(timeout=3.0 if self._stop_requested else None)
            except subprocess.TimeoutExpired:
                try:
                    self._process.kill()
                except Exception:
                    pass
                returncode = self._process.wait()

            if self._stop_requested:
                self._db.mark_failed(self._row.id, "Stopped")
                self.url_failed.emit(self._worker_id, self._row.id, "Stopped")
                return

            if returncode == 0:
                self._db.mark_completed(self._row.id)
                self.url_completed.emit(self._worker_id, self._row.id)
            else:
                error = f"gallery-dl exited with code {returncode}"
                self._db.mark_failed(self._row.id, error)
                self.url_failed.emit(self._worker_id, self._row.id, error)

        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            try:
                self._db.mark_failed(self._row.id, error)
            except Exception:
                pass
            self.url_failed.emit(self._worker_id, self._row.id, error)
        finally:
            self._process = None
