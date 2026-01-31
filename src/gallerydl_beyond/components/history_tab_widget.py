from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gallerydl_beyond.common.constants import SettingsKeys, UrlStatus
from gallerydl_beyond.common.database_manager import DatabaseManager
from gallerydl_beyond.models.history_model import HistoryModel

DEFAULT_PAGE_SIZE = 100


class HistoryTabWidget(QWidget):
    url_removed = pyqtSignal(int, str)

    def __init__(
        self,
        *,
        db_manager: DatabaseManager,
        on_check_new: callable,
        on_force_redownload: callable,
        on_resume: callable | None = None,
        on_skip: callable | None = None,
        on_tags_changed: callable | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._db = db_manager
        self._on_check_new = on_check_new
        self._on_force_redownload = on_force_redownload
        self._on_resume = on_resume
        self._on_skip = on_skip
        self._on_tags_changed = on_tags_changed
        self._settings = QSettings()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search URL...")

        # Tag filter dropdown
        self._tag_filter_label = QLabel("Tag:")
        self._tag_filter = QComboBox()
        self._tag_filter.setMinimumWidth(100)
        self._tag_filter.currentIndexChanged.connect(lambda _: self.refresh())
        self._refresh_tag_filter()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(lambda: self.refresh())

        # Pagination controls
        self._first_btn = QPushButton("<<")
        self._first_btn.setFixedWidth(40)
        self._first_btn.setToolTip("First page")
        self._first_btn.clicked.connect(self._go_first)

        self._prev_btn = QPushButton("<")
        self._prev_btn.setFixedWidth(30)
        self._prev_btn.setToolTip("Previous page")
        self._prev_btn.clicked.connect(self._go_prev)

        self._page_label = QLabel("Page 1 of 1 (0 items)")
        self._page_label.setMinimumWidth(160)

        self._next_btn = QPushButton(">")
        self._next_btn.setFixedWidth(30)
        self._next_btn.setToolTip("Next page")
        self._next_btn.clicked.connect(self._go_next)

        self._last_btn = QPushButton(">>")
        self._last_btn.setFixedWidth(40)
        self._last_btn.setToolTip("Last page")
        self._last_btn.clicked.connect(self._go_last)

        self._rows_label = QLabel("Rows:")
        self._page_size_combo = QComboBox()
        self._page_size_combo.addItem("50", 50)
        self._page_size_combo.addItem("100", 100)
        self._page_size_combo.addItem("200", 200)
        self._page_size_combo.addItem("500", 500)
        self._load_page_size_setting()
        self._page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_context_menu)

        self.model = HistoryModel(self._db)
        self.table.setModel(self.model)

        self.search.textChanged.connect(lambda _text: self.refresh())

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Top row: Search, Tag filter, Refresh
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        top.addWidget(self.search, 1)
        top.addWidget(self._tag_filter_label, 0)
        top.addWidget(self._tag_filter, 0)
        top.addWidget(self.refresh_button, 0)

        # Pagination row
        pagination = QHBoxLayout()
        pagination.setContentsMargins(0, 0, 0, 0)
        pagination.setSpacing(4)
        pagination.addWidget(self._first_btn)
        pagination.addWidget(self._prev_btn)
        pagination.addWidget(self._page_label)
        pagination.addWidget(self._next_btn)
        pagination.addWidget(self._last_btn)
        pagination.addStretch()
        pagination.addWidget(self._rows_label)
        pagination.addWidget(self._page_size_combo)

        layout.addLayout(top)
        layout.addLayout(pagination)
        layout.addWidget(self.table, 1)

    def refresh(self, *, page: int | None = None, preserve_sort: bool = True) -> None:
        text = self.search.text().strip() or None
        tag_id = self._tag_filter.currentData()
        page_size = self._page_size_combo.currentData() or DEFAULT_PAGE_SIZE

        if page is None:
            page = 0  # Reset to first page on search/filter change

        # Preserve current sort state unless explicitly changing filters
        sort_column = self.model.sort_column if preserve_sort else None
        sort_ascending = self.model.sort_ascending if preserve_sort else None

        self.model.refresh(
            search=text,
            tag_id=tag_id,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_ascending=sort_ascending,
        )
        self._update_pagination_ui()
        self.table.resizeColumnsToContents()

    def _refresh_tag_filter(self) -> None:
        """Refresh the tag filter dropdown."""
        current_tag_id = self._tag_filter.currentData()
        self._tag_filter.blockSignals(True)
        self._tag_filter.clear()
        self._tag_filter.addItem("All", None)
        try:
            tags = self._db.list_tags()
            for tag in tags:
                self._tag_filter.addItem(tag.name, tag.id)
            # Restore selection if still valid
            if current_tag_id is not None:
                for i in range(self._tag_filter.count()):
                    if self._tag_filter.itemData(i) == current_tag_id:
                        self._tag_filter.setCurrentIndex(i)
                        break
        except Exception:
            pass  # Ignore errors loading tags
        finally:
            self._tag_filter.blockSignals(False)

    def refresh_tags(self) -> None:
        """Refresh both the tag filter and the table (call after tag list changes)."""
        self._refresh_tag_filter()
        self.refresh()

    def _go_first(self) -> None:
        self.refresh(page=0)

    def _go_prev(self) -> None:
        self.refresh(page=self.model.current_page - 1)

    def _go_next(self) -> None:
        self.refresh(page=self.model.current_page + 1)

    def _go_last(self) -> None:
        self.refresh(page=self.model.total_pages - 1)

    def _update_pagination_ui(self) -> None:
        page = self.model.current_page + 1  # 1-indexed for display
        total = self.model.total_pages
        count = self.model.total_count

        self._page_label.setText(f"Page {page} of {total} ({count:,} items)")

        self._first_btn.setEnabled(page > 1)
        self._prev_btn.setEnabled(page > 1)
        self._next_btn.setEnabled(page < total)
        self._last_btn.setEnabled(page < total)

    def _load_page_size_setting(self) -> None:
        """Load page size from settings."""
        saved_size = self._settings.value(SettingsKeys.HISTORY_PAGE_SIZE, DEFAULT_PAGE_SIZE, type=int)
        for i in range(self._page_size_combo.count()):
            if self._page_size_combo.itemData(i) == saved_size:
                self._page_size_combo.setCurrentIndex(i)
                return
        # Default to 100 if saved value not found
        self._page_size_combo.setCurrentIndex(1)

    def _on_page_size_changed(self) -> None:
        """Handle page size change and persist to settings."""
        page_size = self._page_size_combo.currentData()
        if page_size is not None:
            self._settings.setValue(SettingsKeys.HISTORY_PAGE_SIZE, page_size)
        self.refresh()  # Reset to first page with new page size

    def _selected_url(self) -> str | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        row = self.model.get_row(idx.row())
        return row.url if row else None

    def _selected_row_id(self) -> int | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        row = self.model.get_row(idx.row())
        return row.id if row else None

    def _selected_row_status(self) -> int | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        row = self.model.get_row(idx.row())
        return row.status if row else None

    def _open_context_menu(self, pos) -> None:
        # Ensure the row under the cursor is selected.
        index = self.table.indexAt(pos)
        if index.isValid():
            self.table.setCurrentIndex(index)

        url = self._selected_url()
        url_id = self._selected_row_id()
        status = self._selected_row_status()
        if not url:
            return

        menu = QMenu(self)

        copy_url = QAction("Copy URL", self)
        copy_url.triggered.connect(lambda: self._copy_to_clipboard(url))
        menu.addAction(copy_url)
        menu.addSeparator()

        # Show "Resume download" for STOPPED or FAILED items
        added_action = False
        if status in (UrlStatus.STOPPED, UrlStatus.FAILED) and self._on_resume:
            resume_action = QAction("Resume download", self)
            resume_action.triggered.connect(lambda: self._on_resume(url))
            menu.addAction(resume_action)
            added_action = True

        # Show "Skip" for items that are not IN_PROGRESS and not already SKIPPED
        if status not in (UrlStatus.IN_PROGRESS, UrlStatus.SKIPPED) and self._on_skip:
            skip_action = QAction("Skip", self)
            skip_action.triggered.connect(lambda: self._on_skip(url_id))
            menu.addAction(skip_action)
            added_action = True

        if added_action:
            menu.addSeparator()

        check_new = QAction("Check for new files", self)
        check_new.triggered.connect(lambda: self._on_check_new(url))
        menu.addAction(check_new)

        force = QAction("Force full re-download", self)
        force.triggered.connect(lambda: self._on_force_redownload(url))
        menu.addAction(force)

        # Tags submenu
        tags_menu = QMenu("Tags", self)
        self._build_tags_submenu(tags_menu, url_id)
        menu.addMenu(tags_menu)

        menu.addSeparator()

        remove_action = QAction("Remove from history…", self)
        remove_action.triggered.connect(lambda: self._confirm_and_remove(url_id, url))
        menu.addAction(remove_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_to_clipboard(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _confirm_and_remove(self, url_id: int | None, url: str) -> None:
        if url_id is None:
            return

        result = QMessageBox.question(
            self,
            "Remove from history",
            f"Are you sure you want to remove this URL from history?\n\n{url}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = self._db.delete_url(int(url_id))
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot remove", str(e))
            return

        if deleted:
            self.refresh(page=self.model.current_page)
            self.url_removed.emit(int(url_id), url)

    def _build_tags_submenu(self, menu: QMenu, url_id: int | None) -> None:
        """Build the tags submenu with checkable tag items."""
        if url_id is None:
            return

        try:
            all_tags = self._db.list_tags()
            url_tags = self._db.get_tags_for_url(url_id)
            url_tag_ids = {t.id for t in url_tags}

            if not all_tags:
                no_tags_action = QAction("No tags defined", self)
                no_tags_action.setEnabled(False)
                menu.addAction(no_tags_action)
                return

            for tag in all_tags:
                action = QAction(tag.name, self)
                action.setCheckable(True)
                action.setChecked(tag.id in url_tag_ids)
                # Use default argument to capture current values
                action.triggered.connect(
                    lambda checked, tid=tag.id, uid=url_id: self._toggle_tag(uid, tid, checked)
                )
                menu.addAction(action)
        except Exception:
            error_action = QAction("Error loading tags", self)
            error_action.setEnabled(False)
            menu.addAction(error_action)

    def _toggle_tag(self, url_id: int, tag_id: int, assign: bool) -> None:
        """Toggle a tag assignment for a URL."""
        try:
            if assign:
                self._db.assign_tag_to_url(url_id, tag_id)
            else:
                self._db.remove_tag_from_url(url_id, tag_id)
            self.refresh(page=self.model.current_page)
            if self._on_tags_changed:
                self._on_tags_changed()
        except Exception as e:
            QMessageBox.warning(self, "Tag Error", f"Failed to update tag: {e}")
