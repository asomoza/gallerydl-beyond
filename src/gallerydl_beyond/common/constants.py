from __future__ import annotations


class UrlStatus:
    PENDING = 0
    IN_PROGRESS = 1
    COMPLETED = 2
    FAILED = 3
    STOPPED = 4  # User manually stopped
    COMPLETED_PARTIAL = 5  # Completed but some files failed
    SKIPPED = 6  # User marked URL to be skipped


class SettingsKeys:
    MAX_CONCURRENT_DOWNLOADS = "downloads/maxConcurrent"  # int, default: 2
    GALLERYDL_PATH = "gallerydl/path"  # str | None
    GALLERYDL_MODE = "gallerydl/mode"  # str: auto|system|python|external_python|custom
    GALLERYDL_CUSTOM_PATH = "gallerydl/customPath"  # str | None
    GALLERYDL_EXTERNAL_INTERP = "gallerydl/externalInterp"  # str | None — path to external Python interpreter
    HISTORY_PAGE_SIZE = "history/pageSize"  # int, default: 100
    # Window geometry/state — saved on close, restored on launch. Bare-string
    # keys "geometry"/"windowState" are kept for back-compat with installs
    # that already wrote them to QSettings, so the values round-trip across
    # the upgrade.
    WINDOW_GEOMETRY = "geometry"  # QByteArray
    WINDOW_STATE = "windowState"  # QByteArray


DEFAULT_DB_FILENAME = "gallery-dl.db"
