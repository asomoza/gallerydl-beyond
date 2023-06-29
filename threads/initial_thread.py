import sys
import os
import shutil
import platform

from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
import urllib.request


class Signals(QObject):
    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)


class InitialWorker(QRunnable):
    def __init__(self, message_window, gallerydl_filename):
        super().__init__()

        self.signals = Signals()
        self.message_window = message_window
        self.gallerydl_filename = gallerydl_filename

    def run(self):
        self.signals.started.emit()

        # Check for a config file and copy it if it doesn't exist
        self.message_window.add_message("Checking for config file...")
        if not os.path.isfile("config.json"):
            self.message_window.warning(
                "No config file found. Copying default.")
            shutil.copy(os.path.join(self.resource_path(),
                        "config.json"), "config.json")
            self.message_window.success("Default config file copied.")
        else:
            self.message_window.success("Config file found.")

        # Check for gallery-dl
        self.message_window.add_message("Checking for gallery-dl binary...")

        bin_dir = './bin'
        log_dir = './bin/logs'
        os.makedirs(bin_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)

        dest_path = os.path.join(bin_dir, self.gallerydl_filename)

        if not os.path.isfile(dest_path):
            self.message_window.error(
                f"{self.gallerydl_filename} not found. Downloading...")
            url = f"https://github.com/mikf/gallery-dl/releases/download/v1.25.6/{self.gallerydl_filename}"
            self.message_window.warning(
                f"Downloading {self.gallerydl_filename}")
            if self.download_file(url, dest_path):
                self.message_window.success(
                    f"{self.gallerydl_filename} downloaded")
                self.signals.finished.emit()
            else:
                self.signals.error.emit()
        else:
            self.message_window.success(f"{self.gallerydl_filename} found.")
            self.signals.finished.emit()

    def download_file(self, url, dest_path):
        """
        Downloads a file from the given URL to the given destination path.
        """
        try:
            urllib.request.urlretrieve(url, dest_path)
            if platform.system() == 'Linux':
                os.chmod(dest_path, 0o755)
            return True
        except urllib.error.HTTPError as error:
            self.message_window.append(
                f"HTTP Error: {error.code} - {error.reason}")
        except urllib.error.URLError as error:
            self.message_window.append(f"URL Error: {error.reason}")

        return False

    def resource_path(self):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            # pylint: disable=protected-access
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath("./config_example")

        return base_path
