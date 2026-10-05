"""Unit tests for the Playwright html-frame-renderer session.

Covers:
  - Frame count from (duration, frame_rate) via HtmlFrameRenderOrchestrator
  - Pipelined capture when the page calls `__renderer.rendered(t)`
  - The render-returns-before-rendered race (render RPC completes first; the
    session must keep waiting for `rendered()` up to the remaining timeout)
  - Fallback to sequential render/screenshot when the first frame never
    signals `rendered()`
  - Mid-render stall (rendered() stops after being proven) → RuntimeError
  - render() errors propagate without masking as a fallback
  - The driver waits on window.__renderer.ready in load_html()
  - Multi-worker ordering: frames yield monotonically even if workers finish
    out of order
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

from mindor.core.component.services.html_frame_renderer.drivers.playwright import (
    PlaywrightHtmlFrameRendererSession,
)
from mindor.core.component.services.html_frame_renderer.drivers.common import (
    HtmlFrameRenderOrchestrator,
)
from mindor.core.utils.url import UrlResource


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakePage:
    """Minimal stand-in for a Playwright `Page`.

    Fakes just the methods the session touches. Tests drive the
    `rendered(t)` binding directly to simulate the page pushing frames.
    """

    def __init__(
        self,
        render_behavior: Optional[Callable[[float], Any]] = None,
    ) -> None:
        self._render_behavior = render_behavior
        self.rendered_binding: Optional[Callable[[Any, float], None]] = None
        self.render_calls: List[float] = []
        self.screenshot_calls = 0
        self.last_screenshot_params: Dict[str, Any] = {}
        self.wait_for_function_calls: List[str] = []

    async def set_viewport_size(self, _size: Dict[str, int]) -> None:
        return None

    async def expose_binding(self, name: str, callback: Callable[[Any, float], None]) -> None:
        assert name == "__renderer_frame_done"
        self.rendered_binding = callback

    async def add_init_script(self, _script: str) -> None:
        return None

    async def goto(self, _url: str) -> None:
        return None

    async def wait_for_function(self, expr: str, timeout: Optional[int] = None) -> None:
        self.wait_for_function_calls.append(expr)
        return None

    async def evaluate(self, expr: str, *args: Any) -> Any:
        if "window.render(" in expr:
            timestamp = args[0] if args else 0.0
            self.render_calls.append(timestamp)

            if self._render_behavior is not None:
                result = self._render_behavior(timestamp)

                if asyncio.iscoroutine(result):
                    return await result

                return result

            return None

        raise AssertionError(f"unexpected evaluate: {expr!r}")

    async def screenshot(self, **params: Any) -> bytes:
        self.screenshot_calls += 1
        self.last_screenshot_params = params
        return b"\x89PNG-fake"

    async def close(self) -> None:
        return None


def _html() -> UrlResource:
    return UrlResource("about:blank")


def _params(
    duration: float = 0.2,
    frame_rate: int = 10,
    render_timeout: float = 1.0,
    transparent: bool = False,
    worker_count: int = 1,
) -> Dict[str, Any]:
    return {
        "duration": duration,
        "frame_rate": frame_rate,
        "width": 320,
        "height": 240,
        "format": "png",
        "quality": None,
        "transparent": transparent,
        "ready_timeout": 1.0,
        "render_timeout": render_timeout,
        "worker_count": worker_count,
        "filename_format": None,
    }


async def _orchestrate(pages: List[_FakePage], params: Dict[str, Any]) -> List[Tuple[int, float]]:
    """Drive HtmlFrameRenderOrchestrator with N fake pages. Returns
    `(number, timestamp)` pairs in yielded order. Images are not inspected."""
    sessions = [ PlaywrightHtmlFrameRendererSession(p) for p in pages ]
    orchestrator = HtmlFrameRenderOrchestrator(sessions, _html(), None, params)
    out: List[Tuple[int, float]] = []
    async for number, _image, timestamp in orchestrator.render_frames():
        out.append((number, timestamp))
    return out


class TestFrameCount:
    """Frame count matches `round(duration * frame_rate)` so the encoded
    video's length (frame_count / frame_rate) equals `duration`. Timestamps
    run 0 .. (frame_count - 1) / frame_rate."""

    @pytest.mark.anyio
    async def test_two_seconds_at_30fps_yields_60_frames(self):
        page = _FakePage()
        params = _params(duration=2.0, frame_rate=30, render_timeout=0.01)
        pairs = await _orchestrate([page], params)

        assert len(pairs) == 60
        assert pairs[0] == (0, 0.0)
        assert pairs[-1][0] == 59
        assert pairs[-1][1] == pytest.approx(59 / 30)

    @pytest.mark.anyio
    async def test_half_slot_rounds_up_not_down(self):
        # duration=0.5, frame_rate=1 → 0.5 frames. int(0.5+0.5)=1 (not 0 like round()).
        page = _FakePage()
        params = _params(duration=0.5, frame_rate=1, render_timeout=0.01)
        pairs = await _orchestrate([page], params)

        assert len(pairs) == 1


class TestReadySignalWait:
    """The session blocks on `window.__renderer.ready === true` in load_html()
    before any render_frame call. Page-level async setup (webfonts, textures,
    scene load) is the page's responsibility."""

    @pytest.mark.anyio
    async def test_waits_for_ready_signal_in_load_html(self):
        page = _FakePage()
        params = _params(duration=0.1, render_timeout=0.01)
        await _orchestrate([page], params)

        assert any(
            "window.__renderer" in expr and "ready" in expr
            for expr in page.wait_for_function_calls
        ), f"session should wait on ready signal; saw: {page.wait_for_function_calls!r}"


class TestTransparentCapture:
    """`transparent: true` must pass `omit_background=True` to Playwright's
    screenshot so pages that leave html/body backgrounds unset capture an
    alpha channel. The default stays opaque."""

    @pytest.mark.anyio
    async def test_transparent_passes_omit_background(self):
        page = _FakePage()
        params = _params(duration=0.1, render_timeout=0.01, transparent=True)
        await _orchestrate([page], params)

        assert page.last_screenshot_params.get("omit_background") is True
        assert page.last_screenshot_params["type"] == "png"

    @pytest.mark.anyio
    async def test_opaque_default_omits_omit_background(self):
        page = _FakePage()
        params = _params(duration=0.1, render_timeout=0.01)
        await _orchestrate([page], params)

        assert "omit_background" not in page.last_screenshot_params


class TestRenderRenderedRace:
    """The core bug: render RPC returning before `rendered()` fires must not
    be mistaken for "page doesn't push". The session should keep waiting for
    `rendered()` up to the remaining render_timeout."""

    @pytest.mark.anyio
    async def test_rendered_arrives_shortly_after_render_stays_in_push_mode(self):
        # 2 frames @ 10fps for 0.2s duration → frame_count = 2.
        page = _FakePage()

        async def render_behavior(t: float) -> None:
            # render returns immediately; the page emulates rAF by scheduling
            # rendered() a tick later. The session must keep waiting past
            # render completion rather than fall back to legacy mode.
            async def _emit() -> None:
                await asyncio.sleep(0.01)
                page.rendered_binding(None, t)

            asyncio.create_task(_emit())

        page._render_behavior = render_behavior
        pairs = await _orchestrate([page], _params(duration=0.2))

        assert [p[1] for p in pairs] == [0.0, 0.1]
        # Both frames reach render — push mode is retained; no fallback.
        assert page.render_calls == [0.0, 0.1]
        assert page.screenshot_calls == 2


class TestFallbackOnFirstFrame:
    """When this session's first frame never calls `rendered()`, the session
    falls back to a sequential render/screenshot path and finishes."""

    @pytest.mark.anyio
    async def test_fallback_when_rendered_never_fires_on_first_frame(self):
        # Page never emits rendered(). With a short render_timeout the first
        # frame times out and the session switches to the legacy path.
        page = _FakePage()
        pairs = await _orchestrate([page], _params(duration=0.2, render_timeout=0.05))

        assert [p[1] for p in pairs] == [0.0, 0.1]
        assert page.render_calls == [0.0, 0.1]
        assert page.screenshot_calls == 2


class TestMidRenderStall:
    """Once a `rendered()` signal has been seen (push mode is proven), a
    later stall is a real failure — don't silently switch modes mid-render."""

    @pytest.mark.anyio
    async def test_rendered_stops_after_first_frame_raises(self):
        # 3 frames @ 10fps for 0.2s. First frame signals, the second doesn't.
        page = _FakePage()

        async def render_behavior(t: float) -> None:
            if t == 0.0:
                async def _emit() -> None:
                    await asyncio.sleep(0.01)
                    page.rendered_binding(None, t)
                asyncio.create_task(_emit())
            # Later frames: don't signal — session should raise mid-render.

        page._render_behavior = render_behavior

        with pytest.raises(RuntimeError, match="stopped calling"):
            await _orchestrate([page], _params(duration=0.2, render_timeout=0.05))


class TestRenderErrorPropagation:
    """A render() that raises must surface as-is, not be masked as a fallback."""

    @pytest.mark.anyio
    async def test_render_exception_propagates(self):
        page = _FakePage()

        def render_behavior(_t: float) -> None:
            raise RuntimeError("page closed")

        page._render_behavior = render_behavior

        with pytest.raises(RuntimeError, match="page closed"):
            await _orchestrate([page], _params(duration=0.1))


class TestMultiWorkerOrdering:
    """With N workers running in parallel, HtmlFrameRenderOrchestrator must still
    yield frames in monotonic (0, 1, 2, …) order — never the completion
    order — so downstream consumers (video-encoder) see a correct timeline."""

    @pytest.mark.anyio
    async def test_two_workers_yield_in_order_despite_jittered_completion(self):
        # 6 frames @ 10fps for 0.6s → frame_count = 6.
        # Each page has a per-timestamp delay that intentionally reverses
        # within pairs, so if the orchestrator yielded completion-order it
        # would come out shuffled. The test asserts strict (0,1,2,3,4,5).
        delays_by_timestamp = {
            0.0: 0.03,  # worker 0 picks this first
            0.1: 0.00,  # worker 1 picks this first; finishes before frame 0
            0.2: 0.03,
            0.3: 0.00,
            0.4: 0.03,
            0.5: 0.00,
        }

        def make_behavior(page: _FakePage) -> Callable[[float], Any]:
            async def behavior(t: float) -> None:
                async def _emit() -> None:
                    await asyncio.sleep(delays_by_timestamp.get(round(t, 1), 0.0))
                    page.rendered_binding(None, t)
                asyncio.create_task(_emit())
            return behavior

        pages = [_FakePage() for _ in range(2)]
        for p in pages:
            p._render_behavior = make_behavior(p)

        params = _params(duration=0.6, frame_rate=10, worker_count=2)
        pairs = await _orchestrate(pages, params)

        assert [p[0] for p in pairs] == [0, 1, 2, 3, 4, 5]
        assert [p[1] for p in pairs] == pytest.approx([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
        # Every frame rendered exactly once across the two workers.
        total_renders = sum(len(p.render_calls) for p in pages)
        assert total_renders == 6


class TestFrameCountEdges:
    """`frame_count = round(duration * frame_rate)` edge inputs."""

    @pytest.mark.anyio
    async def test_zero_duration_yields_nothing(self):
        # duration=0 → frame_count=0. The iterator must terminate cleanly
        # without calling render() or screenshot() at all.
        page = _FakePage()
        params = _params(duration=0.0, render_timeout=0.01)
        pairs = await _orchestrate([page], params)

        assert pairs == []
        assert page.render_calls == []
        assert page.screenshot_calls == 0

    @pytest.mark.anyio
    async def test_single_frame(self):
        # frame_count = 1. Initial burst is 1, no further submits.
        page = _FakePage()

        async def behavior(t: float) -> None:
            page.rendered_binding(None, t)

        page._render_behavior = behavior
        params = _params(duration=0.1, frame_rate=10, render_timeout=0.01)
        pairs = await _orchestrate([page], params)

        assert pairs == [(0, 0.0)]
        assert page.render_calls == [0.0]

    @pytest.mark.anyio
    async def test_worker_count_exceeds_frame_count(self):
        # 2 frames but 4 workers. The initial burst must clamp to 2; the
        # other 2 workers stay blocked on request_queue.get() and get
        # cancelled cleanly in finally.
        pages = [_FakePage() for _ in range(4)]

        def make_behavior(page: _FakePage) -> Callable[[float], Any]:
            async def behavior(t: float) -> None:
                page.rendered_binding(None, t)
            return behavior

        for p in pages:
            p._render_behavior = make_behavior(p)

        params = _params(duration=0.2, frame_rate=10, worker_count=4)
        pairs = await _orchestrate(pages, params)

        assert [p[0] for p in pairs] == [0, 1]
        # Only 2 frames rendered in total across 4 workers.
        assert sum(len(p.render_calls) for p in pages) == 2


class TestErrorIdentityPreserved:
    """When a worker's render fails, the orchestrator must raise the *same*
    exception instance — not a wrapped `RuntimeError` with a lossy message."""

    @pytest.mark.anyio
    async def test_original_exception_instance_propagates(self):
        page = _FakePage()
        sentinel = ValueError("sentinel 42")

        def behavior(_t: float):
            raise sentinel

        page._render_behavior = behavior

        with pytest.raises(ValueError) as excinfo:
            await _orchestrate([page], _params(duration=0.1))

        assert excinfo.value is sentinel


class TestLoadHtmlPartialFailure:
    """If one session's `load_html` raises during the parallel setup gather,
    the orchestrator must surface that error. The other sessions were already
    `load_html`-ing in parallel — document whether they're left mid-flight
    (potential resource leak) or awaited to completion."""

    @pytest.mark.anyio
    async def test_one_session_load_fails(self):
        good_page = _FakePage()

        async def good_behavior(t: float) -> None:
            good_page.rendered_binding(None, t)

        good_page._render_behavior = good_behavior

        # Build a session whose load_html raises. Easiest is subclassing the
        # real session class and overriding load_html.
        class _ExplodingSession(PlaywrightHtmlFrameRendererSession):
            async def load_html(self, *_args, **_kwargs):
                raise RuntimeError("boom in load_html")

        sessions = [
            PlaywrightHtmlFrameRendererSession(good_page),
            _ExplodingSession(_FakePage()),
        ]
        params = _params(duration=0.2, frame_rate=10, worker_count=2)
        orchestrator = HtmlFrameRenderOrchestrator(sessions, _html(), None, params)

        with pytest.raises(RuntimeError, match="boom in load_html"):
            async for _ in orchestrator.render_frames():
                pass


class TestPerWorkerFallbackIndependence:
    """Each session decides fallback independently. Two workers, one page
    emits `rendered()` and keeps push mode; the other times out on its first
    frame and falls back. Both must complete the overall render."""

    @pytest.mark.anyio
    async def test_one_worker_push_one_worker_fallback(self):
        # worker 0's page always emits rendered(); worker 1's never does.
        pushing_page = _FakePage()
        silent_page = _FakePage()

        async def pushing_behavior(t: float) -> None:
            pushing_page.rendered_binding(None, t)

        pushing_page._render_behavior = pushing_behavior
        # silent_page: no behavior, no rendered() emission. Session will
        # time out on its first frame and switch to sequential mode.

        pages = [pushing_page, silent_page]
        # Short render_timeout so silent_page's fallback triggers quickly.
        params = _params(duration=0.4, frame_rate=10, worker_count=2, render_timeout=0.05)
        pairs = await _orchestrate(pages, params)

        # 4 frames total; all delivered in order.
        assert [p[0] for p in pairs] == [0, 1, 2, 3]
        # Both pages contributed renders.
        assert len(pushing_page.render_calls) >= 1
        assert len(silent_page.render_calls) >= 1
        assert len(pushing_page.render_calls) + len(silent_page.render_calls) == 4


class TestTimestampArithmetic:
    """`number / frame_rate` can produce float-arithmetic surprises at common
    rates. Sanity-check that render_calls land on the exact timestamps the
    orchestrator computes (same formula on both sides). Any assertion failure
    here points to a drift between orchestrator and session timestamp
    derivation."""

    @pytest.mark.anyio
    async def test_timestamps_match_formula_at_30fps(self):
        page = _FakePage()

        async def behavior(t: float) -> None:
            page.rendered_binding(None, t)

        page._render_behavior = behavior
        # 10 frames @ 30fps — includes 1/30, 2/30 etc. that aren't exact binary floats.
        params = _params(duration=10 / 30, frame_rate=30, render_timeout=0.01)
        pairs = await _orchestrate([page], params)

        expected = [i / 30 for i in range(10)]
        assert [p[0] for p in pairs] == list(range(10))
        assert [p[1] for p in pairs] == expected  # exact equality — same formula
        assert page.render_calls == expected
