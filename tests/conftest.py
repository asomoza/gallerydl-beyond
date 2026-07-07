"""Shared pytest fixtures for gallerydl_beyond tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a path to a temporary database file."""
    return tmp_path / "test.db"


@pytest.fixture
def db_manager(tmp_db_path: Path):
    """Create a DatabaseManager with a temporary database."""
    from gallerydl_beyond.common.database_manager import DatabaseManager

    # Create without QMutex for simpler testing (single-threaded tests)
    manager = DatabaseManager(db_path=tmp_db_path, mutex=MagicMock())
    manager.ensure_database()
    return manager


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    """Return a path to a temporary config.json file."""
    return tmp_path / "config.json"


@pytest.fixture
def config_manager():
    """Create a ConfigManager instance."""
    from gallerydl_beyond.gallerydl_utils.config_manager import ConfigManager

    return ConfigManager()


@pytest.fixture
def mock_qsettings():
    """Create a mock QSettings object for testing."""
    settings = MagicMock()
    _store: dict[str, str] = {}

    def get_value(key, default=None):
        return _store.get(key, default)

    def set_value(key, value):
        _store[key] = value

    def remove_key(key):
        _store.pop(key, None)

    settings.value = MagicMock(side_effect=get_value)
    settings.setValue = MagicMock(side_effect=set_value)
    settings.remove = MagicMock(side_effect=remove_key)
    settings._store = _store  # Expose for test inspection

    return settings


@pytest.fixture
def sample_config() -> dict:
    """Return a sample gallery-dl config."""
    return {
        "extractor": {
            "base-directory": "./downloads",
            "archive": "./bin/archive.sqlite3",
        },
        "downloader": {
            "rate": "2M",
            "retries": 5,
            "timeout": 10.0,
        },
    }


@pytest.fixture
def legacy_db(tmp_path: Path) -> Path:
    """Create a database with the legacy schema for migration testing."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0,
            date_processed TEXT
        );
    """)
    # Insert some legacy data
    conn.execute(
        "INSERT INTO urls (url, processed, date_processed) VALUES (?, ?, ?);",
        ("https://example.com/gallery1", 1, "2024-01-15T10:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO urls (url, processed, date_processed) VALUES (?, ?, ?);",
        ("https://example.com/gallery2", 0, None),
    )
    conn.commit()
    conn.close()
    return db_path
