from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QRect


ABE_TOP = 1
ABE_BOTTOM = 3

ABM_NEW = 0x00000000
ABM_REMOVE = 0x00000001
ABM_QUERYPOS = 0x00000002
ABM_SETPOS = 0x00000003


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uCallbackMessage", wintypes.UINT),
        ("uEdge", wintypes.UINT),
        ("rc", RECT),
        ("lParam", wintypes.LPARAM),
    ]


class WindowsAppBar:
    def __init__(self) -> None:
        self.available = hasattr(ctypes, "windll")
        self._registered = False
        self._hwnd: int | None = None
        self._callback_message = 0
        if not self.available:
            return
        self._shell32 = ctypes.windll.shell32
        self._user32 = ctypes.windll.user32
        self._callback_message = self._user32.RegisterWindowMessageW("NewsTicker.AppBar")

    def reserve(self, hwnd: int, screen_rect: QRect, edge_name: str, thickness: int) -> QRect | None:
        if not self.available:
            return None

        edge = ABE_BOTTOM if edge_name == "bottom" else ABE_TOP
        if not self._registered or self._hwnd != hwnd:
            self.release()
            self._register(hwnd)

        data = self._make_data(hwnd)
        data.uEdge = edge
        data.rc = RECT(
            screen_rect.left(),
            screen_rect.top(),
            screen_rect.right() + 1,
            screen_rect.bottom() + 1,
        )

        if edge == ABE_TOP:
            data.rc.bottom = data.rc.top + thickness
        else:
            data.rc.top = data.rc.bottom - thickness

        self._shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(data))

        if edge == ABE_TOP:
            data.rc.bottom = data.rc.top + thickness
        else:
            data.rc.top = data.rc.bottom - thickness

        self._shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(data))
        return QRect(
            data.rc.left,
            data.rc.top,
            data.rc.right - data.rc.left,
            data.rc.bottom - data.rc.top,
        )

    def release(self) -> None:
        if not self.available or not self._registered or self._hwnd is None:
            return

        data = self._make_data(self._hwnd)
        self._shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(data))
        self._registered = False
        self._hwnd = None

    def _register(self, hwnd: int) -> None:
        data = self._make_data(hwnd)
        data.uCallbackMessage = self._callback_message
        self._shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(data))
        self._registered = True
        self._hwnd = hwnd

    def _make_data(self, hwnd: int) -> APPBARDATA:
        data = APPBARDATA()
        data.cbSize = ctypes.sizeof(APPBARDATA)
        data.hWnd = wintypes.HWND(hwnd)
        return data
