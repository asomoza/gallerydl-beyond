from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialogButtonBox, QLabel, QPushButton

from gallerydl_beyond.common.base_dialog import BaseDialog


UrlExistsAction = Literal["check_new", "force", "cancel"]


@dataclass(frozen=True)
class UrlExistsResult:
    action: UrlExistsAction


class UrlExistsDialog(BaseDialog):
    def __init__(self, show_error: callable, url: str):
        super().__init__("URL already exists", show_error)
        self._url = url
        self._result: UrlExistsResult = UrlExistsResult(action="cancel")

        self._build_ui()

    @property
    def result(self) -> UrlExistsResult:
        return self._result

    def _build_ui(self) -> None:
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        title = QLabel("This URL is already in the database")
        title.setStyleSheet("font-weight: 600;")
        self.main_layout.addWidget(title)

        url_label = QLabel(self._url)
        url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        url_label.setWordWrap(True)
        self.main_layout.addWidget(url_label)

        hint = QLabel("Choose what to do:")
        hint.setStyleSheet("color: #8a8a8a;")
        self.main_layout.addWidget(hint)

        buttons = QDialogButtonBox()

        check_new_btn = QPushButton("Check New")
        check_new_btn.setToolTip("Use archive to download only new files")
        check_new_btn.clicked.connect(lambda: self._accept("check_new"))

        force_btn = QPushButton("Force Re-download")
        force_btn.setToolTip("Re-run gallery-dl with --no-skip")
        force_btn.clicked.connect(lambda: self._accept("force"))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        buttons.addButton(check_new_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(force_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)

        self.main_layout.addWidget(buttons, alignment=Qt.AlignmentFlag.AlignRight)

    def _accept(self, action: UrlExistsAction) -> None:
        self._result = UrlExistsResult(action=action)
        self.accept()
