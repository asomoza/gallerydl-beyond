from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QWidget,
)

from gallerydl_beyond.common.base_dialog import BaseDialog
from gallerydl_beyond.gallerydl_utils.gallerydl_manager import GalleryDLManager, GalleryDLMode


class SettingsDialog(BaseDialog):
    def __init__(self, show_error: callable, manager: GalleryDLManager):
        super().__init__("Settings", show_error)
        self._manager = manager

        self._mode_group = QButtonGroup(self)
        self._mode_auto = QRadioButton("Auto (recommended)")
        self._mode_system = QRadioButton("System gallery-dl (PATH)")
        self._mode_python = QRadioButton("Python env (python -m gallery_dl)")
        self._mode_custom = QRadioButton("Custom executable")

        for button in (self._mode_auto, self._mode_system, self._mode_python, self._mode_custom):
            self._mode_group.addButton(button)

        self._custom_path = QLineEdit()
        self._custom_path.setPlaceholderText("/path/to/gallery-dl")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._save)
        self._buttons.rejected.connect(self.reject)

        self._build_ui(browse_btn)
        self._load_from_settings()

        self._mode_group.buttonClicked.connect(self._update_enabled_state)
        self._update_enabled_state()

    def _build_ui(self, browse_btn: QPushButton) -> None:
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        title = QLabel("Gallery-dl")
        title.setStyleSheet("font-weight: 600;")
        self.main_layout.addWidget(title)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        grid.addWidget(self._mode_auto, 0, 0, 1, 3)
        grid.addWidget(self._mode_system, 1, 0, 1, 3)
        grid.addWidget(self._mode_python, 2, 0, 1, 3)
        grid.addWidget(self._mode_custom, 3, 0, 1, 3)

        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.setSpacing(8)
        custom_row.addWidget(self._custom_path, 1)
        custom_row.addWidget(browse_btn, 0)

        grid.addLayout(custom_row, 4, 0, 1, 3)

        hint = QLabel("Tip: Auto uses system if available, otherwise the current Python env.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8a8a;")
        grid.addWidget(hint, 5, 0, 1, 3)

        self.main_layout.addWidget(container)
        self.main_layout.addWidget(self._buttons, alignment=Qt.AlignmentFlag.AlignRight)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select gallery-dl executable")
        if path:
            self._custom_path.setText(path)
            self._mode_custom.setChecked(True)
            self._update_enabled_state()

    def _load_from_settings(self) -> None:
        mode: GalleryDLMode = self._manager.get_mode()
        if mode == "system":
            self._mode_system.setChecked(True)
        elif mode == "python":
            self._mode_python.setChecked(True)
        elif mode == "custom":
            self._mode_custom.setChecked(True)
        else:
            self._mode_auto.setChecked(True)

        custom_path = self._manager.get_custom_path()
        if custom_path:
            self._custom_path.setText(custom_path)

    def _selected_mode(self) -> GalleryDLMode:
        if self._mode_system.isChecked():
            return "system"
        if self._mode_python.isChecked():
            return "python"
        if self._mode_custom.isChecked():
            return "custom"
        return "auto"

    def _update_enabled_state(self) -> None:
        is_custom = self._selected_mode() == "custom"
        self._custom_path.setEnabled(is_custom)

    def _save(self) -> None:
        mode = self._selected_mode()
        self._manager.set_mode(mode)
        if mode == "custom":
            self._manager.set_custom_path(self._custom_path.text())
        self.accept()
