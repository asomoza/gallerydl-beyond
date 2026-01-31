from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from gallerydl_beyond.common.constants import UrlStatus
from gallerydl_beyond.common.database_manager import DatabaseManager, UrlRow


class HistoryModel(QAbstractTableModel):
    COLUMNS = [
        "URL",
        "Status",
        "Downloads",
        "Added",
        "Processed",
        "Last error",
    ]

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._db = db
        self._rows: list[UrlRow] = []

    def refresh(self, *, search: str | None = None) -> None:
        self.beginResetModel()
        self._rows = self._db.list_urls(search=search, limit=500)
        self.endResetModel()

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
                return row.url
            if col == 1:
                return self._status_text(row.status)
            if col == 2:
                return str(row.download_count)
            if col == 3:
                return row.date_added
            if col == 4:
                return row.date_processed or ""
            if col == 5:
                return row.last_error or ""

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == 5 and row.last_error:
                return row.last_error

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 1:
                return self._status_color(row.status)

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
