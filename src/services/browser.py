from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path


WINDOWS_BROWSER_CANDIDATES = {
    "edge": {
        "label": "Microsoft Edge",
        "executables": ["msedge.exe"],
        "paths": [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        ],
    },
    "chrome": {
        "label": "Google Chrome",
        "executables": ["chrome.exe"],
        "paths": [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        ],
    },
    "firefox": {
        "label": "Mozilla Firefox",
        "executables": ["firefox.exe"],
        "paths": [
            Path(r"C:\Program Files\Mozilla Firefox\firefox.exe"),
            Path(r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"),
        ],
    },
    "brave": {
        "label": "Brave",
        "executables": ["brave.exe", "brave-browser.exe"],
        "paths": [
            Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
            Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
    },
    "opera_gx": {
        "label": "Opera GX",
        "executables": ["opera.exe"],
        "paths": [],
    },
}


def available_browser_options() -> list[dict[str, str]]:
    options = [{"id": "system", "label": "System Default"}]
    for browser_id, spec in WINDOWS_BROWSER_CANDIDATES.items():
        if resolve_browser_command(browser_id) is not None:
            options.append({"id": browser_id, "label": spec["label"]})
    return options


def launch_url(url: str, browser_id: str = "system") -> None:
    browser_command = resolve_browser_command(browser_id)
    if browser_command is None:
        _open_with_system_default(url)
        return
    subprocess.Popen([browser_command, url])


def resolve_browser_command(browser_id: str) -> str | None:
    if browser_id == "system":
        return None

    spec = WINDOWS_BROWSER_CANDIDATES.get(browser_id)
    if spec is None:
        return None

    for executable in spec["executables"]:
        resolved = shutil.which(executable)
        if resolved:
            return resolved

    local_appdata = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")

    extra_paths: list[Path] = []
    if browser_id == "chrome" and local_appdata:
        extra_paths.append(Path(local_appdata) / "Google" / "Chrome" / "Application" / "chrome.exe")
    if browser_id == "edge" and local_appdata:
        extra_paths.append(Path(local_appdata) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    if browser_id == "brave" and local_appdata:
        extra_paths.append(Path(local_appdata) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe")
    if browser_id == "opera_gx" and local_appdata:
        extra_paths.append(Path(local_appdata) / "Programs" / "Opera GX" / "opera.exe")
    if browser_id == "firefox":
        if program_files:
            extra_paths.append(Path(program_files) / "Mozilla Firefox" / "firefox.exe")
        if program_files_x86:
            extra_paths.append(Path(program_files_x86) / "Mozilla Firefox" / "firefox.exe")

    for path in [*spec["paths"], *extra_paths]:
        if path.exists():
            return str(path)

    return None


def _open_with_system_default(url: str) -> None:
    if hasattr(os, "startfile"):
        os.startfile(url)  # type: ignore[attr-defined]
        return
    webbrowser.open(url)
