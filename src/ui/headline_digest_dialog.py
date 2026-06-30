from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPlainTextEdit, QPushButton, QVBoxLayout

from src.feeds.models import HeadlineItem
from src.utils.text import format_headline_digest


class HeadlineDigestDialog(QDialog):
    def __init__(self, items: list[HeadlineItem], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Headline Digest")
        self.setModal(False)
        self.resize(760, 520)

        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.text.setPlainText(format_headline_digest(items))

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.close)
        close_button.setAutoDefault(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.text)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
