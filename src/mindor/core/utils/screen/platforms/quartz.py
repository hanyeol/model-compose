from __future__ import annotations

from typing import List
from ..window import WindowSelector, WindowInfo

def list_windows(selector: WindowSelector) -> List[WindowInfo]:
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGWindowListExcludeDesktopElements,
        kCGNullWindowID,
    )

    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    # Returned front-to-back, so the natural order is already "frontmost first".
    windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) or []
    results: List[WindowInfo] = []

    for window in windows:
        # kCGWindowName stays empty unless the host app holds Screen Recording
        # permission, so title-only selectors silently match nothing without it.
        title = window.get("kCGWindowName") or ""
        app   = window.get("kCGWindowOwnerName") or ""

        if not selector.matches(title, app):
            continue

        bounds = window.get("kCGWindowBounds") or {}
        width  = int(bounds.get("Width", 0))
        height = int(bounds.get("Height", 0))

        if width <= 0 or height <= 0:
            continue

        results.append(WindowInfo(
            title=title,
            app=app,
            x=int(bounds.get("X", 0)),
            y=int(bounds.get("Y", 0)),
            width=width,
            height=height,
            handle=str(window.get("kCGWindowNumber", "")),
            layer=int(window.get("kCGWindowLayer", 0)),
        ))

    return results
