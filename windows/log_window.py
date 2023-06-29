from PyQt6.QtWidgets import QTextEdit
from PyQt6 import QtGui


class LogWindow(QTextEdit):
    def __init__(self):
        super().__init__()

        self.setReadOnly(True)
        font = QtGui.QFont("Courier New", 10)
        self.setFont(font)
        self.setTextColor(QtGui.QColor("green"))
        self.setStyleSheet("background-color: black;")

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        clearAction = menu.addAction("Clear")
        clearAction.triggered.connect(self.clear)
        menu.exec(event.globalPos())
