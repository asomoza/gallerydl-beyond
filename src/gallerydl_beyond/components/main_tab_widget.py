from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gallerydl_beyond.common.constants import SettingsKeys
from gallerydl_beyond.components.log_window import LogWindow
from gallerydl_beyond.components.url_input_widget import UrlInputWidget


class DownloadsTabWidget(QWidget):
    url_submitted = pyqtSignal(str)

    start_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    stop_download_clicked = pyqtSignal(int)  # worker_id
    skip_download_clicked = pyqtSignal(int)  # worker_id

    max_concurrent_changed = pyqtSignal(int)

    def __init__(self, *, settings, parent=None):
        super().__init__(parent)
        self._settings = settings

        self.url_input = UrlInputWidget()
        self.url_input.url_submitted.connect(self.url_submitted)

        self.start_button = QPushButton("Start")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop All")

        self.start_button.clicked.connect(self.start_clicked)
        self.pause_button.clicked.connect(self.pause_clicked)
        self.stop_button.clicked.connect(self.stop_clicked)

        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(1, 8)
        self.max_concurrent.setValue(int(self._settings.value(SettingsKeys.MAX_CONCURRENT_DOWNLOADS, 2)))
        self.max_concurrent.valueChanged.connect(self._on_max_concurrent_changed)

        self.status_label = QLabel("Queue: 0 | Active: 0")
        self.status_label.setStyleSheet("color: #8a8a8a;")

        self.active_list = QListWidget()
        self.active_list.setMinimumHeight(90)
        self.active_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.active_list.customContextMenuRequested.connect(self._open_active_context_menu)

        self.log_window = LogWindow()

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        instructions = QLabel("Ctrl+V to paste, Enter to add URL")
        instructions.setStyleSheet("color: #8a8a8a;")
        layout.addWidget(instructions)

        layout.addWidget(self.url_input)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(10)

        controls.addWidget(self.start_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)

        controls.addWidget(QLabel("Concurrent:"))
        controls.addWidget(self.max_concurrent)
        controls.addStretch(1)
        controls.addWidget(self.status_label)

        layout.addLayout(controls)

        layout.addWidget(QLabel("Active downloads"))
        layout.addWidget(self.active_list)

        layout.addWidget(QLabel("Log output"))
        layout.addWidget(self.log_window)

    def handle_keypress(self, event) -> bool:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # If the line edit already has focus, its returnPressed handler will fire.
            if self.url_input.is_input_focused():
                return False
            self.url_input.submit_current()
            return True
        if event.matches(QKeySequence.StandardKey.Paste):
            # If the line edit has focus, let it handle paste normally.
            if self.url_input.is_input_focused():
                return False
            self.url_input.paste_from_clipboard()
            return True
        return False

    def set_counts(self, pending: int, stopped: int, active: int) -> None:
        if stopped > 0:
            self.status_label.setText(f"Queue: {pending} | Stopped: {stopped} | Active: {active}")
        else:
            self.status_label.setText(f"Queue: {pending} | Active: {active}")

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.stop_button.setEnabled(running)
        if not running:
            self.pause_button.setText("Pause")

    def set_paused(self, paused: bool) -> None:
        self.pause_button.setText("Resume" if paused else "Pause")

    def set_active(self, worker_id: int, url: str) -> None:
        key = f"[{worker_id}] {url}"
        for i in range(self.active_list.count()):
            if self.active_list.item(i).text().startswith(f"[{worker_id}]"):
                self.active_list.item(i).setText(key)
                return
        self.active_list.addItem(key)

    def clear_active(self, worker_id: int) -> None:
        for i in range(self.active_list.count() - 1, -1, -1):
            if self.active_list.item(i).text().startswith(f"[{worker_id}]"):
                self.active_list.takeItem(i)

    def append_log_line(self, line: str) -> None:
        self.log_window.add_message(line)

    def append_log_success(self, line: str) -> None:
        self.log_window.success(line)

    def append_log_warning(self, line: str) -> None:
        self.log_window.warning(line)

    def append_log_error(self, line: str) -> None:
        self.log_window.error(line)

    def _on_max_concurrent_changed(self, value: int) -> None:
        self._settings.setValue(SettingsKeys.MAX_CONCURRENT_DOWNLOADS, int(value))
        self.max_concurrent_changed.emit(int(value))

    def _get_selected_worker_id(self) -> int | None:
        """Extract worker_id from selected active list item."""
        item = self.active_list.currentItem()
        if item is None:
            return None
        text = item.text()
        # Format is "[worker_id] url"
        if text.startswith("[") and "]" in text:
            try:
                return int(text[1 : text.index("]")])
            except ValueError:
                return None
        return None

    def _open_active_context_menu(self, pos) -> None:
        index = self.active_list.indexAt(pos)
        if index.isValid():
            self.active_list.setCurrentIndex(index)

        worker_id = self._get_selected_worker_id()
        if worker_id is None:
            return

        menu = QMenu(self)

        stop_action = QAction("Stop this download", self)
        stop_action.triggered.connect(lambda: self.stop_download_clicked.emit(worker_id))
        menu.addAction(stop_action)

        skip_action = QAction("Skip this download", self)
        skip_action.triggered.connect(lambda: self.skip_download_clicked.emit(worker_id))
        menu.addAction(skip_action)

        menu.exec(self.active_list.viewport().mapToGlobal(pos))
