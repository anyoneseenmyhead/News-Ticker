from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.feeds.fetcher import FeedFetchWorker
from src.feeds.models import HeadlineItem
from src.feeds.store import FeedStore
from src.services.autostart import WindowsAutoStart
from src.services.paths import user_data_dir
from src.services.settings import SettingsService
from src.ui.settings_dialog import SettingsDialog
from src.ui.ticker_window import TickerWindow
from src.utils.text import normalize_headline_key

ROOT_DIR = Path(__file__).resolve().parents[2]
SOURCE_ICON_PNG = ROOT_DIR / "news-ticker-icon.png"
GENERATED_ICON_PNG = ROOT_DIR / "assets" / "generated" / "app_icon.png"
GENERATED_ICON_ICO = ROOT_DIR / "assets" / "generated" / "app_icon.ico"


class AppController(QObject):
    headlines_updated = Signal(list, list)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self._shutting_down = False
        self.settings = SettingsService()
        self.feed_store = FeedStore(max_items=100)
        self.autostart = WindowsAutoStart(self.settings.app_name)
        self.window = TickerWindow(self.settings.data)
        self.tray = self._build_tray()
        self.refresh_thread: QThread | None = None
        self.refresh_worker: FeedFetchWorker | None = None
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_feeds)
        self.headlines_updated.connect(self.window.set_headlines)

        self.window.request_open_settings.connect(self.open_settings)
        self.window.request_refresh.connect(self.refresh_feeds)

        self._apply_settings_to_services()
        self.window.show()
        self.refresh_feeds()

    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(self.app)
        tray.setIcon(load_app_icon())
        tray.setToolTip("News Ticker")
        menu = QMenu()

        self.toggle_action = QAction("Hide Ticker", self)
        self.toggle_action.triggered.connect(self.toggle_window_visibility)
        menu.addAction(self.toggle_action)

        self.pause_action = QAction("Pause", self)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.window.set_manual_paused)
        menu.addAction(self.pause_action)

        refresh_action = QAction("Refresh Now", self)
        refresh_action.triggered.connect(self.refresh_feeds)
        menu.addAction(refresh_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.shutdown)
        menu.addAction(exit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(self._handle_tray_activation)
        tray.show()
        return tray

    def _handle_tray_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window_visibility()

    def _apply_settings_to_services(self) -> None:
        self.window.apply_settings(self.settings.data)

        interval_ms = max(1, int(self.settings.data["refresh_interval_minutes"])) * 60 * 1000
        self.refresh_timer.start(interval_ms)

        if self.settings.data.get("launch_on_startup"):
            self.autostart.enable()
        else:
            self.autostart.disable()

    def toggle_window_visibility(self) -> None:
        visible = self.window.isVisible()
        if visible:
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()
        self.toggle_action.setText("Show Ticker" if visible else "Hide Ticker")

    def refresh_feeds(self) -> None:
        if self.refresh_thread is not None:
            return

        enabled_feeds = [feed for feed in self.settings.data["feeds"] if feed.get("enabled", True)]
        if not enabled_feeds:
            self.window.set_status_message("No feeds enabled")
            self.window.set_status_state("empty", "No feeds enabled")
            self.window.set_headlines(self.feed_store.items, [])
            return

        self.window.set_status_message("Refreshing headlines...")
        self.window.set_status_state("loading", "Refreshing headlines...")
        self.refresh_thread = QThread()
        self.refresh_worker = FeedFetchWorker(enabled_feeds)
        self.refresh_worker.moveToThread(self.refresh_thread)
        self.refresh_thread.started.connect(self.refresh_worker.run)
        self.refresh_worker.finished.connect(self._handle_refresh_success)
        self.refresh_worker.failed.connect(self._handle_refresh_failure)
        self.refresh_worker.finished.connect(self._cleanup_refresh_thread)
        self.refresh_worker.failed.connect(self._cleanup_refresh_thread)
        self.refresh_thread.start()

    def _handle_refresh_success(self, items: list[HeadlineItem], warnings: list[str]) -> None:
        existing_keys = {self._headline_key(item) for item in self.feed_store.items}
        merged = self.feed_store.merge(items)
        highlight_keys = [
            self._headline_key(item)
            for item in merged
            if self._headline_key(item) not in existing_keys
        ]
        if warnings:
            self.window.set_status_message(
                f"{len(merged)} headlines loaded. {len(warnings)} feed issue(s). Hover for details.",
                "\n".join(warnings),
            )
            self.window.set_status_state("warning", "\n".join(warnings))
        else:
            self.window.set_status_message(f"{len(merged)} headlines loaded")
            self.window.set_status_state("ok", f"{len(merged)} headlines loaded")
        self.headlines_updated.emit(merged, highlight_keys)

    def _handle_refresh_failure(self, message: str) -> None:
        if self.feed_store.items:
            self.window.set_status_message(
                f"Refresh failed, showing cached headlines. Hover for details.",
                message,
            )
            self.window.set_status_state("warning", message)
            self.window.set_headlines(self.feed_store.items, [])
            return

        self.window.set_status_message("Refresh failed. Hover for details.", message)
        self.window.set_status_state("error", message)

    def _headline_key(self, item: HeadlineItem) -> str:
        return item.guid.strip() or normalize_headline_key(item.title, item.url)

    def _cleanup_refresh_thread(self, *_args: object) -> None:
        if self.refresh_thread is None:
            return

        self.refresh_thread.quit()
        self.refresh_thread.wait(2000)
        if self.refresh_worker is not None:
            self.refresh_worker.deleteLater()
        self.refresh_thread.deleteLater()
        self.refresh_thread = None
        self.refresh_worker = None

    def open_settings(self) -> None:
        original_settings = deepcopy(self.settings.data)
        dialog = SettingsDialog(self.settings.data, self.window)
        dialog.preview_requested.connect(self.window.apply_settings)
        if not dialog.exec():
            self.window.apply_settings(original_settings)
            return

        self.settings.save(dialog.get_settings())
        self._apply_settings_to_services()
        self.refresh_feeds()

    def shutdown(self) -> None:
        if self._shutting_down:
            return

        self._shutting_down = True
        self.refresh_timer.stop()

        if self.refresh_thread is not None:
            self.refresh_thread.quit()
            self.refresh_thread.wait(2000)
            if self.refresh_worker is not None:
                self.refresh_worker.deleteLater()
            self.refresh_thread.deleteLater()
            self.refresh_thread = None
            self.refresh_worker = None

        self.tray.hide()
        self.window.close()
        self.app.quit()


def _ensure_data_dir() -> None:
    user_data_dir().mkdir(parents=True, exist_ok=True)


def build_tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#101418"))
    painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
    painter.setBrush(QColor("#FF6B35"))
    painter.drawRect(6, 10, 20, 3)
    painter.drawRect(6, 16, 14, 3)
    painter.end()
    return QIcon(pixmap)


def load_app_icon() -> QIcon:
    for icon_path in (SOURCE_ICON_PNG, GENERATED_ICON_ICO, GENERATED_ICON_PNG):
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
    return build_tray_icon()


def run() -> None:
    _ensure_data_dir()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("News Ticker")
    app.setWindowIcon(load_app_icon())
    app.setQuitOnLastWindowClosed(False)
    controller = AppController(app)
    app.aboutToQuit.connect(controller.shutdown)
    sys.exit(app.exec())
