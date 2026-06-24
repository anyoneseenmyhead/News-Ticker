from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

from src.services.paths import user_data_dir, legacy_data_dir


DEFAULT_FEEDS = [
    {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml", "enabled": True},
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "enabled": True},
]

LEGACY_INITIAL_FEEDS = [
    {"name": "Reuters World", "url": "https://feeds.reuters.com/Reuters/worldNews", "enabled": True},
    {"name": "AP Top News", "url": "https://apnews.com/hub/ap-top-news?output=rss", "enabled": True},
    {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml", "enabled": True},
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "enabled": True},
]


DEFAULT_SETTINGS = {
    "monitor_id": "primary",
    "position": "top",
    "height": 32,
    "opacity": 0.9,
    "scroll_speed": 100,
    "headline_spacing": 32,
    "font_size": 10,
    "refresh_interval_minutes": 5,
    "max_headlines": 40,
    "max_headline_age_hours": 5,
    "browser_preference": "system",
    "show_source_label": True,
    "deduplicate_headlines": True,
    "pause_on_hover": True,
    "launch_on_startup": False,
    "always_on_top": False,
    "reserve_screen_space": True,
    "new_headline_pulse_enabled": True,
    "new_headline_pulse_duration": 18,
    "new_headline_pulse_speed": 16,
    "new_headline_pulse_strength": 54,
    "new_headline_pulse_color": "#AA00FF",
    "background_color": "#101418",
    "text_color": "#F5F7FA",
    "accent_color": "#AA00FF",
    "separator_color": "#FFBF00",
    "feeds": deepcopy(DEFAULT_FEEDS),
}


class SettingsService:
    def __init__(self, app_name: str = "News Ticker") -> None:
        self.app_name = app_name
        self.path = user_data_dir(app_name) / "settings.json"
        self.data = self.load()

    def load(self) -> dict:
        self._migrate_legacy_settings()
        if not self.path.exists():
            self.save(deepcopy(DEFAULT_SETTINGS))
            return deepcopy(DEFAULT_SETTINGS)

        with self.path.open("r", encoding="utf-8") as handle:
            stored = json.load(handle)

        merged = merge_dicts(deepcopy(DEFAULT_SETTINGS), stored)
        if merged.get("feeds") == LEGACY_INITIAL_FEEDS:
            merged["feeds"] = deepcopy(DEFAULT_FEEDS)
            self.save(merged)
        return merged

    def save(self, settings: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
        self.data = settings

    def _migrate_legacy_settings(self) -> None:
        legacy_path = legacy_data_dir() / "settings.json"
        if self.path.exists() or not legacy_path.exists() or legacy_path == self.path:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_path, self.path)


def merge_dicts(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = merge_dicts(base[key], value)
        else:
            base[key] = value
    return base
