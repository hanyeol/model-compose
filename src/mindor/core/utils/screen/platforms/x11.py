from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from ...shell import run_command
from ..window import WindowSelector, WindowInfo
import asyncio, shutil

# Upper bound on concurrent xdotool/xwininfo probes.
_MAX_CONCURRENT_PROBES = 16

_XWININFO_FIELDS = {
    "Absolute upper-left X": "x",
    "Absolute upper-left Y": "y",
    "Width":                 "width",
    "Height":                "height",
}

async def _search_visible_windows() -> List[str]:
    # xdotool's --name is a regex; an empty pattern matches every window so we
    # can filter in Python with the same substring rules as the other backends.
    stdout, _, code = await run_command(
        [ "xdotool", "search", "--onlyvisible", "--name", "" ],
        timeout=5.0,
    )

    if code != 0:
        return []

    return [ line.strip() for line in stdout.decode(errors="replace").splitlines() if line.strip() ]

async def _get_window_name(wid: str) -> str:
    stdout, _, code = await run_command([ "xdotool", "getwindowname", wid ], timeout=2.0)

    if code != 0:
        return ""

    return stdout.decode(errors="replace").strip()

async def _get_window_class(wid: str) -> str:
    stdout, _, code = await run_command([ "xdotool", "getwindowclassname", wid ], timeout=2.0)

    if code != 0:
        return ""

    return stdout.decode(errors="replace").strip()

async def _get_window_geometry(wid: str) -> Optional[Tuple[int, int, int, int]]:
    stdout, _, code = await run_command([ "xwininfo", "-id", wid ], timeout=5.0)

    if code != 0:
        return None

    return _parse_xwininfo(stdout.decode(errors="replace"))

async def _describe_window(wid: str, selector: WindowSelector) -> Optional[WindowInfo]:
    title, app = await asyncio.gather(_get_window_name(wid), _get_window_class(wid))

    if not selector.matches(title, app):
        return None

    rect = await _get_window_geometry(wid)

    if rect is None:
        return None

    x, y, width, height = rect

    return WindowInfo(
        title=title,
        app=app,
        x=x,
        y=y,
        width=width,
        height=height,
        handle=wid,
    )

def _parse_xwininfo(text: str) -> Optional[Tuple[int, int, int, int]]:
    values: Dict[str, int] = {}

    for line in text.splitlines():
        key, separator, raw = line.strip().partition(":")

        if not separator:
            continue

        field = _XWININFO_FIELDS.get(key)

        if field is None or field in values:
            continue

        try:
            values[field] = int(raw.strip())
        except ValueError:
            continue

    if len(values) != len(_XWININFO_FIELDS):
        return None

    if values["width"] <= 0 or values["height"] <= 0:
        return None

    return values["x"], values["y"], values["width"], values["height"]

async def list_windows(selector: WindowSelector) -> List[WindowInfo]:
    missing_tools = [ tool for tool in ("xdotool", "xwininfo") if shutil.which(tool) is None ]

    if missing_tools:
        raise RuntimeError(
            f"Linux window capture requires {' and '.join(repr(tool) for tool in missing_tools)} on PATH. "
            "Install them via your package manager (e.g. 'apt install xdotool x11-utils')."
        )

    window_ids = await _search_visible_windows()
    limit = asyncio.Semaphore(_MAX_CONCURRENT_PROBES)

    async def _describe(wid: str) -> Optional[WindowInfo]:
        async with limit:
            return await _describe_window(wid, selector)

    # gather preserves input order, so results stay in xdotool's stacking order.
    candidates = await asyncio.gather(*(_describe(wid) for wid in window_ids))

    return [ info for info in candidates if info is not None ]
