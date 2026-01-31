from PyQt6.QtWidgets import QLabel

from gallerydl_beyond.common.base_dialog import BaseDialog


class DatabaseDialog(BaseDialog):
    def __init__(self, *args):
        super().__init__("Database Manager", *args)

        self.init_ui()

    def init_ui(self):
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)

        label = QLabel("Database")
        self.main_layout.addWidget(label)
