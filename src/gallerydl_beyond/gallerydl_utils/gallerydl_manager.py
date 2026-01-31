from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PyQt6.QtCore import QSettings

from gallerydl_beyond.common.constants import SettingsKeys


logger = logging.getLogger(__name__)


GalleryDLMode = Literal["auto", "system", "python", "custom"]


@dataclass(frozen=True)
class GalleryDLResolution:
    mode: GalleryDLMode
    command: list[str]
    display: str


class GalleryDLManager:
    def __init__(self, settings: QSettings):
        self._settings = settings

    def get_mode(self) -> GalleryDLMode:
        mode = self._settings.value(SettingsKeys.GALLERYDL_MODE)
        if mode in {"auto", "system", "python", "custom"}:
            return mode  # type: ignore[return-value]
        return "auto"

    def set_mode(self, mode: GalleryDLMode) -> None:
        self._settings.setValue(SettingsKeys.GALLERYDL_MODE, mode)

    def get_custom_path(self) -> str | None:
        value = self._settings.value(SettingsKeys.GALLERYDL_PATH)
        if value is None:
            value = self._settings.value(SettingsKeys.GALLERYDL_CUSTOM_PATH)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def set_custom_path(self, path: str | None) -> None:
        if path and path.strip():
            self._settings.setValue(SettingsKeys.GALLERYDL_CUSTOM_PATH, path.strip())
            # Back-compat: older code reads GALLERYDL_PATH
            self._settings.setValue(SettingsKeys.GALLERYDL_PATH, path.strip())
        else:
            self._settings.remove(SettingsKeys.GALLERYDL_CUSTOM_PATH)
            self._settings.remove(SettingsKeys.GALLERYDL_PATH)

    def detect_system(self) -> str | None:
        return shutil.which("gallery-dl")

    def detect_python_module(self, timeout_s: float = 5.0) -> bool:
        cmd = [sys.executable, "-m", "gallery_dl", "--version"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
            return result.returncode == 0
        except Exception as exc:
            logger.debug("python-module detection failed: %s", exc)
            return False

    def resolve(self) -> GalleryDLResolution | None:
        mode = self.get_mode()

        if mode == "system":
            system_path = self.detect_system()
            if system_path:
                return GalleryDLResolution(mode="system", command=[system_path], display=system_path)
            return None

        if mode == "python":
            if self.detect_python_module():
                return GalleryDLResolution(
                    mode="python", command=[sys.executable, "-m", "gallery_dl"], display="python -m gallery_dl"
                )
            return None

        if mode == "custom":
            custom_path = self.get_custom_path()
            if not custom_path:
                return None
            path = Path(custom_path)
            if not path.exists() or not path.is_file():
                return None
            return GalleryDLResolution(mode="custom", command=[str(path)], display=str(path))

        # auto
        system_path = self.detect_system()
        if system_path:
            return GalleryDLResolution(mode="system", command=[system_path], display=system_path)
        if self.detect_python_module():
            return GalleryDLResolution(
                mode="python", command=[sys.executable, "-m", "gallery_dl"], display="python -m gallery_dl"
            )
        return None

    def can_self_update(self, resolved: GalleryDLResolution) -> bool:
        # Only safe to self-update the package in the current Python env.
        return resolved.mode in {"python", "auto"} or (
            resolved.mode == "system" and resolved.command and resolved.command[0] == sys.executable
        )

    def try_update_in_current_env(self) -> tuple[bool, str]:
        """Attempts to update gallery-dl in the current Python environment using uv/pip.

        Returns: (ok, message)
        """
        for update_cmd in (
            ["uv", "pip", "install", "--upgrade", "gallery-dl"],
            [sys.executable, "-m", "pip", "install", "--upgrade", "gallery-dl"],
        ):
            try:
                process = subprocess.run(update_cmd, capture_output=True, text=True)
                if process.returncode == 0:
                    return True, process.stdout.strip() or "gallery-dl updated"
                stderr = process.stderr.strip()
                stdout = process.stdout.strip()
                return False, stderr or stdout or f"Update failed (exit {process.returncode})"
            except FileNotFoundError:
                continue
            except Exception as exc:
                return False, str(exc)
        return False, "Neither uv nor pip was available to update gallery-dl"
