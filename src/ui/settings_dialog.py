from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlparse

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.services.browser import available_browser_options


def is_valid_feed_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class ColorButton(QPushButton):
    color_changed = Signal(str)

    def __init__(self, color_value: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.color_value = color_value
        self.clicked.connect(self._pick_color)
        self._sync_appearance()

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.color_value), self, self.title)
        if not chosen.isValid():
            return
        self.set_color(chosen.name())
        self.color_changed.emit(self.color_value)

    def set_color(self, value: str) -> None:
        self.color_value = value
        self._sync_appearance()

    def _sync_appearance(self) -> None:
        self.setText(self.color_value.upper())
        self.setStyleSheet(
            "QPushButton {"
            f"background-color: {self.color_value};"
            "border: 1px solid #38424d;"
            "border-radius: 4px;"
            "padding: 6px 10px;"
            "text-align: left;"
            "}"
        )


class FeedRow(QFrame):
    move_up_requested = Signal(object)
    move_down_requested = Signal(object)
    remove_requested = Signal(object)
    changed = Signal()

    def __init__(self, feed: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("feedRow")

        self.name_edit = QLineEdit(feed.get("name", ""))
        self.url_edit = QLineEdit(feed.get("url", ""))
        self.url_edit.setPlaceholderText("https://example.com/feed.xml")
        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(feed.get("enabled", True))

        self.move_up_button = QPushButton("Up")
        self.move_down_button = QPushButton("Down")
        self.remove_button = QPushButton("Remove")

        self.move_up_button.clicked.connect(lambda: self.move_up_requested.emit(self))
        self.move_down_button.clicked.connect(lambda: self.move_down_requested.emit(self))
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))

        for widget in (self.name_edit, self.url_edit):
            widget.textChanged.connect(self.changed.emit)
        self.enabled_checkbox.toggled.connect(self.changed.emit)

        actions = QVBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        actions.addWidget(self.move_up_button)
        actions.addWidget(self.move_down_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)

        fields = QGridLayout()
        fields.setContentsMargins(10, 10, 10, 10)
        fields.setHorizontalSpacing(10)
        fields.addWidget(QLabel("Name"), 0, 0)
        fields.addWidget(self.name_edit, 0, 1)
        fields.addWidget(self.enabled_checkbox, 0, 2)
        fields.addWidget(QLabel("URL"), 1, 0)
        fields.addWidget(self.url_edit, 1, 1, 1, 2)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addLayout(fields, 1)
        root.addLayout(actions)

        self.sync_validation_state()

    def sync_validation_state(self) -> None:
        url_value = self.url_edit.text().strip()
        valid = not url_value or is_valid_feed_url(url_value)
        self.url_edit.setStyleSheet("" if valid else "border: 1px solid #c94f4f;")
        self.url_edit.setToolTip("" if valid else "Feed URLs must start with http:// or https://")

    def to_dict(self) -> dict:
        return {
            "name": self.name_edit.text().strip() or "Unnamed Feed",
            "url": self.url_edit.text().strip(),
            "enabled": self.enabled_checkbox.isChecked(),
        }


class SettingsDialog(QDialog):
    preview_requested = Signal(dict)

    def __init__(self, settings: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("News Ticker Settings")
        self.resize(820, 700)
        self._settings = deepcopy(settings)
        self.feed_rows: list[FeedRow] = []
        self.monitor_options = self._build_monitor_options()
        self.browser_options = available_browser_options()

        root_layout = QVBoxLayout(self)

        preview_note = QLabel("Appearance changes preview live while this dialog is open.")
        preview_note.setStyleSheet("color: #7f8b99;")
        root_layout.addWidget(preview_note)

        general_box = QGroupBox("General")
        general_form = QFormLayout(general_box)

        self.position_combo = QComboBox()
        self.position_combo.addItems(["top", "bottom"])
        self.position_combo.setCurrentText(settings["position"])

        self.monitor_combo = QComboBox()
        for option in self.monitor_options:
            self.monitor_combo.addItem(option["label"], option["id"])
        self._set_current_monitor(settings.get("monitor_id", "primary"))

        self.height_spin = QSpinBox()
        self.height_spin.setRange(28, 100)
        self.height_spin.setValue(int(settings["height"]))

        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.2, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setValue(float(settings["opacity"]))

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(20, 300)
        self.speed_spin.setValue(int(settings["scroll_speed"]))

        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(0, 32)
        self.spacing_spin.setValue(int(settings.get("headline_spacing", 8)))

        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 28)
        self.font_spin.setValue(int(settings["font_size"]))

        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(1, 120)
        self.refresh_spin.setValue(int(settings["refresh_interval_minutes"]))

        self.max_headline_age_spin = QSpinBox()
        self.max_headline_age_spin.setRange(1, 168)
        self.max_headline_age_spin.setValue(int(settings.get("max_headline_age_hours", 5)))
        self.max_headline_age_spin.setSuffix(" hr")

        self.max_headlines_spin = QSpinBox()
        self.max_headlines_spin.setRange(10, 500)
        self.max_headlines_spin.setValue(int(settings.get("max_headlines", 40)))

        self.browser_combo = QComboBox()
        for option in self.browser_options:
            self.browser_combo.addItem(option["label"], option["id"])
        self._set_current_browser(settings.get("browser_preference", "system"))

        general_form.addRow("Monitor", self.monitor_combo)
        general_form.addRow("Position", self.position_combo)
        general_form.addRow("Bar Height", self.height_spin)
        general_form.addRow("Opacity", self.opacity_spin)
        general_form.addRow("Scroll Speed", self.speed_spin)
        general_form.addRow("Headline Gap", self.spacing_spin)
        general_form.addRow("Font Size", self.font_spin)
        general_form.addRow("Refresh Interval (min)", self.refresh_spin)
        general_form.addRow("Headline Max Age", self.max_headline_age_spin)
        general_form.addRow("Max Headlines", self.max_headlines_spin)
        general_form.addRow("Open Links In", self.browser_combo)

        toggles_box = QGroupBox("Behavior")
        toggles_layout = QVBoxLayout(toggles_box)
        self.show_source_checkbox = QCheckBox("Show source label")
        self.show_source_checkbox.setChecked(settings.get("show_source_label", True))
        self.pause_hover_checkbox = QCheckBox("Pause on hover")
        self.pause_hover_checkbox.setChecked(settings.get("pause_on_hover", True))
        self.always_on_top_checkbox = QCheckBox("Always on top")
        self.always_on_top_checkbox.setChecked(settings.get("always_on_top", True))
        self.reserve_space_checkbox = QCheckBox("Reserve screen space")
        self.reserve_space_checkbox.setChecked(settings.get("reserve_screen_space", True))
        self.startup_checkbox = QCheckBox("Launch on startup")
        self.startup_checkbox.setChecked(settings.get("launch_on_startup", False))

        toggles_layout.addWidget(self.show_source_checkbox)
        toggles_layout.addWidget(self.pause_hover_checkbox)
        toggles_layout.addWidget(self.always_on_top_checkbox)
        toggles_layout.addWidget(self.reserve_space_checkbox)
        toggles_layout.addWidget(self.startup_checkbox)

        pulse_box = QGroupBox("New Headline Pulse")
        pulse_form = QFormLayout(pulse_box)
        self.pulse_enabled_checkbox = QCheckBox("Enable pulse for new headlines")
        self.pulse_enabled_checkbox.setChecked(settings.get("new_headline_pulse_enabled", True))

        self.pulse_duration_spin = QSpinBox()
        self.pulse_duration_spin.setRange(1, 60)
        self.pulse_duration_spin.setValue(int(settings.get("new_headline_pulse_duration", 18)))
        self.pulse_duration_spin.setSuffix(" s")

        self.pulse_speed_spin = QSpinBox()
        self.pulse_speed_spin.setRange(2, 40)
        self.pulse_speed_spin.setValue(int(settings.get("new_headline_pulse_speed", 16)))

        self.pulse_strength_spin = QSpinBox()
        self.pulse_strength_spin.setRange(10, 120)
        self.pulse_strength_spin.setValue(int(settings.get("new_headline_pulse_strength", 54)))

        self.pulse_color_button = ColorButton(
            settings.get("new_headline_pulse_color", settings.get("accent_color", "#AA00FF")),
            "Select new headline pulse color",
            self,
        )

        pulse_form.addRow(self.pulse_enabled_checkbox)
        pulse_form.addRow("Duration", self.pulse_duration_spin)
        pulse_form.addRow("Pulse Speed", self.pulse_speed_spin)
        pulse_form.addRow("Glow Strength", self.pulse_strength_spin)
        pulse_form.addRow("Pulse Color", self.pulse_color_button)

        appearance_box = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_box)
        self.background_button = ColorButton(settings["background_color"], "Select ticker background color", self)
        self.text_button = ColorButton(settings["text_color"], "Select headline text color", self)
        self.accent_button = ColorButton(settings["accent_color"], "Select source badge color", self)
        self.separator_button = ColorButton(settings["separator_color"], "Select divider and border color", self)

        appearance_form.addRow("Ticker Background", self.background_button)
        appearance_form.addRow("Headline Text", self.text_button)
        appearance_form.addRow("Source Badges", self.accent_button)
        appearance_form.addRow("Dividers and Borders", self.separator_button)

        side_column = QVBoxLayout()
        side_column.addWidget(toggles_box)
        side_column.addWidget(pulse_box)
        side_column.addStretch(1)

        top_row = QHBoxLayout()
        top_row.addWidget(general_box, 1)
        top_row.addLayout(side_column, 1)
        top_row.addWidget(appearance_box, 1)

        feeds_box = QGroupBox("Feeds")
        feeds_layout = QVBoxLayout(feeds_box)
        feeds_hint = QLabel("Add, remove, or reorder feeds. Invalid URLs are highlighted.")
        feeds_hint.setStyleSheet("color: #7f8b99;")
        feeds_layout.addWidget(feeds_hint)

        self.feed_error_label = QLabel("")
        self.feed_error_label.setStyleSheet("color: #c94f4f;")
        self.feed_error_label.hide()
        feeds_layout.addWidget(self.feed_error_label)

        self.feed_container = QWidget()
        self.feed_layout = QVBoxLayout(self.feed_container)
        self.feed_layout.setContentsMargins(0, 0, 0, 0)
        self.feed_layout.setSpacing(10)
        self.feed_layout.addStretch(1)

        for feed in settings["feeds"]:
            self._add_feed_row(feed)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.feed_container)
        feeds_layout.addWidget(scroll, 1)

        feed_buttons = QHBoxLayout()
        add_feed_button = QPushButton("Add Feed")
        add_feed_button.clicked.connect(
            lambda: self._add_feed_row({"name": "", "url": "", "enabled": True})
        )
        feed_buttons.addWidget(add_feed_button)
        feed_buttons.addStretch(1)
        feeds_layout.addLayout(feed_buttons)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_with_validation)
        buttons.rejected.connect(self.reject)

        root_layout.addLayout(top_row)
        root_layout.addWidget(feeds_box, 1)
        root_layout.addWidget(buttons)

        self._connect_preview_inputs()
        self._sync_pulse_controls()
        self._emit_preview()

    def _connect_preview_inputs(self) -> None:
        preview_sources = [
            self.position_combo.currentTextChanged,
            self.monitor_combo.currentIndexChanged,
            self.height_spin.valueChanged,
            self.opacity_spin.valueChanged,
            self.speed_spin.valueChanged,
            self.spacing_spin.valueChanged,
            self.font_spin.valueChanged,
            self.show_source_checkbox.toggled,
            self.pause_hover_checkbox.toggled,
            self.always_on_top_checkbox.toggled,
            self.reserve_space_checkbox.toggled,
            self.pulse_enabled_checkbox.toggled,
            self.pulse_duration_spin.valueChanged,
            self.pulse_speed_spin.valueChanged,
            self.pulse_strength_spin.valueChanged,
            self.pulse_color_button.color_changed,
            self.background_button.color_changed,
            self.text_button.color_changed,
            self.accent_button.color_changed,
            self.separator_button.color_changed,
        ]
        for signal in preview_sources:
            signal.connect(self._emit_preview)
        self.pulse_enabled_checkbox.toggled.connect(self._sync_pulse_controls)

    def _emit_preview(self, *_args: object) -> None:
        self.preview_requested.emit(self.get_preview_settings())

    def _sync_pulse_controls(self) -> None:
        enabled = self.pulse_enabled_checkbox.isChecked()
        self.pulse_duration_spin.setEnabled(enabled)
        self.pulse_speed_spin.setEnabled(enabled)
        self.pulse_strength_spin.setEnabled(enabled)

    def _build_monitor_options(self) -> list[dict]:
        options = [{"id": "primary", "label": "Primary Display"}]
        for index, screen in enumerate(QGuiApplication.screens(), start=1):
            geometry = screen.geometry()
            screen_name = screen.name() or f"Display {index}"
            options.append(
                {
                    "id": monitor_id_for_screen(screen),
                    "label": (
                        f"{index}. {screen_name} "
                        f"({geometry.width()}x{geometry.height()} at {geometry.x()},{geometry.y()})"
                    ),
                }
            )
        return options

    def _set_current_monitor(self, monitor_id: str) -> None:
        for index in range(self.monitor_combo.count()):
            if self.monitor_combo.itemData(index) == monitor_id:
                self.monitor_combo.setCurrentIndex(index)
                return
        self.monitor_combo.setCurrentIndex(0)

    def _add_feed_row(self, feed: dict) -> None:
        row = FeedRow(feed, self)
        row.move_up_requested.connect(self._move_feed_up)
        row.move_down_requested.connect(self._move_feed_down)
        row.remove_requested.connect(self._remove_feed_row)
        row.changed.connect(self._handle_feed_row_changed)
        self.feed_rows.append(row)
        self.feed_layout.insertWidget(self.feed_layout.count() - 1, row)
        self._sync_feed_row_controls()
        self._handle_feed_row_changed()

    def _set_current_browser(self, browser_id: str) -> None:
        for index in range(self.browser_combo.count()):
            if self.browser_combo.itemData(index) == browser_id:
                self.browser_combo.setCurrentIndex(index)
                return
        self.browser_combo.setCurrentIndex(0)

    def _remove_feed_row(self, row: FeedRow) -> None:
        if row not in self.feed_rows:
            return
        self.feed_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._sync_feed_row_controls()
        self._handle_feed_row_changed()

    def _move_feed_up(self, row: FeedRow) -> None:
        index = self.feed_rows.index(row)
        if index == 0:
            return
        self.feed_rows[index - 1], self.feed_rows[index] = self.feed_rows[index], self.feed_rows[index - 1]
        self._rebuild_feed_layout()

    def _move_feed_down(self, row: FeedRow) -> None:
        index = self.feed_rows.index(row)
        if index >= len(self.feed_rows) - 1:
            return
        self.feed_rows[index + 1], self.feed_rows[index] = self.feed_rows[index], self.feed_rows[index + 1]
        self._rebuild_feed_layout()

    def _rebuild_feed_layout(self) -> None:
        for row in self.feed_rows:
            self.feed_layout.removeWidget(row)
        for row in self.feed_rows:
            self.feed_layout.insertWidget(self.feed_layout.count() - 1, row)
        self._sync_feed_row_controls()
        self._handle_feed_row_changed()

    def _sync_feed_row_controls(self) -> None:
        for index, row in enumerate(self.feed_rows):
            row.move_up_button.setEnabled(index > 0)
            row.move_down_button.setEnabled(index < len(self.feed_rows) - 1)

    def _handle_feed_row_changed(self) -> None:
        invalid_count = 0
        for row in self.feed_rows:
            row.sync_validation_state()
            if row.url_edit.text().strip() and not is_valid_feed_url(row.url_edit.text()):
                invalid_count += 1

        if invalid_count:
            self.feed_error_label.setText(f"{invalid_count} feed URL(s) need correction before saving.")
            self.feed_error_label.show()
        else:
            self.feed_error_label.hide()

    def _accept_with_validation(self) -> None:
        invalid_rows = [
            row for row in self.feed_rows if row.url_edit.text().strip() and not is_valid_feed_url(row.url_edit.text())
        ]
        if invalid_rows:
            QMessageBox.warning(
                self,
                "Invalid Feed URLs",
                "One or more feed URLs are invalid. Feed URLs must start with http:// or https://",
            )
            return

        self.accept()

    def get_preview_settings(self) -> dict:
        preview = deepcopy(self._settings)
        preview["monitor_id"] = self.monitor_combo.currentData()
        preview["position"] = self.position_combo.currentText()
        preview["height"] = self.height_spin.value()
        preview["opacity"] = self.opacity_spin.value()
        preview["scroll_speed"] = self.speed_spin.value()
        preview["headline_spacing"] = self.spacing_spin.value()
        preview["font_size"] = self.font_spin.value()
        preview["browser_preference"] = self.browser_combo.currentData()
        preview["show_source_label"] = self.show_source_checkbox.isChecked()
        preview["pause_on_hover"] = self.pause_hover_checkbox.isChecked()
        preview["always_on_top"] = self.always_on_top_checkbox.isChecked()
        preview["reserve_screen_space"] = self.reserve_space_checkbox.isChecked()
        preview["new_headline_pulse_enabled"] = self.pulse_enabled_checkbox.isChecked()
        preview["new_headline_pulse_duration"] = self.pulse_duration_spin.value()
        preview["new_headline_pulse_speed"] = self.pulse_speed_spin.value()
        preview["new_headline_pulse_strength"] = self.pulse_strength_spin.value()
        preview["new_headline_pulse_color"] = self.pulse_color_button.color_value
        preview["background_color"] = self.background_button.color_value
        preview["text_color"] = self.text_button.color_value
        preview["accent_color"] = self.accent_button.color_value
        preview["separator_color"] = self.separator_button.color_value
        return preview

    def get_settings(self) -> dict:
        self._settings = self.get_preview_settings()
        self._settings["refresh_interval_minutes"] = self.refresh_spin.value()
        self._settings["max_headline_age_hours"] = self.max_headline_age_spin.value()
        self._settings["max_headlines"] = self.max_headlines_spin.value()
        self._settings["launch_on_startup"] = self.startup_checkbox.isChecked()
        self._settings["feeds"] = [feed for feed in (row.to_dict() for row in self.feed_rows) if feed["url"]]
        return self._settings


def monitor_id_for_screen(screen) -> str:
    geometry = screen.geometry()
    name = screen.name() or "display"
    return f"{name}|{geometry.x()}|{geometry.y()}|{geometry.width()}|{geometry.height()}"
