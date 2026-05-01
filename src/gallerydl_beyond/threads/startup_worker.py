from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from packaging import version
from PyQt6.QtCore import QThread, pyqtSignal

from gallerydl_beyond.common.database_manager import DatabaseManager
from gallerydl_beyond.gallerydl_utils.config_manager import ConfigManager
from gallerydl_beyond.gallerydl_utils.gallerydl_utils import get_installed_version, get_latest_version


logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    """Check if running as a PyInstaller frozen executable."""
    return getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")


LogLevel = Literal["info", "success", "warning", "error"]


@dataclass(frozen=True)
class StartupResult:
    config_path: Path | None
    gallerydl_cmd: list[str] | None
    gallerydl_display: str | None
    gallerydl_mode: str | None
    installed_version: str | None
    latest_version: str | None


class StartupWorker(QThread):
    log = pyqtSignal(str, str)  # level, message
    finished_result = pyqtSignal(object)  # StartupResult

    def __init__(
        self,
        *,
        db_manager: DatabaseManager,
        config_manager: ConfigManager,
        gallerydl_mode: str,
        gallerydl_custom_path: str | None,
        config_path: str | Path | None,
        parent=None,
    ):
        super().__init__(parent)
        self._db = db_manager
        self._config_manager = config_manager
        self._gallerydl_mode = gallerydl_mode
        self._gallerydl_custom_path = gallerydl_custom_path
        self._config_path = config_path

    def run(self) -> None:
        config_path: Path | None = None
        gallerydl_cmd: list[str] | None = None
        gallerydl_display: str | None = None
        gallerydl_mode: str | None = None
        installed: str | None = None
        latest: str | None = None

        try:
            self.log.emit("info", "Initializing config...")
            config_path = self._config_manager.ensure_exists(self._config_path)
            self.log.emit("success", f"Using config: {config_path}")

            self.log.emit("info", "Resolving gallery-dl...")
            resolved = self._resolve_gallerydl(self._gallerydl_mode, self._gallerydl_custom_path)
            if resolved is None:
                self.log.emit("error", "gallery-dl not found (Settings → choose system/python/custom)")
            else:
                gallerydl_mode, gallerydl_cmd, gallerydl_display = resolved
                self.log.emit("success", f"Using: {gallerydl_display}")

            self.log.emit("info", "Checking database...")
            self._db.ensure_database()
            self.log.emit("success", "Database ready")

            if gallerydl_cmd is not None:
                self.log.emit("info", "Checking gallery-dl version...")
                latest = get_latest_version()
                installed = get_installed_version(gallerydl_cmd)

                if installed and latest:
                    try:
                        if version.parse(latest) > version.parse(installed):
                            # Report only — auto-updating at startup was misleading: a
                            # `uv pip install --upgrade` succeeds in the moment but is
                            # silently reverted on the next `uv run` (the lockfile wins),
                            # so the user saw "updated" every launch with no real change.
                            # The Options dialog has an Update button for an explicit
                            # one-shot upgrade; permanent fixes need a lockfile change.
                            self.log.emit(
                                "warning",
                                f"gallery-dl out of date (installed {installed}, latest {latest})",
                            )
                            self.log.emit(
                                "info",
                                "To update: open Gallery-dl Options → Update, "
                                "or run `uv sync --upgrade-package gallery-dl` "
                                "(uv-managed projects) / `pip install -U gallery-dl`.",
                            )
                        else:
                            self.log.emit("success", "gallery-dl is up to date")
                    except Exception as exc:
                        self.log.emit("warning", f"Version check failed: {exc}")
                else:
                    self.log.emit("warning", "Version check skipped")

        except Exception as exc:
            logger.exception("Startup worker failed")
            self.log.emit("error", str(exc))
        finally:
            self.finished_result.emit(
                StartupResult(
                    config_path=config_path,
                    gallerydl_cmd=gallerydl_cmd,
                    gallerydl_display=gallerydl_display,
                    gallerydl_mode=gallerydl_mode,
                    installed_version=installed,
                    latest_version=latest,
                )
            )

    def _resolve_gallerydl(self, mode: str, custom_path: str | None) -> tuple[str, list[str], str] | None:
        mode = (mode or "auto").strip().lower()

        if mode == "system":
            system_path = shutil.which("gallery-dl")
            if system_path:
                return "system", [system_path], system_path
            return None

        if mode == "python":
            if self._detect_python_module():
                return "python", [sys.executable, "-m", "gallery_dl"], "python -m gallery_dl"
            return None

        if mode == "custom":
            if not custom_path:
                return None
            p = Path(custom_path)
            if p.is_file():
                return "custom", [str(p)], str(p)
            return None

        # auto
        system_path = shutil.which("gallery-dl")
        if system_path:
            return "system", [system_path], system_path
        if self._detect_python_module():
            return "python", [sys.executable, "-m", "gallery_dl"], "python -m gallery_dl"
        return None

    def _detect_python_module(self) -> bool:
        # When frozen (PyInstaller), sys.executable is the bundled app, not Python
        if is_frozen():
            return False
        cmd = [sys.executable, "-m", "gallery_dl", "--version"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            return result.returncode == 0
        except Exception:
            return False
