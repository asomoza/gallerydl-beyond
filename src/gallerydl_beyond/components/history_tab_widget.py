from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gallerydl_beyond.common.database_manager import DatabaseManager
from gallerydl_beyond.models.history_model import HistoryModel


class HistoryTabWidget(QWidget):
    url_removed = pyqtSignal(int, str)

    def __init__(
        self, *, db_manager: DatabaseManager, on_check_new: callable, on_force_redownload: callable, parent=None
    ):
        super().__init__(parent)
        self._db = db_manager
        self._on_check_new = on_check_new
        self._on_force_redownload = on_force_redownload

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search URL...")

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)
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

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        top.addWidget(self.search, 1)
        top.addWidget(self.refresh_button, 0)

        layout.addLayout(top)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        text = self.search.text().strip() or None
        self.model.refresh(search=text)
        self.table.resizeColumnsToContents()

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

    def _open_context_menu(self, pos) -> None:
        # Ensure the row under the cursor is selected.
        index = self.table.indexAt(pos)
        if index.isValid():
            self.table.setCurrentIndex(index)

        url = self._selected_url()
        url_id = self._selected_row_id()
        if not url:
            return

        menu = QMenu(self)

        copy_url = QAction("Copy URL", self)
        copy_url.triggered.connect(lambda: self._copy_to_clipboard(url))
        menu.addAction(copy_url)
        menu.addSeparator()

        check_new = QAction("Check for new files", self)
        check_new.triggered.connect(lambda: self._on_check_new(url))
        menu.addAction(check_new)

        force = QAction("Force full re-download", self)
        force.triggered.connect(lambda: self._on_force_redownload(url))
        menu.addAction(force)

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
            self.refresh()
            self.url_removed.emit(int(url_id), url)
