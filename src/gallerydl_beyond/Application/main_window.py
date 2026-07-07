import logging
import platform

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QPushButton, QTabWidget, QVBoxLayout, QWidget

from gallerydl_beyond.common import DEFAULT_DB_FILENAME, DatabaseManager, SettingsKeys
from gallerydl_beyond.components.history_tab_widget import HistoryTabWidget
from gallerydl_beyond.components.main_tab_widget import DownloadsTabWidget
from gallerydl_beyond.dialogs.database_dialog import DatabaseDialog
from gallerydl_beyond.dialogs.gallerydl_options_dialog import GalleryDLOptionsDialog
from gallerydl_beyond.dialogs.url_exists_dialog import UrlExistsDialog
from gallerydl_beyond.gallerydl_utils.config_manager import ConfigManager
from gallerydl_beyond.gallerydl_utils.gallerydl_manager import GalleryDLManager
from gallerydl_beyond.threads.download_manager import DownloadManager
from gallerydl_beyond.threads.startup_worker import StartupResult, StartupWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("GalleryDL Beyond")
        self.setMinimumSize(550, 650)

        self.logger = logging.getLogger(__name__)

        self.db_manager = DatabaseManager(DEFAULT_DB_FILENAME)
        self.db_manager.ensure_database()

        # Reset any URLs left in IN_PROGRESS state from a previous session
        reset_count = self.db_manager.reset_in_progress_to_stopped()
        if reset_count > 0:
            logging.getLogger(__name__).info(f"Reset {reset_count} interrupted download(s) to stopped")

        self.settings = QSettings("ZCode", "GalleryDLBeyond")
        self.gallerydl_manager = GalleryDLManager(self.settings)
        self.config_manager = ConfigManager()
        self.config_path = None
        self.download_manager: DownloadManager | None = None
        self.gallerydl_cmd = None
        self._startup_worker: StartupWorker | None = None

        geometry = self.settings.value(SettingsKeys.WINDOW_GEOMETRY)
        if geometry is not None:
            self.restoreGeometry(geometry)

        window_state = self.settings.value(SettingsKeys.WINDOW_STATE)
        if window_state is not None:
            self.restoreState(window_state)

        self.init_ui()
        self.start_up()

    def init_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(10)

        manage_database_button = QPushButton("Manage Database")
        manage_database_button.clicked.connect(self.open_database_dialog)
        toolbar.addWidget(manage_database_button)

        gallerydl_options_button = QPushButton("Gallery-dl Options")
        gallerydl_options_button.clicked.connect(self.open_gallerydl_options_dialog)
        toolbar.addWidget(gallerydl_options_button)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.tabs = QTabWidget()

        self.downloads_tab = DownloadsTabWidget(settings=self.settings)
        self.downloads_tab.url_submitted.connect(self._on_url_submitted)
        self.downloads_tab.start_clicked.connect(self._on_start_download)
        self.downloads_tab.pause_clicked.connect(self._on_pause_resume)
        self.downloads_tab.stop_clicked.connect(self._on_stop_all)
        self.downloads_tab.max_concurrent_changed.connect(self._on_max_concurrent_changed)
        self.downloads_tab.stop_download_clicked.connect(self._on_stop_download)
        self.downloads_tab.skip_download_clicked.connect(self._on_skip_download)

        self.history_tab = HistoryTabWidget(
            db_manager=self.db_manager,
            on_check_new=self._history_check_new,
            on_force_redownload=self._history_force_redownload,
            on_resume=self._history_resume,
            on_skip=self._history_skip,
            on_tags_changed=self._on_tags_changed,
        )
        self.history_tab.url_removed.connect(self._on_history_url_removed)
        self.history_tab.urls_requeued.connect(self._on_history_urls_requeued)

        self.tabs.addTab(self.downloads_tab, "Downloads")
        self.tabs.addTab(self.history_tab, "History")
        layout.addWidget(self.tabs, 1)

        self.setCentralWidget(root)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Global shortcuts for fast queueing when the window has focus.
        if self.tabs.currentWidget() == self.downloads_tab and self.downloads_tab.handle_keypress(event):
            event.accept()
            return

        super().keyPressEvent(event)

    def _on_start_download(self) -> None:
        if not self.gallerydl_cmd:
            self.downloads_tab.append_log_error("gallery-dl not configured")
            self.downloads_tab.append_log_line("Open Settings and choose system/python/custom.")
            return

        if not self.config_path:
            self.downloads_tab.append_log_error("config.json not available")
            return

        if self.download_manager and self.download_manager.is_running:
            self.downloads_tab.append_log_warning("Downloads already running")
            return

        max_workers = int(self.settings.value(SettingsKeys.MAX_CONCURRENT_DOWNLOADS, 2))
        self.download_manager = DownloadManager(
            db_manager=self.db_manager,
            gallerydl_cmd=self.gallerydl_cmd,
            config_path=self.config_path,
            max_workers=max_workers,
        )
        self._wire_download_manager(self.download_manager)

        self.downloads_tab.set_paused(False)
        self.downloads_tab.set_running(True)
        self.download_manager.start()

    def _on_pause_resume(self) -> None:
        manager = self.download_manager
        if not manager or not manager.is_running:
            return

        if manager.is_paused:
            manager.resume()
            self.downloads_tab.set_paused(False)
            self.downloads_tab.append_log_line("Resumed")
        else:
            manager.pause()
            self.downloads_tab.set_paused(True)
            self.downloads_tab.append_log_line("Paused (active downloads will finish)")

    def _on_stop_all(self) -> None:
        manager = self.download_manager
        if not manager:
            return
        manager.stop_all()
        self.downloads_tab.append_log_line("Stopping all downloads...")

    def _on_max_concurrent_changed(self, value: int) -> None:
        manager = self.download_manager
        if manager and manager.is_running:
            old_count = len(manager._workers)
            manager.set_max_workers(int(value))
            new_max = int(value)
            if old_count > new_max:
                excess = old_count - new_max
                self.downloads_tab.append_log_line(f"Reducing to {new_max} workers (requeuing {excess} download(s))")
            elif new_max > old_count:
                self.downloads_tab.append_log_line(f"Increasing to {new_max} workers")

    def _wire_download_manager(self, manager: DownloadManager) -> None:
        manager.all_started.connect(lambda: self.downloads_tab.append_log_line("Downloads started"))
        manager.all_finished.connect(self._on_downloads_finished)
        manager.queue_updated.connect(self._on_queue_updated)
        manager.worker_started.connect(self._on_worker_started)
        manager.worker_output.connect(lambda wid, line: self.downloads_tab.append_log_line(f"[{wid}] {line}"))
        manager.worker_completed.connect(lambda wid, url_id: self._on_worker_done(wid, f"Completed (id={url_id})"))
        manager.worker_failed.connect(
            lambda wid, url_id, err: self._on_worker_done(wid, f"Failed (id={url_id}): {err}")
        )

    def _on_queue_updated(self, pending: int, stopped: int, active: int) -> None:
        self.downloads_tab.set_counts(pending, stopped, active)

    def _on_downloads_finished(self) -> None:
        self.downloads_tab.append_log_line("All downloads finished")
        self.downloads_tab.set_running(False)
        self.history_tab.refresh(preserve_page=True)

    def _refresh_counts(self) -> None:
        try:
            pending, stopped, active = self.db_manager.get_counts()
            self.downloads_tab.set_counts(pending, stopped, active)
        except Exception:
            self.logger.exception("Failed to get DB counts")

    def _on_history_url_removed(self, _url_id: int, url: str) -> None:
        if url:
            self.downloads_tab.append_log_line(f"Removed from history: {url}")
        self._refresh_counts()

    def _on_history_urls_requeued(self, count: int) -> None:
        """Handle bulk requeue from history tab."""
        self.downloads_tab.append_log_line(f"Re-queued {count} URLs from history")
        self._refresh_counts()
        self._try_auto_start()

    def _on_url_submitted(self, url: str) -> None:
        try:
            row_id = self.db_manager.add_url(url)
            if row_id is not None:
                self.downloads_tab.append_log_success("Added")
                self.downloads_tab.append_log_line(url)
                self.downloads_tab.url_input.clear()
                self._refresh_counts()
                self.history_tab.refresh(preserve_page=True)
                self._try_auto_start()
                return

            dialog = UrlExistsDialog(self.show_error, url)
            if not dialog.exec():
                return

            action = dialog.result.action
            if action == "check_new":
                updated = self.db_manager.requeue_existing_url(url, check_new_only=True, force_redownload=False)
                if updated is not None:
                    self.downloads_tab.append_log_line(f"Re-queued (check new): {url}")
                    self._refresh_counts()
                    self.history_tab.refresh(preserve_page=True)
                    self._try_auto_start()
            elif action == "force":
                updated = self.db_manager.requeue_existing_url(url, check_new_only=False, force_redownload=True)
                if updated is not None:
                    self.downloads_tab.append_log_line(f"Re-queued (force): {url}")
                    self._refresh_counts()
                    self.history_tab.refresh(preserve_page=True)
                    self._try_auto_start()
        except Exception as e:
            self.logger.exception("Failed to add URL")
            self.downloads_tab.append_log_error("URL add failed")
            self.downloads_tab.append_log_line(str(e))

    def _try_auto_start(self) -> None:
        """Try to start downloading newly added URLs if the manager is running."""
        if self.download_manager and self.download_manager.is_running:
            self.download_manager.try_fill_workers()

    def closeEvent(self, event):
        self.settings.setValue(SettingsKeys.WINDOW_GEOMETRY, self.saveGeometry())
        self.settings.setValue(SettingsKeys.WINDOW_STATE, self.saveState())

        # Stop all running downloads gracefully
        if self.download_manager and self.download_manager.is_running:
            self.download_manager.stop_all()
            # Wait for workers to finish (they will mark URLs as STOPPED)
            for worker in list(self.download_manager._workers.values()):
                worker.wait(5000)  # Wait up to 5 seconds per worker

        event.accept()

    def start_up(self):
        # If the user changes settings while downloads are running, stop them.
        if self.download_manager and self.download_manager.is_running:
            self.download_manager.stop_all()
            self.download_manager = None
            self.downloads_tab.set_running(False)

        os_name = platform.system()
        self.downloads_tab.append_log_line(f"Detected OS: {os_name}")

        # Disable starting downloads until startup has resolved dependencies.
        self.downloads_tab.start_button.setEnabled(False)

        if self._startup_worker and self._startup_worker.isRunning():
            return

        mode = self.gallerydl_manager.get_mode()
        custom_path = self.gallerydl_manager.get_custom_path()

        self._startup_worker = StartupWorker(
            db_manager=self.db_manager,
            config_manager=self.config_manager,
            gallerydl_mode=mode,
            gallerydl_custom_path=custom_path,
            config_path=self.config_path,
        )
        self._startup_worker.log.connect(self._on_startup_log)
        self._startup_worker.finished_result.connect(self._on_startup_finished)
        self._startup_worker.start()

    def _on_startup_log(self, level: str, message: str) -> None:
        if level == "success":
            self.downloads_tab.append_log_success(message)
        elif level == "warning":
            self.downloads_tab.append_log_warning(message)
        elif level == "error":
            self.downloads_tab.append_log_error(message)
        else:
            self.downloads_tab.append_log_line(message)

    def _on_startup_finished(self, result_obj: object) -> None:
        result = result_obj if isinstance(result_obj, StartupResult) else None
        if result is None:
            self.downloads_tab.append_log_error("Startup failed")
            self.downloads_tab.start_button.setEnabled(True)
            return

        self.config_path = result.config_path
        self.gallerydl_cmd = result.gallerydl_cmd

        if self.gallerydl_cmd and self.config_path:
            self.downloads_tab.append_log_success("Ready!")
            self.downloads_tab.start_button.setEnabled(True)
        else:
            self.downloads_tab.append_log_warning("Ready (gallery-dl missing)")
            self.downloads_tab.start_button.setEnabled(False)

        self._refresh_counts()
        self.history_tab.refresh()

    def open_database_dialog(self):
        database_dialog = DatabaseDialog(self.db_manager, self.config_path, self.show_error)
        database_dialog.exec()
        # Refresh UI after dialog closes since database may have changed
        self._refresh_counts()
        self.history_tab.refresh_tags()  # Refresh tag filter and table

    def open_gallerydl_options_dialog(self):
        dialog = GalleryDLOptionsDialog(self.show_error, self.gallerydl_manager, self.config_manager, self.config_path)
        if dialog.exec():
            self.config_path = dialog.config_path
            self.downloads_tab.append_log_success("Options saved")
            if dialog.mode_changed:
                self.start_up()
            else:
                self.downloads_tab.append_log_line(f"Using config: {self.config_path}")

    def show_error(self, message):
        self.logger.error(message)

    def _on_worker_started(self, worker_id: int, url: str) -> None:
        self.downloads_tab.set_active(worker_id, url)
        self.downloads_tab.append_log_line(f"[{worker_id}] Starting: {url}")
        self.history_tab.refresh(preserve_page=True)

    def _on_worker_done(self, worker_id: int, message: str) -> None:
        self.downloads_tab.clear_active(worker_id)
        self.downloads_tab.append_log_line(f"[{worker_id}] {message}")
        self.history_tab.refresh(preserve_page=True)

    def _history_check_new(self, url: str) -> None:
        updated = self.db_manager.requeue_existing_url(url, check_new_only=True, force_redownload=False)
        if updated is not None:
            self.downloads_tab.append_log_line(f"Re-queued (check new): {url}")
            self._refresh_counts()
            self.history_tab.refresh(preserve_page=True)
            self._try_auto_start()

    def _history_force_redownload(self, url: str) -> None:
        updated = self.db_manager.requeue_existing_url(url, check_new_only=False, force_redownload=True)
        if updated is not None:
            self.downloads_tab.append_log_line(f"Re-queued (force): {url}")
            self._refresh_counts()
            self.history_tab.refresh(preserve_page=True)
            self._try_auto_start()

    def _history_resume(self, url: str) -> None:
        """Resume a stopped or failed download by re-queuing it."""
        updated = self.db_manager.requeue_existing_url(url, check_new_only=False, force_redownload=False)
        if updated is not None:
            self.downloads_tab.append_log_line(f"Re-queued (resume): {url}")
            self._refresh_counts()
            self.history_tab.refresh(preserve_page=True)
            self._try_auto_start()

    def _history_skip(self, url_id: int) -> None:
        """Mark a URL as skipped from history."""
        self.db_manager.mark_skipped(url_id)
        self.downloads_tab.append_log_line(f"Marked as skipped (id={url_id})")
        self._refresh_counts()
        self.history_tab.refresh(preserve_page=True)

    def _on_tags_changed(self) -> None:
        """Called when tags are modified. Refresh history to show updated tags."""
        self.history_tab.refresh(preserve_page=True)

    def _on_stop_download(self, worker_id: int) -> None:
        """Stop a specific download from the active list."""
        if self.download_manager:
            if self.download_manager.stop_worker(worker_id):
                self.downloads_tab.append_log_line(f"[{worker_id}] Stopping...")

    def _on_skip_download(self, worker_id: int) -> None:
        """Skip a specific download from the active list (stop and mark as skipped)."""
        if self.download_manager:
            if self.download_manager.skip_worker(worker_id):
                self.downloads_tab.append_log_line(f"[{worker_id}] Skipping...")
