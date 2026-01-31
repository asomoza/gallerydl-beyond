from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gallerydl_beyond.common.base_dialog import BaseDialog
from gallerydl_beyond.gallerydl_utils.config_manager import ConfigManager
from gallerydl_beyond.gallerydl_utils.gallerydl_manager import GalleryDLManager, GalleryDLMode


class GalleryDLOptionsDialog(BaseDialog):
    """Unified dialog for gallery-dl execution mode and config.json settings."""

    def __init__(
        self,
        show_error: callable,
        gallerydl_manager: GalleryDLManager,
        config_manager: ConfigManager,
        config_path: str | Path | None = None,
    ):
        super().__init__("Gallery-dl Options", show_error)
        self._gallerydl_manager = gallerydl_manager
        self._config_manager = config_manager
        self._config_path = config_path
        self._initial_mode: GalleryDLMode = gallerydl_manager.get_mode()
        self._mode_changed = False

        self._build_ui()
        self._load_execution_settings()
        self._load_config_settings()

    def _build_ui(self) -> None:
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        self._tabs = QTabWidget()

        # Execution tab
        execution_tab = self._build_execution_tab()
        self._tabs.addTab(execution_tab, "Execution")

        # Configuration tab
        config_tab = self._build_config_tab()
        self._tabs.addTab(config_tab, "Configuration")

        self.main_layout.addWidget(self._tabs, 1)

        # Buttons at the bottom
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._save)
        self._buttons.rejected.connect(self.reject)
        self.main_layout.addWidget(self._buttons, alignment=Qt.AlignmentFlag.AlignRight)

    def _build_execution_tab(self) -> QWidget:
        """Build the execution mode tab (how to run gallery-dl)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("How to run gallery-dl")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        # Mode selection
        self._mode_group = QButtonGroup(self)
        self._mode_auto = QRadioButton("Auto (recommended)")
        self._mode_system = QRadioButton("System gallery-dl (PATH)")
        self._mode_python = QRadioButton("Python env (python -m gallery_dl)")
        self._mode_custom = QRadioButton("Custom executable")

        for button in (self._mode_auto, self._mode_system, self._mode_python, self._mode_custom):
            self._mode_group.addButton(button)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        grid.addWidget(self._mode_auto, 0, 0, 1, 3)
        grid.addWidget(self._mode_system, 1, 0, 1, 3)
        grid.addWidget(self._mode_python, 2, 0, 1, 3)
        grid.addWidget(self._mode_custom, 3, 0, 1, 3)

        # Custom path row
        self._custom_path = QLineEdit()
        self._custom_path.setPlaceholderText("/path/to/gallery-dl")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_executable)

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

        layout.addWidget(container)
        layout.addStretch(1)

        self._mode_group.buttonClicked.connect(self._update_custom_enabled)

        return tab

    def _build_config_tab(self) -> QWidget:
        """Build the configuration tab (config.json settings)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("config.json settings")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        # Config path row
        self._path_label = QLabel()
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)
        path_row.addWidget(QLabel("Path:"))
        path_row.addWidget(self._path_label, 1)

        browse_config_btn = QPushButton("Browse")
        browse_config_btn.clicked.connect(self._browse_config)
        path_row.addWidget(browse_config_btn)

        layout.addLayout(path_row)

        # Form fields
        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self._base_dir = QLineEdit()
        self._base_dir.setPlaceholderText("./downloads")

        self._archive = QLineEdit()
        self._archive.setPlaceholderText("./bin/archive.sqlite3")

        self._rate = QLineEdit()
        self._rate.setPlaceholderText("1M")

        self._retries = QSpinBox()
        self._retries.setRange(0, 999)

        self._timeout = QDoubleSpinBox()
        self._timeout.setRange(0.0, 9999.0)
        self._timeout.setSingleStep(1.0)
        self._timeout.setDecimals(1)

        form.addRow("Base directory", self._base_dir)
        form.addRow("Archive", self._archive)
        form.addRow("Rate", self._rate)
        form.addRow("Retries", self._retries)
        form.addRow("Timeout (s)", self._timeout)

        layout.addWidget(form_container)

        hint = QLabel(
            "Tip: Archive tracks downloaded items. Use rate like '1M' or '500K'. "
            "Timeout is seconds of inactivity before failing."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8a8a;")
        layout.addWidget(hint)

        layout.addStretch(1)

        return tab

    def _load_execution_settings(self) -> None:
        """Load current gallery-dl execution mode settings."""
        mode: GalleryDLMode = self._gallerydl_manager.get_mode()
        if mode == "system":
            self._mode_system.setChecked(True)
        elif mode == "python":
            self._mode_python.setChecked(True)
        elif mode == "custom":
            self._mode_custom.setChecked(True)
        else:
            self._mode_auto.setChecked(True)

        custom_path = self._gallerydl_manager.get_custom_path()
        if custom_path:
            self._custom_path.setText(custom_path)

        self._update_custom_enabled()

    def _load_config_settings(self) -> None:
        """Load current config.json settings."""
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

    def _selected_mode(self) -> GalleryDLMode:
        if self._mode_system.isChecked():
            return "system"
        if self._mode_python.isChecked():
            return "python"
        if self._mode_custom.isChecked():
            return "custom"
        return "auto"

    def _update_custom_enabled(self) -> None:
        is_custom = self._selected_mode() == "custom"
        self._custom_path.setEnabled(is_custom)

    def _browse_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select gallery-dl executable")
        if path:
            self._custom_path.setText(path)
            self._mode_custom.setChecked(True)
            self._update_custom_enabled()

    def _browse_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select config.json", filter="JSON Files (*.json);;All Files (*)")
        if not path:
            return

        self._config_path = Path(path)
        self._load_config_settings()

    def _save(self) -> None:
        """Save both execution mode and config settings."""
        try:
            # Save execution mode
            mode = self._selected_mode()
            self._gallerydl_manager.set_mode(mode)
            if mode == "custom":
                self._gallerydl_manager.set_custom_path(self._custom_path.text())

            self._mode_changed = mode != self._initial_mode

            # Save config.json
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

    @property
    def mode_changed(self) -> bool:
        """Returns True if the execution mode was changed."""
        return self._mode_changed

    @property
    def config_path(self) -> str | Path | None:
        """Returns the current config path."""
        return self._config_path
