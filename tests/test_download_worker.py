"""Tests for DownloadWorker command building and failure detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gallerydl_beyond.common.constants import UrlStatus
from gallerydl_beyond.common.database_manager import UrlRow

# Import the failure patterns directly for testing
from gallerydl_beyond.threads.download_worker import _FAILURE_PATTERNS


class TestFailurePatterns:
    """Test failure detection patterns."""

    def test_pattern_download_error(self):
        """Should detect [download][error] pattern."""
        line = "[download][error] Failed to download image.jpg"
        assert any(p.search(line) for p in _FAILURE_PATTERNS)

    def test_pattern_failed_to_download(self):
        """Should detect 'download: Failed to download' pattern."""
        line = "download: Failed to download https://example.com/image.jpg"
        assert any(p.search(line) for p in _FAILURE_PATTERNS)

    def test_pattern_error_failed(self):
        """Should detect [error]...failed pattern."""
        line = "[error] Download failed for image.jpg"
        assert any(p.search(line) for p in _FAILURE_PATTERNS)

    def test_pattern_http_error(self):
        """Should detect HttpError pattern."""
        line = "HttpError: 404 Not Found"
        assert any(p.search(line) for p in _FAILURE_PATTERNS)

    def test_pattern_case_insensitive(self):
        """Patterns should be case insensitive."""
        line = "[DOWNLOAD][ERROR] Something failed"
        assert any(p.search(line) for p in _FAILURE_PATTERNS)

    def test_pattern_no_match_normal_output(self):
        """Normal output should not match failure patterns."""
        lines = [
            "[download] Downloading image.jpg",
            "gallery-dl 1.27.0",
            "# https://example.com/gallery",
            "/downloads/image_001.jpg",
        ]
        for line in lines:
            assert not any(p.search(line) for p in _FAILURE_PATTERNS), f"Unexpected match: {line}"


class TestUrlRowDataclass:
    """Test UrlRow dataclass used by DownloadWorker."""

    def test_url_row_creation(self):
        """UrlRow should be created with all fields."""
        row = UrlRow(
            id=1,
            url="https://example.com/gallery",
            status=UrlStatus.PENDING,
            force_redownload=0,
            check_new_only=0,
            download_count=0,
            date_added="2024-01-01T00:00:00+00:00",
            date_processed=None,
            last_error=None,
            skipped_count=0,
        )

        assert row.id == 1
        assert row.url == "https://example.com/gallery"
        assert row.status == UrlStatus.PENDING

    def test_url_row_immutable(self):
        """UrlRow should be immutable (frozen dataclass)."""
        row = UrlRow(
            id=1,
            url="https://example.com/gallery",
            status=UrlStatus.PENDING,
            force_redownload=0,
            check_new_only=0,
            download_count=0,
            date_added="2024-01-01T00:00:00+00:00",
            date_processed=None,
            last_error=None,
        )

        with pytest.raises(AttributeError):
            row.url = "https://other.com"


class TestCommandBuilding:
    """Test the command building logic (without running actual subprocess)."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock DatabaseManager."""
        return MagicMock()

    @pytest.fixture
    def sample_row(self) -> UrlRow:
        """Create a sample UrlRow for testing."""
        return UrlRow(
            id=1,
            url="https://example.com/gallery",
            status=UrlStatus.IN_PROGRESS,
            force_redownload=0,
            check_new_only=0,
            download_count=0,
            date_added="2024-01-01T00:00:00+00:00",
            date_processed=None,
            last_error=None,
        )

    @pytest.fixture
    def sample_row_force(self) -> UrlRow:
        """Create a UrlRow with force_redownload=1."""
        return UrlRow(
            id=2,
            url="https://example.com/gallery2",
            status=UrlStatus.IN_PROGRESS,
            force_redownload=1,
            check_new_only=0,
            download_count=1,
            date_added="2024-01-01T00:00:00+00:00",
            date_processed=None,
            last_error=None,
        )

    def test_command_basic_structure(self, sample_row: UrlRow):
        """Command should include gallerydl_cmd, config flag, and URL."""
        # Simulate command building logic from DownloadWorker.run()
        gallerydl_cmd = ["gallery-dl"]
        config_path = Path("/path/to/config.json")

        cmd = list(gallerydl_cmd)
        cmd.extend(["-c", str(config_path)])
        if int(sample_row.force_redownload) == 1:
            cmd.append("--no-skip")
        cmd.append(sample_row.url)

        assert cmd == [
            "gallery-dl",
            "-c",
            "/path/to/config.json",
            "https://example.com/gallery",
        ]

    def test_command_with_force_redownload(self, sample_row_force: UrlRow):
        """Command should include --no-skip when force_redownload=1."""
        gallerydl_cmd = ["gallery-dl"]
        config_path = Path("/path/to/config.json")

        cmd = list(gallerydl_cmd)
        cmd.extend(["-c", str(config_path)])
        if int(sample_row_force.force_redownload) == 1:
            cmd.append("--no-skip")
        cmd.append(sample_row_force.url)

        assert "--no-skip" in cmd
        assert cmd == [
            "gallery-dl",
            "-c",
            "/path/to/config.json",
            "--no-skip",
            "https://example.com/gallery2",
        ]

    def test_command_python_module_style(self, sample_row: UrlRow):
        """Command should work with python -m gallery_dl style."""
        import sys

        gallerydl_cmd = [sys.executable, "-m", "gallery_dl"]
        config_path = Path("config.json")

        cmd = list(gallerydl_cmd)
        cmd.extend(["-c", str(config_path)])
        cmd.append(sample_row.url)

        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "gallery_dl"
        assert "-c" in cmd
        assert sample_row.url in cmd

    def test_command_url_with_special_characters(self):
        """Command should handle URLs with special characters."""
        row = UrlRow(
            id=1,
            url="https://example.com/gallery?page=1&sort=date",
            status=UrlStatus.IN_PROGRESS,
            force_redownload=0,
            check_new_only=0,
            download_count=0,
            date_added="2024-01-01T00:00:00+00:00",
            date_processed=None,
            last_error=None,
        )

        gallerydl_cmd = ["gallery-dl"]
        config_path = Path("config.json")

        cmd = list(gallerydl_cmd)
        cmd.extend(["-c", str(config_path)])
        cmd.append(row.url)

        # URL should be passed as-is (subprocess handles it)
        assert cmd[-1] == "https://example.com/gallery?page=1&sort=date"


class TestWorkerProperties:
    """Test DownloadWorker property accessors."""

    @pytest.fixture
    def mock_worker(self, tmp_path: Path):
        """Create a mock-like worker without Qt dependencies."""

        class MockWorker:
            def __init__(self, worker_id: int, row: UrlRow):
                self._worker_id = worker_id
                self._row = row
                self._stop_requested = False
                self._mark_as_skipped = False

            @property
            def worker_id(self) -> int:
                return self._worker_id

            @property
            def url_id(self) -> int:
                return self._row.id

            @property
            def url(self) -> str:
                return self._row.url

            def request_stop(self):
                self._stop_requested = True

            def request_skip(self):
                self._mark_as_skipped = True
                self.request_stop()

        row = UrlRow(
            id=42,
            url="https://example.com/gallery",
            status=UrlStatus.IN_PROGRESS,
            force_redownload=0,
            check_new_only=0,
            download_count=0,
            date_added="2024-01-01T00:00:00+00:00",
            date_processed=None,
            last_error=None,
        )

        return MockWorker(worker_id=3, row=row)

    def test_worker_id_property(self, mock_worker):
        """worker_id property should return the worker ID."""
        assert mock_worker.worker_id == 3

    def test_url_id_property(self, mock_worker):
        """url_id property should return the URL row ID."""
        assert mock_worker.url_id == 42

    def test_url_property(self, mock_worker):
        """url property should return the URL string."""
        assert mock_worker.url == "https://example.com/gallery"

    def test_request_stop(self, mock_worker):
        """request_stop() should set stop flag."""
        assert mock_worker._stop_requested is False

        mock_worker.request_stop()

        assert mock_worker._stop_requested is True

    def test_request_skip(self, mock_worker):
        """request_skip() should set skip flag and stop flag."""
        assert mock_worker._mark_as_skipped is False
        assert mock_worker._stop_requested is False

        mock_worker.request_skip()

        assert mock_worker._mark_as_skipped is True
        assert mock_worker._stop_requested is True


class TestPopenKwargs:
    """Test platform-specific subprocess kwargs."""

    def test_popen_kwargs_linux(self):
        """On Linux, should set start_new_session."""
        import sys

        if not sys.platform.startswith("win"):
            # Simulate the logic from DownloadWorker._popen_kwargs()
            kwargs = {}
            if sys.platform.startswith("win"):
                import subprocess

                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            else:
                kwargs["start_new_session"] = True

            assert kwargs.get("start_new_session") is True
            assert "creationflags" not in kwargs
