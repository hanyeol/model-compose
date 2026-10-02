"""Unit tests for the Playwright html-frame-renderer session.

Covers:
  - Pipelined capture when the page calls `__renderer.rendered(t)`
  - The seek-returns-before-rendered race (seek RPC completes first; the
    engine must keep waiting for `rendered()` up to the remaining timeout)
  - Fallback to sequential seek/screenshot when the first frame never
    signals `rendered()`
  - Mid-render stall (rendered() stops after being proven) → RuntimeError
  - Seek errors propagate without masking as a fallback
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

import pytest

from mindor.core.component.services.html_frame_renderer.drivers.playwright import (
    PlaywrightHtmlFrameRendererSession,
)
from mindor.core.utils.url import UrlResource


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakePage:
    """Minimal stand-in for a Playwright `Page`.

    The session only touches a handful of methods; we fake just those. The
    test drives the binding callback directly to simulate `rendered(t)` firing.
    """

    def __init__(
        self,
        duration: float,
        seek_behavior: Optional[Callable[[float], Any]] = None,
    ) -> None:
        self.duration = duration
        self._seek_behavior = seek_behavior
        self.rendered_binding: Optional[Callable[[Any, float], None]] = None
        self.seek_calls: List[float] = []
        self.screenshot_calls = 0
        self.last_screenshot_params: Dict[str, Any] = {}
        self.fonts_ready_awaited = False

    async def set_viewport_size(self, _size: Dict[str, int]) -> None:
        return None

    async def expose_binding(self, name: str, callback: Callable[[Any, float], None]) -> None:
        assert name == "__renderer_frame_done"
        self.rendered_binding = callback

    async def add_init_script(self, _script: str) -> None:
        return None

    async def goto(self, _url: str) -> None:
        return None

    async def wait_for_function(self, _expr: str, timeout: Optional[int] = None) -> None:
        return None

    async def evaluate(self, expr: str, *args: Any) -> Any:
        if "duration" in expr:
            return self.duration

        if "document.fonts.ready" in expr:
            self.fonts_ready_awaited = True
            return None

        if "seek" in expr:
            timestamp = args[0] if args else 0.0
            self.seek_calls.append(timestamp)

            if self._seek_behavior is not None:
                result = self._seek_behavior(timestamp)

                if asyncio.iscoroutine(result):
                    return await result

                return result

            return None

        raise AssertionError(f"unexpected evaluate: {expr!r}")

    async def screenshot(self, **params: Any) -> bytes:
        self.screenshot_calls += 1
        self.last_screenshot_params = params
        return b"\x89PNG-fake"


def _html() -> UrlResource:
    return UrlResource("about:blank")


def _params(render_timeout: float = 1.0, transparent: bool = False) -> Dict[str, Any]:
    return {
        "fps": 10,
        "width": 320,
        "height": 240,
        "format": "png",
        "quality": None,
        "transparent": transparent,
        "ready_timeout": 1.0,
        "render_timeout": render_timeout,
    }


async def _collect(session: PlaywrightHtmlFrameRendererSession, page: _FakePage, params: Dict[str, Any]) -> List[float]:
    timestamps: List[float] = []
    async for _image, timestamp in session.render_frames(_html(), None, params):
        timestamps.append(timestamp)
    return timestamps


class TestFrameCount:
    """Frame count matches the declared duration so the encoded video's
    length (frame_count / fps) equals `duration`. Timestamps run
    0 .. (frame_count - 1) / fps."""

    @pytest.mark.anyio
    async def test_two_seconds_at_30fps_yields_60_frames(self):
        page = _FakePage(duration=2.0)
        session = PlaywrightHtmlFrameRendererSession(page)
        params = {
            "fps": 30,
            "width": 320,
            "height": 240,
            "format": "png",
            "quality": None,
            "transparent": False,
            "ready_timeout": 1.0,
            "render_timeout": 0.01,
        }
        timestamps = await _collect(session, page, params)

        assert len(timestamps) == 60
        assert timestamps[0] == 0.0
        assert timestamps[-1] == pytest.approx(59 / 30)

    @pytest.mark.anyio
    async def test_half_slot_rounds_up_not_down(self):
        # duration=0.5, fps=1 → 0.5 frames. int(0.5+0.5)=1 (not 0 like round()).
        page = _FakePage(duration=0.5)
        session = PlaywrightHtmlFrameRendererSession(page)
        params = {
            "fps": 1,
            "width": 320,
            "height": 240,
            "format": "png",
            "quality": None,
            "transparent": False,
            "ready_timeout": 1.0,
            "render_timeout": 0.01,
        }
        timestamps = await _collect(session, page, params)

        assert len(timestamps) == 1


class TestFontLoading:
    """`document.fonts.ready` must be awaited after the page loads and
    before the first seek, so webfont FOUT doesn't bleed across frames."""

    @pytest.mark.anyio
    async def test_fonts_ready_awaited_before_first_seek(self):
        # Capture whether fonts.ready was awaited by the time the first
        # seek fires. The fake page sets `fonts_ready_awaited` on the
        # fonts.ready evaluate; the first seek_behavior invocation reads
        # that flag and asserts it was already true.
        page = _FakePage(duration=0.1)
        order: Dict[str, bool] = {}

        def seek_behavior(_t: float) -> None:
            order.setdefault("fonts_before_seek", page.fonts_ready_awaited)

        page._seek_behavior = seek_behavior
        session = PlaywrightHtmlFrameRendererSession(page)
        await _collect(session, page, _params(render_timeout=0.01))

        assert order["fonts_before_seek"] is True


class TestTransparentCapture:
    """`transparent: true` must pass `omit_background=True` to Playwright's
    screenshot so pages that leave html/body backgrounds unset capture an
    alpha channel. The default stays opaque."""

    @pytest.mark.anyio
    async def test_transparent_passes_omit_background(self):
        page = _FakePage(duration=0.1)
        session = PlaywrightHtmlFrameRendererSession(page)
        await _collect(session, page, _params(render_timeout=0.01, transparent=True))

        assert page.last_screenshot_params.get("omit_background") is True
        assert page.last_screenshot_params["type"] == "png"

    @pytest.mark.anyio
    async def test_opaque_default_omits_omit_background(self):
        page = _FakePage(duration=0.1)
        session = PlaywrightHtmlFrameRendererSession(page)
        await _collect(session, page, _params(render_timeout=0.01))

        assert "omit_background" not in page.last_screenshot_params


class TestSeekRenderedRace:
    """The core bug: seek RPC returning before `rendered()` fires must not
    be mistaken for "page doesn't push". The engine should keep waiting for
    `rendered()` up to the remaining render_timeout."""

    @pytest.mark.anyio
    async def test_rendered_arrives_shortly_after_seek_stays_in_push_mode(self):
        # 2 frames @ 10fps for 0.2s duration → frame_count = 2.
        page = _FakePage(duration=0.2)

        async def seek_behavior(t: float) -> None:
            # seek returns immediately; the page emulates rAF by scheduling
            # rendered() a tick later. The engine must keep waiting past
            # seek completion rather than fall back to legacy mode.
            async def _emit() -> None:
                await asyncio.sleep(0.01)
                page.rendered_binding(None, t)

            asyncio.create_task(_emit())

        page._seek_behavior = seek_behavior
        session = PlaywrightHtmlFrameRendererSession(page)
        timestamps = await _collect(session, page, _params())

        assert timestamps == [0.0, 0.1]
        # Both frames reach seek — push mode is retained; no fallback.
        assert page.seek_calls == [0.0, 0.1]
        assert page.screenshot_calls == 2


class TestFallbackOnFirstFrame:
    """When the first frame never calls `rendered()`, the engine falls back
    to a sequential seek/screenshot path and finishes the render."""

    @pytest.mark.anyio
    async def test_fallback_when_rendered_never_fires_on_first_frame(self):
        # Page never emits rendered(). With a short render_timeout the first
        # frame times out and the engine switches to the legacy path.
        page = _FakePage(duration=0.2)
        session = PlaywrightHtmlFrameRendererSession(page)
        timestamps = await _collect(session, page, _params(render_timeout=0.05))

        assert timestamps == [0.0, 0.1]
        assert page.seek_calls == [0.0, 0.1]
        assert page.screenshot_calls == 2


class TestMidRenderStall:
    """Once a `rendered()` signal has been seen (push mode is proven), a
    later stall is a real failure — don't silently switch modes mid-render."""

    @pytest.mark.anyio
    async def test_rendered_stops_after_first_frame_raises(self):
        # 3 frames @ 10fps for 0.2s. First frame signals, the second doesn't.
        page = _FakePage(duration=0.2)

        async def seek_behavior(t: float) -> None:
            if t == 0.0:
                async def _emit() -> None:
                    await asyncio.sleep(0.01)
                    page.rendered_binding(None, t)
                asyncio.create_task(_emit())
            # Later frames: don't signal — engine should raise mid-render.

        page._seek_behavior = seek_behavior
        session = PlaywrightHtmlFrameRendererSession(page)

        with pytest.raises(RuntimeError, match="stopped calling"):
            await _collect(session, page, _params(render_timeout=0.05))


class TestSeekErrorPropagation:
    """A seek that raises must surface as-is, not be masked as a fallback."""

    @pytest.mark.anyio
    async def test_seek_exception_propagates(self):
        page = _FakePage(duration=0.1)

        def seek_behavior(_t: float) -> None:
            raise RuntimeError("page closed")

        page._seek_behavior = seek_behavior
        session = PlaywrightHtmlFrameRendererSession(page)

        with pytest.raises(RuntimeError, match="page closed"):
            await _collect(session, page, _params())
