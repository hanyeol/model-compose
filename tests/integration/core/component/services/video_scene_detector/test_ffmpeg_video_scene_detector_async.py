"""Async / non-blocking tests for the FFmpeg video-scene-detector driver.

Verifies:
  - `Action.run(context)` yields the event loop while ffmpeg runs
    scene-detection (native asyncio subprocess, no thread offload needed
    but the loop still must remain responsive).
  - `Service._run(action, context)` takes no `loop` kwarg after the refactor.
  - Streaming path yields scene dicts without stalling the loop.
  - Batch (list) input returns list-of-lists.
"""

from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_scene_detector.base import (
    VideoSceneDetectorService,
)
from mindor.core.component.services.video_scene_detector.drivers.ffmpeg import (
    FFmpegVideoSceneDetectorAction,
    FFmpegVideoSceneDetectorService,
)
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.media import MediaSource, create_media_source
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig

from tests.async_helpers import assert_does_not_block, collect_async


ffmpeg_required = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe not available on PATH",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video():
    """~2s video — long enough to give the ticker time to accumulate ticks
    while ffmpeg + ffprobe run.
    """
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


def _make_context(video_value: Any, *, cancellation_token=None) -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = cancellation_token
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
        return cast(value)

    async def render_time(value, default=None):
        if value is None:
            return default
        from mindor.core.foundation.variable.time import parse_time
        return parse_time(value)

    async def render_string(value, default=None):
        if value is None or value == "":
            return default
        return value

    ctx.render_scalar = AsyncMock(side_effect=render_scalar)
    ctx.render_time = AsyncMock(side_effect=render_time)
    ctx.render_string = AsyncMock(side_effect=render_string)
    return ctx


def _make_config(**kwargs) -> VideoSceneDetectorActionConfig:
    payload = {"video": "<placeholder>", **kwargs}
    return VideoSceneDetectorActionConfig(**payload)


@ffmpeg_required
class TestFFmpegVideoSceneDetectorAsync:

    @pytest.mark.anyio
    async def test_run_does_not_block_event_loop(self, sample_video):
        """ffmpeg scene detection + ffprobe metadata calls — the loop must stay responsive."""
        action = FFmpegVideoSceneDetectorAction(_make_config())
        ctx = _make_context(sample_video)

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_service_run_signature_has_no_loop_kwarg(self, sample_video):
        sig = inspect.signature(FFmpegVideoSceneDetectorService._run)
        assert list(sig.parameters.keys()) == ["self", "action", "context"], (
            f"Unexpected _run signature: {sig}"
        )

        service = FFmpegVideoSceneDetectorService.__new__(FFmpegVideoSceneDetectorService)
        VideoSceneDetectorService.__init__(service, "vsd", MagicMock(), False)

        ctx = _make_context(sample_video)
        result = await service._run(_make_config(), ctx)
        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_streaming_path_does_not_block(self, sample_video):
        """Streaming yields scene dicts incrementally — the loop must remain responsive.

        Single-input + streaming=True returns a StreamChunkIterator directly.
        """
        action = FFmpegVideoSceneDetectorAction(_make_config(streaming=True))
        ctx = _make_context(sample_video)

        async def _consume():
            result = await action.run(ctx)
            assert isinstance(result, (StreamChunkIterator, AsyncIterator))
            return await collect_async(result)

        frames = await assert_does_not_block(
            _consume(),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert len(frames) >= 1
        for frame in frames:
            assert isinstance(frame, dict)
            assert "index" in frame

    @pytest.mark.anyio
    async def test_batch_input_processes_each(self, sample_video):
        """List input returns List[List[Scene]]."""
        action = FFmpegVideoSceneDetectorAction(_make_config())
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
            assert len(per_video) >= 1
