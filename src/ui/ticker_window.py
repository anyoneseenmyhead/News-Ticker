from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QMenu, QVBoxLayout, QWidget

from src.feeds.models import HeadlineItem
from src.services.appbar import WindowsAppBar
from src.ui.ticker_canvas import TickerCanvas


class TickerWindow(QWidget):
    request_open_settings = Signal()
    request_refresh = Signal()
    request_show_digest = Signal()
    request_show_feed_diagnostics = Signal()

    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.drag_origin: QPoint | None = None
        self.appbar = WindowsAppBar()
        self._reserved_monitor_id: str | None = None
        self._reserved_edge: str | None = None
        self._reserved_enabled = False

        self.setWindowTitle("News Ticker")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.canvas = TickerCanvas(settings, self)
        self.canvas.status_changed.connect(self.set_status_message)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)

        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._handle_screen_configuration_changed)
            app.screenRemoved.connect(self._handle_screen_configuration_changed)

        self.apply_settings(settings)

    def apply_settings(self, settings: dict) -> None:
        was_visible = self.isVisible()
        self.settings = settings
        self.setWindowOpacity(float(settings["opacity"]))
        self.canvas.apply_settings(settings)
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint,
            bool(settings.get("always_on_top", True)),
        )
        if was_visible:
            self.show()
            self.raise_()
            self._sync_screen_reservation()

    def _resolve_screen(self):
        monitor_id = self.settings.get("monitor_id", "primary")
        screens = list(QGuiApplication.screens())
        if not screens:
            return None

        if monitor_id == "primary":
            return QGuiApplication.primaryScreen() or screens[0]

        for screen in screens:
            if monitor_id_for_screen(screen) == monitor_id:
                return screen

        return QGuiApplication.primaryScreen() or screens[0]

    def _should_reregister_appbar(self, monitor_id: str) -> bool:
        return any(
            [
                self._reserved_monitor_id != monitor_id,
                self._reserved_edge != self.settings["position"],
                self._reserved_enabled != bool(self.settings.get("reserve_screen_space", True)),
            ]
        )

    def _sync_screen_reservation(self) -> None:
        screen = self._resolve_screen()
        if screen is None:
            return

        if self.windowHandle() is not None and self.windowHandle().screen() != screen:
            self.windowHandle().setScreen(screen)

        geometry = screen.geometry()
        height = int(self.settings["height"])
        reserved_rect = None
        monitor_id = monitor_id_for_screen(screen)
        reserve_screen_space = bool(self.settings.get("reserve_screen_space", True))

        if self._should_reregister_appbar(monitor_id):
            self.appbar.release()

        if reserve_screen_space:
            reserved_rect = self.appbar.reserve(
                int(self.winId()),
                geometry,
                self.settings["position"],
                height,
            )
        else:
            self.appbar.release()

        self._reserved_monitor_id = monitor_id
        self._reserved_edge = self.settings["position"]
        self._reserved_enabled = reserve_screen_space

        if reserved_rect is not None:
            self.setGeometry(reserved_rect)
            return

        self.setGeometry(geometry.x(), geometry.y(), geometry.width(), height)
        if self.settings["position"] == "bottom":
            self.move(geometry.x(), geometry.bottom() - height + 1)
        else:
            self.move(geometry.x(), geometry.y())

    def set_headlines(self, items: list[HeadlineItem], highlighted_keys: list[str] | None = None) -> None:
        self.canvas.set_headlines(items, highlighted_keys)

    def set_manual_paused(self, paused: bool) -> None:
        self.canvas.set_manual_paused(paused)

    def set_status_message(self, message: str, details: str | None = None) -> None:
        tooltip = details or message
        self.setToolTip(tooltip)
        self.canvas.setToolTip(tooltip)

    def set_status_state(self, kind: str, message: str) -> None:
        self.canvas.set_status_state(kind, message)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._sync_screen_reservation()

    def hideEvent(self, event) -> None:  # type: ignore[override]
        self.appbar.release()
        self._reserved_monitor_id = None
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.appbar.release()
        self._reserved_monitor_id = None
        super().closeEvent(event)

    def _handle_screen_configuration_changed(self, *_args) -> None:
        if self.isVisible():
            self._sync_screen_reservation()

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        digest_action = QAction("Show Headline Digest", self)
        digest_action.triggered.connect(self.request_show_digest.emit)
        diagnostics_action = QAction("Show Feed Diagnostics", self)
        diagnostics_action.triggered.connect(self.request_show_feed_diagnostics.emit)
        refresh_action = QAction("Refresh Now", self)
        refresh_action.triggered.connect(self.request_refresh.emit)
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.request_open_settings.emit)
        close_action = QAction("Close Ticker", self)
        close_action.triggered.connect(self.hide)
        menu.addAction(digest_action)
        menu.addAction(diagnostics_action)
        menu.addAction(refresh_action)
        menu.addAction(settings_action)
        menu.addAction(close_action)
        menu.exec(event.globalPos())


def monitor_id_for_screen(screen) -> str:
    geometry = screen.geometry()
    name = screen.name() or "display"
    return f"{name}|{geometry.x()}|{geometry.y()}|{geometry.width()}|{geometry.height()}"
