from __future__ import annotations

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - only relevant outside Windows
    winreg = None

from src.services.paths import app_root


class WindowsAutoStart:
    def __init__(self, app_name: str) -> None:
        self.app_name = app_name
        self.command = self._build_command()

    def _build_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}"'
        return f'"{Path(sys.executable).resolve()}" "{app_root() / "main.py"}"'

    def enable(self) -> None:
        if winreg is None:
            return
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, self.command)

    def disable(self) -> None:
        if winreg is None:
            return
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, self.app_name)
            except FileNotFoundError:
                return
