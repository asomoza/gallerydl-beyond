from __future__ import annotations


class UrlStatus:
    PENDING = 0
    IN_PROGRESS = 1
    COMPLETED = 2
    FAILED = 3


class SettingsKeys:
    MAX_CONCURRENT_DOWNLOADS = "downloads/maxConcurrent"  # int, default: 2
    GALLERYDL_PATH = "gallerydl/path"  # str | None
    GALLERYDL_MODE = "gallerydl/mode"  # str: auto|system|python|custom
    GALLERYDL_CUSTOM_PATH = "gallerydl/customPath"  # str | None


DEFAULT_DB_FILENAME = "gallery-dl.db"
