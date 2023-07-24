"""
This module provides a graphical user interface for downloading images using the gallery-dl command.
"""

import sys
import sqlite3
import platform

from PyQt6 import QtWidgets, QtGui
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtCore import QSettings, Qt, QDateTime, QMutex, QThreadPool
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlRecord, QSqlField, QSqlQuery

from threads import DownloadThread, InitialWorker
from tables_views import ProcessedTableView, QueueTableView
from windows import LogWindow, MessageWindow

# Create a mutex to synchronize access to the database
db_mutex = QMutex()


class MainWindow(QtWidgets.QMainWindow):
    """Main window class for GalleryDL Beyond application."""

    def __init__(self, *args, **kwargs):
        """Initialize the main window."""
        super(MainWindow, self).__init__(*args, **kwargs)

        self.setWindowTitle("GalleryDL Beyond")
        self.settings = QSettings("ZCode", "GalleryDLBeyond")

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        window_state = self.settings.value("windowState")
        if window_state is not None:
            self.restoreState(window_state)

        # Create the urls table if it doesn"t exist
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                processed INTEGER NOT NULL DEFAULT 0,
                date_processed TEXT
            );
        """
        )
        conn.commit()
        conn.close()

        self.downloading = False
        self.blocked = True
        self.aborted = False

        # Main layout
        main_layout = QtWidgets.QVBoxLayout()
        list_layout = QtWidgets.QHBoxLayout()

        # Create the queue table view
        queue_layout = QtWidgets.QVBoxLayout()
        queue_layout.addWidget(QtWidgets.QLabel("Queue"))
        self.queue_table = QueueTableView()
        queue_layout.addWidget(self.queue_table)

        # Create the processed table view
        done_layout = QtWidgets.QVBoxLayout()
        done_layout.addWidget(QtWidgets.QLabel("Processed"))
        self.processed_table = ProcessedTableView()
        done_layout.addWidget(self.processed_table)

        # Assign each table the reference of the other
        self.processed_table.set_queue_table(self.queue_table)

        # Create the model for the queue table view
        self.queue_model = QSqlTableModel()

        list_layout.addLayout(queue_layout)
        list_layout.addLayout(done_layout)

        log_layout = QtWidgets.QHBoxLayout()

        # Log window
        self.log_text = LogWindow()
        log_layout.addWidget(self.log_text)

        # Message window
        self.messages = MessageWindow()
        log_layout.addWidget(self.messages)

        # Add references to message window in the table views
        self.queue_table.set_message_window(self.messages)
        self.processed_table.set_message_window(self.messages)

        add_layout = QtWidgets.QHBoxLayout()
        self.url_input = QtWidgets.QLineEdit()
        self.queue_button = QtWidgets.QPushButton("Queue")
        self.queue_button.setShortcut("Return")
        add_layout.addWidget(self.url_input)
        add_layout.addWidget(self.queue_button)

        self.start_button = QtWidgets.QPushButton()
        self.set_button_blocked()

        main_layout.addLayout(list_layout)
        main_layout.addLayout(log_layout)
        main_layout.addLayout(add_layout)
        main_layout.addWidget(self.start_button)

        # Set the stretch factors of the items
        main_layout.setStretch(0, 8)  # list_layout
        main_layout.setStretch(1, 4)  # log_text
        main_layout.setStretch(2, 1)  # add_layout
        main_layout.setStretch(3, 1)  # start_button

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.log_text)

        widget = QtWidgets.QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

        # Set up the database connection
        database = QSqlDatabase.addDatabase("QSQLITE")
        database.setDatabaseName("database.db")
        database.open()

        # Set up the queue model
        self.queue_model = QSqlTableModel(db=database)
        self.queue_model.setTable("urls")
        self.queue_model.setFilter("processed = 0")
        self.queue_model.select()

        # Set up the table view
        self.queue_table.setModel(self.queue_model)
        self.queue_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.queue_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.queue_table.hideColumn(0)
        self.queue_table.hideColumn(2)
        self.queue_table.hideColumn(3)
        self.queue_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )

        # Set up the processed model
        self.processed_model = QSqlTableModel(db=database)
        self.processed_model.setTable("urls")
        self.processed_model.setFilter("processed = 1")
        self.processed_model.setSort(3, Qt.SortOrder.DescendingOrder)
        self.processed_model.select()

        # Set up the processed table view
        self.processed_table.setModel(self.processed_model)
        self.processed_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.processed_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.processed_table.hideColumn(0)
        self.processed_table.hideColumn(2)
        self.processed_table.resizeColumnToContents(3)
        self.processed_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )

        # Define the download_thread attribute and set its initial value to None
        self.download_thread = None

        # Connect the add button"s clicked signal to the add_queue method
        self.queue_button.clicked.connect(self.add_queue)

        # Connect the start button"s clicked signal to the start method
        self.start_button.clicked.connect(self.start)

        # Check pĺatform
        os_name = platform.system()
        self.gallerydl_bin = ""

        if os_name == "Windows":
            gallerydl_ext = ".exe"
        elif os_name == "Linux":
            gallerydl_ext = ".bin"
        else:
            self.messages.append(f"Unsupported platform: {os_name}")
            return

        self.gallerydl_bin = "gallery-dl" + gallerydl_ext

        worker = InitialWorker(self.messages, self.gallerydl_bin)
        worker.signals.finished.connect(self.set_button_start)
        QThreadPool.globalInstance().start(worker)

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.StandardKey.Paste):
            # Handle the Ctrl+V shortcut in a custom way
            clipboard_text = QtGui.QGuiApplication.clipboard().text()
            self.url_input.setText(clipboard_text)
        else:
            super().keyPressEvent(event)

    # pylint: disable=invalid-name
    def closeEvent(self, event):
        """
        Reimplemented closeEvent method to save the window size and position when the application
        is closed.
        """

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def add_queue(self):
        # Acquire the mutex before writing to the database
        db_mutex.lock()

        url = self.url_input.text()
        if url:
            # Check if the URL already exists in the database
            query = QSqlQuery()
            query.prepare("SELECT COUNT(*) FROM urls WHERE url = ?")
            query.addBindValue(url)
            query.exec()
            query.next()
            count = query.value(0)

            if count > 0:
                # URL already exists, print an error message
                self.messages.warning(f"{url} already exists in the database")
            else:
                record = QSqlRecord()
                record.append(QSqlField("url"))
                record.setValue("url", url)
                self.queue_model.insertRecord(-1, record)
                self.queue_model.submitAll()
                self.url_input.clear()
                self.messages.add_message(f"{url} added to queue")

        # Release the mutex after writing to the database
        db_mutex.unlock()

    def set_button_blocked(self):
        self.start_button.setStyleSheet("background-color: #9c0d20;")
        self.start_button.setText("Waiting...")

    def set_button_start(self):
        self.blocked = False
        self.start_button.setStyleSheet("background-color: #0b5e26;")
        self.start_button.setText("Start")
        self.start_button.setShortcut("Ctrl+Return")

    def set_button_abort(self):
        self.start_button.setStyleSheet("background-color: #9c0d20;")
        self.start_button.setText("Abort")
        self.start_button.setShortcut("Ctrl+Return")

    def start(self):
        """Start the downloading of all URLS in the queue"""
        if self.blocked == True:
            self.messages.warning("Can't start yet, please wait.")
            return

        if self.downloading == True:
            self.aborted = True
            self.download_thread.stop()
        else:
            # Connect to the SQLite database
            conn = sqlite3.connect("database.db")
            c = conn.cursor()

            # Query the urls table for the next URL that is not processed
            c.execute(
                "SELECT id, url FROM urls WHERE processed = 0 ORDER BY id LIMIT 1"
            )
            row = c.fetchone()

            # Download URLs until there are no more URLs with processed = 0
            if row:
                self.set_button_abort()
                self.downloading = True
                url_id, url = row

                self.messages.add_message(f"Starting download of URL: {url}")

                # Create and start a download thread for the URL
                self.download_thread = DownloadThread(url_id, url, self.gallerydl_bin)
                self.download_thread.output.connect(self.append_output)
                self.download_thread.finished.connect(
                    lambda: self.download_finished(conn, c)
                )
                self.download_thread.start()
            else:
                conn.close()

    def download_finished(self, conn, c):
        # Acquire the mutex before writing to the database
        db_mutex.lock()

        if self.aborted == True:
            self.aborted = False
            self.set_button_start()
            self.downloading = False

            self.messages.error("Download process aborted.")
        else:
            # Get the URL ID from the sender
            download_thread = self.sender()
            url_id = download_thread.url_id
            url = download_thread.url

            # Get the index of the record with the specified url_id
            record_index = self.queue_model.match(
                self.queue_model.index(0, 0),
                Qt.ItemDataRole.DisplayRole,
                url_id,
                1,
                Qt.MatchFlag.MatchExactly,
            )[0]

            # Update the processed and date_processed columns for the record
            self.queue_model.setData(
                self.queue_model.index(
                    record_index.row(), self.queue_model.fieldIndex("processed")
                ),
                1,
            )
            self.queue_model.setData(
                self.queue_model.index(
                    record_index.row(), self.queue_model.fieldIndex("date_processed")
                ),
                QDateTime.currentDateTimeUtc().toString("yyyy-MM-dd hh:mm:ss"),
            )

            # Submit the changes to the database
            self.queue_model.submitAll()

            self.messages.success(f"Finished download of URL: {url}")

            # Refresh the models
            self.queue_model.select()
            self.processed_model.select()

            # Query the urls table for the next URL that is not processed
            c.execute(
                "SELECT id, url FROM urls WHERE processed = 0 ORDER BY id LIMIT 1"
            )
            row = c.fetchone()

            if row:
                url_id, url = row

                self.messages.add_message(f"Starting download of URL: {url}")

                # Create and start a download thread for the URL
                self.download_thread = DownloadThread(url_id, url, self.gallerydl_bin)
                self.download_thread.output.connect(self.append_output)
                self.download_thread.finished.connect(
                    lambda: self.download_finished(conn, c)
                )
                self.download_thread.start()
            else:
                conn.close()
                self.messages.success("No more urls to download, queue finished.")
                self.set_button_start()
                self.downloading = False
        # Release the mutex after writing to the database
        db_mutex.unlock()

    def append_output(self, output):
        """Append the output to the text widget."""

        # Split the output by the "/" character and get the last element
        filename = output.strip().split("/")[-1]

        # Append the filename to the text widget
        self.log_text.append(filename)

        lines = self.log_text.toPlainText().splitlines()
        if len(lines) > 2000:
            self.log_text.setPlainText("\n".join(lines[-1000:]))
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    if sys.platform == "win32":
        app.setStyle("Windows")

    window = MainWindow()
    window.show()
    app.exec()
