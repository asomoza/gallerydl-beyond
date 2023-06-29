import os
import subprocess
import platform

from PyQt6.QtCore import pyqtSignal, QThread


class DownloadThread(QThread):
    """
    A subclass of `QThread` that runs the gallery-dl command in a separate thread.

    :param url: The URL to download images from.
    :type url: str
    """
    output = pyqtSignal(str)

    def __init__(self, url_id, url, gallerydl_bin):
        super().__init__()
        self.url_id = url_id
        self.url = url
        self.stop_requested = False
        self.process = None
        self.gallerydl_bin = gallerydl_bin

    def run(self):
        """
        Runs the gallery-dl command in a separate thread.

        The output from the gallery-dl command is emitted as a signal using the `output` signal.
        """

        args = [f"./bin/{self.gallerydl_bin}", self.url]

        if os.path.isfile("config.json"):
            args.extend(['-c', "config.json"])

        # Call the gallery-dl command with the URL as an argument
        if platform.system() == 'Windows':
            self.process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            self.process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Emit the output from the gallery-dl command as a signal
        while self.process.poll() is None and not self.stop_requested:
            output = self.process.stdout.readline().decode("utf-8")
            if output:
                self.output.emit(output)

    def stop(self):
        self.stop_requested = True
        if self.process is not None:
            self.process.terminate()
