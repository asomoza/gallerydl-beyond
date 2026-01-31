"""Tests for DatabaseManager."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gallerydl_beyond.common.constants import UrlStatus
from gallerydl_beyond.common.database_manager import DatabaseManager, UrlRow


class TestDatabaseCreation:
    """Test database creation and schema."""

    def test_ensure_database_creates_file(self, tmp_db_path: Path):
        """ensure_database() should create the database file."""
        manager = DatabaseManager(db_path=tmp_db_path, mutex=MagicMock())
        assert not tmp_db_path.exists()

        manager.ensure_database()

        assert tmp_db_path.exists()

    def test_ensure_database_creates_urls_table(self, tmp_db_path: Path):
        """ensure_database() should create the urls table with correct schema."""
        manager = DatabaseManager(db_path=tmp_db_path, mutex=MagicMock())
        manager.ensure_database()

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.execute("PRAGMA table_info(urls);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            "id",
            "url",
            "status",
            "force_redownload",
            "check_new_only",
            "download_count",
            "date_added",
            "date_processed",
            "last_error",
            "skipped_count",
        }
        assert columns == expected_columns

    def test_ensure_database_creates_index(self, tmp_db_path: Path):
        """ensure_database() should create the status index."""
        manager = DatabaseManager(db_path=tmp_db_path, mutex=MagicMock())
        manager.ensure_database()

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_urls_status';")
        result = cursor.fetchone()
        conn.close()

        assert result is not None

    def test_ensure_database_idempotent(self, db_manager: DatabaseManager):
        """Calling ensure_database() multiple times should be safe."""
        # db_manager fixture already called ensure_database()
        db_manager.ensure_database()
        db_manager.ensure_database()
        # No exception means success


class TestLegacyMigration:
    """Test migration from legacy schema."""

    def test_migrate_legacy_schema(self, legacy_db: Path):
        """Should migrate legacy schema to new schema."""
        manager = DatabaseManager(db_path=legacy_db, mutex=MagicMock())
        manager.ensure_database()

        # Check new schema columns exist
        conn = sqlite3.connect(legacy_db)
        cursor = conn.execute("PRAGMA table_info(urls);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "status" in columns
        assert "date_added" in columns
        assert "skipped_count" in columns

    def test_migrate_preserves_data(self, legacy_db: Path):
        """Migration should preserve existing URL data."""
        manager = DatabaseManager(db_path=legacy_db, mutex=MagicMock())
        manager.ensure_database()

        urls = manager.list_urls()
        assert len(urls) == 2

        # Find the completed URL
        completed = next((u for u in urls if "gallery1" in u.url), None)
        assert completed is not None
        assert completed.status == UrlStatus.COMPLETED
        assert completed.download_count == 1

        # Find the pending URL
        pending = next((u for u in urls if "gallery2" in u.url), None)
        assert pending is not None
        assert pending.status == UrlStatus.PENDING
        assert pending.download_count == 0

    def test_migrate_keeps_legacy_table(self, legacy_db: Path):
        """Migration should keep urls_legacy table for safety."""
        manager = DatabaseManager(db_path=legacy_db, mutex=MagicMock())
        manager.ensure_database()

        conn = sqlite3.connect(legacy_db)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls_legacy';")
        result = cursor.fetchone()
        conn.close()

        assert result is not None


class TestAddUrl:
    """Test adding URLs to the database."""

    def test_add_url_returns_id(self, db_manager: DatabaseManager):
        """add_url() should return the new row id."""
        url_id = db_manager.add_url("https://example.com/gallery")

        assert url_id is not None
        assert isinstance(url_id, int)
        assert url_id > 0

    def test_add_url_stores_url(self, db_manager: DatabaseManager):
        """add_url() should store the URL in the database."""
        url = "https://example.com/gallery"
        url_id = db_manager.add_url(url)

        row = db_manager.get_by_url(url)
        assert row is not None
        assert row.id == url_id
        assert row.url == url

    def test_add_url_default_status_pending(self, db_manager: DatabaseManager):
        """New URLs should have PENDING status by default."""
        db_manager.add_url("https://example.com/gallery")

        row = db_manager.get_by_url("https://example.com/gallery")
        assert row is not None
        assert row.status == UrlStatus.PENDING

    def test_add_url_force_redownload_flag(self, db_manager: DatabaseManager):
        """add_url() should store force_redownload flag."""
        db_manager.add_url("https://example.com/gallery", force_redownload=True)

        row = db_manager.get_by_url("https://example.com/gallery")
        assert row is not None
        assert row.force_redownload == 1

    def test_add_url_check_new_only_flag(self, db_manager: DatabaseManager):
        """add_url() should store check_new_only flag."""
        db_manager.add_url("https://example.com/gallery", check_new_only=True)

        row = db_manager.get_by_url("https://example.com/gallery")
        assert row is not None
        assert row.check_new_only == 1

    def test_add_url_duplicate_returns_none(self, db_manager: DatabaseManager):
        """Adding a duplicate URL should return None."""
        url = "https://example.com/gallery"
        first_id = db_manager.add_url(url)
        second_id = db_manager.add_url(url)

        assert first_id is not None
        assert second_id is None

    def test_add_url_strips_whitespace(self, db_manager: DatabaseManager):
        """add_url() should strip whitespace from URL."""
        db_manager.add_url("  https://example.com/gallery  ")

        row = db_manager.get_by_url("https://example.com/gallery")
        assert row is not None
        assert row.url == "https://example.com/gallery"

    def test_add_url_empty_raises(self, db_manager: DatabaseManager):
        """add_url() should raise ValueError for empty URL."""
        with pytest.raises(ValueError, match="url cannot be empty"):
            db_manager.add_url("")

        with pytest.raises(ValueError, match="url cannot be empty"):
            db_manager.add_url("   ")


class TestUrlExists:
    """Test URL existence checking."""

    def test_url_exists_true(self, db_manager: DatabaseManager):
        """url_exists() should return True for existing URLs."""
        db_manager.add_url("https://example.com/gallery")

        assert db_manager.url_exists("https://example.com/gallery") is True

    def test_url_exists_false(self, db_manager: DatabaseManager):
        """url_exists() should return False for non-existing URLs."""
        assert db_manager.url_exists("https://example.com/nonexistent") is False


class TestGetByUrl:
    """Test URL retrieval by URL string."""

    def test_get_by_url_found(self, db_manager: DatabaseManager):
        """get_by_url() should return UrlRow for existing URL."""
        db_manager.add_url("https://example.com/gallery")

        row = db_manager.get_by_url("https://example.com/gallery")

        assert row is not None
        assert isinstance(row, UrlRow)
        assert row.url == "https://example.com/gallery"

    def test_get_by_url_not_found(self, db_manager: DatabaseManager):
        """get_by_url() should return None for non-existing URL."""
        row = db_manager.get_by_url("https://example.com/nonexistent")
        assert row is None

    def test_get_by_url_empty_returns_none(self, db_manager: DatabaseManager):
        """get_by_url() should return None for empty URL."""
        assert db_manager.get_by_url("") is None
        assert db_manager.get_by_url("   ") is None


class TestRequeueExistingUrl:
    """Test re-queuing existing URLs."""

    def test_requeue_updates_status(self, db_manager: DatabaseManager):
        """requeue_existing_url() should set status to PENDING."""
        url = "https://example.com/gallery"
        db_manager.add_url(url)

        # Simulate completion
        row = db_manager.get_by_url(url)
        db_manager.mark_completed(row.id)

        # Re-queue
        result = db_manager.requeue_existing_url(url)

        assert result is not None
        row = db_manager.get_by_url(url)
        assert row.status == UrlStatus.PENDING

    def test_requeue_sets_force_redownload(self, db_manager: DatabaseManager):
        """requeue_existing_url() should set force_redownload flag."""
        url = "https://example.com/gallery"
        db_manager.add_url(url)

        db_manager.requeue_existing_url(url, force_redownload=True)

        row = db_manager.get_by_url(url)
        assert row.force_redownload == 1

    def test_requeue_sets_check_new_only(self, db_manager: DatabaseManager):
        """requeue_existing_url() should set check_new_only flag."""
        url = "https://example.com/gallery"
        db_manager.add_url(url)

        db_manager.requeue_existing_url(url, check_new_only=True)

        row = db_manager.get_by_url(url)
        assert row.check_new_only == 1

    def test_requeue_clears_last_error(self, db_manager: DatabaseManager):
        """requeue_existing_url() should clear last_error."""
        url = "https://example.com/gallery"
        db_manager.add_url(url)

        row = db_manager.get_by_url(url)
        db_manager.mark_failed(row.id, "Some error")

        db_manager.requeue_existing_url(url)

        row = db_manager.get_by_url(url)
        assert row.last_error is None

    def test_requeue_nonexistent_returns_none(self, db_manager: DatabaseManager):
        """requeue_existing_url() should return None for non-existing URL."""
        result = db_manager.requeue_existing_url("https://example.com/nonexistent")
        assert result is None

    def test_requeue_empty_url_raises(self, db_manager: DatabaseManager):
        """requeue_existing_url() should raise ValueError for empty URL."""
        with pytest.raises(ValueError, match="url cannot be empty"):
            db_manager.requeue_existing_url("")


class TestClaimNextPending:
    """Test atomic URL claiming for workers."""

    def test_claim_returns_url_row(self, db_manager: DatabaseManager):
        """claim_next_pending() should return a UrlRow."""
        db_manager.add_url("https://example.com/gallery")

        claimed = db_manager.claim_next_pending()

        assert claimed is not None
        assert isinstance(claimed, UrlRow)
        assert claimed.url == "https://example.com/gallery"

    def test_claim_sets_in_progress(self, db_manager: DatabaseManager):
        """claim_next_pending() should set status to IN_PROGRESS."""
        db_manager.add_url("https://example.com/gallery")

        claimed = db_manager.claim_next_pending()

        assert claimed.status == UrlStatus.IN_PROGRESS

        # Verify in database
        row = db_manager.get_by_url("https://example.com/gallery")
        assert row.status == UrlStatus.IN_PROGRESS

    def test_claim_respects_order(self, db_manager: DatabaseManager):
        """claim_next_pending() should claim URLs in order of id."""
        db_manager.add_url("https://example.com/first")
        db_manager.add_url("https://example.com/second")
        db_manager.add_url("https://example.com/third")

        first = db_manager.claim_next_pending()
        second = db_manager.claim_next_pending()
        third = db_manager.claim_next_pending()

        assert first.url == "https://example.com/first"
        assert second.url == "https://example.com/second"
        assert third.url == "https://example.com/third"

    def test_claim_skips_in_progress(self, db_manager: DatabaseManager):
        """claim_next_pending() should not claim already in-progress URLs."""
        db_manager.add_url("https://example.com/first")
        db_manager.add_url("https://example.com/second")

        # Claim first
        db_manager.claim_next_pending()

        # Next claim should get second
        claimed = db_manager.claim_next_pending()
        assert claimed.url == "https://example.com/second"

    def test_claim_includes_stopped(self, db_manager: DatabaseManager):
        """claim_next_pending(include_stopped=True) should also claim STOPPED URLs."""
        db_manager.add_url("https://example.com/gallery")

        # Claim and mark as stopped
        claimed = db_manager.claim_next_pending()
        db_manager.mark_stopped(claimed.id)

        # Should NOT be able to claim by default (include_stopped=False)
        not_reclaimed = db_manager.claim_next_pending()
        assert not_reclaimed is None

        # Reset to stopped for next test
        db_manager.mark_stopped(claimed.id)

        # Should be able to claim with include_stopped=True
        reclaimed = db_manager.claim_next_pending(include_stopped=True)
        assert reclaimed is not None
        assert reclaimed.url == "https://example.com/gallery"

    def test_claim_empty_queue_returns_none(self, db_manager: DatabaseManager):
        """claim_next_pending() should return None when queue is empty."""
        claimed = db_manager.claim_next_pending()
        assert claimed is None

    def test_claim_all_completed_returns_none(self, db_manager: DatabaseManager):
        """claim_next_pending() should return None when all URLs are completed."""
        db_manager.add_url("https://example.com/gallery")

        claimed = db_manager.claim_next_pending()
        db_manager.mark_completed(claimed.id)

        # Queue should be empty now
        second_claim = db_manager.claim_next_pending()
        assert second_claim is None


class TestStatusUpdates:
    """Test status update methods."""

    def test_mark_completed(self, db_manager: DatabaseManager):
        """mark_completed() should set status and increment download_count."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")

        db_manager.mark_completed(row.id)

        updated = db_manager.get_by_url("https://example.com/gallery")
        assert updated.status == UrlStatus.COMPLETED
        assert updated.download_count == 1
        assert updated.date_processed is not None
        assert updated.last_error is None

    def test_mark_completed_increments_count(self, db_manager: DatabaseManager):
        """mark_completed() should increment download_count each time."""
        url = "https://example.com/gallery"
        db_manager.add_url(url)
        row = db_manager.get_by_url(url)

        db_manager.mark_completed(row.id)
        db_manager.requeue_existing_url(url)

        claimed = db_manager.claim_next_pending()
        db_manager.mark_completed(claimed.id)

        updated = db_manager.get_by_url(url)
        assert updated.download_count == 2

    def test_mark_failed(self, db_manager: DatabaseManager):
        """mark_failed() should set status and store error."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")

        db_manager.mark_failed(row.id, "Connection timeout")

        updated = db_manager.get_by_url("https://example.com/gallery")
        assert updated.status == UrlStatus.FAILED
        assert updated.last_error == "Connection timeout"

    def test_mark_pending(self, db_manager: DatabaseManager):
        """mark_pending() should set status to PENDING and clear last_error."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")

        # First mark it as something else with an error
        db_manager.mark_failed(row.id, "Some error")
        failed = db_manager.get_by_url("https://example.com/gallery")
        assert failed.status == UrlStatus.FAILED
        assert failed.last_error == "Some error"

        # Now mark it pending again
        db_manager.mark_pending(row.id)

        updated = db_manager.get_by_url("https://example.com/gallery")
        assert updated.status == UrlStatus.PENDING
        assert updated.last_error is None

    def test_mark_stopped(self, db_manager: DatabaseManager):
        """mark_stopped() should set status and store message."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")

        db_manager.mark_stopped(row.id)

        updated = db_manager.get_by_url("https://example.com/gallery")
        assert updated.status == UrlStatus.STOPPED
        assert updated.last_error == "Stopped by user"

    def test_mark_skipped(self, db_manager: DatabaseManager):
        """mark_skipped() should set status and store message."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")

        db_manager.mark_skipped(row.id)

        updated = db_manager.get_by_url("https://example.com/gallery")
        assert updated.status == UrlStatus.SKIPPED
        assert updated.last_error == "Skipped by user"

    def test_mark_completed_partial(self, db_manager: DatabaseManager):
        """mark_completed_partial() should set status and skipped_count."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")

        db_manager.mark_completed_partial(row.id, skipped_count=3, errors="file1.jpg\nfile2.jpg")

        updated = db_manager.get_by_url("https://example.com/gallery")
        assert updated.status == UrlStatus.COMPLETED_PARTIAL
        assert updated.skipped_count == 3
        assert updated.download_count == 1
        assert "file1.jpg" in updated.last_error


class TestGetCounts:
    """Test status count retrieval."""

    def test_get_counts_empty(self, db_manager: DatabaseManager):
        """get_counts() should return zeros for empty database."""
        pending, stopped, active = db_manager.get_counts()

        assert pending == 0
        assert stopped == 0
        assert active == 0

    def test_get_counts_pending(self, db_manager: DatabaseManager):
        """get_counts() should count pending URLs."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")

        pending, stopped, active = db_manager.get_counts()

        assert pending == 2
        assert stopped == 0
        assert active == 0

    def test_get_counts_mixed(self, db_manager: DatabaseManager):
        """get_counts() should count each status correctly."""
        db_manager.add_url("https://example.com/pending1")
        db_manager.add_url("https://example.com/pending2")
        db_manager.add_url("https://example.com/active")
        db_manager.add_url("https://example.com/stopped")

        # Claim one (becomes active)
        db_manager.claim_next_pending()

        # Claim and stop one
        claimed = db_manager.claim_next_pending()
        db_manager.mark_stopped(claimed.id)

        pending, stopped, active = db_manager.get_counts()

        assert pending == 2  # pending1, pending2 (one was claimed)
        # Wait, let me recalculate: we added 4, claimed 2 (active + stopped)
        # So pending should be 2
        assert stopped == 1
        assert active == 1


class TestListUrls:
    """Test URL listing with search."""

    def test_list_urls_empty(self, db_manager: DatabaseManager):
        """list_urls() should return empty list for empty database."""
        urls = db_manager.list_urls()
        assert urls == []

    def test_list_urls_returns_all(self, db_manager: DatabaseManager):
        """list_urls() should return all URLs."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")
        db_manager.add_url("https://example.com/3")

        urls = db_manager.list_urls()

        assert len(urls) == 3

    def test_list_urls_search_filter(self, db_manager: DatabaseManager):
        """list_urls() should filter by search term."""
        db_manager.add_url("https://example.com/cats")
        db_manager.add_url("https://example.com/dogs")
        db_manager.add_url("https://other.com/cats")

        urls = db_manager.list_urls(search="cats")

        assert len(urls) == 2
        assert all("cats" in u.url for u in urls)

    def test_list_urls_search_case_insensitive(self, db_manager: DatabaseManager):
        """list_urls() search should be case-insensitive (SQLite LIKE default)."""
        db_manager.add_url("https://example.com/CATS")
        db_manager.add_url("https://example.com/cats")

        urls = db_manager.list_urls(search="cats")

        assert len(urls) == 2

    def test_list_urls_limit(self, db_manager: DatabaseManager):
        """list_urls() should respect limit parameter."""
        for i in range(10):
            db_manager.add_url(f"https://example.com/{i}")

        urls = db_manager.list_urls(limit=5)

        assert len(urls) == 5


class TestResetInProgress:
    """Test startup recovery for interrupted downloads."""

    def test_reset_in_progress_to_stopped(self, db_manager: DatabaseManager):
        """reset_in_progress_to_stopped() should reset IN_PROGRESS to STOPPED."""
        db_manager.add_url("https://example.com/gallery")
        claimed = db_manager.claim_next_pending()

        count = db_manager.reset_in_progress_to_stopped()

        assert count == 1
        row = db_manager.get_by_url("https://example.com/gallery")
        assert row.status == UrlStatus.STOPPED
        assert "Interrupted" in row.last_error

    def test_reset_returns_count(self, db_manager: DatabaseManager):
        """reset_in_progress_to_stopped() should return number of reset URLs."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")
        db_manager.add_url("https://example.com/3")

        db_manager.claim_next_pending()
        db_manager.claim_next_pending()

        count = db_manager.reset_in_progress_to_stopped()

        assert count == 2

    def test_reset_no_in_progress(self, db_manager: DatabaseManager):
        """reset_in_progress_to_stopped() should return 0 when no IN_PROGRESS."""
        db_manager.add_url("https://example.com/gallery")

        count = db_manager.reset_in_progress_to_stopped()

        assert count == 0


class TestDeleteUrl:
    """Test URL deletion."""

    def test_delete_url_success(self, db_manager: DatabaseManager):
        """delete_url() should remove the URL."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")

        result = db_manager.delete_url(row.id)

        assert result is True
        assert db_manager.get_by_url("https://example.com/gallery") is None

    def test_delete_url_not_found(self, db_manager: DatabaseManager):
        """delete_url() should return False for non-existing URL."""
        result = db_manager.delete_url(9999)
        assert result is False

    def test_delete_url_in_progress_raises(self, db_manager: DatabaseManager):
        """delete_url() should raise RuntimeError for IN_PROGRESS URL."""
        db_manager.add_url("https://example.com/gallery")
        claimed = db_manager.claim_next_pending()

        with pytest.raises(RuntimeError, match="Cannot remove.*downloading"):
            db_manager.delete_url(claimed.id)

    def test_delete_url_completed_allowed(self, db_manager: DatabaseManager):
        """delete_url() should allow deleting COMPLETED URLs."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")
        db_manager.mark_completed(row.id)

        result = db_manager.delete_url(row.id)

        assert result is True

    def test_delete_url_failed_allowed(self, db_manager: DatabaseManager):
        """delete_url() should allow deleting FAILED URLs."""
        db_manager.add_url("https://example.com/gallery")
        row = db_manager.get_by_url("https://example.com/gallery")
        db_manager.mark_failed(row.id, "Error")

        result = db_manager.delete_url(row.id)

        assert result is True


class TestGetStatistics:
    """Test database statistics retrieval."""

    def test_get_statistics_empty(self, db_manager: DatabaseManager):
        """get_statistics() should return zeros for empty database."""
        stats = db_manager.get_statistics()

        assert stats["total"] == 0
        assert stats["total_downloads"] == 0
        assert stats["date_range"] == (None, None)

    def test_get_statistics_counts_by_status(self, db_manager: DatabaseManager):
        """get_statistics() should count each status."""
        db_manager.add_url("https://example.com/pending")
        db_manager.add_url("https://example.com/completed")
        db_manager.add_url("https://example.com/failed")

        # Mark one as completed
        row = db_manager.get_by_url("https://example.com/completed")
        db_manager.mark_completed(row.id)

        # Mark one as failed
        row = db_manager.get_by_url("https://example.com/failed")
        db_manager.mark_failed(row.id, "Error")

        stats = db_manager.get_statistics()

        assert stats["total"] == 3
        assert stats["by_status"][UrlStatus.PENDING] == 1
        assert stats["by_status"][UrlStatus.COMPLETED] == 1
        assert stats["by_status"][UrlStatus.FAILED] == 1

    def test_get_statistics_total_downloads(self, db_manager: DatabaseManager):
        """get_statistics() should sum download_count."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")

        row1 = db_manager.get_by_url("https://example.com/1")
        row2 = db_manager.get_by_url("https://example.com/2")

        # Complete twice
        db_manager.mark_completed(row1.id)
        db_manager.requeue_existing_url("https://example.com/1")
        db_manager.mark_completed(row1.id)
        db_manager.mark_completed(row2.id)

        stats = db_manager.get_statistics()

        assert stats["total_downloads"] == 3


class TestClearByStatus:
    """Test bulk deletion by status."""

    def test_clear_by_status_completed(self, db_manager: DatabaseManager):
        """clear_by_status() should delete all URLs with given status."""
        db_manager.add_url("https://example.com/completed1")
        db_manager.add_url("https://example.com/completed2")
        db_manager.add_url("https://example.com/pending")

        row1 = db_manager.get_by_url("https://example.com/completed1")
        row2 = db_manager.get_by_url("https://example.com/completed2")
        db_manager.mark_completed(row1.id)
        db_manager.mark_completed(row2.id)

        deleted = db_manager.clear_by_status(UrlStatus.COMPLETED)

        assert deleted == 2
        assert db_manager.get_by_url("https://example.com/completed1") is None
        assert db_manager.get_by_url("https://example.com/completed2") is None
        assert db_manager.get_by_url("https://example.com/pending") is not None

    def test_clear_by_status_in_progress_raises(self, db_manager: DatabaseManager):
        """clear_by_status() should raise for IN_PROGRESS status."""
        with pytest.raises(RuntimeError, match="Cannot clear.*downloading"):
            db_manager.clear_by_status(UrlStatus.IN_PROGRESS)


class TestRetryAllFailed:
    """Test bulk retry of failed URLs."""

    def test_retry_all_failed(self, db_manager: DatabaseManager):
        """retry_all_failed() should reset failed URLs to pending."""
        db_manager.add_url("https://example.com/failed1")
        db_manager.add_url("https://example.com/failed2")
        db_manager.add_url("https://example.com/completed")

        row1 = db_manager.get_by_url("https://example.com/failed1")
        row2 = db_manager.get_by_url("https://example.com/failed2")
        row3 = db_manager.get_by_url("https://example.com/completed")
        db_manager.mark_failed(row1.id, "Error 1")
        db_manager.mark_failed(row2.id, "Error 2")
        db_manager.mark_completed(row3.id)

        reset = db_manager.retry_all_failed()

        assert reset == 2
        assert db_manager.get_by_url("https://example.com/failed1").status == UrlStatus.PENDING
        assert db_manager.get_by_url("https://example.com/failed2").status == UrlStatus.PENDING
        assert db_manager.get_by_url("https://example.com/completed").status == UrlStatus.COMPLETED


class TestClearAll:
    """Test clearing entire database."""

    def test_clear_all(self, db_manager: DatabaseManager):
        """clear_all() should delete all URLs."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")
        db_manager.add_url("https://example.com/3")

        deleted = db_manager.clear_all()

        assert deleted == 3
        assert db_manager.list_urls() == []

    def test_clear_all_with_in_progress_raises(self, db_manager: DatabaseManager):
        """clear_all() should raise if any URL is in progress."""
        db_manager.add_url("https://example.com/1")
        db_manager.claim_next_pending()

        with pytest.raises(RuntimeError, match="downloads are in progress"):
            db_manager.clear_all()


class TestVacuum:
    """Test database vacuum/compaction."""

    def test_vacuum_runs(self, db_manager: DatabaseManager):
        """vacuum() should run without error."""
        db_manager.add_url("https://example.com/1")
        db_manager.delete_url(db_manager.get_by_url("https://example.com/1").id)

        # Should not raise
        db_manager.vacuum()


class TestGetFileSize:
    """Test file size retrieval."""

    def test_get_file_size(self, db_manager: DatabaseManager):
        """get_file_size() should return positive size for existing database."""
        db_manager.add_url("https://example.com/1")

        size = db_manager.get_file_size()

        assert size > 0


class TestExportImportUrls:
    """Test URL export and import."""

    def test_export_urls(self, db_manager: DatabaseManager, tmp_path: Path):
        """export_urls() should write URLs to file."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")

        export_file = tmp_path / "export.txt"
        count = db_manager.export_urls(export_file)

        assert count == 2
        assert export_file.exists()
        content = export_file.read_text()
        assert "https://example.com/1" in content
        assert "https://example.com/2" in content

    def test_import_urls(self, db_manager: DatabaseManager, tmp_path: Path):
        """import_urls() should add URLs from file."""
        import_file = tmp_path / "import.txt"
        import_file.write_text("https://example.com/new1\nhttps://example.com/new2\n")

        added, skipped = db_manager.import_urls(import_file)

        assert added == 2
        assert skipped == 0
        assert db_manager.get_by_url("https://example.com/new1") is not None
        assert db_manager.get_by_url("https://example.com/new2") is not None

    def test_import_urls_skips_duplicates(self, db_manager: DatabaseManager, tmp_path: Path):
        """import_urls() should skip existing URLs."""
        db_manager.add_url("https://example.com/existing")

        import_file = tmp_path / "import.txt"
        import_file.write_text("https://example.com/existing\nhttps://example.com/new\n")

        added, skipped = db_manager.import_urls(import_file)

        assert added == 1
        assert skipped == 1

    def test_import_urls_skips_comments(self, db_manager: DatabaseManager, tmp_path: Path):
        """import_urls() should skip lines starting with #."""
        import_file = tmp_path / "import.txt"
        import_file.write_text("# This is a comment\nhttps://example.com/url\n# Another comment\n")

        added, skipped = db_manager.import_urls(import_file)

        assert added == 1
        assert skipped == 0
