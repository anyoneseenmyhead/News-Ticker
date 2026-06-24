from __future__ import annotations

from pathlib import Path

import pytest

from src.services import browser


def test_resolve_browser_command_returns_none_for_system_and_unknown() -> None:
    assert browser.resolve_browser_command("system") is None
    assert browser.resolve_browser_command("not-a-browser") is None


def test_resolve_browser_command_prefers_shutil_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser.shutil, "which", lambda executable: r"C:\Tools\chrome.exe" if executable == "chrome.exe" else None)

    resolved = browser.resolve_browser_command("chrome")

    assert resolved == r"C:\Tools\chrome.exe"


def test_available_browser_options_only_lists_resolved_browsers(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve(browser_id: str):
        return r"C:\Tools\msedge.exe" if browser_id == "edge" else None

    monkeypatch.setattr(browser, "resolve_browser_command", fake_resolve)

    options = browser.available_browser_options()

    assert options == [
        {"id": "system", "label": "System Default"},
        {"id": "edge", "label": "Microsoft Edge"},
    ]


def test_launch_url_uses_subprocess_for_specific_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(browser, "resolve_browser_command", lambda browser_id: r"C:\Tools\firefox.exe")
    monkeypatch.setattr(browser.subprocess, "Popen", lambda args: calls.append(args))

    browser.launch_url("https://example.com/story", "firefox")

    assert calls == [[r"C:\Tools\firefox.exe", "https://example.com/story"]]
