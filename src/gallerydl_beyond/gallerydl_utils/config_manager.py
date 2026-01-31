from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConfigPaths:
    config_path: Path
    example_path: Path | None


class ConfigManager:
    """Load/save/validate the user-facing gallery-dl config.json.

    By convention, this app looks for `config.json` in the current working directory.
    If it doesn't exist, it will be created from `config_example/config.json` when
    available, otherwise from a minimal built-in default.
    """

    DEFAULT_FILENAME = "config.json"

    def resolve_paths(self, config_path: str | Path | None = None) -> ConfigPaths:
        resolved_config = self._resolve_config_path(config_path)
        return ConfigPaths(config_path=resolved_config, example_path=self._find_example_config())

    def ensure_exists(self, config_path: str | Path | None = None) -> Path:
        paths = self.resolve_paths(config_path)
        if paths.config_path.exists():
            return paths.config_path

        paths.config_path.parent.mkdir(parents=True, exist_ok=True)

        template = None
        if paths.example_path and paths.example_path.exists():
            template = paths.example_path.read_text(encoding="utf-8")

        if template is None:
            template = json.dumps(self._default_config(), indent=4, ensure_ascii=False)

        paths.config_path.write_text(template, encoding="utf-8")
        return paths.config_path

    def load(self, config_path: str | Path | None = None) -> dict[str, Any]:
        path = self.ensure_exists(config_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._coerce_and_fill_defaults(data)

    def save(self, config: dict[str, Any], config_path: str | Path | None = None) -> Path:
        path = self._resolve_config_path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = self._coerce_and_fill_defaults(config)
        path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
        return path

    def update_common_fields(
        self,
        *,
        base_directory: str,
        archive_path: str,
        rate: str,
        retries: int,
        timeout: float,
        config_path: str | Path | None = None,
    ) -> Path:
        data = self.load(config_path)

        extractor = data.setdefault("extractor", {})
        extractor["base-directory"] = base_directory
        extractor["archive"] = archive_path

        downloader = data.setdefault("downloader", {})
        downloader["rate"] = rate
        downloader["retries"] = retries
        downloader["timeout"] = timeout

        return self.save(data, config_path)

    def _resolve_config_path(self, config_path: str | Path | None) -> Path:
        if config_path:
            return Path(config_path).expanduser().resolve()

        cwd_path = Path.cwd() / self.DEFAULT_FILENAME
        return cwd_path

    def _find_example_config(self) -> Path | None:
        # Development (repo) layout: src/gallerydl_beyond/gallerydl_utils/config_manager.py
        # -> project root is parents[3]
        here = Path(__file__).resolve()
        candidates: list[Path] = []

        if len(here.parents) >= 4:
            project_root = here.parents[3]
            candidates.append(project_root / "config_example" / "config.json")

        # PyInstaller: file is typically unpacked into sys._MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "config.json")
            candidates.append(Path(meipass) / "config_example" / "config.json")

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return None

    def _default_config(self) -> dict[str, Any]:
        return {
            "extractor": {
                "base-directory": "./downloads",
                "archive": "./bin/archive.sqlite3",
            },
            "downloader": {
                "rate": "1M",
                "retries": 3,
                "timeout": 8.0,
            },
        }

    def _coerce_and_fill_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            data = {}

        extractor = data.get("extractor")
        if not isinstance(extractor, dict):
            extractor = {}
            data["extractor"] = extractor

        downloader = data.get("downloader")
        if not isinstance(downloader, dict):
            downloader = {}
            data["downloader"] = downloader

        extractor.setdefault("base-directory", "./downloads")
        extractor.setdefault("archive", "./bin/archive.sqlite3")

        downloader.setdefault("rate", "1M")

        retries = downloader.get("retries", 3)
        try:
            downloader["retries"] = int(retries)
        except Exception:
            downloader["retries"] = 3

        timeout = downloader.get("timeout", 8.0)
        try:
            downloader["timeout"] = float(timeout)
        except Exception:
            downloader["timeout"] = 8.0

        return data
