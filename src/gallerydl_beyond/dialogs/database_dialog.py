from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gallerydl_beyond.common.base_dialog import BaseDialog
from gallerydl_beyond.common.constants import UrlStatus
from gallerydl_beyond.common.database_manager import DatabaseManager


# URL patterns for known extractors (extractor_name -> URL template with {id} placeholder)
# These are best-effort reconstructions - some sites need tokens or other info we don't have
# Patterns are curated based on gallery-dl's archive_fmt and URL patterns
EXTRACTOR_URL_PATTERNS: dict[str, str | None] = {
    # === Booru-style sites (simple ID-based) ===
    "danbooru": "https://danbooru.donmai.us/posts/{id}",
    "gelbooru": "https://gelbooru.com/index.php?page=post&s=view&id={id}",
    "rule34": "https://rule34.xxx/index.php?page=post&s=view&id={id}",
    "safebooru": "https://safebooru.org/index.php?page=post&s=view&id={id}",
    "sankaku": "https://chan.sankakucomplex.com/post/show/{id}",
    "idolcomplex": "https://idol.sankakucomplex.com/post/show/{id}",
    "yandere": "https://yande.re/post/show/{id}",
    "konachan": "https://konachan.com/post/show/{id}",
    "lolibooru": "https://lolibooru.moe/post/show/{id}",
    "e621": "https://e621.net/posts/{id}",
    "e926": "https://e926.net/posts/{id}",
    "3dbooru": "http://behoimi.org/post/show/{id}",
    "realbooru": "https://realbooru.com/index.php?page=post&s=view&id={id}",
    "tbib": "https://tbib.org/index.php?page=post&s=view&id={id}",
    "xbooru": "https://xbooru.com/index.php?page=post&s=view&id={id}",
    "allgirlbooru": "https://allgirl.booru.org/index.php?page=post&s=view&id={id}",
    "aibooru": "https://aibooru.online/posts/{id}",
    "furry34": "https://furry34.com/post/show/{id}",

    # === Art platforms ===
    "pixiv": "https://www.pixiv.net/en/artworks/{id}",
    "deviantart": "https://www.deviantart.com/deviation/{id}",
    "artstation": "https://www.artstation.com/artwork/{id}",
    "newgrounds": "https://www.newgrounds.com/art/view/{id}",
    "hentaifoundry": "https://www.hentai-foundry.com/pictures/user/_/{id}",
    "furaffinity": "https://www.furaffinity.net/view/{id}",
    "inkbunny": "https://inkbunny.net/s/{id}",
    "weasyl": "https://www.weasyl.com/~_/submissions/{id}",
    "aryion": "https://aryion.com/g4/view/{id}",
    "agnph": "https://agn.ph/gallery/post/show/{id}",
    "pillowfort": "https://www.pillowfort.social/posts/{id}",
    "itaku": "https://itaku.ee/images/{id}",
    "vk": "https://vk.com/photo{id}",

    # === Social media ===
    "twitter": "https://twitter.com/i/status/{id}",
    "x": "https://x.com/i/status/{id}",
    "instagram": "https://www.instagram.com/p/{id}/",
    "tumblr": "https://www.tumblr.com/post/{id}",
    "reddit": "https://www.reddit.com/comments/{id}",
    "bluesky": "https://bsky.app/profile/_/post/{id}",
    "mastodon": None,  # Needs instance + username
    "threads": "https://www.threads.net/t/{id}",
    "facebook": None,  # Complex auth
    "flickr": "https://www.flickr.com/photo.gne?id={id}",
    "weibo": "https://weibo.com/detail/{id}",
    "bilibili": "https://www.bilibili.com/video/{id}",

    # === Image hosts ===
    "imgur": "https://imgur.com/{id}",
    "imgbb": "https://ibb.co/{id}",
    "catbox": "https://catbox.moe/c/{id}",
    "bunkr": "https://bunkr.si/a/{id}",
    "cyberdrop": "https://cyberdrop.me/a/{id}",
    "gofile": "https://gofile.io/d/{id}",
    "pixhost": "https://pixhost.to/show/{id}",

    # === Hentai/Doujin sites ===
    "nhentai": "https://nhentai.net/g/{id}/",
    "hitomi": "https://hitomi.la/galleries/{id}.html",
    "hentainexus": "https://hentainexus.com/view/{id}",
    "pururin": "https://pururin.to/gallery/{id}",
    "tsumino": "https://www.tsumino.com/entry/{id}",
    "8muses": "https://comics.8muses.com/comics/album/{id}",
    "hentaihand": "https://hentaihand.com/en/comic/{id}",
    "simplyhentai": "https://www.simply-hentai.com/g/{id}",

    # === Subscription/Patreon-like ===
    "fanbox": "https://www.fanbox.cc/@_/posts/{id}",
    "fantia": "https://fantia.jp/posts/{id}",
    "patreon": "https://www.patreon.com/posts/{id}",
    "subscribestar": "https://subscribestar.adult/posts/{id}",
    "gumroad": "https://gumroad.com/l/{id}",
    "boosty": "https://boosty.to/_/posts/{id}",
    "kemono": "https://kemono.su/_/post/{id}",
    "coomer": "https://coomer.su/_/post/{id}",
    "cien": "https://ci-en.net/creator/_/article/{id}",

    # === Manga/Comics ===
    "mangadex": "https://mangadex.org/chapter/{id}",
    "batoto": "https://bato.to/chapter/{id}",
    "webtoons": None,  # Needs title slug
    "tapas": "https://tapas.io/episode/{id}",
    "dynastyscans": "https://dynasty-scans.com/chapters/{id}",
    "hentai2read": "https://hentai2read.com/{id}",
    "hentaihere": "https://hentaihere.com/m/{id}",
    "readcomiconline": None,  # Complex URL
    "comicvine": "https://comicvine.gamespot.com/a/{id}",

    # === Other ===
    "behance": "https://www.behance.net/gallery/{id}",
    "500px": "https://500px.com/photo/{id}",
    "pinterest": "https://www.pinterest.com/pin/{id}/",
    "zerochan": "https://www.zerochan.net/{id}",
    "wallhaven": "https://wallhaven.cc/w/{id}",
    "fuskator": "https://fuskator.com/full/{id}",
    "erome": "https://www.erome.com/a/{id}",
    "imagefap": "https://www.imagefap.com/photo/{id}/",
    "xhamster": "https://xhamster.com/photos/gallery/{id}",
    "pornhub": "https://www.pornhub.com/photo/{id}",
    "scrolller": "https://scrolller.com/r/{id}",
    "redgifs": "https://www.redgifs.com/watch/{id}",

    # === Sites that CAN'T be reconstructed (need tokens, complex URLs, etc.) ===
    "exhentai": None,  # Needs token: https://exhentai.org/g/{id}/{token}/
    "e-hentai": None,  # Needs token
    "discord": None,   # Needs channel ID + auth
    "naver": None,     # Complex auth
    "afdian": None,    # Chinese, complex
    "bilibili": None,  # Different URL types
    "lofter": None,    # Needs blog name
    "poipiku": None,   # Complex URL
    "skeb": None,      # Needs username
    "blogger": None,   # Needs blog name
    "smugmug": None,   # Needs album path
    "photobucket": None,  # Complex URL
    "vsco": None,      # Needs username
}


def _get_gallerydl_categories() -> dict[str, str]:
    """Get available categories and their root URLs from gallery-dl.

    Returns dict mapping category name -> root URL (or empty string if no root).
    """
    try:
        from gallery_dl import extractor

        categories = {}
        for ext in extractor.extractors():
            cat = getattr(ext, "category", None)
            root = getattr(ext, "root", None) or ""
            if cat and cat not in categories:
                categories[cat] = root
        return categories
    except ImportError:
        return {}
    except Exception:
        return {}


def _parse_archive_entry(entry: str) -> tuple[str, str, str | None] | None:
    """Parse a gallery-dl archive entry into (extractor, gallery_id, page).

    Common formats:
    - exhentai3617659_1 -> (exhentai, 3617659, 1)
    - pixiv12345678_p0 -> (pixiv, 12345678, p0)
    - twitter_1234567890 -> (twitter, 1234567890, None)

    Returns None if parsing fails.
    """
    # Try pattern: {extractor}{gallery_id}_{page}
    match = re.match(r'^([a-zA-Z_-]+?)(\d+)(?:_(.+))?$', entry)
    if match:
        return match.group(1), match.group(2), match.group(3)

    # Try pattern: {extractor}_{id} (no page suffix)
    match = re.match(r'^([a-zA-Z_-]+)_(\d+)$', entry)
    if match:
        return match.group(1), match.group(2), None

    # Try pattern with alphanumeric id: {extractor}_{alphanum_id}_{page}
    match = re.match(r'^([a-zA-Z]+)_([a-zA-Z0-9_-]+?)(?:_(\d+))?$', entry)
    if match:
        return match.group(1), match.group(2), match.group(3)

    return None


def _extract_galleries_from_archive(archive_path: Path) -> dict[str, set[str]]:
    """Extract unique gallery IDs from a gallery-dl archive.

    Returns: dict mapping extractor name -> set of gallery IDs
    """
    if not archive_path.exists():
        return {}

    galleries: dict[str, set[str]] = {}

    conn = sqlite3.connect(archive_path)
    try:
        cursor = conn.execute("SELECT entry FROM archive;")
        for (entry,) in cursor.fetchall():
            parsed = _parse_archive_entry(entry)
            if parsed:
                extractor, gallery_id, _ = parsed
                extractor = extractor.lower().rstrip("_- ")
                if extractor not in galleries:
                    galleries[extractor] = set()
                galleries[extractor].add(gallery_id)
    finally:
        conn.close()

    return galleries


def _reconstruct_url(extractor: str, gallery_id: str) -> str | None:
    """Try to reconstruct a URL from extractor and gallery ID.

    Returns None if the extractor's URL pattern is unknown or requires additional info.
    """
    pattern = EXTRACTOR_URL_PATTERNS.get(extractor.lower())
    if pattern:
        return pattern.format(id=gallery_id)
    return None


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _format_date(iso_date: str | None) -> str:
    """Format ISO date string for display."""
    if not iso_date:
        return "N/A"
    try:
        # Just take the date part
        return iso_date.split("T")[0]
    except Exception:
        return iso_date[:10] if len(iso_date) >= 10 else iso_date


class DatabaseDialog(BaseDialog):
    def __init__(self, db_manager: DatabaseManager, config_path: Path | None, show_error: callable):
        super().__init__("Database Manager", show_error)
        self._db = db_manager
        self._config_path = config_path
        self._archive_path: Path | None = None

        # Try to get archive path from config
        if config_path and config_path.exists():
            try:
                import json

                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                archive_str = config.get("extractor", {}).get("archive")
                if archive_str:
                    self._archive_path = Path(archive_str)
                    if not self._archive_path.is_absolute():
                        self._archive_path = config_path.parent / self._archive_path
            except Exception:
                pass

        self.setMinimumWidth(500)
        self._init_ui()
        self._refresh_stats()

    def _init_ui(self) -> None:
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(12)

        # Statistics Group
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout()
        stats_layout.setSpacing(6)

        self._total_label = QLabel()
        self._completed_label = QLabel()
        self._failed_label = QLabel()
        self._pending_label = QLabel()
        self._stopped_label = QLabel()
        self._partial_label = QLabel()
        self._skipped_label = QLabel()
        self._downloads_label = QLabel()
        self._date_range_label = QLabel()

        stats_layout.addRow("Total URLs:", self._total_label)
        stats_layout.addRow("Completed:", self._completed_label)
        stats_layout.addRow("Partial:", self._partial_label)
        stats_layout.addRow("Failed:", self._failed_label)
        stats_layout.addRow("Pending:", self._pending_label)
        stats_layout.addRow("Stopped:", self._stopped_label)
        stats_layout.addRow("Skipped:", self._skipped_label)
        stats_layout.addRow("Total Downloads:", self._downloads_label)
        stats_layout.addRow("Date Range:", self._date_range_label)

        stats_group.setLayout(stats_layout)
        self.main_layout.addWidget(stats_group)

        # Bulk Operations Group
        bulk_group = QGroupBox("Bulk Operations")
        bulk_layout = QVBoxLayout()
        bulk_layout.setSpacing(8)

        # Row 1: Clear by status
        clear_row = QHBoxLayout()
        clear_completed_btn = QPushButton("Clear Completed")
        clear_completed_btn.setToolTip("Remove all completed URLs from history")
        clear_completed_btn.clicked.connect(lambda: self._clear_by_status(UrlStatus.COMPLETED, "completed"))

        clear_failed_btn = QPushButton("Clear Failed")
        clear_failed_btn.setToolTip("Remove all failed URLs from history")
        clear_failed_btn.clicked.connect(lambda: self._clear_by_status(UrlStatus.FAILED, "failed"))

        clear_stopped_btn = QPushButton("Clear Stopped")
        clear_stopped_btn.setToolTip("Remove all stopped URLs from history")
        clear_stopped_btn.clicked.connect(lambda: self._clear_by_status(UrlStatus.STOPPED, "stopped"))

        clear_row.addWidget(clear_completed_btn)
        clear_row.addWidget(clear_failed_btn)
        clear_row.addWidget(clear_stopped_btn)
        bulk_layout.addLayout(clear_row)

        # Row 2: Retry and clear all
        action_row = QHBoxLayout()
        retry_failed_btn = QPushButton("Retry All Failed")
        retry_failed_btn.setToolTip("Reset all failed URLs to pending for another attempt")
        retry_failed_btn.clicked.connect(self._retry_all_failed)

        clear_partial_btn = QPushButton("Clear Partial")
        clear_partial_btn.setToolTip("Remove all partially completed URLs")
        clear_partial_btn.clicked.connect(lambda: self._clear_by_status(UrlStatus.COMPLETED_PARTIAL, "partial"))

        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.setToolTip("Remove ALL URLs from history (cannot be undone)")
        clear_all_btn.setStyleSheet("color: #ff6b6b;")
        clear_all_btn.clicked.connect(self._clear_all)

        action_row.addWidget(retry_failed_btn)
        action_row.addWidget(clear_partial_btn)
        action_row.addWidget(clear_all_btn)
        bulk_layout.addLayout(action_row)

        bulk_group.setLayout(bulk_layout)
        self.main_layout.addWidget(bulk_group)

        # Import/Export Group
        io_group = QGroupBox("Import / Export")
        io_layout = QHBoxLayout()
        io_layout.setSpacing(8)

        export_btn = QPushButton("Export URLs...")
        export_btn.setToolTip("Export all URLs to a text file")
        export_btn.clicked.connect(self._export_urls)

        import_btn = QPushButton("Import URLs...")
        import_btn.setToolTip("Import URLs from a text file (one per line)")
        import_btn.clicked.connect(self._import_urls)

        io_layout.addWidget(export_btn)
        io_layout.addWidget(import_btn)
        io_layout.addStretch()

        io_group.setLayout(io_layout)
        self.main_layout.addWidget(io_group)

        # Gallery-dl Archive Group
        archive_group = QGroupBox("Gallery-dl Archive Import")
        archive_layout = QVBoxLayout()
        archive_layout.setSpacing(8)

        archive_desc = QLabel(
            "Import data from external gallery-dl archive databases (.sqlite3).\n"
            "• Merge Archive: Copy download records into current archive\n"
            "• Extract URLs: Try to reconstruct gallery URLs and add to history"
        )
        archive_desc.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        archive_desc.setWordWrap(True)
        archive_layout.addWidget(archive_desc)

        archive_btn_layout = QHBoxLayout()

        merge_archive_btn = QPushButton("Merge Archive...")
        merge_archive_btn.setToolTip(
            "Merge entries from another gallery-dl archive into the current one.\n"
            "This combines download records so gallery-dl knows what was already downloaded."
        )
        merge_archive_btn.clicked.connect(self._merge_archive)

        extract_urls_btn = QPushButton("Extract URLs from Archive...")
        extract_urls_btn.setToolTip(
            "Extract unique gallery URLs from a gallery-dl archive and add them to history.\n"
            "Note: Not all URLs can be reconstructed (some sites need tokens)."
        )
        extract_urls_btn.clicked.connect(self._extract_urls_from_archive)

        archive_btn_layout.addWidget(merge_archive_btn)
        archive_btn_layout.addWidget(extract_urls_btn)
        archive_btn_layout.addStretch()
        archive_layout.addLayout(archive_btn_layout)

        archive_group.setLayout(archive_layout)
        self.main_layout.addWidget(archive_group)

        # Tag Management Group
        tag_group = QGroupBox("Tag Management")
        tag_layout = QVBoxLayout()
        tag_layout.setSpacing(8)

        tag_desc = QLabel(
            "Create and manage tags to organize your URLs.\n"
            "Tags can be assigned to URLs from the History tab context menu."
        )
        tag_desc.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        tag_desc.setWordWrap(True)
        tag_layout.addWidget(tag_desc)

        self._tag_list = QListWidget()
        self._tag_list.setMaximumHeight(120)
        self._tag_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        tag_layout.addWidget(self._tag_list)

        tag_btn_layout = QHBoxLayout()

        add_tag_btn = QPushButton("Add Tag...")
        add_tag_btn.setToolTip("Create a new tag")
        add_tag_btn.clicked.connect(self._add_tag)

        rename_tag_btn = QPushButton("Rename...")
        rename_tag_btn.setToolTip("Rename the selected tag")
        rename_tag_btn.clicked.connect(self._rename_tag)

        delete_tag_btn = QPushButton("Delete")
        delete_tag_btn.setToolTip("Delete the selected tag")
        delete_tag_btn.setStyleSheet("color: #ff6b6b;")
        delete_tag_btn.clicked.connect(self._delete_tag)

        tag_btn_layout.addWidget(add_tag_btn)
        tag_btn_layout.addWidget(rename_tag_btn)
        tag_btn_layout.addWidget(delete_tag_btn)
        tag_btn_layout.addStretch()
        tag_layout.addLayout(tag_btn_layout)

        tag_group.setLayout(tag_layout)
        self.main_layout.addWidget(tag_group)

        # Database Maintenance Group
        maint_group = QGroupBox("Database Maintenance")
        maint_layout = QVBoxLayout()
        maint_layout.setSpacing(8)

        # Database info
        info_layout = QFormLayout()
        self._db_path_label = QLabel(str(self._db.db_path))
        self._db_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._db_path_label.setWordWrap(True)
        self._db_size_label = QLabel()
        info_layout.addRow("Database:", self._db_path_label)
        info_layout.addRow("Size:", self._db_size_label)

        # Archive info (if available)
        if self._archive_path:
            self._archive_path_label = QLabel(str(self._archive_path))
            self._archive_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._archive_path_label.setWordWrap(True)
            self._archive_size_label = QLabel()
            info_layout.addRow("Archive:", self._archive_path_label)
            info_layout.addRow("Archive Size:", self._archive_size_label)

        maint_layout.addLayout(info_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        maint_layout.addWidget(line)

        # Maintenance buttons
        btn_layout = QHBoxLayout()

        vacuum_btn = QPushButton("Vacuum Database")
        vacuum_btn.setToolTip("Compact database file to reclaim space")
        vacuum_btn.clicked.connect(self._vacuum_database)

        backup_btn = QPushButton("Backup Database...")
        backup_btn.setToolTip("Create a backup copy of the database file")
        backup_btn.clicked.connect(self._backup_database)

        btn_layout.addWidget(vacuum_btn)
        btn_layout.addWidget(backup_btn)

        if self._archive_path:
            clear_archive_btn = QPushButton("Clear Archive")
            clear_archive_btn.setToolTip("Delete gallery-dl archive (forces full re-check on all URLs)")
            clear_archive_btn.setStyleSheet("color: #ff6b6b;")
            clear_archive_btn.clicked.connect(self._clear_archive)
            btn_layout.addWidget(clear_archive_btn)

        btn_layout.addStretch()
        maint_layout.addLayout(btn_layout)

        maint_group.setLayout(maint_layout)
        self.main_layout.addWidget(maint_group)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        self.main_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _refresh_stats(self) -> None:
        """Refresh all statistics displays."""
        try:
            stats = self._db.get_statistics()

            self._total_label.setText(str(stats["total"]))
            by_status = stats["by_status"]
            self._completed_label.setText(str(by_status.get(UrlStatus.COMPLETED, 0)))
            self._partial_label.setText(str(by_status.get(UrlStatus.COMPLETED_PARTIAL, 0)))
            self._failed_label.setText(str(by_status.get(UrlStatus.FAILED, 0)))
            self._pending_label.setText(str(by_status.get(UrlStatus.PENDING, 0)))
            self._stopped_label.setText(str(by_status.get(UrlStatus.STOPPED, 0)))
            self._skipped_label.setText(str(by_status.get(UrlStatus.SKIPPED, 0)))
            self._downloads_label.setText(str(stats["total_downloads"]))

            oldest, newest = stats["date_range"]
            if oldest and newest:
                self._date_range_label.setText(f"{_format_date(oldest)} to {_format_date(newest)}")
            else:
                self._date_range_label.setText("N/A")

            # File sizes
            self._db_size_label.setText(_format_size(self._db.get_file_size()))

            if self._archive_path and hasattr(self, "_archive_size_label"):
                if self._archive_path.exists():
                    self._archive_size_label.setText(_format_size(self._archive_path.stat().st_size))
                else:
                    self._archive_size_label.setText("Not created yet")

            # Refresh tag list
            self._refresh_tag_list()

        except Exception as e:
            self._show_error(f"Failed to load statistics: {e}")

    def _clear_by_status(self, status: int, status_name: str) -> None:
        """Clear all URLs with the given status."""
        try:
            stats = self._db.get_statistics()
            count = stats["by_status"].get(status, 0)

            if count == 0:
                QMessageBox.information(self, "Nothing to Clear", f"No {status_name} URLs to clear.")
                return

            reply = QMessageBox.question(
                self,
                "Confirm Clear",
                f"Delete {count} {status_name} URL(s) from history?\n\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                deleted = self._db.clear_by_status(status)
                QMessageBox.information(self, "Cleared", f"Removed {deleted} {status_name} URL(s).")
                self._refresh_stats()

        except Exception as e:
            self._show_error(f"Failed to clear {status_name} URLs: {e}")

    def _retry_all_failed(self) -> None:
        """Reset all failed URLs to pending."""
        try:
            stats = self._db.get_statistics()
            count = stats["by_status"].get(UrlStatus.FAILED, 0)

            if count == 0:
                QMessageBox.information(self, "Nothing to Retry", "No failed URLs to retry.")
                return

            reply = QMessageBox.question(
                self,
                "Confirm Retry",
                f"Reset {count} failed URL(s) to pending for retry?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                reset = self._db.retry_all_failed()
                QMessageBox.information(self, "Reset", f"Reset {reset} URL(s) to pending.")
                self._refresh_stats()

        except Exception as e:
            self._show_error(f"Failed to retry URLs: {e}")

    def _clear_all(self) -> None:
        """Clear all URLs from the database."""
        try:
            stats = self._db.get_statistics()
            total = stats["total"]

            if total == 0:
                QMessageBox.information(self, "Empty Database", "The database is already empty.")
                return

            reply = QMessageBox.warning(
                self,
                "Confirm Clear All",
                f"DELETE ALL {total} URL(s) from the database?\n\n"
                "This will remove your entire download history.\n"
                "This action CANNOT be undone!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Double confirmation for destructive action
                reply2 = QMessageBox.warning(
                    self,
                    "Are You Sure?",
                    "Are you absolutely sure you want to delete all history?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply2 == QMessageBox.StandardButton.Yes:
                    deleted = self._db.clear_all()
                    QMessageBox.information(self, "Cleared", f"Deleted {deleted} URL(s).")
                    self._refresh_stats()

        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Clear", str(e))
        except Exception as e:
            self._show_error(f"Failed to clear database: {e}")

    def _export_urls(self) -> None:
        """Export URLs to a text file."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export URLs",
                "urls_export.txt",
                "Text Files (*.txt);;All Files (*)",
            )

            if not file_path:
                return

            count = self._db.export_urls(Path(file_path), include_all=True)
            QMessageBox.information(self, "Export Complete", f"Exported {count} URL(s) to:\n{file_path}")

        except Exception as e:
            self._show_error(f"Failed to export URLs: {e}")

    def _import_urls(self) -> None:
        """Import URLs from a text file."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import URLs",
                "",
                "Text Files (*.txt);;All Files (*)",
            )

            if not file_path:
                return

            added, skipped = self._db.import_urls(Path(file_path))
            QMessageBox.information(
                self,
                "Import Complete",
                f"Added: {added} URL(s)\nSkipped (duplicates): {skipped}",
            )
            self._refresh_stats()

        except FileNotFoundError as e:
            QMessageBox.warning(self, "File Not Found", str(e))
        except Exception as e:
            self._show_error(f"Failed to import URLs: {e}")

    def _vacuum_database(self) -> None:
        """Compact the database."""
        try:
            size_before = self._db.get_file_size()
            self._db.vacuum()
            size_after = self._db.get_file_size()

            saved = size_before - size_after
            if saved > 0:
                msg = f"Database compacted.\nSpace saved: {_format_size(saved)}"
            else:
                msg = "Database compacted. No additional space could be reclaimed."

            QMessageBox.information(self, "Vacuum Complete", msg)
            self._refresh_stats()

        except Exception as e:
            self._show_error(f"Failed to vacuum database: {e}")

    def _backup_database(self) -> None:
        """Create a backup copy of the database."""
        try:
            default_name = f"gallery-dl_backup_{self._db.db_path.stem}.db"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Backup Database",
                default_name,
                "SQLite Database (*.db);;All Files (*)",
            )

            if not file_path:
                return

            import shutil

            shutil.copy2(self._db.db_path, file_path)
            QMessageBox.information(self, "Backup Complete", f"Database backed up to:\n{file_path}")

        except Exception as e:
            self._show_error(f"Failed to backup database: {e}")

    def _clear_archive(self) -> None:
        """Clear the gallery-dl archive file."""
        if not self._archive_path:
            return

        try:
            if not self._archive_path.exists():
                QMessageBox.information(self, "No Archive", "The archive file does not exist yet.")
                return

            size = self._archive_path.stat().st_size
            reply = QMessageBox.warning(
                self,
                "Confirm Clear Archive",
                f"Delete the gallery-dl archive file?\n\n"
                f"File: {self._archive_path}\n"
                f"Size: {_format_size(size)}\n\n"
                "This will cause gallery-dl to re-check ALL files on next download.\n"
                "This cannot be undone!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                os.remove(self._archive_path)
                QMessageBox.information(self, "Archive Cleared", "Gallery-dl archive has been deleted.")
                self._refresh_stats()

        except Exception as e:
            self._show_error(f"Failed to clear archive: {e}")

    def _merge_archive(self) -> None:
        """Merge entries from another gallery-dl archive into the current one."""
        if not self._archive_path:
            QMessageBox.warning(
                self,
                "No Archive Configured",
                "No gallery-dl archive is configured.\nCheck your config.json settings.",
            )
            return

        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Archive to Merge",
                "",
                "SQLite Database (*.sqlite3 *.db);;All Files (*)",
            )

            if not file_path:
                return

            source_path = Path(file_path)
            if not source_path.exists():
                QMessageBox.warning(self, "File Not Found", f"File not found: {file_path}")
                return

            # Count entries in source
            source_conn = sqlite3.connect(source_path)
            try:
                source_count = source_conn.execute("SELECT COUNT(*) FROM archive;").fetchone()[0]
            except sqlite3.OperationalError:
                QMessageBox.warning(
                    self,
                    "Invalid Archive",
                    "The selected file is not a valid gallery-dl archive.\n"
                    "Expected a SQLite database with an 'archive' table.",
                )
                source_conn.close()
                return
            source_conn.close()

            if source_count == 0:
                QMessageBox.information(self, "Empty Archive", "The selected archive is empty.")
                return

            reply = QMessageBox.question(
                self,
                "Confirm Merge",
                f"Merge {source_count:,} entries from:\n{source_path.name}\n\n"
                f"Into current archive:\n{self._archive_path.name}\n\n"
                "Duplicate entries will be skipped.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Ensure target archive exists
            if not self._archive_path.exists():
                self._archive_path.parent.mkdir(parents=True, exist_ok=True)
                target_conn = sqlite3.connect(self._archive_path)
                target_conn.execute("CREATE TABLE archive (entry TEXT PRIMARY KEY) WITHOUT ROWID;")
                target_conn.commit()
                target_conn.close()

            # Merge entries
            target_conn = sqlite3.connect(self._archive_path)
            source_conn = sqlite3.connect(source_path)
            try:
                cursor = source_conn.execute("SELECT entry FROM archive;")
                entries = cursor.fetchall()

                added = 0
                for (entry,) in entries:
                    try:
                        target_conn.execute("INSERT INTO archive (entry) VALUES (?);", (entry,))
                        added += 1
                    except sqlite3.IntegrityError:
                        pass  # Duplicate, skip

                target_conn.commit()
                skipped = source_count - added

                QMessageBox.information(
                    self,
                    "Merge Complete",
                    f"Added: {added:,} entries\nSkipped (duplicates): {skipped:,}",
                )
                self._refresh_stats()

            finally:
                source_conn.close()
                target_conn.close()

        except Exception as e:
            self._show_error(f"Failed to merge archive: {e}")

    def _extract_urls_from_archive(self) -> None:
        """Extract unique gallery URLs from a gallery-dl archive and add to history."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Archive to Extract URLs From",
                "",
                "SQLite Database (*.sqlite3 *.db);;All Files (*)",
            )

            if not file_path:
                return

            source_path = Path(file_path)
            if not source_path.exists():
                QMessageBox.warning(self, "File Not Found", f"File not found: {file_path}")
                return

            # Extract galleries
            galleries = _extract_galleries_from_archive(source_path)

            if not galleries:
                QMessageBox.information(
                    self,
                    "No Galleries Found",
                    "Could not extract any gallery information from the archive.",
                )
                return

            # Get known categories from gallery-dl for better reporting
            known_categories = _get_gallerydl_categories()

            # Count totals
            total_galleries = sum(len(ids) for ids in galleries.values())
            reconstructable = 0
            not_reconstructable = 0

            for extractor, ids in galleries.items():
                if EXTRACTOR_URL_PATTERNS.get(extractor.lower()):
                    reconstructable += len(ids)
                else:
                    not_reconstructable += len(ids)

            # Build summary using a scrollable dialog for large extractor lists
            if not self._show_extract_summary_dialog(
                galleries, known_categories, total_galleries, reconstructable, not_reconstructable
            ):
                return

            # Add reconstructable URLs
            added = 0
            skipped = 0
            for extractor, ids in galleries.items():
                for gallery_id in ids:
                    url = _reconstruct_url(extractor, gallery_id)
                    if url:
                        result = self._db.add_url(url)
                        if result is not None:
                            # Mark as completed since it was already downloaded
                            self._db.mark_completed(result)
                            added += 1
                        else:
                            skipped += 1

            QMessageBox.information(
                self,
                "Extraction Complete",
                f"Added to history: {added} URLs\n"
                f"Skipped (duplicates): {skipped}\n"
                f"Could not reconstruct: {not_reconstructable}",
            )
            self._refresh_stats()

        except Exception as e:
            self._show_error(f"Failed to extract URLs: {e}")

    def _show_extract_summary_dialog(
        self,
        galleries: dict[str, set[str]],
        known_categories: dict[str, str],
        total_galleries: int,
        reconstructable: int,
        not_reconstructable: int,
    ) -> bool:
        """Show a scrollable dialog with extraction summary. Returns True if user confirms."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Extract URLs")
        dialog.setMinimumWidth(500)
        dialog.setMaximumHeight(600)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # Header summary
        header = QLabel(f"Found {total_galleries} unique galleries from {len(galleries)} extractors")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        # Scrollable extractor list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(350)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(4)

        for extractor, ids in sorted(galleries.items(), key=lambda x: -len(x[1])):
            pattern = EXTRACTOR_URL_PATTERNS.get(extractor.lower())
            root = known_categories.get(extractor.lower(), "")

            if pattern:
                status = "can reconstruct"
                color = "#4caf50"  # green
            elif root:
                status = f"known site - no URL pattern"
                color = "#ff9800"  # orange
            else:
                status = "unknown extractor"
                color = "#f44336"  # red

            line_label = QLabel(f"• <b>{extractor}</b>: {len(ids)} galleries (<span style='color:{color}'>{status}</span>)")
            line_label.setTextFormat(Qt.TextFormat.RichText)
            scroll_layout.addWidget(line_label)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # Summary stats
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 4px; padding: 8px;")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 8, 12, 8)

        can_label = QLabel(f"<span style='color:#4caf50'>✓</span> Can reconstruct: <b>{reconstructable}</b>")
        can_label.setTextFormat(Qt.TextFormat.RichText)
        stats_layout.addWidget(can_label)

        cannot_label = QLabel(f"<span style='color:#f44336'>✗</span> Cannot reconstruct: <b>{not_reconstructable}</b>")
        cannot_label.setTextFormat(Qt.TextFormat.RichText)
        stats_layout.addWidget(cannot_label)

        layout.addWidget(stats_frame)

        # Question
        question = QLabel("Proceed to add reconstructable URLs to history?")
        question.setStyleSheet("margin-top: 8px;")
        layout.addWidget(question)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        return dialog.exec() == QDialog.DialogCode.Accepted

    # ============== Tag Management Methods ==============

    def _refresh_tag_list(self) -> None:
        """Refresh the tag list widget."""
        self._tag_list.clear()
        try:
            tags = self._db.list_tags()
            for tag in tags:
                item = QListWidgetItem(tag.name)
                item.setData(Qt.ItemDataRole.UserRole, tag.id)
                self._tag_list.addItem(item)
        except Exception as e:
            self._show_error(f"Failed to load tags: {e}")

    def _add_tag(self) -> None:
        """Add a new tag."""
        name, ok = QInputDialog.getText(
            self,
            "Add Tag",
            "Enter tag name:",
        )
        if not ok or not name.strip():
            return

        try:
            tag_id = self._db.create_tag(name.strip())
            if tag_id is None:
                QMessageBox.warning(self, "Tag Exists", f"A tag named '{name.strip()}' already exists.")
                return
            self._refresh_tag_list()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Name", str(e))
        except Exception as e:
            self._show_error(f"Failed to create tag: {e}")

    def _rename_tag(self) -> None:
        """Rename the selected tag."""
        item = self._tag_list.currentItem()
        if item is None:
            QMessageBox.information(self, "No Selection", "Please select a tag to rename.")
            return

        old_name = item.text()
        tag_id = item.data(Qt.ItemDataRole.UserRole)

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Tag",
            "Enter new name:",
            text=old_name,
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return

        try:
            if not self._db.rename_tag(tag_id, new_name.strip()):
                QMessageBox.warning(
                    self, "Rename Failed", f"A tag named '{new_name.strip()}' already exists."
                )
                return
            self._refresh_tag_list()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Name", str(e))
        except Exception as e:
            self._show_error(f"Failed to rename tag: {e}")

    def _delete_tag(self) -> None:
        """Delete the selected tag."""
        item = self._tag_list.currentItem()
        if item is None:
            QMessageBox.information(self, "No Selection", "Please select a tag to delete.")
            return

        tag_name = item.text()
        tag_id = item.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete tag '{tag_name}'?\n\nThis will remove the tag from all URLs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._db.delete_tag(tag_id)
                self._refresh_tag_list()
            except Exception as e:
                self._show_error(f"Failed to delete tag: {e}")
