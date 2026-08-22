from __future__ import annotations

from typing import Optional, List
from ..window import WindowSelector, WindowInfo

# Long-path aware; MAX_PATH is not enough for QueryFullProcessImageNameW.
_PATH_BUFFER_CHARS = 32768
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_DWMWA_CLOAKED = 14

class _Win32Api:
    """Thin ctypes wrapper around the few Win32 calls we need.

    Declaring argtypes/restypes is not cosmetic: ctypes defaults restype to
    c_int, which truncates the 64-bit HANDLE returned by OpenProcess.
    """
    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.user32   = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.psapi    = ctypes.WinDLL("psapi", use_last_error=True)

        try:
            self.dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        except OSError:  # dwmapi is present on Vista+ so this branch is unreachable in practice.
            self.dwmapi = None

        self.enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        u32, k32, ps = self.user32, self.kernel32, self.psapi

        u32.IsWindowVisible.argtypes        = [ wintypes.HWND ]
        u32.IsWindowVisible.restype         = wintypes.BOOL
        u32.IsIconic.argtypes               = [ wintypes.HWND ]
        u32.IsIconic.restype                = wintypes.BOOL
        u32.GetWindowTextLengthW.argtypes   = [ wintypes.HWND ]
        u32.GetWindowTextLengthW.restype    = ctypes.c_int
        u32.GetWindowTextW.argtypes         = [ wintypes.HWND, wintypes.LPWSTR, ctypes.c_int ]
        u32.GetWindowTextW.restype          = ctypes.c_int
        u32.GetWindowThreadProcessId.argtypes = [ wintypes.HWND, ctypes.POINTER(wintypes.DWORD) ]
        u32.GetWindowThreadProcessId.restype  = wintypes.DWORD
        u32.GetWindowRect.argtypes          = [ wintypes.HWND, ctypes.POINTER(wintypes.RECT) ]
        u32.GetWindowRect.restype           = wintypes.BOOL

        k32.OpenProcess.argtypes            = [ wintypes.DWORD, wintypes.BOOL, wintypes.DWORD ]
        k32.OpenProcess.restype             = wintypes.HANDLE
        k32.CloseHandle.argtypes            = [ wintypes.HANDLE ]
        k32.CloseHandle.restype             = wintypes.BOOL
        k32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
        ]
        k32.QueryFullProcessImageNameW.restype  = wintypes.BOOL

        ps.GetModuleBaseNameW.argtypes = [ wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD ]
        ps.GetModuleBaseNameW.restype  = wintypes.DWORD

        if self.dwmapi is not None:
            self.dwmapi.DwmGetWindowAttribute.argtypes = [
                wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
            ]
            self.dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

    def list_windows(self, selector: WindowSelector) -> List[WindowInfo]:
        results: List[WindowInfo] = []

        def _on_window(hwnd, _lparam) -> bool:
            info = self.describe_window(hwnd, selector)

            if info is not None:
                results.append(info)

            return True

        # Keep a reference to the trampoline alive for the duration of the call.
        callback = self.enum_windows_proc(_on_window)
        self.user32.EnumWindows(callback, 0)

        return results

    def describe_window(self, hwnd, selector: WindowSelector) -> Optional[WindowInfo]:
        import ctypes
        from ctypes import wintypes

        if not self.user32.IsWindowVisible(hwnd):
            return None

        # Minimized windows report a bogus (-32000, -32000) origin.
        if self.user32.IsIconic(hwnd):
            return None

        if self.is_cloaked(hwnd):
            return None

        title = self.window_title(hwnd)

        if not title:
            return None

        app = self.process_name(self.window_pid(hwnd))

        if not selector.matches(title, app):
            return None

        rect = wintypes.RECT()

        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None

        width  = rect.right - rect.left
        height = rect.bottom - rect.top

        if width <= 0 or height <= 0:
            return None

        return WindowInfo(
            title=title,
            app=app,
            x=rect.left,
            y=rect.top,
            width=width,
            height=height,
            handle=title,  # gdigrab keys on the exact title string; titles are not guaranteed unique.
        )

    def window_title(self, hwnd) -> str:
        import ctypes

        length = self.user32.GetWindowTextLengthW(hwnd)

        if length <= 0:
            return ""

        buffer = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buffer, length + 1)

        return buffer.value

    def window_pid(self, hwnd) -> int:
        import ctypes
        from ctypes import wintypes

        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        return pid.value

    def process_name(self, pid: int) -> str:
        import ctypes
        from ctypes import wintypes

        handle = self.kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

        if not handle:
            return ""

        try:
            buffer = ctypes.create_unicode_buffer(_PATH_BUFFER_CHARS)
            size = wintypes.DWORD(_PATH_BUFFER_CHARS)

            # QueryFullProcessImageNameW first: GetModuleBaseNameW needs
            # PROCESS_VM_READ, which a limited-information handle never grants.
            if self.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value.rsplit("\\", 1)[-1]

            if self.psapi.GetModuleBaseNameW(handle, None, buffer, _PATH_BUFFER_CHARS):
                return buffer.value

            return ""
        finally:
            self.kernel32.CloseHandle(handle)

    def is_cloaked(self, hwnd) -> bool:
        """True for DWM-cloaked windows (suspended UWP apps, other desktops)."""
        import ctypes

        if self.dwmapi is None:
            return False

        cloaked = ctypes.c_int(0)
        hresult = self.dwmapi.DwmGetWindowAttribute(
            hwnd, _DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )

        return hresult == 0 and cloaked.value != 0

_api: Optional[_Win32Api] = None

def list_windows(selector: WindowSelector) -> List[WindowInfo]:
    global _api

    if _api is None:
        _api = _Win32Api()

    return _api.list_windows(selector)
