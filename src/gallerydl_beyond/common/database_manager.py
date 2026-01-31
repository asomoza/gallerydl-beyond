from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import QMutex

from gallerydl_beyond.common.constants import DEFAULT_DB_FILENAME, UrlStatus


@dataclass(frozen=True)
class UrlRow:
    id: int
    url: str
    status: int
    force_redownload: int
    check_new_only: int
    download_count: int
    date_added: str
    date_processed: str | None
    last_error: str | None
    skipped_count: int = 0


class DatabaseManager:
    """Thread-safe SQLite access layer.

    Uses a `QMutex` so it can be safely used from Qt threads.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_FILENAME, mutex: QMutex | None = None):
        self.db_path = Path(db_path)
        self._mutex = mutex or QMutex()

    @contextmanager
    def _locked(self):
        self._mutex.lock()
        try:
            yield
        finally:
            self._mutex.unlock()

    @contextmanager
    def _connect(self):
        # Keep connections short-lived; safer across threads.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def ensure_database(self) -> None:
        """Create DB file if missing and ensure schema is migrated."""
        with self._locked():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.db_path.exists():
                self.db_path.touch()

            with self._connect() as conn:
                self._migrate_if_needed(conn)

    def _migrate_if_needed(self, conn: sqlite3.Connection) -> None:
        """Migrate from legacy schema to enhanced schema."""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls';")
        if cursor.fetchone() is None:
            self._create_urls_table(conn)
            return

        cursor.execute("PRAGMA table_info(urls);")
        cols = [row[1] for row in cursor.fetchall()]  # name is index 1

        # New schema already present
        if "status" in cols and "date_added" in cols:
            # Check if skipped_count column needs to be added
            if "skipped_count" not in cols:
                conn.execute("ALTER TABLE urls ADD COLUMN skipped_count INTEGER NOT NULL DEFAULT 0;")
            self._ensure_indexes(conn)
            return

        # Legacy schema (id, url, processed, date_processed)
        legacy_cols = {"id", "url", "processed", "date_processed"}
        if set(cols) >= legacy_cols and "status" not in cols:
            self._migrate_legacy_urls(conn)
            return

        # Unknown schema: do not destroy data.
        raise RuntimeError(f"Unsupported urls table schema: {cols}")

    def _create_urls_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                status INTEGER NOT NULL DEFAULT 0,
                force_redownload INTEGER NOT NULL DEFAULT 0,
                check_new_only INTEGER NOT NULL DEFAULT 0,
                download_count INTEGER NOT NULL DEFAULT 0,
                date_added TEXT NOT NULL,
                date_processed TEXT,
                last_error TEXT,
                skipped_count INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self._ensure_indexes(conn)

    def _ensure_indexes(self, conn: sqlite3.Connection) -> None:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status);")

    def _migrate_legacy_urls(self, conn: sqlite3.Connection) -> None:
        # Rename existing table and recreate with new schema.
        conn.execute("ALTER TABLE urls RENAME TO urls_legacy;")
        self._create_urls_table(conn)

        # Copy data. Use INSERT OR IGNORE to handle duplicate URLs.
        cursor = conn.cursor()
        cursor.execute("SELECT id, url, processed, date_processed FROM urls_legacy ORDER BY id ASC;")

        now = datetime.now(timezone.utc).isoformat()
        rows: Iterable[tuple[int, str, int, str | None]] = cursor.fetchall()
        for _legacy_id, url, processed, date_processed in rows:
            status = UrlStatus.COMPLETED if int(processed) == 1 else UrlStatus.PENDING
            download_count = 1 if status == UrlStatus.COMPLETED else 0
            date_added = date_processed or now

            conn.execute(
                """
                INSERT OR IGNORE INTO urls (
                    url, status, force_redownload, check_new_only, download_count,
                    date_added, date_processed, last_error
                ) VALUES (?, ?, 0, 0, ?, ?, ?, NULL);
                """,
                (url, status, download_count, date_added, date_processed),
            )

        # Keep legacy table around for safety; can be cleaned later.
        self._ensure_indexes(conn)

    def url_exists(self, url: str) -> bool:
        with self._locked(), self._connect() as conn:
            cur = conn.execute("SELECT 1 FROM urls WHERE url = ? LIMIT 1;", (url,))
            return cur.fetchone() is not None

    def get_by_url(self, url: str) -> UrlRow | None:
        url = url.strip()
        if not url:
            return None

        with self._locked(), self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, url, status, force_redownload, check_new_only, download_count,
                       date_added, date_processed, last_error, skipped_count
                FROM urls
                WHERE url = ?
                LIMIT 1;
                """,
                (url,),
            ).fetchone()

            if row is None:
                return None

            return UrlRow(
                id=int(row[0]),
                url=str(row[1]),
                status=int(row[2]),
                force_redownload=int(row[3]),
                check_new_only=int(row[4]),
                download_count=int(row[5]),
                date_added=str(row[6]),
                date_processed=row[7],
                last_error=row[8],
                skipped_count=int(row[9]) if row[9] is not None else 0,
            )

    def add_url(self, url: str, *, force_redownload: bool = False, check_new_only: bool = False) -> int | None:
        """Add a URL to the queue.

        Returns the new row id, or None if the URL already exists.
        """
        url = url.strip()
        if not url:
            raise ValueError("url cannot be empty")

        with self._locked(), self._connect() as conn:
            now = datetime.now(timezone.utc).isoformat()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO urls (
                        url, status, force_redownload, check_new_only,
                        download_count, date_added, date_processed, last_error
                    ) VALUES (?, ?, ?, ?, 0, ?, NULL, NULL);
                    """,
                    (
                        url,
                        UrlStatus.PENDING,
                        1 if force_redownload else 0,
                        1 if check_new_only else 0,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                return None

            return int(cur.lastrowid)

    def requeue_existing_url(
        self,
        url: str,
        *,
        force_redownload: bool = False,
        check_new_only: bool = False,
    ) -> int | None:
        """Re-queue an existing URL (UNIQUE url).

        Because `urls.url` is UNIQUE, duplicate handling must update the existing row
        instead of inserting a new one.

        Returns the row id if updated, otherwise None if URL doesn't exist.
        """
        url = url.strip()
        if not url:
            raise ValueError("url cannot be empty")

        with self._locked(), self._connect() as conn:
            row = conn.execute("SELECT id FROM urls WHERE url = ? LIMIT 1;", (url,)).fetchone()
            if row is None:
                return None

            url_id = int(row[0])
            conn.execute(
                """
                UPDATE urls
                SET status = ?,
                    force_redownload = ?,
                    check_new_only = ?,
                    last_error = NULL
                WHERE id = ?;
                """,
                (
                    UrlStatus.PENDING,
                    1 if force_redownload else 0,
                    1 if check_new_only else 0,
                    url_id,
                ),
            )
            return url_id

    def get_counts(self) -> tuple[int, int, int]:
        """Return (pending_count, stopped_count, active_count)."""
        with self._locked(), self._connect() as conn:
            pending = conn.execute("SELECT COUNT(*) FROM urls WHERE status = ?;", (UrlStatus.PENDING,)).fetchone()[0]
            stopped = conn.execute("SELECT COUNT(*) FROM urls WHERE status = ?;", (UrlStatus.STOPPED,)).fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM urls WHERE status = ?;", (UrlStatus.IN_PROGRESS,)).fetchone()[
                0
            ]
            return int(pending), int(stopped), int(active)

    def list_urls(self, *, search: str | None = None, limit: int = 500) -> list[UrlRow]:
        """Return recent URLs for History tab.

        `search` filters by substring match on URL.
        """
        limit = max(1, int(limit))

        with self._locked(), self._connect() as conn:
            if search and search.strip():
                needle = f"%{search.strip()}%"
                rows = conn.execute(
                    """
                    SELECT id, url, status, force_redownload, check_new_only, download_count,
                           date_added, date_processed, last_error, skipped_count
                    FROM urls
                    WHERE url LIKE ?
                    ORDER BY COALESCE(date_processed, date_added) DESC
                    LIMIT ?;
                    """,
                    (needle, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, url, status, force_redownload, check_new_only, download_count,
                           date_added, date_processed, last_error, skipped_count
                    FROM urls
                    ORDER BY COALESCE(date_processed, date_added) DESC
                    LIMIT ?;
                    """,
                    (limit,),
                ).fetchall()

            return [
                UrlRow(
                    id=int(r[0]),
                    url=str(r[1]),
                    status=int(r[2]),
                    force_redownload=int(r[3]),
                    check_new_only=int(r[4]),
                    download_count=int(r[5]),
                    date_added=str(r[6]),
                    date_processed=r[7],
                    last_error=r[8],
                    skipped_count=int(r[9]) if r[9] is not None else 0,
                )
                for r in rows
            ]

    def claim_next_pending(self, include_stopped: bool = False) -> UrlRow | None:
        """Atomically claim one pending URL (PENDING -> IN_PROGRESS).

        Args:
            include_stopped: If True, also claim STOPPED URLs. Use this only when
                            the user explicitly clicks Start, not for auto-refilling.
        """
        with self._locked(), self._connect() as conn:
            conn.isolation_level = None
            conn.execute("BEGIN IMMEDIATE;")
            if include_stopped:
                row = conn.execute(
                    """
                    SELECT id, url, status, force_redownload, check_new_only, download_count,
                           date_added, date_processed, last_error, skipped_count
                    FROM urls
                    WHERE status IN (?, ?)
                    ORDER BY id ASC
                    LIMIT 1;
                    """,
                    (UrlStatus.PENDING, UrlStatus.STOPPED),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id, url, status, force_redownload, check_new_only, download_count,
                           date_added, date_processed, last_error, skipped_count
                    FROM urls
                    WHERE status = ?
                    ORDER BY id ASC
                    LIMIT 1;
                    """,
                    (UrlStatus.PENDING,),
                ).fetchone()

            if row is None:
                conn.execute("COMMIT;")
                return None

            url_id = int(row[0])
            conn.execute("UPDATE urls SET status = ? WHERE id = ?;", (UrlStatus.IN_PROGRESS, url_id))
            conn.execute("COMMIT;")

            return UrlRow(
                id=int(row[0]),
                url=str(row[1]),
                status=UrlStatus.IN_PROGRESS,
                force_redownload=int(row[3]),
                check_new_only=int(row[4]),
                download_count=int(row[5]),
                date_added=str(row[6]),
                date_processed=row[7],
                last_error=row[8],
                skipped_count=int(row[9]) if row[9] is not None else 0,
            )

    def mark_completed(self, url_id: int) -> None:
        with self._locked(), self._connect() as conn:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE urls
                SET status = ?,
                    download_count = download_count + 1,
                    date_processed = ?,
                    last_error = NULL
                WHERE id = ?;
                """,
                (UrlStatus.COMPLETED, now, url_id),
            )

    def mark_failed(self, url_id: int, error: str) -> None:
        with self._locked(), self._connect() as conn:
            conn.execute(
                "UPDATE urls SET status = ?, last_error = ? WHERE id = ?;",
                (UrlStatus.FAILED, error, url_id),
            )

    def mark_pending(self, url_id: int) -> None:
        """Mark a URL as pending (put it back in the queue)."""
        with self._locked(), self._connect() as conn:
            conn.execute(
                "UPDATE urls SET status = ?, last_error = NULL WHERE id = ?;",
                (UrlStatus.PENDING, url_id),
            )

    def mark_stopped(self, url_id: int) -> None:
        """Mark a URL as stopped (user manually stopped the download)."""
        with self._locked(), self._connect() as conn:
            conn.execute(
                "UPDATE urls SET status = ?, last_error = ? WHERE id = ?;",
                (UrlStatus.STOPPED, "Stopped by user", url_id),
            )

    def mark_skipped(self, url_id: int) -> None:
        """Mark a URL as skipped (user chose to skip this download)."""
        with self._locked(), self._connect() as conn:
            conn.execute(
                "UPDATE urls SET status = ?, last_error = ? WHERE id = ?;",
                (UrlStatus.SKIPPED, "Skipped by user", url_id),
            )

    def mark_completed_partial(self, url_id: int, skipped_count: int, errors: str | None = None) -> None:
        """Mark a URL as completed with partial failures (some files skipped)."""
        with self._locked(), self._connect() as conn:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE urls
                SET status = ?,
                    download_count = download_count + 1,
                    date_processed = ?,
                    skipped_count = ?,
                    last_error = ?
                WHERE id = ?;
                """,
                (UrlStatus.COMPLETED_PARTIAL, now, skipped_count, errors, url_id),
            )

    def reset_in_progress_to_stopped(self) -> int:
        """Reset any IN_PROGRESS URLs to STOPPED status.

        This should be called on startup to handle URLs that were left in progress
        when the app was closed or crashed.

        Returns the number of URLs that were reset.
        """
        with self._locked(), self._connect() as conn:
            cur = conn.execute(
                "UPDATE urls SET status = ?, last_error = ? WHERE status = ?;",
                (UrlStatus.STOPPED, "Interrupted - app was closed", UrlStatus.IN_PROGRESS),
            )
            return cur.rowcount

    def delete_url(self, url_id: int) -> bool:
        """Delete a URL row from the database.

        Returns True if a row was deleted.

        Raises:
            RuntimeError: if the row is currently in progress.
        """
        with self._locked(), self._connect() as conn:
            row = conn.execute("SELECT status FROM urls WHERE id = ? LIMIT 1;", (int(url_id),)).fetchone()
            if row is None:
                return False

            status = int(row[0])
            if status == UrlStatus.IN_PROGRESS:
                raise RuntimeError("Cannot remove a URL while it is downloading")

            cur = conn.execute("DELETE FROM urls WHERE id = ?;", (int(url_id),))
            return int(cur.rowcount) > 0

    def get_statistics(self) -> dict:
        """Get comprehensive database statistics.

        Returns dict with:
            - total: total URL count
            - by_status: dict mapping status -> count
            - total_downloads: sum of all download_count
            - date_range: (oldest_date, newest_date) or (None, None)
        """
        with self._locked(), self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM urls;").fetchone()[0]

            by_status = {}
            for status_val in (
                UrlStatus.PENDING,
                UrlStatus.IN_PROGRESS,
                UrlStatus.COMPLETED,
                UrlStatus.FAILED,
                UrlStatus.STOPPED,
                UrlStatus.COMPLETED_PARTIAL,
                UrlStatus.SKIPPED,
            ):
                count = conn.execute(
                    "SELECT COUNT(*) FROM urls WHERE status = ?;", (status_val,)
                ).fetchone()[0]
                by_status[status_val] = int(count)

            total_downloads = conn.execute(
                "SELECT COALESCE(SUM(download_count), 0) FROM urls;"
            ).fetchone()[0]

            oldest = conn.execute(
                "SELECT MIN(date_added) FROM urls;"
            ).fetchone()[0]
            newest = conn.execute(
                "SELECT MAX(COALESCE(date_processed, date_added)) FROM urls;"
            ).fetchone()[0]

            return {
                "total": int(total),
                "by_status": by_status,
                "total_downloads": int(total_downloads),
                "date_range": (oldest, newest),
            }

    def clear_by_status(self, status: int) -> int:
        """Delete all URLs with the given status.

        Returns the number of rows deleted.

        Raises:
            RuntimeError: if trying to clear IN_PROGRESS URLs.
        """
        if status == UrlStatus.IN_PROGRESS:
            raise RuntimeError("Cannot clear URLs that are currently downloading")

        with self._locked(), self._connect() as conn:
            cur = conn.execute("DELETE FROM urls WHERE status = ?;", (status,))
            return int(cur.rowcount)

    def retry_all_failed(self) -> int:
        """Reset all FAILED URLs to PENDING status for retry.

        Returns the number of URLs reset.
        """
        with self._locked(), self._connect() as conn:
            cur = conn.execute(
                "UPDATE urls SET status = ?, last_error = NULL WHERE status = ?;",
                (UrlStatus.PENDING, UrlStatus.FAILED),
            )
            return int(cur.rowcount)

    def clear_all(self) -> int:
        """Delete all URLs from the database.

        Returns the number of rows deleted.

        Raises:
            RuntimeError: if any URLs are currently IN_PROGRESS.
        """
        with self._locked(), self._connect() as conn:
            in_progress = conn.execute(
                "SELECT COUNT(*) FROM urls WHERE status = ?;", (UrlStatus.IN_PROGRESS,)
            ).fetchone()[0]
            if in_progress > 0:
                raise RuntimeError(f"Cannot clear database while {in_progress} downloads are in progress")

            cur = conn.execute("DELETE FROM urls;")
            return int(cur.rowcount)

    def vacuum(self) -> None:
        """Compact the database file to reclaim space."""
        with self._locked():
            # VACUUM must run outside a transaction
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("VACUUM;")
            finally:
                conn.close()

    def get_file_size(self) -> int:
        """Return the database file size in bytes."""
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0

    def export_urls(self, file_path: Path, *, include_all: bool = True) -> int:
        """Export URLs to a text file (one per line).

        Args:
            file_path: Destination file path
            include_all: If True, export all URLs. If False, only completed.

        Returns the number of URLs exported.
        """
        with self._locked(), self._connect() as conn:
            if include_all:
                rows = conn.execute("SELECT url FROM urls ORDER BY id ASC;").fetchall()
            else:
                rows = conn.execute(
                    "SELECT url FROM urls WHERE status IN (?, ?) ORDER BY id ASC;",
                    (UrlStatus.COMPLETED, UrlStatus.COMPLETED_PARTIAL),
                ).fetchall()

            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                for (url,) in rows:
                    f.write(f"{url}\n")

            return len(rows)

    def import_urls(self, file_path: Path) -> tuple[int, int]:
        """Import URLs from a text file (one per line).

        Returns (added_count, skipped_count) - skipped are duplicates.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        added = 0
        skipped = 0
        now = datetime.now(timezone.utc).isoformat()

        with self._locked(), self._connect() as conn:
            for line in lines:
                url = line.strip()
                if not url or url.startswith("#"):
                    continue

                try:
                    conn.execute(
                        """
                        INSERT INTO urls (
                            url, status, force_redownload, check_new_only,
                            download_count, date_added, date_processed, last_error
                        ) VALUES (?, ?, 0, 0, 0, ?, NULL, NULL);
                        """,
                        (url, UrlStatus.PENDING, now),
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    skipped += 1

        return added, skipped
