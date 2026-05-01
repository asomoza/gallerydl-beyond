from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from gallerydl_beyond.common.constants import UrlStatus
from gallerydl_beyond.common.database_manager import DatabaseManager, UrlRow


class HistoryModel(QAbstractTableModel):
    COLUMNS = [
        "#",
        "URL",
        "Status",
        "Downloads",
        "Added",
        "Processed",
        "Last error",
        "Tags",
    ]

    # Map column index to database sort column name
    SORTABLE_COLUMNS = {
        0: "id",  # # (row number based on id order)
        1: "url",  # URL
        2: "status",  # Status
        3: "download_count",  # Downloads
        4: "date_added",  # Added
        5: "date_processed",  # Processed
        # 6: Last error - not sortable
        # 7: Tags - not sortable
    }

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._db = db
        self._rows: list[UrlRow] = []
        # Pagination state
        self._page_size: int = 100
        self._current_page: int = 0
        self._total_count: int = 0
        self._search: str | None = None
        self._tag_id: int | None = None
        # Sorting state
        self._sort_column: str = "date_processed"
        self._sort_ascending: bool = False

    def refresh(
        self,
        *,
        search: str | None = None,
        tag_id: int | None = None,
        page: int = 0,
        page_size: int = 100,
        sort_column: str | None = None,
        sort_ascending: bool | None = None,
    ) -> None:
        self._search = search
        self._tag_id = tag_id
        self._page_size = page_size

        # Update sort state if provided
        if sort_column is not None:
            self._sort_column = sort_column
        if sort_ascending is not None:
            self._sort_ascending = sort_ascending

        self._total_count = self._db.count_urls(search=search, tag_id=tag_id)

        # Clamp page to valid range
        max_page = max(0, (self._total_count - 1) // page_size) if self._total_count > 0 else 0
        self._current_page = max(0, min(page, max_page))

        offset = self._current_page * page_size

        self.beginResetModel()
        self._rows = self._db.list_urls(
            search=search,
            tag_id=tag_id,
            limit=page_size,
            offset=offset,
            sort_column=self._sort_column,
            sort_ascending=self._sort_ascending,
        )
        self.endResetModel()

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:  # noqa: N802
        """Handle column header click for sorting."""
        sort_col = self.SORTABLE_COLUMNS.get(column)
        if sort_col is None:
            return  # Column not sortable

        ascending = order == Qt.SortOrder.AscendingOrder
        self.refresh(
            search=self._search,
            tag_id=self._tag_id,
            page=0,  # Reset to first page on sort change
            page_size=self._page_size,
            sort_column=sort_col,
            sort_ascending=ascending,
        )

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def total_pages(self) -> int:
        if self._total_count == 0:
            return 1
        return (self._total_count - 1) // self._page_size + 1

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def sort_column(self) -> str:
        return self._sort_column

    @property
    def sort_ascending(self) -> bool:
        return self._sort_ascending

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                # Row number: absolute position in the filtered/sorted result
                return str(self._current_page * self._page_size + index.row() + 1)
            if col == 1:
                return row.url
            if col == 2:
                return self._status_text(row.status)
            if col == 3:
                return str(row.download_count)
            if col == 4:
                return row.date_added
            if col == 5:
                return row.date_processed or ""
            if col == 6:
                return row.last_error or ""
            if col == 7:
                return ", ".join(row.tags) if row.tags else ""

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == 6 and row.last_error:
                return row.last_error
            if col == 7 and row.tags:
                return "\n".join(row.tags)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 2:
                return self._status_color(row.status)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 3):  # # and Downloads columns
                return Qt.AlignmentFlag.AlignCenter

        return None

    def get_row(self, row_index: int) -> UrlRow | None:
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    @staticmethod
    def _status_text(status: int) -> str:
        if status == UrlStatus.PENDING:
            return "Pending"
        if status == UrlStatus.IN_PROGRESS:
            return "In progress"
        if status == UrlStatus.COMPLETED:
            return "Completed"
        if status == UrlStatus.FAILED:
            return "Failed"
        if status == UrlStatus.STOPPED:
            return "Stopped"
        if status == UrlStatus.COMPLETED_PARTIAL:
            return "Partial"
        if status == UrlStatus.SKIPPED:
            return "Skipped"
        return str(status)

    @staticmethod
    def _status_color(status: int) -> QColor | None:
        if status == UrlStatus.PENDING:
            return QColor("#808080")  # Gray
        if status == UrlStatus.IN_PROGRESS:
            return QColor("#3498db")  # Blue
        if status == UrlStatus.COMPLETED:
            return QColor("#27ae60")  # Green
        if status == UrlStatus.FAILED:
            return QColor("#e74c3c")  # Red
        if status == UrlStatus.STOPPED:
            return QColor("#e67e22")  # Orange
        if status == UrlStatus.COMPLETED_PARTIAL:
            return QColor("#f1c40f")  # Yellow
        if status == UrlStatus.SKIPPED:
            return QColor("#9b59b6")  # Purple
        return None
