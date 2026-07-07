from PyQt6.QtWidgets import QApplication

from gallerydl_beyond.Application.main_window import MainWindow


class GalleryDLBeyondApplication(QApplication):
    def __init__(self, *args, **kwargs):
        super(GalleryDLBeyondApplication, self).__init__(*args, **kwargs)

        self.window = MainWindow()
        self.window.show()
