from __future__ import annotations

from datetime import timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.feeds.models import FeedDiagnostic


class FeedDiagnosticsDialog(QDialog):
    def __init__(self, diagnostics: list[FeedDiagnostic], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Feed Diagnostics")
        self.setModal(False)
        self.resize(980, 560)

        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["When", "Feed", "Result", "Stage", "Items", "HTTP", "Time"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._sync_details)

        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.close)
        close_button.setAutoDefault(False)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.table, stretch=3)
        layout.addWidget(self.details, stretch=2)
        layout.addLayout(button_row)

        self._diagnostics: list[FeedDiagnostic] = []
        self.set_diagnostics(diagnostics)

    def set_diagnostics(self, diagnostics: list[FeedDiagnostic]) -> None:
        self._diagnostics = list(diagnostics)
        self.table.setRowCount(len(self._diagnostics))
        for row, diagnostic in enumerate(self._diagnostics):
            values = [
                diagnostic.fetched_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                diagnostic.feed_name,
                diagnostic.result.upper(),
                diagnostic.stage,
                str(diagnostic.item_count),
                str(diagnostic.http_status or ""),
                f"{diagnostic.elapsed_ms} ms",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

        self.table.resizeColumnsToContents()
        if self._diagnostics:
            self.table.selectRow(0)
        else:
            self.details.setPlainText("No feed diagnostics recorded yet.")

    def _sync_details(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._diagnostics):
            self.details.clear()
            return

        diagnostic = self._diagnostics[row]
        lines = [
            f"Feed: {diagnostic.feed_name}",
            f"Requested URL: {diagnostic.feed_url}",
            f"Final URL: {diagnostic.final_url or diagnostic.feed_url}",
            f"When: {diagnostic.fetched_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Result: {diagnostic.result}",
            f"Stage: {diagnostic.stage}",
            f"Items: {diagnostic.item_count}",
            f"HTTP status: {diagnostic.http_status if diagnostic.http_status is not None else 'n/a'}",
            f"Content type: {diagnostic.content_type or 'n/a'}",
            f"Bytes read: {diagnostic.bytes_read}",
            f"Elapsed: {diagnostic.elapsed_ms} ms",
            f"Root tag: {diagnostic.root_tag or 'n/a'}",
            f"Exception: {diagnostic.exception_type or 'n/a'}",
            f"Error: {diagnostic.error_message or 'n/a'}",
        ]
        if diagnostic.payload_preview:
            lines.extend(["", "Payload preview:", diagnostic.payload_preview])
        self.details.setPlainText("\n".join(lines))
