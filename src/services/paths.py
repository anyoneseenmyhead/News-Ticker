from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "News Ticker"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_data_dir(app_name: str = APP_NAME) -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / app_name / "data"
    return Path.home() / "AppData" / "Local" / app_name / "data"


def legacy_data_dir() -> Path:
    return app_root() / "data"
