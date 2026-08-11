"""Async / non-blocking tests for the PySceneDetect video-scene-detector driver.

PySceneDetect is a sync library that decodes and analyses frames on the
calling thread. The driver must offload it via `_run_in_executor` so the
asyncio loop stays responsive.

Verifies:
  - `Action.run(context)` yields the event loop while pyscenedetect runs.
  - `Service._run(action, context)` takes no `loop` kwarg after the refactor.
  - Batch (list) input returns list-of-lists.
"""

from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import tempfile
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.media import MediaSource, create_media_source
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig

from tests.async_helpers import assert_does_not_block


# Guard: require both scenedetect (Python) and ffmpeg (fixture generation).
pytest.importorskip("scenedetect", reason="scenedetect not installed")

from mindor.core.component.services.video_scene_detector.base import (
    VideoSceneDetectorService,
)
from mindor.core.component.services.video_scene_detector.drivers.pyscenedetect import (
    PySceneVideoSceneDetectorAction,
    PySceneVideoSceneDetectorService,
)


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """~2s testsrc @ 24fps — enough wall time for the ticker."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _make_context(video_value: Any) -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        return value

    def resolve_one(value):
        if isinstance(value, MediaSource):
            return value
        return create_media_source(value)

    async def render_video(_value):
        if isinstance(video_value, list):
            return [resolve_one(v) for v in video_value]
        return resolve_one(video_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)

    async def render_scalar(value, cast, default=None):
        if value is None:
            return default
        if isinstance(cast, str):
            from mindor.core.foundation.variable.time import parse_time
            from mindor.core.foundation.variable.size import parse_size
            from mindor.core.foundation.variable.decimal import parse_decimal
            from mindor.core.foundation.variable.color import parse_color
            parsers = {
                "time": parse_time,
                "size": parse_size,
                "decimal": parse_decimal,
                "color": parse_color,
            }
            return parsers[cast](value)
        return cast(value)

    ctx.render_scalar = AsyncMock(side_effect=render_scalar)
    return ctx


def _make_config(**kwargs) -> VideoSceneDetectorActionConfig:
    payload = {"video": "<placeholder>", **kwargs}
    return VideoSceneDetectorActionConfig(**payload)


@ffmpeg_required
class TestPySceneDetectorAsync:

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self, sample_video):
        """PySceneDetect is CPU-bound sync work — must be offloaded to executor."""
        action = PySceneVideoSceneDetectorAction(_make_config())
        ctx = _make_context(sample_video)

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self, sample_video):
        sig = inspect.signature(PySceneVideoSceneDetectorService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )

        service = PySceneVideoSceneDetectorService.__new__(PySceneVideoSceneDetectorService)
        VideoSceneDetectorService.__init__(service, "vsd", MagicMock(), False)

        ctx = _make_context(sample_video)
        result = await service._run(_make_config(), ctx)
        assert isinstance(result, list)

    @pytest.mark.anyio
    async def test_batch_input_processes_each(self, sample_video):
        """List input returns List[List[Scene]]."""
        action = PySceneVideoSceneDetectorAction(_make_config())
        ctx = _make_context([sample_video, sample_video])

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) == 2
        for per_video in result:
            assert isinstance(per_video, list)
