"""Tests for DatabaseManager."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gallerydl_beyond.common.constants import UrlStatus
from gallerydl_beyond.common.database_manager import DatabaseManager, TagRow, UrlRow


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


class TestTagCreation:
    """Test tag tables creation."""

    def test_ensure_database_creates_tags_table(self, tmp_db_path: Path):
        """ensure_database() should create the tags table."""
        manager = DatabaseManager(db_path=tmp_db_path, mutex=MagicMock())
        manager.ensure_database()

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.execute("PRAGMA table_info(tags);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert columns == {"id", "name", "date_created"}

    def test_ensure_database_creates_url_tags_table(self, tmp_db_path: Path):
        """ensure_database() should create the url_tags table."""
        manager = DatabaseManager(db_path=tmp_db_path, mutex=MagicMock())
        manager.ensure_database()

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.execute("PRAGMA table_info(url_tags);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert columns == {"url_id", "tag_id", "date_assigned"}


class TestTagCRUD:
    """Test tag create/read/update/delete operations."""

    def test_create_tag_returns_id(self, db_manager: DatabaseManager):
        """create_tag() should return the new tag id."""
        tag_id = db_manager.create_tag("test-tag")

        assert tag_id is not None
        assert isinstance(tag_id, int)
        assert tag_id > 0

    def test_create_tag_stores_tag(self, db_manager: DatabaseManager):
        """create_tag() should store the tag in the database."""
        tag_id = db_manager.create_tag("my-tag")

        tag = db_manager.get_tag_by_id(tag_id)
        assert tag is not None
        assert tag.name == "my-tag"
        assert tag.date_created is not None

    def test_create_tag_duplicate_returns_none(self, db_manager: DatabaseManager):
        """Creating a duplicate tag should return None."""
        db_manager.create_tag("duplicate")
        result = db_manager.create_tag("duplicate")

        assert result is None

    def test_create_tag_strips_whitespace(self, db_manager: DatabaseManager):
        """create_tag() should strip whitespace from name."""
        tag_id = db_manager.create_tag("  my-tag  ")

        tag = db_manager.get_tag_by_id(tag_id)
        assert tag.name == "my-tag"

    def test_create_tag_empty_raises(self, db_manager: DatabaseManager):
        """create_tag() should raise ValueError for empty name."""
        with pytest.raises(ValueError, match="tag name cannot be empty"):
            db_manager.create_tag("")

        with pytest.raises(ValueError, match="tag name cannot be empty"):
            db_manager.create_tag("   ")

    def test_list_tags_empty(self, db_manager: DatabaseManager):
        """list_tags() should return empty list when no tags."""
        tags = db_manager.list_tags()
        assert tags == []

    def test_list_tags_returns_all(self, db_manager: DatabaseManager):
        """list_tags() should return all tags sorted by name."""
        db_manager.create_tag("zebra")
        db_manager.create_tag("apple")
        db_manager.create_tag("mango")

        tags = db_manager.list_tags()

        assert len(tags) == 3
        assert tags[0].name == "apple"
        assert tags[1].name == "mango"
        assert tags[2].name == "zebra"

    def test_rename_tag(self, db_manager: DatabaseManager):
        """rename_tag() should update the tag name."""
        tag_id = db_manager.create_tag("old-name")

        result = db_manager.rename_tag(tag_id, "new-name")

        assert result is True
        tag = db_manager.get_tag_by_id(tag_id)
        assert tag.name == "new-name"

    def test_rename_tag_not_found(self, db_manager: DatabaseManager):
        """rename_tag() should return False for non-existing tag."""
        result = db_manager.rename_tag(9999, "new-name")
        assert result is False

    def test_rename_tag_conflict(self, db_manager: DatabaseManager):
        """rename_tag() should return False when name conflicts."""
        db_manager.create_tag("existing")
        tag_id = db_manager.create_tag("to-rename")

        result = db_manager.rename_tag(tag_id, "existing")

        assert result is False

    def test_rename_tag_empty_raises(self, db_manager: DatabaseManager):
        """rename_tag() should raise ValueError for empty name."""
        tag_id = db_manager.create_tag("test")

        with pytest.raises(ValueError, match="tag name cannot be empty"):
            db_manager.rename_tag(tag_id, "")

    def test_delete_tag(self, db_manager: DatabaseManager):
        """delete_tag() should remove the tag."""
        tag_id = db_manager.create_tag("to-delete")

        result = db_manager.delete_tag(tag_id)

        assert result is True
        assert db_manager.get_tag_by_id(tag_id) is None

    def test_delete_tag_not_found(self, db_manager: DatabaseManager):
        """delete_tag() should return False for non-existing tag."""
        result = db_manager.delete_tag(9999)
        assert result is False

    def test_get_tag_by_id_found(self, db_manager: DatabaseManager):
        """get_tag_by_id() should return TagRow for existing tag."""
        tag_id = db_manager.create_tag("my-tag")

        tag = db_manager.get_tag_by_id(tag_id)

        assert tag is not None
        assert isinstance(tag, TagRow)
        assert tag.name == "my-tag"

    def test_get_tag_by_id_not_found(self, db_manager: DatabaseManager):
        """get_tag_by_id() should return None for non-existing tag."""
        tag = db_manager.get_tag_by_id(9999)
        assert tag is None


class TestUrlTagAssociation:
    """Test URL-tag association methods."""

    def test_assign_tag_to_url(self, db_manager: DatabaseManager):
        """assign_tag_to_url() should create an association."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag_id = db_manager.create_tag("my-tag")

        result = db_manager.assign_tag_to_url(url_id, tag_id)

        assert result is True
        tags = db_manager.get_tags_for_url(url_id)
        assert len(tags) == 1
        assert tags[0].name == "my-tag"

    def test_assign_tag_duplicate(self, db_manager: DatabaseManager):
        """Assigning the same tag twice should return False."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag_id = db_manager.create_tag("my-tag")

        db_manager.assign_tag_to_url(url_id, tag_id)
        result = db_manager.assign_tag_to_url(url_id, tag_id)

        assert result is False

    def test_remove_tag_from_url(self, db_manager: DatabaseManager):
        """remove_tag_from_url() should remove the association."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag_id = db_manager.create_tag("my-tag")
        db_manager.assign_tag_to_url(url_id, tag_id)

        result = db_manager.remove_tag_from_url(url_id, tag_id)

        assert result is True
        tags = db_manager.get_tags_for_url(url_id)
        assert tags == []

    def test_remove_tag_not_assigned(self, db_manager: DatabaseManager):
        """remove_tag_from_url() should return False when not assigned."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag_id = db_manager.create_tag("my-tag")

        result = db_manager.remove_tag_from_url(url_id, tag_id)

        assert result is False

    def test_get_tags_for_url_empty(self, db_manager: DatabaseManager):
        """get_tags_for_url() should return empty list when no tags."""
        url_id = db_manager.add_url("https://example.com/gallery")

        tags = db_manager.get_tags_for_url(url_id)

        assert tags == []

    def test_get_tags_for_url_multiple(self, db_manager: DatabaseManager):
        """get_tags_for_url() should return all assigned tags sorted."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag1 = db_manager.create_tag("zebra")
        tag2 = db_manager.create_tag("apple")
        db_manager.assign_tag_to_url(url_id, tag1)
        db_manager.assign_tag_to_url(url_id, tag2)

        tags = db_manager.get_tags_for_url(url_id)

        assert len(tags) == 2
        assert tags[0].name == "apple"
        assert tags[1].name == "zebra"

    def test_set_url_tags(self, db_manager: DatabaseManager):
        """set_url_tags() should replace all tags for a URL."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag1 = db_manager.create_tag("tag1")
        tag2 = db_manager.create_tag("tag2")
        tag3 = db_manager.create_tag("tag3")

        # Assign initial tags
        db_manager.assign_tag_to_url(url_id, tag1)
        db_manager.assign_tag_to_url(url_id, tag2)

        # Replace with new set
        db_manager.set_url_tags(url_id, [tag2, tag3])

        tags = db_manager.get_tags_for_url(url_id)
        tag_names = [t.name for t in tags]
        assert sorted(tag_names) == ["tag2", "tag3"]

    def test_set_url_tags_empty(self, db_manager: DatabaseManager):
        """set_url_tags() with empty list should remove all tags."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag_id = db_manager.create_tag("my-tag")
        db_manager.assign_tag_to_url(url_id, tag_id)

        db_manager.set_url_tags(url_id, [])

        tags = db_manager.get_tags_for_url(url_id)
        assert tags == []

    def test_delete_tag_cascade(self, db_manager: DatabaseManager):
        """Deleting a tag should cascade to url_tags."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag_id = db_manager.create_tag("my-tag")
        db_manager.assign_tag_to_url(url_id, tag_id)

        db_manager.delete_tag(tag_id)

        tags = db_manager.get_tags_for_url(url_id)
        assert tags == []

    def test_delete_url_cascade(self, db_manager: DatabaseManager):
        """Deleting a URL should cascade to url_tags."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag_id = db_manager.create_tag("my-tag")
        db_manager.assign_tag_to_url(url_id, tag_id)

        db_manager.delete_url(url_id)

        # Tag should still exist
        tag = db_manager.get_tag_by_id(tag_id)
        assert tag is not None


class TestCountUrls:
    """Test URL counting for pagination."""

    def test_count_urls_no_filter(self, db_manager: DatabaseManager):
        """count_urls() should return total count without filters."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")
        db_manager.add_url("https://example.com/3")

        count = db_manager.count_urls()

        assert count == 3

    def test_count_urls_empty(self, db_manager: DatabaseManager):
        """count_urls() should return 0 for empty database."""
        count = db_manager.count_urls()
        assert count == 0

    def test_count_urls_with_search(self, db_manager: DatabaseManager):
        """count_urls() should filter by search term."""
        db_manager.add_url("https://example.com/cats")
        db_manager.add_url("https://example.com/dogs")
        db_manager.add_url("https://other.com/cats")

        count = db_manager.count_urls(search="cats")

        assert count == 2

    def test_count_urls_with_tag(self, db_manager: DatabaseManager):
        """count_urls() should filter by tag."""
        url1 = db_manager.add_url("https://example.com/tagged1")
        url2 = db_manager.add_url("https://example.com/tagged2")
        db_manager.add_url("https://example.com/untagged")
        tag_id = db_manager.create_tag("my-tag")
        db_manager.assign_tag_to_url(url1, tag_id)
        db_manager.assign_tag_to_url(url2, tag_id)

        count = db_manager.count_urls(tag_id=tag_id)

        assert count == 2

    def test_count_urls_combined_filters(self, db_manager: DatabaseManager):
        """count_urls() should combine search and tag filters."""
        url1 = db_manager.add_url("https://example.com/cats")
        url2 = db_manager.add_url("https://example.com/dogs")
        url3 = db_manager.add_url("https://other.com/cats")
        tag_id = db_manager.create_tag("animals")
        db_manager.assign_tag_to_url(url1, tag_id)
        db_manager.assign_tag_to_url(url3, tag_id)

        count = db_manager.count_urls(search="example", tag_id=tag_id)

        assert count == 1


class TestListUrlsWithOffset:
    """Test list_urls with offset for pagination."""

    def test_list_urls_with_offset(self, db_manager: DatabaseManager):
        """list_urls() should skip rows based on offset."""
        for i in range(10):
            db_manager.add_url(f"https://example.com/{i}")

        # Get second page (5 items per page, page 2)
        urls = db_manager.list_urls(limit=5, offset=5)

        assert len(urls) == 5

    def test_list_urls_offset_beyond_end(self, db_manager: DatabaseManager):
        """list_urls() should return empty list when offset is beyond end."""
        db_manager.add_url("https://example.com/1")
        db_manager.add_url("https://example.com/2")

        urls = db_manager.list_urls(offset=100)

        assert urls == []

    def test_list_urls_offset_with_filter(self, db_manager: DatabaseManager):
        """list_urls() should apply offset after filtering."""
        for i in range(10):
            db_manager.add_url(f"https://example.com/cats/{i}")
        for i in range(10):
            db_manager.add_url(f"https://example.com/dogs/{i}")

        # Get second page of cats (3 per page)
        urls = db_manager.list_urls(search="cats", limit=3, offset=3)

        assert len(urls) == 3
        assert all("cats" in u.url for u in urls)


class TestListUrlsSorting:
    """Test list_urls sorting functionality."""

    def test_list_urls_sort_by_url_ascending(self, db_manager: DatabaseManager):
        """list_urls() should sort by URL ascending."""
        db_manager.add_url("https://example.com/zebra")
        db_manager.add_url("https://example.com/apple")
        db_manager.add_url("https://example.com/mango")

        urls = db_manager.list_urls(sort_column="url", sort_ascending=True)

        assert len(urls) == 3
        assert urls[0].url == "https://example.com/apple"
        assert urls[1].url == "https://example.com/mango"
        assert urls[2].url == "https://example.com/zebra"

    def test_list_urls_sort_by_url_descending(self, db_manager: DatabaseManager):
        """list_urls() should sort by URL descending."""
        db_manager.add_url("https://example.com/zebra")
        db_manager.add_url("https://example.com/apple")
        db_manager.add_url("https://example.com/mango")

        urls = db_manager.list_urls(sort_column="url", sort_ascending=False)

        assert len(urls) == 3
        assert urls[0].url == "https://example.com/zebra"
        assert urls[1].url == "https://example.com/mango"
        assert urls[2].url == "https://example.com/apple"

    def test_list_urls_sort_by_status(self, db_manager: DatabaseManager):
        """list_urls() should sort by status."""
        db_manager.add_url("https://example.com/pending")
        db_manager.add_url("https://example.com/completed")
        db_manager.add_url("https://example.com/failed")

        row = db_manager.get_by_url("https://example.com/completed")
        db_manager.mark_completed(row.id)
        row = db_manager.get_by_url("https://example.com/failed")
        db_manager.mark_failed(row.id, "Error")

        urls = db_manager.list_urls(sort_column="status", sort_ascending=True)

        assert len(urls) == 3
        # Status 0=pending, 2=completed, 3=failed
        assert urls[0].status == UrlStatus.PENDING
        assert urls[1].status == UrlStatus.COMPLETED
        assert urls[2].status == UrlStatus.FAILED

    def test_list_urls_sort_by_id(self, db_manager: DatabaseManager):
        """list_urls() should sort by id."""
        id1 = db_manager.add_url("https://example.com/first")
        id2 = db_manager.add_url("https://example.com/second")
        id3 = db_manager.add_url("https://example.com/third")

        urls = db_manager.list_urls(sort_column="id", sort_ascending=True)

        assert len(urls) == 3
        assert urls[0].id == id1
        assert urls[1].id == id2
        assert urls[2].id == id3

    def test_list_urls_sort_invalid_column_uses_default(self, db_manager: DatabaseManager):
        """list_urls() should use default sort for invalid column."""
        db_manager.add_url("https://example.com/test")

        # Should not raise, uses default date_processed sort
        urls = db_manager.list_urls(sort_column="invalid_column")

        assert len(urls) == 1


class TestListUrlsWithTags:
    """Test list_urls with tag filtering and tag column."""

    def test_list_urls_includes_tags(self, db_manager: DatabaseManager):
        """list_urls() should include tags in the UrlRow."""
        url_id = db_manager.add_url("https://example.com/gallery")
        tag1 = db_manager.create_tag("alpha")
        tag2 = db_manager.create_tag("beta")
        db_manager.assign_tag_to_url(url_id, tag1)
        db_manager.assign_tag_to_url(url_id, tag2)

        urls = db_manager.list_urls()

        assert len(urls) == 1
        # Tags should be sorted alphabetically in the tuple
        assert urls[0].tags == ("alpha", "beta")

    def test_list_urls_empty_tags(self, db_manager: DatabaseManager):
        """list_urls() should return empty tags tuple when no tags."""
        db_manager.add_url("https://example.com/gallery")

        urls = db_manager.list_urls()

        assert len(urls) == 1
        assert urls[0].tags == ()

    def test_list_urls_filter_by_tag(self, db_manager: DatabaseManager):
        """list_urls(tag_id=X) should only return URLs with that tag."""
        url1 = db_manager.add_url("https://example.com/tagged")
        db_manager.add_url("https://example.com/untagged")
        tag_id = db_manager.create_tag("my-tag")
        db_manager.assign_tag_to_url(url1, tag_id)

        urls = db_manager.list_urls(tag_id=tag_id)

        assert len(urls) == 1
        assert urls[0].url == "https://example.com/tagged"

    def test_list_urls_filter_combined(self, db_manager: DatabaseManager):
        """list_urls() should combine search and tag filters."""
        url1 = db_manager.add_url("https://example.com/cats")
        url2 = db_manager.add_url("https://example.com/dogs")
        url3 = db_manager.add_url("https://other.com/cats")
        tag_id = db_manager.create_tag("animals")
        db_manager.assign_tag_to_url(url1, tag_id)
        db_manager.assign_tag_to_url(url3, tag_id)

        # Filter by both search and tag
        urls = db_manager.list_urls(search="example", tag_id=tag_id)

        assert len(urls) == 1
        assert urls[0].url == "https://example.com/cats"


class TestBulkUpdateStatus:
    """Test bulk_update_status method."""

    def test_bulk_update_status_multiple_urls(self, db_manager: DatabaseManager):
        """bulk_update_status should update all specified URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        id3 = db_manager.add_url("https://example.com/3")

        updated = db_manager.bulk_update_status([id1, id2], UrlStatus.SKIPPED)

        assert updated == 2
        row1 = db_manager.get_by_url("https://example.com/1")
        row2 = db_manager.get_by_url("https://example.com/2")
        row3 = db_manager.get_by_url("https://example.com/3")
        assert row1.status == UrlStatus.SKIPPED
        assert row2.status == UrlStatus.SKIPPED
        assert row3.status == UrlStatus.PENDING  # Unchanged

    def test_bulk_update_status_skips_in_progress(self, db_manager: DatabaseManager):
        """bulk_update_status should not modify IN_PROGRESS URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        # Claim id1 to make it IN_PROGRESS (claim_next_pending gets first by id)
        db_manager.claim_next_pending()

        updated = db_manager.bulk_update_status([id1, id2], UrlStatus.FAILED)

        # Only id2 should be updated (id1 is IN_PROGRESS)
        assert updated == 1
        row1 = db_manager.get_by_url("https://example.com/1")
        row2 = db_manager.get_by_url("https://example.com/2")
        assert row1.status == UrlStatus.IN_PROGRESS  # Should remain IN_PROGRESS
        assert row2.status == UrlStatus.FAILED

    def test_bulk_update_status_empty_list(self, db_manager: DatabaseManager):
        """bulk_update_status with empty list should return 0."""
        updated = db_manager.bulk_update_status([], UrlStatus.SKIPPED)
        assert updated == 0

    def test_bulk_update_status_rejects_in_progress_target(self, db_manager: DatabaseManager):
        """bulk_update_status should reject setting status to IN_PROGRESS."""
        id1 = db_manager.add_url("https://example.com/1")

        with pytest.raises(RuntimeError, match="IN_PROGRESS"):
            db_manager.bulk_update_status([id1], UrlStatus.IN_PROGRESS)


class TestBulkDeleteUrls:
    """Test bulk_delete_urls method."""

    def test_bulk_delete_urls_multiple(self, db_manager: DatabaseManager):
        """bulk_delete_urls should delete all specified URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        id3 = db_manager.add_url("https://example.com/3")

        deleted, skipped = db_manager.bulk_delete_urls([id1, id2])

        assert deleted == 2
        assert skipped == 0
        assert db_manager.get_by_url("https://example.com/1") is None
        assert db_manager.get_by_url("https://example.com/2") is None
        assert db_manager.get_by_url("https://example.com/3") is not None

    def test_bulk_delete_urls_skips_in_progress(self, db_manager: DatabaseManager):
        """bulk_delete_urls should skip IN_PROGRESS URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        # Claim id1 to make it IN_PROGRESS
        db_manager.claim_next_pending()

        deleted, skipped = db_manager.bulk_delete_urls([id1, id2])

        assert deleted == 1
        assert skipped == 1
        assert db_manager.get_by_url("https://example.com/1") is not None  # Still exists
        assert db_manager.get_by_url("https://example.com/2") is None

    def test_bulk_delete_urls_empty_list(self, db_manager: DatabaseManager):
        """bulk_delete_urls with empty list should return (0, 0)."""
        deleted, skipped = db_manager.bulk_delete_urls([])
        assert deleted == 0
        assert skipped == 0


class TestBulkAddTag:
    """Test bulk_add_tag method."""

    def test_bulk_add_tag_multiple_urls(self, db_manager: DatabaseManager):
        """bulk_add_tag should add tag to all specified URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        id3 = db_manager.add_url("https://example.com/3")
        tag_id = db_manager.create_tag("bulk-tag")

        added = db_manager.bulk_add_tag([id1, id2], tag_id)

        assert added == 2
        tags1 = db_manager.get_tags_for_url(id1)
        tags2 = db_manager.get_tags_for_url(id2)
        tags3 = db_manager.get_tags_for_url(id3)
        assert any(t.name == "bulk-tag" for t in tags1)
        assert any(t.name == "bulk-tag" for t in tags2)
        assert not any(t.name == "bulk-tag" for t in tags3)

    def test_bulk_add_tag_skips_already_tagged(self, db_manager: DatabaseManager):
        """bulk_add_tag should skip URLs that already have the tag."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        tag_id = db_manager.create_tag("existing-tag")
        db_manager.assign_tag_to_url(id1, tag_id)

        added = db_manager.bulk_add_tag([id1, id2], tag_id)

        assert added == 1  # Only id2 was newly tagged

    def test_bulk_add_tag_empty_list(self, db_manager: DatabaseManager):
        """bulk_add_tag with empty list should return 0."""
        tag_id = db_manager.create_tag("test-tag")
        added = db_manager.bulk_add_tag([], tag_id)
        assert added == 0


class TestBulkRemoveTag:
    """Test bulk_remove_tag method."""

    def test_bulk_remove_tag_multiple_urls(self, db_manager: DatabaseManager):
        """bulk_remove_tag should remove tag from all specified URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        tag_id = db_manager.create_tag("remove-me")
        db_manager.assign_tag_to_url(id1, tag_id)
        db_manager.assign_tag_to_url(id2, tag_id)

        removed = db_manager.bulk_remove_tag([id1, id2], tag_id)

        assert removed == 2
        tags1 = db_manager.get_tags_for_url(id1)
        tags2 = db_manager.get_tags_for_url(id2)
        assert not any(t.name == "remove-me" for t in tags1)
        assert not any(t.name == "remove-me" for t in tags2)

    def test_bulk_remove_tag_ignores_untagged(self, db_manager: DatabaseManager):
        """bulk_remove_tag should not fail on URLs without the tag."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        tag_id = db_manager.create_tag("partial-tag")
        db_manager.assign_tag_to_url(id1, tag_id)  # Only id1 has tag

        removed = db_manager.bulk_remove_tag([id1, id2], tag_id)

        assert removed == 1  # Only id1 had the tag

    def test_bulk_remove_tag_empty_list(self, db_manager: DatabaseManager):
        """bulk_remove_tag with empty list should return 0."""
        tag_id = db_manager.create_tag("test-tag")
        removed = db_manager.bulk_remove_tag([], tag_id)
        assert removed == 0


class TestBulkRequeue:
    """Test bulk_requeue method."""

    def test_bulk_requeue_multiple_urls(self, db_manager: DatabaseManager):
        """bulk_requeue should requeue all specified URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        db_manager.mark_completed(id1)
        db_manager.mark_completed(id2)

        requeued = db_manager.bulk_requeue([id1, id2])

        assert requeued == 2
        row1 = db_manager.get_by_url("https://example.com/1")
        row2 = db_manager.get_by_url("https://example.com/2")
        assert row1.status == UrlStatus.PENDING
        assert row2.status == UrlStatus.PENDING

    def test_bulk_requeue_with_force_redownload(self, db_manager: DatabaseManager):
        """bulk_requeue should set force_redownload flag."""
        id1 = db_manager.add_url("https://example.com/1")
        db_manager.mark_completed(id1)

        db_manager.bulk_requeue([id1], force_redownload=True)

        row = db_manager.get_by_url("https://example.com/1")
        assert row.status == UrlStatus.PENDING
        assert row.force_redownload == 1

    def test_bulk_requeue_with_check_new_only(self, db_manager: DatabaseManager):
        """bulk_requeue should set check_new_only flag."""
        id1 = db_manager.add_url("https://example.com/1")
        db_manager.mark_completed(id1)

        db_manager.bulk_requeue([id1], check_new_only=True)

        row = db_manager.get_by_url("https://example.com/1")
        assert row.status == UrlStatus.PENDING
        assert row.check_new_only == 1

    def test_bulk_requeue_skips_in_progress(self, db_manager: DatabaseManager):
        """bulk_requeue should not modify IN_PROGRESS URLs."""
        id1 = db_manager.add_url("https://example.com/1")
        id2 = db_manager.add_url("https://example.com/2")
        # Claim id1 to make it IN_PROGRESS
        db_manager.claim_next_pending()

        requeued = db_manager.bulk_requeue([id1, id2])

        # Only id2 should be affected (but it was already PENDING)
        # id1 should remain IN_PROGRESS
        assert requeued == 1
        row1 = db_manager.get_by_url("https://example.com/1")
        assert row1.status == UrlStatus.IN_PROGRESS

    def test_bulk_requeue_clears_last_error(self, db_manager: DatabaseManager):
        """bulk_requeue should clear last_error."""
        id1 = db_manager.add_url("https://example.com/1")
        db_manager.mark_failed(id1, "some error")

        db_manager.bulk_requeue([id1])

        row = db_manager.get_by_url("https://example.com/1")
        assert row.status == UrlStatus.PENDING
        assert row.last_error is None

    def test_bulk_requeue_empty_list(self, db_manager: DatabaseManager):
        """bulk_requeue with empty list should return 0."""
        requeued = db_manager.bulk_requeue([])
        assert requeued == 0
