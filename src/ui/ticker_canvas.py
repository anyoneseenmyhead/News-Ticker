from __future__ import annotations

from dataclasses import dataclass
from math import sin
from time import perf_counter

from PySide6.QtCore import QPoint, QRectF, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QCursor, QFont, QFontMetrics, QLinearGradient, QMouseEvent, QPainter, QPaintEvent, QPainterPath, QPen
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from src.feeds.models import HeadlineItem
from src.services.browser import launch_url
from src.utils.text import normalize_headline_key


DEFAULT_ITEM_GAP = 8.0
DEFAULT_WRAP_GAP = 10.0
EDGE_FADE_WIDTH = 26.0
DEFAULT_NEW_ITEM_HIGHLIGHT_DURATION = 18.0
DEFAULT_NEW_ITEM_PULSE_SPEED = 16.0
DEFAULT_NEW_ITEM_PULSE_STRENGTH = 54.0


@dataclass(slots=True)
class RenderedItem:
    item: HeadlineItem
    rect: QRectF
    badge_rect: QRectF
    title_rect: QRectF
    separator_x: float
    badge_text: str


class TickerCanvas(QWidget):
    status_changed = Signal(str)

    def __init__(self, settings: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.items: list[HeadlineItem] = []
        self.staged_items: list[HeadlineItem] = []
        self.rendered_items: list[RenderedItem] = []
        self.offset = 0.0
        self.content_width = 0.0
        self.paused = False
        self.manual_paused = False
        self.hover_paused = False
        self.hovered_guid: str | None = None
        self.last_tick = perf_counter()
        self._layout_key: tuple | None = None
        self.highlight_deadlines: dict[str, float] = {}
        self.pending_highlight_keys: set[str] = set()
        self.status_kind = "idle"
        self.status_message = ""

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_frame)
        self.timer.start(16)

    def sizeHint(self) -> QSize:
        return QSize(1200, int(self.settings["height"]))

    def apply_settings(self, settings: dict) -> None:
        self.settings = settings
        font = QFont("Segoe UI", int(settings["font_size"]))
        self.setFont(font)
        self._layout_key = None
        self.update()

    def set_headlines(self, items: list[HeadlineItem], highlighted_keys: list[str] | None = None) -> None:
        previous_width = self.content_width + self._wrap_gap() if self.content_width > 0 else 0.0
        self.items, self.staged_items = self._partition_display_items(items)
        self.hovered_guid = None
        self._layout_key = None
        active_keys = {self._item_key(item) for item in items}
        self.highlight_deadlines = {
            key: deadline
            for key, deadline in self.highlight_deadlines.items()
            if key in active_keys and deadline > perf_counter()
        }
        self.pending_highlight_keys = {
            key for key in self.pending_highlight_keys if key in active_keys
        }
        if highlighted_keys:
            for key in highlighted_keys:
                if key in active_keys:
                    self.pending_highlight_keys.add(key)
        self._rebuild_layout()
        if previous_width <= 0 or not self.items:
            self.offset = 0.0
        else:
            wrap_width = self.content_width + self._wrap_gap()
            self.offset = self.offset % wrap_width if wrap_width > 0 else 0.0
        self._release_staged_items_if_ready()
        self.update()

    def set_manual_paused(self, paused: bool) -> None:
        self.manual_paused = paused
        self._sync_pause_state()

    def set_hover_paused(self, paused: bool) -> None:
        self.hover_paused = paused
        self._sync_pause_state()

    def _sync_pause_state(self) -> None:
        self.paused = self.manual_paused or self.hover_paused
        self.update()

    def set_status_state(self, kind: str, message: str) -> None:
        self.status_kind = kind
        self.status_message = message
        self.update()

    def advance_frame(self) -> None:
        now = perf_counter()
        delta = now - self.last_tick
        self.last_tick = now

        if self.paused or self.content_width <= self.width():
            self._release_staged_items_if_ready()
            self.update()
            return

        speed = float(self.settings["scroll_speed"])
        self.offset += speed * delta
        wrap_width = self.content_width + self._wrap_gap()
        if self.offset >= wrap_width:
            self.offset = 0.0
        self._release_staged_items_if_ready()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            background = QColor(self.settings["background_color"])
            text_color = QColor(self.settings["text_color"])
            accent_color = QColor(self.settings["accent_color"])
            separator_color = QColor(self.settings["separator_color"])
            pulse_color = QColor(
                self.settings.get(
                    "new_headline_pulse_color",
                    self.settings.get("accent_color", "#AA00FF"),
                )
            )

            painter.fillRect(self.rect(), background)
            self._draw_frame_lines(painter, accent_color, separator_color)

            if not self.items:
                painter.setPen(text_color)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No headlines available")
                return

            self._rebuild_layout()
            metrics = QFontMetrics(self.font())
            baseline_y = int((self.height() + metrics.ascent() - metrics.descent()) / 2)
            frame_now = perf_counter()
            content_layer = QPixmap(self.size())
            content_layer.fill(Qt.GlobalColor.transparent)
            content_painter = QPainter(content_layer)
            content_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setFont(self.font())
            content_painter.setFont(self.font())

            try:
                base_x = -self.offset
                for cycle in range(2):
                    x = base_x + (cycle * (self.content_width + self._wrap_gap()))
                    for rendered in self.rendered_items:
                        draw_rect = translated_rect(rendered.rect, x)
                        if draw_rect.right() < 0 or draw_rect.left() > self.width():
                            continue

                        hovered = rendered.item.guid == self.hovered_guid
                        badge_rect = translated_rect(rendered.badge_rect, x)
                        title_rect = translated_rect(rendered.title_rect, x)
                        separator_x = rendered.separator_x + x
                        item_key = self._item_key(rendered.item)
                        self._activate_highlight_if_visible(item_key, draw_rect, frame_now)
                        highlight_alpha = self._highlight_alpha(rendered.item, frame_now)

                        if highlight_alpha > 0:
                            self._draw_new_item_highlight(
                                content_painter,
                                draw_rect,
                                pulse_color,
                                highlight_alpha,
                            )

                        if hovered:
                            hover_fill = QColor(text_color)
                            hover_fill.setAlpha(18)
                            content_painter.fillRect(draw_rect.adjusted(0, 5, 0, -5), hover_fill)

                        if self.settings.get("show_source_label", True):
                            self._draw_badge(
                                content_painter,
                                badge_rect,
                                rendered.badge_text,
                                baseline_y,
                                accent_color,
                                background,
                                hovered,
                            )

                        content_painter.setPen(text_color if not hovered else lighten(text_color, 12))
                        content_painter.drawText(int(title_rect.x()), baseline_y, rendered.item.title)

                        self._draw_separator(content_painter, separator_x, separator_color)
            finally:
                content_painter.end()

            self._apply_edge_fade_mask(content_layer)
            painter.drawPixmap(0, 0, content_layer)
            self._draw_status_indicator(painter, background, text_color, accent_color)
        finally:
            painter.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        hovered = self._item_at(event.position().toPoint())
        if hovered is None:
            self.hovered_guid = None
            self.unsetCursor()
            if self.settings.get("pause_on_hover") and self.underMouse():
                self.set_hover_paused(False)
            self.update()
            return

        self.hovered_guid = hovered.guid
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if self.settings.get("pause_on_hover"):
            self.set_hover_paused(True)
        self.status_changed.emit(f"{hovered.source_name}: {hovered.title}")
        self.update()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        del event
        self.hovered_guid = None
        self.unsetCursor()
        if self.settings.get("pause_on_hover"):
            self.set_hover_paused(False)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        item = self._item_at(event.position().toPoint())
        if item is None:
            return
        launch_url(item.url, str(self.settings.get("browser_preference", "system")))

    def _item_at(self, point: QPoint) -> HeadlineItem | None:
        if not self.rendered_items:
            return None

        check_points = [
            point.x() + self.offset,
            point.x() + self.offset - (self.content_width + self._wrap_gap()),
        ]
        for candidate_x in check_points:
            local_point = QPoint(int(candidate_x), point.y())
            for rendered in self.rendered_items:
                if rendered.rect.contains(local_point):
                    return rendered.item
        return None

    def _rebuild_layout(self) -> None:
        layout_key = (
            len(self.items),
            tuple(self._item_key(item) for item in self.items),
            self.width(),
            self.height(),
            self.font().pointSize(),
            int(self.settings.get("headline_spacing", DEFAULT_ITEM_GAP)),
            bool(self.settings.get("show_source_label", True)),
        )
        if self._layout_key == layout_key:
            return

        metrics = QFontMetrics(self.font())
        x = 12.0
        item_height = float(self.height())
        item_gap = self._item_gap()
        separator_lead = item_gap * 0.5
        separator_trail = item_gap * 0.5
        badge_padding_x = 10.0
        badge_height = max(18.0, item_height - 16.0)
        rendered: list[RenderedItem] = []

        for item in self.items:
            badge_text = item.source_name.upper()
            badge_width = (
                metrics.horizontalAdvance(badge_text) + (badge_padding_x * 2.0)
                if self.settings.get("show_source_label", True)
                else 0.0
            )
            badge_rect = QRectF(x, (item_height - badge_height) / 2.0, badge_width, badge_height)

            title_x = badge_rect.right() + 8.0 if badge_width else x
            title_advance = float(metrics.horizontalAdvance(item.title))
            title_rect = QRectF(title_x, 0.0, title_advance, item_height)
            tight_bounds = metrics.tightBoundingRect(item.title)
            title_visual_right = title_x + tight_bounds.x() + tight_bounds.width()
            separator_x = title_visual_right + separator_lead
            total_width = (separator_x - x) + separator_trail

            rendered.append(
                RenderedItem(
                    item=item,
                    rect=QRectF(x, 0.0, total_width, item_height),
                    badge_rect=badge_rect,
                    title_rect=title_rect,
                    separator_x=separator_x,
                    badge_text=badge_text,
                )
            )
            x += total_width

        self.rendered_items = rendered
        self.content_width = x
        self._layout_key = layout_key

    def _partition_display_items(
        self, items: list[HeadlineItem]
    ) -> tuple[list[HeadlineItem], list[HeadlineItem]]:
        incoming_by_key = {self._item_key(item): item for item in items}
        previous_visible_keys = {self._item_key(item) for item in self.items}
        previous_order = self.items + self.staged_items
        previous_order_keys = {self._item_key(item) for item in previous_order}

        ordered_items: list[HeadlineItem] = []
        seen_keys: set[str] = set()

        for item in previous_order:
            key = self._item_key(item)
            incoming_item = incoming_by_key.get(key)
            if incoming_item is None or key in seen_keys:
                continue
            ordered_items.append(incoming_item)
            seen_keys.add(key)

        for item in items:
            key = self._item_key(item)
            if key in seen_keys:
                continue
            ordered_items.append(item)
            seen_keys.add(key)

        visible_items: list[HeadlineItem] = []
        staged_items: list[HeadlineItem] = []
        for item in ordered_items:
            key = self._item_key(item)
            if key in previous_visible_keys:
                visible_items.append(item)
                continue
            if key in previous_order_keys:
                staged_items.append(item)
                continue
            staged_items.append(item)

        if not visible_items and staged_items:
            return staged_items, []

        return visible_items, staged_items

    def _release_staged_items_if_ready(self) -> None:
        if not self.staged_items:
            return
        if not self.items:
            self.items = self.staged_items
            self.staged_items = []
            self._layout_key = None
            self._rebuild_layout()
            return
        if not self.rendered_items:
            self._rebuild_layout()
            if not self.rendered_items:
                return

        last_visible_rect = self.rendered_items[-1].rect
        if last_visible_rect.right() - self.offset > self.width():
            return

        self.items.extend(self.staged_items)
        self.staged_items = []
        self._layout_key = None
        self._rebuild_layout()

    def _item_gap(self) -> float:
        return float(self.settings.get("headline_spacing", DEFAULT_ITEM_GAP))

    def _wrap_gap(self) -> float:
        return max(2.0, DEFAULT_WRAP_GAP + (self._item_gap() * 0.5))

    def _draw_frame_lines(self, painter: QPainter, accent_color: QColor, separator_color: QColor) -> None:
        top_line = lighten(accent_color, 10)
        top_line.setAlpha(120)
        bottom_line = QColor(separator_color)
        bottom_line.setAlpha(110)

        painter.setPen(QPen(top_line, 1))
        painter.drawLine(0, 0, self.width(), 0)
        painter.setPen(QPen(bottom_line, 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    def _draw_badge(
        self,
        painter: QPainter,
        rect: QRectF,
        text: str,
        baseline_y: int,
        accent_color: QColor,
        background: QColor,
        hovered: bool,
    ) -> None:
        badge_fill = QColor(accent_color if not hovered else accent_color.lighter(108))
        badge_fill.setAlpha(236)
        badge_stroke = QColor(accent_color.darker(120))
        badge_stroke.setAlpha(255)

        path = QPainterPath()
        path.addRoundedRect(rect, 7.0, 7.0)
        painter.fillPath(path, badge_fill)
        painter.setPen(QPen(badge_stroke, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        if badge_fill.lightness() >= 170:
            badge_text_color = QColor("#1B1F23")
        else:
            badge_text_color = QColor("#F5F7FA")
        painter.setPen(badge_text_color)
        text_width = painter.fontMetrics().horizontalAdvance(text)
        text_x = int(rect.x() + (rect.width() - text_width) / 2.0)
        painter.drawText(text_x, baseline_y, text)

    def _draw_separator(self, painter: QPainter, x: float, separator_color: QColor) -> None:
        line_color = QColor(separator_color)
        line_color.setAlpha(90)
        dot_color = QColor(separator_color)
        dot_color.setAlpha(170)

        center_y = self.height() / 2.0
        painter.setPen(QPen(line_color, 1))
        painter.drawLine(int(x - 6), int(center_y), int(x + 6), int(center_y))
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(x - 2.0, center_y - 2.0, 4.0, 4.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _apply_edge_fade_mask(self, content_layer: QPixmap) -> None:
        mask_painter = QPainter(content_layer)
        try:
            mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)

            mask_painter.fillRect(self.rect(), QColor(0, 0, 0, 255))

            left = QLinearGradient(0.0, 0.0, EDGE_FADE_WIDTH, 0.0)
            left.setColorAt(0.0, QColor(0, 0, 0, 0))
            left.setColorAt(1.0, QColor(0, 0, 0, 255))
            mask_painter.fillRect(QRectF(0.0, 0.0, EDGE_FADE_WIDTH, float(self.height())), left)

            right = QLinearGradient(float(self.width()) - EDGE_FADE_WIDTH, 0.0, float(self.width()), 0.0)
            right.setColorAt(0.0, QColor(0, 0, 0, 255))
            right.setColorAt(1.0, QColor(0, 0, 0, 0))
            mask_painter.fillRect(
                QRectF(float(self.width()) - EDGE_FADE_WIDTH, 0.0, EDGE_FADE_WIDTH, float(self.height())),
                right,
            )
        finally:
            mask_painter.end()

    def _draw_status_indicator(
        self,
        painter: QPainter,
        background: QColor,
        text_color: QColor,
        accent_color: QColor,
    ) -> None:
        if self.status_kind in {"idle", "ok"}:
            return

        metrics = painter.fontMetrics()
        label = {
            "loading": "Refreshing",
            "warning": "Feed Issue",
            "error": "Refresh Failed",
            "empty": "No Feeds",
        }.get(self.status_kind, "Status")

        indicator_color = {
            "loading": accent_color,
            "warning": QColor("#E6A23C"),
            "error": QColor("#D64545"),
            "empty": QColor("#7F8B99"),
        }.get(self.status_kind, accent_color)

        pill_height = max(18.0, float(self.height()) - 18.0)
        pill_width = metrics.horizontalAdvance(label) + 24
        pill_rect = QRectF(float(self.width()) - pill_width - 12.0, (self.height() - pill_height) / 2.0, pill_width, pill_height)

        fill = QColor(indicator_color)
        fill.setAlpha(52)
        stroke = QColor(indicator_color)
        stroke.setAlpha(160)

        path = QPainterPath()
        path.addRoundedRect(pill_rect, 8.0, 8.0)
        painter.fillPath(path, fill)
        painter.setPen(QPen(stroke, 1))
        painter.drawPath(path)

        dot_rect = QRectF(pill_rect.x() + 8.0, pill_rect.y() + (pill_rect.height() - 6.0) / 2.0, 6.0, 6.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(stroke)
        painter.drawEllipse(dot_rect)

        label_color = QColor(text_color if text_color.lightness() > 150 else QColor("#F5F7FA"))
        painter.setPen(label_color)
        text_x = int(dot_rect.right() + 8.0)
        baseline_y = int((self.height() + metrics.ascent() - metrics.descent()) / 2)
        painter.drawText(text_x, baseline_y, label)

    def _draw_new_item_highlight(
        self,
        painter: QPainter,
        rect: QRectF,
        accent_color: QColor,
        alpha: int,
    ) -> None:
        glow_rect = rect.adjusted(-2.0, 3.0, 2.0, -3.0)
        fill = QColor(accent_color)
        fill.setAlpha(alpha)
        stroke = QColor(lighten(accent_color, 18))
        stroke.setAlpha(min(255, int(alpha * 2.2)))

        path = QPainterPath()
        path.addRoundedRect(glow_rect, 8.0, 8.0)
        painter.fillPath(path, fill)
        painter.setPen(QPen(stroke, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _activate_highlight_if_visible(self, item_key: str, rect: QRectF, now: float) -> None:
        if not self.settings.get("new_headline_pulse_enabled", True):
            self.pending_highlight_keys.discard(item_key)
            return
        if item_key not in self.pending_highlight_keys:
            return
        if rect.right() < 0 or rect.left() > self.width():
            return
        self.pending_highlight_keys.discard(item_key)
        self.highlight_deadlines[item_key] = now + self._highlight_duration()

    def _highlight_alpha(self, item: HeadlineItem, now: float) -> int:
        if not self.settings.get("new_headline_pulse_enabled", True):
            self.highlight_deadlines.pop(self._item_key(item), None)
            return 0

        deadline = self.highlight_deadlines.get(self._item_key(item))
        if deadline is None:
            return 0
        remaining = deadline - now
        if remaining <= 0:
            self.highlight_deadlines.pop(self._item_key(item), None)
            return 0

        duration = self._highlight_duration()
        progress = 1.0 - (remaining / duration)
        fade = min(1.0, remaining / 4.5)
        pulse_speed = float(self.settings.get("new_headline_pulse_speed", DEFAULT_NEW_ITEM_PULSE_SPEED))
        pulse_strength = float(self.settings.get("new_headline_pulse_strength", DEFAULT_NEW_ITEM_PULSE_STRENGTH))
        pulse = 0.65 + (0.55 * ((sin(progress * pulse_speed) + 1.0) / 2.0))
        return int(28 + (pulse_strength * pulse * fade))

    def _highlight_duration(self) -> float:
        return max(
            0.1,
            float(self.settings.get("new_headline_pulse_duration", DEFAULT_NEW_ITEM_HIGHLIGHT_DURATION)),
        )

    def _item_key(self, item: HeadlineItem) -> str:
        return item.guid.strip() or normalize_headline_key(item.title, item.url)


def translated_rect(rect: QRectF, dx: float) -> QRectF:
    return QRectF(rect.x() + dx, rect.y(), rect.width(), rect.height())


def lighten(color: QColor, amount: int) -> QColor:
    return color.lighter(100 + amount)
