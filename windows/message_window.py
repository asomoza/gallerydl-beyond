from PyQt6.QtWidgets import QTextEdit
from PyQt6 import QtGui

white_color = QtGui.QColor(227, 226, 224)
yellow_color = QtGui.QColor(214, 187, 103)
green_color = QtGui.QColor(29, 218, 153)
red_color = QtGui.QColor(255, 0, 0)


class MessageWindow(QTextEdit):
    def __init__(self):
        super().__init__()

        self.setReadOnly(True)
        font = QtGui.QFont("Courier New", 10)
        self.setFont(font)
        self.setTextColor(QtGui.QColor("white"))
        self.setStyleSheet("background-color: black;")

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        clearAction = menu.addAction("Clear")
        clearAction.triggered.connect(self.clear)
        menu.exec(event.globalPos())

    def add_message(self, message):
        self.setTextColor(white_color)
        self.append(message)

    def warning(self, message):
        self.setTextColor(yellow_color)
        self.append(message)

    def success(self, message):
        self.setTextColor(green_color)
        self.append(message)

    def error(self, message):
        self.setTextColor(red_color)
        self.append(message)
