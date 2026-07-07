from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
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
    QMenu,
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
        self._mode_external = QRadioButton("External Python environment")
        self._mode_custom = QRadioButton("Custom executable")

        for button in (
            self._mode_auto,
            self._mode_system,
            self._mode_python,
            self._mode_external,
            self._mode_custom,
        ):
            self._mode_group.addButton(button)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        grid.addWidget(self._mode_auto, 0, 0, 1, 3)
        grid.addWidget(self._mode_system, 1, 0, 1, 3)
        grid.addWidget(self._mode_python, 2, 0, 1, 3)

        # External python row: path edit + Browse + Discover
        grid.addWidget(self._mode_external, 3, 0, 1, 3)

        self._external_interp = QLineEdit()
        self._external_interp.setPlaceholderText("/path/to/venv/bin/python")
        # Re-evaluate the Update button whenever the interp path changes —
        # otherwise the button stays stale (enabled/disabled) until the user
        # clicks a radio button.
        self._external_interp.textChanged.connect(self._refresh_update_button_state)

        external_browse_btn = QPushButton("Browse")
        external_browse_btn.clicked.connect(self._browse_external_interp)

        self._discover_btn = QPushButton("Discover")
        self._discover_btn.setToolTip("Scan well-known venv locations for gallery-dl")
        self._discover_btn.clicked.connect(self._discover_environments)

        external_row = QHBoxLayout()
        external_row.setContentsMargins(20, 0, 0, 0)  # indent under the radio
        external_row.setSpacing(8)
        external_row.addWidget(self._external_interp, 1)
        external_row.addWidget(external_browse_btn, 0)
        external_row.addWidget(self._discover_btn, 0)

        grid.addLayout(external_row, 4, 0, 1, 3)

        # Custom executable row
        grid.addWidget(self._mode_custom, 5, 0, 1, 3)

        self._custom_path = QLineEdit()
        self._custom_path.setPlaceholderText("/path/to/gallery-dl")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_executable)

        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(20, 0, 0, 0)  # indent under the radio
        custom_row.setSpacing(8)
        custom_row.addWidget(self._custom_path, 1)
        custom_row.addWidget(browse_btn, 0)

        grid.addLayout(custom_row, 6, 0, 1, 3)

        hint = QLabel("Tip: Auto uses system if available, otherwise the current Python env.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8a8a;")
        grid.addWidget(hint, 7, 0, 1, 3)

        layout.addWidget(container)

        # --- Update gallery-dl --------------------------------------------------
        # Manual update button + status label. We deliberately do NOT auto-update
        # at startup: in a uv-managed project the upgrade succeeds in the moment
        # but is reverted by the next `uv run`'s sync from uv.lock, which used
        # to make the warning loop forever. The button is honest — it runs the
        # upgrade in the live env, and the hint reminds the user that a
        # permanent fix needs the lockfile too.
        update_box = QWidget()
        update_layout = QVBoxLayout(update_box)
        update_layout.setContentsMargins(0, 8, 0, 0)
        update_layout.setSpacing(6)

        update_title = QLabel("Update gallery-dl")
        update_title.setStyleSheet("font-weight: 600;")
        update_layout.addWidget(update_title)

        update_row = QHBoxLayout()
        update_row.setContentsMargins(0, 0, 0, 0)
        update_row.setSpacing(8)

        self._update_btn = QPushButton("Update gallery-dl")
        self._update_btn.setToolTip("Run `uv pip install --upgrade gallery-dl` (with pip fallback)")
        self._update_btn.clicked.connect(self._update_gallerydl)

        self._update_status = QLabel("")
        self._update_status.setWordWrap(True)
        self._update_status.setStyleSheet("color: #8a8a8a;")

        update_row.addWidget(self._update_btn, 0)
        update_row.addWidget(self._update_status, 1)
        update_layout.addLayout(update_row)

        update_hint = QLabel(
            "Updates the running env immediately. For uv-managed projects, also run "
            "`uv sync --upgrade-package gallery-dl` to update uv.lock — otherwise the "
            "next `uv run` will revert the upgrade."
        )
        update_hint.setWordWrap(True)
        update_hint.setStyleSheet("color: #8a8a8a;")
        update_layout.addWidget(update_hint)

        layout.addWidget(update_box)
        layout.addStretch(1)

        self._mode_group.buttonClicked.connect(self._update_mode_dependent_enabled)

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
        elif mode == "external_python":
            self._mode_external.setChecked(True)
        elif mode == "custom":
            self._mode_custom.setChecked(True)
        else:
            self._mode_auto.setChecked(True)

        custom_path = self._gallerydl_manager.get_custom_path()
        if custom_path:
            self._custom_path.setText(custom_path)

        external_interp = self._gallerydl_manager.get_external_interp()
        if external_interp:
            self._external_interp.setText(external_interp)

        self._update_mode_dependent_enabled()

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
        if self._mode_external.isChecked():
            return "external_python"
        if self._mode_custom.isChecked():
            return "custom"
        return "auto"

    def _update_mode_dependent_enabled(self) -> None:
        mode = self._selected_mode()
        self._custom_path.setEnabled(mode == "custom")
        is_external = mode == "external_python"
        self._external_interp.setEnabled(is_external)
        # Discover is always available — it just lists candidates; selecting one
        # also flips the radio. Forcing the user to pick the radio first would
        # be a worse flow.
        self._refresh_update_button_state()

    def _refresh_update_button_state(self) -> None:
        """Enable the Update button only for modes where it can plausibly work.

        `system` and `custom` resolutions point at opaque executables we
        don't manage (system package, /usr/bin, etc.); running `pip install
        -U` against them either no-ops or fails with a confusing message.
        Disabling the button there avoids the false hope. For
        `external_python` we additionally require the interpreter field to
        be non-empty, otherwise the dispatcher would just bounce back with
        "no interpreter configured".

        We mirror this server-side check (`GalleryDLManager.try_update`
        also bails on missing interp) but doing it in the UI gives the
        user a clear visual signal without having to click first.
        """
        mode = self._selected_mode()
        if mode in ("auto", "python"):
            self._update_btn.setEnabled(True)
            self._update_btn.setToolTip(
                "Run `uv sync --upgrade-package gallery-dl` (uv-managed projects) "
                "or `uv pip install --upgrade gallery-dl`."
            )
        elif mode == "external_python":
            has_interp = bool(self._external_interp.text().strip())
            self._update_btn.setEnabled(has_interp)
            if has_interp:
                self._update_btn.setToolTip("Upgrade gallery-dl in the selected external Python environment.")
            else:
                self._update_btn.setToolTip("Pick or discover an external Python interpreter first.")
        else:
            # system / custom — we don't own the target env.
            self._update_btn.setEnabled(False)
            self._update_btn.setToolTip(
                "Update is only available in Auto, Python, or External Python modes. "
                "For system/custom installs, upgrade with your package manager "
                "(e.g. `pip install -U gallery-dl`)."
            )

    def _browse_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select gallery-dl executable")
        if path:
            self._custom_path.setText(path)
            self._mode_custom.setChecked(True)
            self._update_mode_dependent_enabled()

    def _browse_external_interp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Python interpreter")
        if path:
            self._external_interp.setText(path)
            self._mode_external.setChecked(True)
            self._update_mode_dependent_enabled()

    def _discover_environments(self) -> None:
        """Probe well-known venv locations and show a menu of matches."""
        # The probe shells out to each candidate — it's fast (a handful of
        # subprocesses with short timeouts) but not instant, so we briefly
        # disable the button to make the wait obvious.
        self._discover_btn.setEnabled(False)
        try:
            envs = self._gallerydl_manager.discover_environments()
        finally:
            self._discover_btn.setEnabled(True)

        menu = QMenu(self._discover_btn)
        if not envs:
            action = QAction("No gallery-dl environments found", menu)
            action.setEnabled(False)
            menu.addAction(action)
        else:
            for env in envs:
                label = f"{env.source} — {env.version}\n{env.interp}"
                action = QAction(label, menu)
                # Capture by default arg so the lambda binds the current env.
                action.triggered.connect(lambda _checked=False, e=env: self._select_discovered(e))
                menu.addAction(action)
        menu.exec(self._discover_btn.mapToGlobal(self._discover_btn.rect().bottomLeft()))

    def _select_discovered(self, env) -> None:
        self._external_interp.setText(str(env.interp))
        self._mode_external.setChecked(True)
        self._update_mode_dependent_enabled()

    def _update_gallerydl(self) -> None:
        """Trigger a one-shot upgrade of gallery-dl in the running environment."""
        # The shell-out can take a few seconds; disable the button and show a
        # transient status so the user has feedback while it runs.
        self._update_btn.setEnabled(False)
        self._update_status.setText("Updating…")
        self._update_status.setStyleSheet("color: #8a8a8a;")
        # Force the label to repaint before the blocking subprocess call.
        self._update_status.repaint()
        try:
            ok, message = self._gallerydl_manager.try_update()
        finally:
            self._update_btn.setEnabled(True)

        if ok:
            self._update_status.setText(message or "gallery-dl updated")
            self._update_status.setStyleSheet("color: #4caf50;")
        else:
            self._update_status.setText(message or "Update failed")
            self._update_status.setStyleSheet("color: #f44336;")

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
            elif mode == "external_python":
                interp = self._external_interp.text().strip()
                if not interp:
                    raise ValueError("External Python: interpreter path cannot be empty")
                self._gallerydl_manager.set_external_interp(interp)

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
