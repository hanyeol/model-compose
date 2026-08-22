from __future__ import annotations

from typing import List, Optional
from dataclasses import dataclass
import asyncio, platform

# Normal application windows; higher layers are menu bars, docks and overlays.
_NORMAL_WINDOW_LAYER = 0

@dataclass(frozen=True)
class WindowSelector:
    title: Optional[str] = None
    app: Optional[str] = None

    def matches(self, title: str, app: str) -> bool:
        # Case-insensitive substring test; empty title/app on the selector matches anything.
        if self.title and self.title.lower() not in (title or "").lower():
            return False

        if self.app and self.app.lower() not in (app or "").lower():
            return False

        return True

    def describe(self) -> str:
        parts = [ f"{field}~='{value}'" for field, value in (("title", self.title), ("app", self.app)) if value ]

        return ", ".join(parts) or "<empty>"

@dataclass(frozen=True)
class WindowInfo:
    title: str
    app: str
    x: int
    y: int
    width: int
    height: int
    # Platform-native handle. Windows: exact title string (gdigrab keys on
    # title=, not HWND; titles are not guaranteed unique). macOS/Linux:
    # numeric window id, kept for logging.
    handle: str
    # Z-order class. 0 is a normal application window; only macOS reports
    # anything else, but the field keeps ranking uniform across backends.
    layer: int = _NORMAL_WINDOW_LAYER

class WindowNotFoundError(RuntimeError):
    pass

async def _list_windows(selector: WindowSelector, system: str) -> List[WindowInfo]:
    if system == "Darwin":
        from .platforms.quartz import list_windows

        return await asyncio.to_thread(list_windows, selector)

    if system == "Windows":
        from .platforms.win32 import list_windows

        # EnumWindows plus one OpenProcess per window is slow enough to stall the
        # event loop, so it runs off-thread.
        return await asyncio.to_thread(list_windows, selector)

    if system == "Linux":
        from .platforms.x11 import list_windows

        return await list_windows(selector)

    raise NotImplementedError(f"Window capture is not supported on platform: {system}")

async def find_window(selector: WindowSelector) -> WindowInfo:
    """Return the best-matching on-screen window, or raise WindowNotFoundError.

    Ranking is stable: normal-layer windows keep their platform order and come
    first, overlays (macOS menu bars, docks, HUDs) are demoted to the tail.
    """
    system = platform.system()
    candidates = await _list_windows(selector, system)
    candidates = sorted(candidates, key=lambda window: window.layer != _NORMAL_WINDOW_LAYER)

    if not candidates:
        raise WindowNotFoundError(f"No window matched selector ({selector.describe()}) on {system}.")

    return candidates[0]
