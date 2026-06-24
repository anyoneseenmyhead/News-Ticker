from __future__ import annotations

import json
from pathlib import Path

from src.services import settings as settings_module


def configure_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    user_root = tmp_path / "user-data"
    legacy_root = tmp_path / "legacy-data"
    monkeypatch.setattr(settings_module, "user_data_dir", lambda app_name="News Ticker": user_root)
    monkeypatch.setattr(settings_module, "legacy_data_dir", lambda: legacy_root)
    return user_root, legacy_root


def test_load_creates_default_settings_file(monkeypatch, tmp_path: Path) -> None:
    user_root, _legacy_root = configure_paths(monkeypatch, tmp_path)

    service = settings_module.SettingsService()

    settings_path = user_root / "settings.json"
    assert settings_path.exists()
    assert service.data["feeds"] == settings_module.DEFAULT_FEEDS
    with settings_path.open("r", encoding="utf-8") as handle:
        stored = json.load(handle)
    assert stored["refresh_interval_minutes"] == settings_module.DEFAULT_SETTINGS["refresh_interval_minutes"]


def test_load_merges_saved_settings_and_replaces_legacy_feed_defaults(monkeypatch, tmp_path: Path) -> None:
    user_root, _legacy_root = configure_paths(monkeypatch, tmp_path)
    user_root.mkdir(parents=True, exist_ok=True)
    settings_path = user_root / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "position": "bottom",
                "feeds": settings_module.LEGACY_INITIAL_FEEDS,
            }
        ),
        encoding="utf-8",
    )

    service = settings_module.SettingsService()

    assert service.data["position"] == "bottom"
    assert service.data["feeds"] == settings_module.DEFAULT_FEEDS
    assert service.data["font_size"] == settings_module.DEFAULT_SETTINGS["font_size"]


def test_migrate_legacy_settings_copies_file_once(monkeypatch, tmp_path: Path) -> None:
    user_root, legacy_root = configure_paths(monkeypatch, tmp_path)
    legacy_root.mkdir(parents=True, exist_ok=True)
    legacy_payload = {"position": "bottom", "feeds": settings_module.DEFAULT_FEEDS}
    (legacy_root / "settings.json").write_text(json.dumps(legacy_payload), encoding="utf-8")

    service = settings_module.SettingsService()

    assert service.data["position"] == "bottom"
    copied_payload = json.loads((user_root / "settings.json").read_text(encoding="utf-8"))
    assert copied_payload["position"] == "bottom"
