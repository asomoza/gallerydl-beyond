from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from gallerydl_beyond.common.base_dialog import BaseDialog
from gallerydl_beyond.gallerydl_utils.config_manager import ConfigManager


class ConfigEditorDialog(BaseDialog):
    def __init__(self, show_error: callable, config_manager: ConfigManager, config_path: str | Path | None = None):
        super().__init__("Config", show_error)
        self._config_manager = config_manager
        self._config_path = config_path

        self._path_label = QLabel()
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._base_dir = QLineEdit()
        self._archive = QLineEdit()
        self._rate = QLineEdit()

        self._retries = QSpinBox()
        self._retries.setRange(0, 999)

        self._timeout = QDoubleSpinBox()
        self._timeout.setRange(0.0, 9999.0)
        self._timeout.setSingleStep(1.0)
        self._timeout.setDecimals(1)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._save)
        self._buttons.rejected.connect(self.reject)

        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        title = QLabel("gallery-dl config.json")
        title.setStyleSheet("font-weight: 600;")
        self.main_layout.addWidget(title)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)
        path_row.addWidget(QLabel("Path:"))
        path_row.addWidget(self._path_label, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)

        self.main_layout.addLayout(path_row)

        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self._base_dir.setPlaceholderText("./downloads")
        self._archive.setPlaceholderText("./bin/archive.sqlite3")
        self._rate.setPlaceholderText("1M")

        form.addRow("Base directory", self._base_dir)
        form.addRow("Archive", self._archive)
        form.addRow("Rate", self._rate)
        form.addRow("Retries", self._retries)
        form.addRow("Timeout (s)", self._timeout)

        hint = QLabel(
            "Tip: Archive tracks downloaded items. Use rate like '1M' or '500K'. "
            "Timeout is seconds of inactivity before failing."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8a8a;")

        self.main_layout.addWidget(form_container)
        self.main_layout.addWidget(hint)
        self.main_layout.addWidget(self._buttons, alignment=Qt.AlignmentFlag.AlignRight)

    def _load(self) -> None:
        try:
            paths = self._config_manager.resolve_paths(self._config_path)
            config_path = self._config_manager.ensure_exists(paths.config_path)
            self._config_path = config_path
            self._path_label.setText(str(config_path))

            data = self._config_manager.load(config_path)
            extractor = data.get("extractor", {})
            downloader = data.get("downloader", {})

            self._base_dir.setText(str(extractor.get("base-directory", "./downloads")))
            self._archive.setText(str(extractor.get("archive", "./bin/archive.sqlite3")))
            self._rate.setText(str(downloader.get("rate", "1M")))
            self._retries.setValue(int(downloader.get("retries", 3)))
            self._timeout.setValue(float(downloader.get("timeout", 8.0)))
        except Exception as exc:
            self.show_error(str(exc))

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select config.json", filter="JSON Files (*.json);;All Files (*)")
        if not path:
            return

        self._config_path = Path(path)
        self._load()

    def _save(self) -> None:
        try:
            base_dir = self._base_dir.text().strip()
            archive = self._archive.text().strip()
            rate = self._rate.text().strip()

            if not base_dir:
                raise ValueError("Base directory cannot be empty")
            if not archive:
                raise ValueError("Archive cannot be empty")
            if not rate:
                rate = "1M"

            self._config_manager.update_common_fields(
                base_directory=base_dir,
                archive_path=archive,
                rate=rate,
                retries=int(self._retries.value()),
                timeout=float(self._timeout.value()),
                config_path=self._config_path,
            )
            self.accept()
        except Exception as exc:
            self.show_error(str(exc))
