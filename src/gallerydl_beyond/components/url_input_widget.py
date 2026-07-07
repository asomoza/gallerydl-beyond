from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class UrlInputWidget(QWidget):
    url_submitted = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Paste URL and press Enter")
        self._input.returnPressed.connect(self._emit_url)

        self._add_btn = QPushButton("Add")
        self._add_btn.clicked.connect(self._emit_url)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._input, 1)
        layout.addWidget(self._add_btn, 0)

        self.setFocusProxy(self._input)

    def set_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._input.selectAll()

    def focus_input(self) -> None:
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)

    def is_input_focused(self) -> bool:
        return self._input.hasFocus()

    def paste_from_clipboard(self) -> None:
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._input.paste()

    def submit_current(self) -> None:
        self._emit_url()

    def text(self) -> str:
        return self._input.text()

    def clear(self) -> None:
        self._input.clear()

    def _emit_url(self) -> None:
        url = self._input.text().strip()
        if not url:
            return
        self.url_submitted.emit(url)
